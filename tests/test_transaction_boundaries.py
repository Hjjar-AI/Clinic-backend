"""Failure injection at durable mutation/cache/recovery boundaries; no clinic DB."""
import io
from datetime import timedelta
from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.db.models.query import QuerySet
from django.http import HttpRequest, JsonResponse, StreamingHttpResponse
from django.utils import timezone
from apps.backup.backup_creator import backup_models
from apps.clinical.models import DiagnosisOption
from apps.tasks.models import UserTask
from core.cache_utils import get_group_version, get_grouped_key, set_grouped_key, invalidate_group
from core.middleware import RequestContextMiddleware
from core.models import IdempotencyOperation, RecoveryOperation
from core.operation_gate import operation_gate, OperationGateMiddleware
from .base import ClinicTransactionTestCase


class DurableBoundaryTests(ClinicTransactionTestCase):
    def request(self, key):
        request = HttpRequest()
        request.method = 'POST'; request.path = '/api/v1/tasks/'
        request.META = {'CONTENT_TYPE': 'application/json', 'HTTP_X_IDEMPOTENCY_KEY': key}
        request.content_type = 'application/json'; request._body = b'{}'
        request._dont_enforce_csrf_checks = True; request.user = self.admin
        return request

    def test_rejected_response_rolls_back_reservation_and_business_mutation_together(self):
        def rejected(request):
            DiagnosisOption.objects.create(code='ROLLBACK', english_name='Synthetic', arabic_name='اصطناعي')
            return JsonResponse({'error': {'message': 'Synthetic validation rejection'}}, status=400)
        response = RequestContextMiddleware(rejected)(self.request('synthetic-rollback'))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(DiagnosisOption.objects.filter(code='ROLLBACK').exists())
        self.assertFalse(IdempotencyOperation.objects.filter(key='synthetic-rollback').exists())

    def test_receipt_failure_cannot_commit_business_mutation(self):
        reached = []
        def completed(request):
            reached.append(True)
            DiagnosisOption.objects.create(code='NO-RECEIPT', english_name='Synthetic', arabic_name='اصطناعي')
            return JsonResponse({'data': {'id': 1}}, status=201)
        original_update = QuerySet.update
        def fail_receipt(queryset, **values):
            if queryset.model is IdempotencyOperation and 'response_body' in values:
                raise RuntimeError('Synthetic durable receipt outage')
            return original_update(queryset, **values)
        with patch.object(QuerySet, 'update', fail_receipt):
            with self.assertRaises(RuntimeError):
                RequestContextMiddleware(completed)(self.request('synthetic-receipt-failure'))
        self.assertEqual(reached, [True])
        self.assertFalse(DiagnosisOption.objects.filter(code='NO-RECEIPT').exists())
        self.assertFalse(IdempotencyOperation.objects.filter(key='synthetic-receipt-failure').exists())

    def test_cache_generation_commits_despite_cache_backend_outage(self):
        before = get_group_version('synthetic-outage')
        with patch('core.cache_utils.cache.set', side_effect=RuntimeError('Synthetic cache outage')):
            with transaction.atomic():
                invalidate_group('synthetic-outage')
                DiagnosisOption.objects.create(code='COMMIT', english_name='Synthetic', arabic_name='اصطناعي')
            after = get_group_version('synthetic-outage')
            self.assertNotEqual(after, before)
            self.assertFalse(set_grouped_key('synthetic-outage', 'report', {'count': 1}, version=after))
        self.assertTrue(DiagnosisOption.objects.filter(code='COMMIT').exists())

    def test_rollback_preserves_previous_generation_and_published_cache(self):
        before = get_group_version('synthetic-rollback-cache')
        self.assertTrue(set_grouped_key('synthetic-rollback-cache', 'report', {'count': 1}, version=before))
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                invalidate_group('synthetic-rollback-cache')
                raise RuntimeError('Synthetic rollback')
        self.assertEqual(get_group_version('synthetic-rollback-cache'), before)
        self.assertEqual(get_grouped_key('synthetic-rollback-cache', 'report'), {'count': 1})

    def test_grouped_cache_outage_is_a_miss_and_stale_publication_is_refused(self):
        before = get_group_version('synthetic-stale'); invalidate_group('synthetic-stale')
        self.assertFalse(set_grouped_key('synthetic-stale', 'report', 'stale', version=before))
        with patch('core.cache_utils.cache.get', side_effect=RuntimeError('Synthetic cache read outage')):
            self.assertEqual(get_grouped_key('synthetic-stale', 'report', default='fallback'), 'fallback')

    def test_idempotent_replay_rechecks_current_action_permissions(self):
        self.admin.is_superuser = False; self.admin.save(update_fields=['is_superuser'])
        result = self.write('post', '/api/v1/tasks/', {'title': 'Synthetic restricted receipt'}, 'synthetic-permission-replay')
        self.assertEqual(result.status_code, 201)
        self.admin.groups.clear(); self.admin.user_permissions.clear(); self.admin.clear_permission_cache()
        replay = self.write('post', '/api/v1/tasks/', {'title': 'Synthetic restricted receipt'}, 'synthetic-permission-replay')
        self.assertEqual(replay.status_code, 403)
        self.assertEqual(UserTask.objects.count(), 1)
        self.assertTrue(IdempotencyOperation.objects.filter(key='synthetic-permission-replay', state='completed').exists())

    def test_expired_operation_key_is_not_reused_as_new_mutation(self):
        self.write('post', '/api/v1/tasks/', {'title': 'Synthetic expired'}, 'synthetic-expired-key')
        IdempotencyOperation.objects.filter(key='synthetic-expired-key').update(expires_at=timezone.now() - timedelta(seconds=1))
        result = self.write('post', '/api/v1/tasks/', {'title': 'Synthetic expired'}, 'synthetic-expired-key')
        self.assertEqual(result.status_code, 410)
        self.assertEqual(result.json()['error']['code'], 'operation_expired')
        self.assertEqual(UserTask.objects.count(), 1)


