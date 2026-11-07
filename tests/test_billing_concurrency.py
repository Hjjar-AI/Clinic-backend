"""Real billing/receipt/cache races against an owned disposable PostgreSQL DB."""
from decimal import Decimal
from threading import Event
from unittest import skipUnless
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.cache.backends.locmem import LocMemCache
from django.db import connection, transaction

from apps.billing.models import Invoice
from apps.billing.services import BillingService
from core.cache_utils import get_group_version, get_grouped_key, set_grouped_key
from core.exceptions import ConflictError
from core.models import AuditLog, IdempotencyOperation
from .base import ClinicTransactionTestCase
from .concurrency_helpers import PostgresConcurrencyMixin


@skipUnless(connection.vendor == 'postgresql', 'requires owned PostgreSQL concurrency profile')
class BillingConcurrencyTests(PostgresConcurrencyMixin, ClinicTransactionTestCase):
    def invoice(self, patient=None):
        return BillingService().create_invoice({'patient': patient or self.patient,
            'lines': [{'description': 'Synthetic initial line', 'quantity': '1.00', 'unit_price': '2.50'}]}, self.admin)

    def issued_invoice(self, patient=None):
        row = self.invoice(patient)
        return BillingService().transition(row, 'issued', self.admin, row.version)

    def paid(self, row):
        return BillingService().transition(row, 'paid', self.admin, row.version, payment_method='cash')

    def rejected_or_value(self, operation):
        try:
            return ('ok', operation())
        except (ValidationError, ConflictError) as error:
            return ('rejected', type(error).__name__)

    def test_same_opening_invoice_version_preserves_one_complete_line_replacement(self):
        row = self.invoice()
        audit_before = AuditLog.objects.filter(entity_type='Invoice', entity_id=row.pk).count()

        def edit(index):
            return self.rejected_or_value(lambda: BillingService().update_invoice(
                Invoice.objects.get(pk=row.pk), {'notes': f'Writer {index}', 'lines': [
                    {'description': f'Writer {index} first', 'quantity': '1.15', 'unit_price': f'{index + 1}.50'},
                    {'description': f'Writer {index} second', 'quantity': '2.00', 'unit_price': '0.25'},
                ]}, row.version, actor=self.admin).notes)

        results = self.simultaneous(edit)
        self.assertEqual([state for state, _ in results].count('ok'), 1)
        winner = next(value for state, value in results if state == 'ok')
        row.refresh_from_db()
        self.assertEqual(row.version, 2)
        self.assertEqual(row.notes, winner)
        self.assertEqual(list(row.lines.order_by('order').values_list('description', flat=True)),
            [f'{winner} first', f'{winner} second'])
        self.assertEqual(row.total_amount, sum(row.lines.values_list('amount', flat=True), Decimal('0')))
        self.assertEqual(row.final_amount, row.total_amount)
        self.assertEqual(AuditLog.objects.filter(entity_type='Invoice', entity_id=row.pk).count(), audit_before + 1)

    def test_payment_race_commits_one_receipt_one_actor_and_one_transition(self):
        row = self.issued_invoice()
        before = AuditLog.objects.filter(entity_type='Invoice', entity_id=row.pk, action='status_transition').count()

        def pay(index):
            return self.api_client().put(f'/api/v1/billing/{row.pk}/transition/',
                {'status': 'paid', 'version': row.version, 'payment_method': ('cash', 'card')[index]},
                format='json', HTTP_X_IDEMPOTENCY_KEY=f'synthetic-payment-race-{index}')

        results = self.simultaneous(pay)
        self.assertEqual(sorted(response.status_code for response in results), [200, 409])
        winner = next(index for index, response in enumerate(results) if response.status_code == 200)
        row.refresh_from_db()
        self.assertEqual((row.status, row.version, row.paid_by_id), ('paid', 3, self.admin.pk))
        self.assertIsNotNone(row.paid_at)
        self.assertEqual(row.payment_method, ('cash', 'card')[winner])
        self.assertEqual(IdempotencyOperation.objects.filter(key__startswith='synthetic-payment-race-').count(), 1)
        self.assertTrue(IdempotencyOperation.objects.filter(key=f'synthetic-payment-race-{winner}', state='completed').exists())
        self.assertEqual(AuditLog.objects.filter(entity_type='Invoice', entity_id=row.pk, action='status_transition').count(), before + 1)

    def test_issue_and_edit_cannot_both_commit_from_the_same_version(self):
        row = self.invoice()

        def mutate(index):
            service = BillingService()
            current = Invoice.objects.get(pk=row.pk)
            return self.rejected_or_value(lambda: service.transition(current, 'issued', self.admin, row.version)
                if index == 0 else service.update_invoice(current, {'notes': 'Synthetic edit'}, row.version, actor=self.admin))

        results = self.simultaneous(mutate)
        self.assertEqual([state for state, _ in results].count('ok'), 1)
        row.refresh_from_db()
        self.assertEqual(row.version, 2)
        if row.status == 'issued':
            self.assertEqual(row.notes, '')
            self.assertEqual(row.issue_snapshot['patient_name'], self.patient.get_full_name())
        else:
            self.assertEqual((row.status, row.notes, row.issue_snapshot), ('draft', 'Synthetic edit', {}))

    def test_same_patient_concurrent_creations_keep_distinct_numbers_and_lines(self):
        results = self.simultaneous(lambda index: self.invoice().pk)
        self.assertEqual(len(set(results)), 2)
        self.assertEqual(Invoice.objects.values('invoice_number').distinct().count(), 2)
        for row in Invoice.objects.all():
            self.assertEqual(row.lines.get().amount, row.final_amount)

    def receipt_race(self, *, changed_payload=False, reject_first=False):
        entered, release = Event(), Event()
        original = BillingService.create_invoice
        calls = []

        def paused(service, data, actor):
            row = original(service, data, actor)
            calls.append(row.pk)
            if len(calls) == 1:
                entered.set()
                if not release.wait(timeout=15):
                    raise RuntimeError('Synthetic leader release timed out')
                if reject_first:
                    raise ValidationError('Synthetic rejected first attempt')
            return row

        payload = {'patient_id': self.patient.pk, 'lines': [
            {'description': 'Synthetic receipt line', 'quantity': '1.15', 'unit_price': '0.50'}]}
        key = 'synthetic-concurrent-invoice-key'
        def send(data):
            return self.api_client().post('/api/v1/billing/', data, format='json', HTTP_X_IDEMPOTENCY_KEY=key)

        with patch.object(BillingService, 'create_invoice', paused), self.workers() as pool:
            leader = pool.submit(self.worker, lambda: send(payload))
            try:
                self.assertTrue(entered.wait(timeout=10), 'Leader never reached invoice persistence')
                name = self.waiter_name()
                follower = pool.submit(self.worker, lambda: send({**payload, 'notes': 'Different payload'} if changed_payload else payload), name=name)
                self.wait_for_database_lock(name)
                self.assertFalse(Invoice.objects.exists())
                self.assertFalse(IdempotencyOperation.objects.filter(key=key).exists())
            finally:
                release.set()
            responses = [leader.result(timeout=20), follower.result(timeout=20)]
        self.assertEqual(Invoice.objects.count(), 1)
        row = Invoice.objects.get()
        self.assertEqual((row.total_amount, row.lines.get().amount), (Decimal('0.58'), Decimal('0.58')))
        self.assertEqual(AuditLog.objects.filter(entity_type='Invoice', entity_id=row.pk, action='create').count(), 1)
        receipt = IdempotencyOperation.objects.get(key=key)
        self.assertEqual(receipt.state, 'completed')
        self.assertEqual(bytes(receipt.response_body), next(response.content for response in responses if response.status_code == 201))
        return responses, calls

    def test_overlapping_same_key_creates_once_and_replays_exact_response(self):
        responses, calls = self.receipt_race()
        self.assertEqual([response.status_code for response in responses], [201, 201])
        self.assertEqual(len(calls), 1)
        self.assertEqual(responses[0].content, responses[1].content)
        self.assertEqual(responses[1]['X-Idempotency-Replayed'], 'true')
        self.assertEqual(responses[0]['Content-Type'], responses[1]['Content-Type'])

    def test_overlapping_same_key_different_payload_is_rejected(self):
        responses, calls = self.receipt_race(changed_payload=True)
        self.assertEqual([response.status_code for response in responses], [201, 409])
        self.assertEqual(responses[1].json()['error']['code'], 'idempotency_key_reused')
        self.assertEqual(len(calls), 1)

    def test_waiting_retry_succeeds_when_first_attempt_rolls_back(self):
        responses, calls = self.receipt_race(reject_first=True)
        self.assertEqual([response.status_code for response in responses], [400, 201])
        self.assertEqual(len(calls), 2)
        self.assertNotIn('X-Idempotency-Replayed', responses[1])
        self.assertEqual(AuditLog.objects.filter(entity_type='Invoice', action='create').count(), 1)

    def test_uncommitted_payment_keeps_old_cache_then_rejects_stale_publication(self):
        row = self.issued_invoice()
        old = get_group_version('reports')
        self.assertTrue(set_grouped_key('reports', 'paid-count', 0, version=old))
        entered, release = Event(), Event()

        def writer():
            with transaction.atomic():
                self.paid(Invoice.objects.get(pk=row.pk))
                entered.set()
                if not release.wait(timeout=15):
                    raise RuntimeError('Synthetic cache writer release timed out')

        with self.workers(1) as pool:
            future = pool.submit(self.worker, writer)
            try:
                self.assertTrue(entered.wait(timeout=10))
                self.assertEqual(Invoice.objects.get(pk=row.pk).status, 'issued')
                self.assertEqual(get_group_version('reports'), old)
                self.assertEqual(get_grouped_key('reports', 'paid-count'), 0)
            finally:
                release.set()
            future.result(timeout=20)
        self.assertNotEqual(get_group_version('reports'), old)
        self.assertIsNone(get_grouped_key('reports', 'paid-count'))
        self.assertFalse(set_grouped_key('reports', 'paid-count', 0, version=old))
        current = get_group_version('reports')
        self.assertTrue(set_grouped_key('reports', 'paid-count', Invoice.objects.filter(status='paid').count(), version=current))
        self.assertEqual(get_grouped_key('reports', 'paid-count'), 1)

    def test_distinct_patient_payments_serialize_cache_generations_without_stale_results(self):
        first = self.issued_invoice()
        second = self.issued_invoice(self.patient_for())
        initial = get_group_version('reports')
        entered, release = Event(), Event()
        second_entered, second_release = Event(), Event()

        def pay_and_pause(row_id, ready, resume):
            with transaction.atomic():
                self.paid(Invoice.objects.get(pk=row_id))
                ready.set()
                if not resume.wait(timeout=15):
                    raise RuntimeError('Synthetic generation writer release timed out')

        with self.workers() as pool:
            one = pool.submit(self.worker, lambda: pay_and_pause(first.pk, entered, release))
            try:
                self.assertTrue(entered.wait(timeout=10))
                name = self.waiter_name()
                two = pool.submit(self.worker, lambda: pay_and_pause(second.pk, second_entered, second_release), name=name)
                self.wait_for_database_lock(name)
                self.assertEqual(get_group_version('reports'), initial)
                release.set()
                one.result(timeout=20)
                self.assertTrue(second_entered.wait(timeout=10))
                middle = get_group_version('reports')
                self.assertNotEqual(middle, initial)
                self.assertEqual(Invoice.objects.filter(status='paid').count(), 1)
                self.assertTrue(set_grouped_key('reports', 'paid-count', 1, version=middle))
            finally:
                release.set()
                second_release.set()
            two.result(timeout=20)
        self.assertEqual(Invoice.objects.filter(status='paid').count(), 2)
        self.assertNotEqual(get_group_version('reports'), middle)
        self.assertIsNone(get_grouped_key('reports', 'paid-count'))
        self.assertFalse(set_grouped_key('reports', 'paid-count', 1, version=middle))

    def test_cache_write_crossing_payment_commit_cannot_publish_a_visible_stale_result(self):
        row = self.issued_invoice()
        old = get_group_version('reports')
        entered, release = Event(), Event()
        original_set = LocMemCache.set

        def delayed_set(backend, key, *args, **kwargs):
            if key == f'reports:v{old}:paid-count':
                entered.set()
                if not release.wait(timeout=15):
                    raise RuntimeError('Synthetic cache publication release timed out')
            return original_set(backend, key, *args, **kwargs)

        with patch.object(LocMemCache, 'set', delayed_set), self.workers(1) as pool:
            publication = pool.submit(self.worker, lambda: set_grouped_key('reports', 'paid-count', 0, version=old))
            try:
                self.assertTrue(entered.wait(timeout=10))
                self.paid(row)
                self.assertNotEqual(get_group_version('reports'), old)
            finally:
                release.set()
            # The old-generation entry may finish writing, but readers resolve
            # the newly committed generation and cannot observe that stale entry.
            self.assertTrue(publication.result(timeout=20))
        self.assertIsNone(get_grouped_key('reports', 'paid-count'))
        current = get_group_version('reports')
        self.assertTrue(set_grouped_key('reports', 'paid-count', 1, version=current))
        self.assertEqual(get_grouped_key('reports', 'paid-count'), 1)
