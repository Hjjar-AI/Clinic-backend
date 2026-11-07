"""Kill real subprocesses at mutation/receipt/media/commit boundaries on PostgreSQL."""
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
from unittest import skipUnless
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection

from apps.accounts.models import User
from apps.backup.backup_creator import BackupCreatorService
from apps.backup.backup_restore import BackupRestoreService
from apps.billing.models import Invoice
from apps.billing.services import BillingService
from apps.patients.models import Patient, PatientDocument
from core.cache_utils import get_group_version, get_grouped_key, set_grouped_key
from core.models import AuditLog, IdempotencyOperation, RecoveryOperation
from .base import ClinicTransactionTestCase
from .concurrency_helpers import PostgresConcurrencyMixin


@skipUnless(connection.vendor == 'postgresql' and os.name == 'posix',
    'requires owned PostgreSQL and native POSIX process termination')
class WorkerTerminationTests(PostgresConcurrencyMixin, ClinicTransactionTestCase):
    @contextmanager
    def killed_worker(self, **payload):
        env = {**os.environ, 'DJANGO_SETTINGS_MODULE': 'tests.postgres_settings'}
        process = subprocess.Popen([sys.executable, '-B', '-m', 'tests.worker_scenarios'],
            cwd=Path(__file__).resolve().parents[1], env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1)
        try:
            process.stdin.write(json.dumps({'database': connection.settings_dict['NAME'],
                'workspace': self.workspace.name, 'actor': self.admin.pk,
                'cookies': {name: cookie.value for name, cookie in self.api.cookies.items()}, **payload}) + '\n')
            process.stdin.flush()
            readable, _, _ = select.select([process.stdout], [], [], 20)
            if not readable:
                process.kill()
                _, errors = process.communicate(timeout=10)
                self.fail(f'Synthetic worker checkpoint timed out: {errors}')
            line = process.stdout.readline()
            if not line:
                _, errors = process.communicate(timeout=10)
                self.fail(f'Synthetic worker exited before checkpoint: {errors}')
            checkpoint = json.loads(line)
            self.assertEqual(checkpoint['checkpoint'], payload['stage'])
            yield process, checkpoint
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)

    def kill(self, process):
        process.kill()
        process.wait(timeout=10)
        self.assertEqual(process.returncode, -signal.SIGKILL)

    def invoice_payload(self):
        return {'patient_id': self.patient.pk, 'lines': [
            {'description': 'Synthetic killed-worker line', 'quantity': '1.15', 'unit_price': '0.50'}]}

    def test_killed_uncommitted_writer_rolls_back_and_unblocks_same_key_retry(self):
        key = 'synthetic-kill-before-commit'
        data = self.invoice_payload()
        before = {group: get_group_version(group) for group in ('dashboard', 'reports')}
        with self.killed_worker(kind='invoice', stage='before_commit', key=key, data=data) as (process, _):
            self.assertFalse(Invoice.objects.exists())
            self.assertFalse(AuditLog.objects.filter(entity_type='Invoice').exists())
            self.assertFalse(IdempotencyOperation.objects.filter(key=key).exists())
            self.assertEqual({group: get_group_version(group) for group in before}, before)
            with self.workers(1) as pool:
                name = self.waiter_name()
                retry = pool.submit(self.worker, lambda: self.api_client().post('/api/v1/billing/', data,
                    format='json', HTTP_X_IDEMPOTENCY_KEY=key), name=name)
                try:
                    self.wait_for_database_lock(name)
                finally:
                    self.kill(process)
                response = retry.result(timeout=20)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertNotIn('X-Idempotency-Replayed', response)
        row = Invoice.objects.get()
        self.assertEqual(row.lines.count(), 1)
        self.assertEqual(str(row.lines.get().amount), '0.58')
        self.assertEqual(AuditLog.objects.filter(entity_type='Invoice', action='create').count(), 1)
        receipt = IdempotencyOperation.objects.get(key=key)
        self.assertEqual((receipt.state, bytes(receipt.response_body)), ('completed', response.content))
        for group, token in before.items():
            self.assertNotEqual(get_group_version(group), token)

    def test_killed_committed_writer_replays_exact_bytes_without_mutation_or_invalidation(self):
        key = 'synthetic-kill-after-commit'
        data = self.invoice_payload()
        with self.killed_worker(kind='invoice', stage='after_commit', key=key, data=data) as (process, checkpoint):
            row = Invoice.objects.get()
            self.assertEqual(IdempotencyOperation.objects.get(key=key).state, 'completed')
            before = {group: get_group_version(group) for group in ('dashboard', 'reports')}
            self.assertTrue(set_grouped_key('reports', 'invoice-count', 1, version=before['reports']))
            audit_count = AuditLog.objects.filter(entity_type='Invoice').count()
            self.kill(process)
        with patch.object(BillingService, 'create_invoice', side_effect=AssertionError('Committed write must not execute again')):
            replay = self.write('post', '/api/v1/billing/', data, key)
        self.assertEqual(replay.status_code, 201)
        self.assertEqual(replay.content.decode(), checkpoint['response'])
        self.assertEqual(replay['Content-Type'], checkpoint['content_type'])
        self.assertEqual(replay['X-Idempotency-Replayed'], 'true')
        self.assertEqual(Invoice.objects.get().pk, row.pk)
        self.assertEqual(AuditLog.objects.filter(entity_type='Invoice').count(), audit_count)
        self.assertEqual({group: get_group_version(group) for group in before}, before)
        self.assertEqual(get_grouped_key('reports', 'invoice-count'), 1)

    def recovery_inventory(self):
        archived = b'%PDF-1.4\nSynthetic archived document'
        current = b'%PDF-1.4\nSynthetic current document'
        path = default_storage.save('suite/worker-document.pdf', ContentFile(archived))
        document = PatientDocument.objects.create(patient=self.patient, filename='worker-document.pdf',
            original_filename='worker-document.pdf', filepath=path, file_size=len(archived),
            checksum=hashlib.sha256(archived).hexdigest(), mime_type='application/pdf', uploaded_by=self.doctor)
        backup = BackupCreatorService().create_full_backup().getvalue()
        archive_path = Path(self.workspace.name) / 'synthetic.zip'
        archive_path.write_bytes(backup)
        default_storage.delete(path)
        self.assertEqual(default_storage.save(path, ContentFile(current)), path)
        document.checksum = hashlib.sha256(current).hexdigest()
        document.file_size = len(current)
        document.save(update_fields=['checksum', 'file_size'])
        extra = self.patient_for(first_name='Synthetic post-backup inventory')
        return backup, archive_path, document, extra, archived, current

    def execute(self, backup, token, key):
        return self.api_client().post('/api/v1/backup/restore/execute/', {
            'backup_file': SimpleUploadedFile('synthetic.zip', backup, 'application/zip'),
            'confirm_clear': 'true', 'confirmation_phrase': 'RESTORE CLINIC', 'preview_token': token,
        }, HTTP_X_IDEMPOTENCY_KEY=key)

    def assert_file(self, path, expected):
        with default_storage.open(path, 'rb') as stream:
            self.assertEqual(stream.read(), expected)

    def interrupted_recovery(self, stage):
        backup, archive_path, document, extra, archived, current = self.recovery_inventory()
        key = f'synthetic-killed-recovery-{stage}'
        generation = get_group_version('reports')
        with self.killed_worker(kind='recovery', stage=stage, key=key,
                backup=str(archive_path), media_path=document.filepath) as (process, checkpoint):
            receipt = RecoveryOperation.objects.get(key=key)
            self.assertEqual(receipt.state, 'processing')
            safety = Path(self.workspace.name) / 'backups' / receipt.result['safety_backup']
            self.assertTrue(safety.is_file())
            self.assertTrue(Patient.objects.filter(pk=extra.pk).exists())
            self.assert_file(document.filepath, archived)
            self.assertEqual(get_group_version('reports'), generation)
            with self.workers(1) as pool:
                name = self.waiter_name()
                retry = pool.submit(self.worker, lambda: self.execute(backup, checkpoint['preview_token'], key), name=name)
                try:
                    self.wait_for_database_lock(name)
                finally:
                    self.kill(process)
                response = retry.result(timeout=20)
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['error']['code'], 'recovery_interrupted')
        receipt.refresh_from_db()
        self.assertEqual(receipt.state, 'interrupted')
        self.assertTrue(Patient.objects.filter(pk=extra.pk).exists())
        document.refresh_from_db()
        self.assertEqual(document.checksum, hashlib.sha256(current).hexdigest())
        self.assert_file(document.filepath, archived)
        with patch.object(BackupRestoreService, 'execute_restore', side_effect=AssertionError('Interrupted restore must not repeat')):
            rejected = self.execute(backup, checkpoint['preview_token'], key + '-new')
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(rejected.json()['error']['code'], 'recovery_interrupted')
        self.assertFalse(RecoveryOperation.objects.filter(key=key + '-new').exists())
        # Simulate the operator repairing BOTH inventory and media from the actual
        # safety copy before acknowledging reconciliation. Acknowledgment alone
        # is never treated as a repair.
        with safety.open('rb') as stream:
            BackupRestoreService().execute_restore(stream)
        self.assertTrue(Patient.objects.filter(pk=extra.pk).exists())
        self.assert_file(document.filepath, current)
        self.assertEqual(PatientDocument.objects.get(pk=document.pk).checksum, hashlib.sha256(current).hexdigest())
        call_command('reconcile_recovery', key=key, reason='Synthetic safety inventory and media verified',
            confirm_inventory_and_media=True, stdout=io.StringIO())
        receipt.refresh_from_db()
        self.assertEqual(receipt.state, 'reconciled')
        self.assertTrue(safety.is_file())

    def test_kill_after_media_replacement_blocks_retries_until_safety_reconciliation(self):
        self.interrupted_recovery('after_media')

    def test_kill_before_restore_commit_rolls_back_inventory_and_retains_safety_receipt(self):
        self.interrupted_recovery('before_commit')

    def test_kill_after_restore_commit_releases_gate_and_replays_bounded_success(self):
        backup, archive_path, document, extra, archived, _ = self.recovery_inventory()
        key = 'synthetic-killed-recovery-after-commit'
        generation = get_group_version('reports')
        with self.killed_worker(kind='recovery', stage='after_commit', key=key,
                backup=str(archive_path), media_path=document.filepath) as (process, checkpoint):
            receipt = RecoveryOperation.objects.get(key=key)
            self.assertEqual(receipt.state, 'completed')
            self.assertFalse(Patient.objects.filter(pk=extra.pk).exists())
            self.assert_file(document.filepath, archived)
            self.assertNotEqual(get_group_version('reports'), generation)
            committed_generation = get_group_version('reports')
            with self.workers(1) as pool:
                name = self.waiter_name()
                # Restore cleared old sessions. A restored administrator starts
                # a fresh synthetic session in this worker before replay.
                def retry():
                    from django.utils import timezone
                    client = self.api_client()
                    client.force_login(User.objects.get(pk=self.admin.pk))
                    session = client.session
                    session['login_time'] = timezone.now().isoformat()
                    session.save()
                    return client.post('/api/v1/backup/restore/execute/', {
                        'backup_file': SimpleUploadedFile('synthetic.zip', backup, 'application/zip'),
                        'confirm_clear': 'true', 'confirmation_phrase': 'RESTORE CLINIC',
                        'preview_token': checkpoint['preview_token'],
                    }, HTTP_X_IDEMPOTENCY_KEY=key)
                with patch.object(BackupRestoreService, 'execute_restore', side_effect=AssertionError('Committed recovery must not repeat')):
                    future = pool.submit(self.worker, retry, name=name)
                    try:
                        self.wait_for_database_lock(name, future)
                    finally:
                        self.kill(process)
                    response = future.result(timeout=20)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response['X-Idempotency-Replayed'], 'true')
        self.assertEqual(response.json()['data'], receipt.result)
        self.assertEqual(set(receipt.result), {'safety_backup'})
        self.assertEqual(get_group_version('reports'), committed_generation)
        self.assertFalse(Patient.objects.filter(pk=extra.pk).exists())
        self.assert_file(document.filepath, archived)
        self.assertTrue((Path(self.workspace.name) / 'backups' / receipt.result['safety_backup']).is_file())
