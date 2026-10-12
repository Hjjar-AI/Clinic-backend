"""Recovery receipts survive restored account IDs and fail closed after interruption."""
import io
from datetime import timedelta
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from apps.accounts.models import User
from apps.accounts.services import UserService
from apps.backup.backup_creator import BackupCreatorService
from apps.backup.backup_restore import BackupRestoreService
from apps.patients.models import Patient
from core.models import RecoveryOperation
from .base import ClinicTransactionTestCase, PASSWORD


class RecoveryReceiptTests(ClinicTransactionTestCase):
    path = '/api/v1/backup/restore/execute/'

    def login_as(self, actor):
        self.api.force_login(actor)
        session = self.api.session; session['login_time'] = timezone.now().isoformat(); session.save()

    def preview(self, data):
        response = self.api.post('/api/v1/backup/restore/preview/', {'backup_file': SimpleUploadedFile('synthetic.zip', data, 'application/zip')}, HTTP_X_IDEMPOTENCY_KEY='synthetic-preview')
        self.assertEqual(response.status_code, 200)
        return response.json()['data']['preview_token']

    def execute(self, data, token, key):
        return self.api.post(self.path, {'backup_file': SimpleUploadedFile('synthetic.zip', data, 'application/zip'),
            'confirm_clear': 'true', 'confirmation_phrase': 'RESTORE CLINIC', 'preview_token': token}, HTTP_X_IDEMPOTENCY_KEY=key)

    def test_restored_admin_can_replay_receipt_after_original_initiator_was_removed(self):
        backup = BackupCreatorService().create_full_backup().getvalue()
        initiator = UserService().create_user('synthetic_later_admin', PASSWORD, 'Synthetic later admin', 'admin')
        initiator.is_superuser = True; initiator.force_password_change = False; initiator.save()
        self.login_as(initiator); token = self.preview(backup)
        extra = self.patient_for(first_name='Synthetic extra inventory')
        result = self.execute(backup, token, 'synthetic-restored-namespace')
        self.assertEqual(result.status_code, 200)
        self.assertFalse(User.objects.filter(pk=initiator.pk).exists())
        self.assertFalse(Patient.objects.filter(pk=extra.pk).exists())
        receipt = RecoveryOperation.objects.get(key='synthetic-restored-namespace')
        self.assertEqual(receipt.state, 'completed'); self.assertEqual(receipt.initiator['id'], initiator.pk)
        self.login_as(User.objects.get(pk=self.admin.pk))
        with patch.object(BackupRestoreService, 'execute_restore', side_effect=AssertionError('Recovery must not execute twice')):
            replay = self.execute(backup, token, 'synthetic-restored-namespace')
        self.assertEqual(replay.status_code, 200); self.assertEqual(replay['X-Idempotency-Replayed'], 'true')
        self.assertEqual(replay.json()['data'], receipt.result)

    def test_interrupted_receipt_blocks_old_and_new_operation_keys_without_reexecution(self):
        backup = BackupCreatorService().create_full_backup().getvalue(); token = self.preview(backup)
        RecoveryOperation.objects.create(key='synthetic-interrupted-old', fingerprint='a' * 64, initiator={'id': self.admin.pk}, state='processing', expires_at=timezone.now() + timedelta(days=1))
        with patch.object(BackupRestoreService, 'execute_restore', side_effect=AssertionError('Interrupted recovery cannot execute')):
            response = self.execute(backup, token, 'synthetic-new-key')
        self.assertEqual(response.status_code, 409); self.assertEqual(response.json()['error']['code'], 'recovery_interrupted')
        self.assertFalse(RecoveryOperation.objects.filter(key='synthetic-new-key').exists())

    def test_failure_before_media_replacement_releases_receipt_for_corrected_retry(self):
        backup = BackupCreatorService().create_full_backup().getvalue(); token = self.preview(backup)
        with patch.object(BackupRestoreService, 'execute_restore', side_effect=ValueError('Synthetic pre-media rejection')):
            result = self.execute(backup, token, 'synthetic-safe-failure')
        self.assertEqual(result.status_code, 400)
        self.assertFalse(RecoveryOperation.objects.filter(key='synthetic-safe-failure').exists())
        result = self.execute(backup, token, 'synthetic-safe-failure')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(RecoveryOperation.objects.get(key='synthetic-safe-failure').state, 'completed')