class RecoveryAndGateTests(ClinicTransactionTestCase):
    def test_recovery_receipts_are_excluded_from_replaced_backup_inventory(self):
        self.assertNotIn(RecoveryOperation, backup_models())

    def receipt(self):
        return RecoveryOperation.objects.create(key='synthetic-interrupted', fingerprint='a' * 64,
            initiator={'id': self.admin.pk, 'username': 'Synthetic'}, state='interrupted',
            expires_at=timezone.now() + timedelta(days=1))

    def test_reconciliation_requires_both_inventory_and_media_confirmation(self):
        row = self.receipt()
        with self.assertRaises(CommandError):
            call_command('reconcile_recovery', key=row.key, reason='Synthetic reviewed', confirm_inventory_and_media=False, stdout=io.StringIO())
        row.refresh_from_db(); self.assertEqual(row.state, 'interrupted')

    def test_reconciliation_records_reason_and_refuses_repeated_acknowledgment(self):
        row = self.receipt()
        call_command('reconcile_recovery', key=row.key, reason=' Synthetic inventory and media reviewed ', confirm_inventory_and_media=True, stdout=io.StringIO())
        row.refresh_from_db(); self.assertEqual(row.state, 'reconciled')
        self.assertEqual(row.result['reconciliation_reason'], 'Synthetic inventory and media reviewed')
        with self.assertRaises(CommandError):
            call_command('reconcile_recovery', key=row.key, reason='Synthetic again', confirm_inventory_and_media=True, stdout=io.StringIO())

    def test_buffering_defers_stream_cleanup_until_after_gate_release(self):
        from django.core.signals import request_finished
        finished = []
        def receiver(**kwargs): finished.append(True)
        request_finished.connect(receiver, weak=False)
        try:
            response = OperationGateMiddleware(lambda request: StreamingHttpResponse(iter([b'Synthetic ', b'bytes'])))(HttpRequest())
            self.assertEqual(response.content, b'Synthetic bytes')
            self.assertEqual(finished, [])
            response.close()
            self.assertEqual(finished, [True])
        finally:
            request_finished.disconnect(receiver)

    def test_shared_gate_cannot_upgrade_mid_operation_and_recovers_after_exception(self):
        with operation_gate():
            with operation_gate():
                pass
            with self.assertRaises(RuntimeError):
                with operation_gate(exclusive=True):
                    pass
        with self.assertRaisesRegex(ValueError, 'Synthetic'):
            with operation_gate(exclusive=True):
                raise ValueError('Synthetic')
        with operation_gate(exclusive=True):
            with operation_gate():
                pass
