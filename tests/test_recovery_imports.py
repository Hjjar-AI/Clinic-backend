import csv
import hashlib
import io
import json
import zipfile
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.sessions.models import Session
from django.utils import timezone
from apps.backup.backup_creator import BackupCreatorService
from apps.backup.backup_restore import BackupRestoreService
from apps.backup.backup_validation import BackupValidationService, payload_bytes
from apps.import_export.services import BulkImportService, OptionsImportService
from apps.patients.models import Patient, PatientDocument
from apps.clinical.models import DiagnosisOption, MedicationOption
from core.upload_security import validate_upload, detect_macros
from .base import ClinicTestCase, ClinicTransactionTestCase


def patient_csv(identifier='1234567890'):
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(['الاسم الأول', 'اللقب', 'الرقم الوطني', 'سنة الميلاد'])
    writer.writerow(['اصطناعي', 'تجريبي', identifier, ''])
    return stream.getvalue().encode('utf-8-sig')


class ImportTests(ClinicTestCase):
    def test_patient_preview_has_no_writes_and_unknown_birth_is_preserved(self):
        count = Patient.objects.count()
        data = patient_csv()
        service = BulkImportService()
        preview = service.preview_patients(io.BytesIO(data), self.doctor.pk, self.admin.pk)
        self.assertEqual(preview['added'], 1)
        self.assertEqual(Patient.objects.count(), count)
        result = service.import_patients(io.BytesIO(data), self.doctor.pk, self.admin.pk)
        self.assertEqual(result['added'], 1)
        self.assertIsNone(Patient.objects.get(national_id='1234567890').dob_year)

    def test_duplicate_import_keeps_identifier_with_warning(self):
        self.patient_for(national_id='1234567890')
        result = BulkImportService().import_patients(io.BytesIO(patient_csv()), self.doctor.pk, self.admin.pk)
        self.assertEqual(result['added'], 1)
        self.assertTrue(result['warnings'])
        self.assertEqual(Patient.objects.filter(national_id='1234567890').count(), 2)

    def test_csv_duplicate_headers_and_invalid_encoding_rejected(self):
        for data in (b'a,a\n1,2\n', b'a,b\n1\n', b'', b'\xff\xfe\x80'):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                BulkImportService()._read_file(io.BytesIO(data))

    def test_xlsx_formulas_rejected(self):
        from openpyxl import Workbook
        wb = Workbook()
        wb.active.append(['Header'])
        wb.active.append(['=1+1'])
        stream = io.BytesIO()
        wb.save(stream)
        wb.close()
        with self.assertRaises(ValidationError):
            BulkImportService()._read_file(stream)

    def test_import_execution_requires_preview_and_unchanged_file(self):
        def upload(data):
            return SimpleUploadedFile('patients.csv', data, content_type='text/csv')
        response = self.api.post('/api/v1/bulk-import/', {'file': upload(patient_csv())}, HTTP_X_IDEMPOTENCY_KEY='suite-import-missing')
        self.assertEqual(response.status_code, 400)
        preview = self.api.post('/api/v1/bulk-import/preview/', {'file': upload(patient_csv()), 'doctor_id': self.doctor.pk}, HTTP_X_IDEMPOTENCY_KEY='suite-import-preview')
        self.assertEqual(preview.status_code, 200)
        token = preview.json()['data']['preview_token']
        response = self.api.post('/api/v1/bulk-import/', {'file': upload(patient_csv('9999999999')), 'doctor_id': self.doctor.pk, 'preview_token': token}, HTTP_X_IDEMPOTENCY_KEY='suite-import-changed')
        self.assertEqual(response.status_code, 409)
        response = self.api.post('/api/v1/bulk-import/', {'file': upload(patient_csv()), 'doctor_id': self.doctor.pk, 'preview_token': token}, HTTP_X_IDEMPOTENCY_KEY='suite-import-execute')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['added'], 1)

    def test_catalog_replacement_rejects_partial_invalid_file(self):
        row = DiagnosisOption.objects.create(code='SYN', english_name='Synthetic', arabic_name='تجريبي')
        # Public diagnosis imports use three positional columns.
        data = 'code,english,arabic\nNEW,Synthetic,تجريبي\n,Missing,ناقص\n'.encode()
        with self.assertRaises(ValidationError):
            OptionsImportService().import_diagnoses(io.BytesIO(data), 'replace')
        row.refresh_from_db()
        self.assertTrue(row.is_active)
        self.assertEqual(DiagnosisOption.objects.count(), 1)


class BackupTests(ClinicTestCase):
    def document(self, content=b'%PDF-1.4\nSynthetic suite document'):
        path = default_storage.save('suite/document.pdf', ContentFile(content))
        return PatientDocument.objects.create(patient=self.patient, filename='document.pdf',
            original_filename='document.pdf', filepath=path, file_size=len(content),
            checksum=hashlib.sha256(content).hexdigest(), mime_type='application/pdf', uploaded_by=self.doctor)

    def test_full_archive_authenticates_every_member_and_media(self):
        document = self.document()
        stream = BackupCreatorService().create_full_backup()
        preview = BackupRestoreService().preview_restore(stream)
        self.assertTrue(preview['compatible'])
        self.assertEqual(preview['patients_count'], 1)
        self.assertEqual(preview['media_files_count'], 1)
        with zipfile.ZipFile(stream) as archive:
            manifest_raw = archive.read('manifest.json')
            self.assertTrue(BackupValidationService().verify_signature(manifest_raw, archive.read('signature.txt').decode()))
            manifest = json.loads(manifest_raw)
            for name, entry in manifest['members'].items():
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), entry['sha256'])
            self.assertEqual(archive.read('media/' + document.filepath), default_storage.open(document.filepath).read())

    def test_tampered_media_rejected(self):
        document = self.document()
        original = BackupCreatorService().create_full_backup()
        changed = io.BytesIO()
        with zipfile.ZipFile(original) as source, zipfile.ZipFile(changed, 'w') as target:
            for name in source.namelist():
                target.writestr(name, b'Tampered' if name == 'media/' + document.filepath else source.read(name))
        with self.assertRaisesRegex(ValueError, 'checksum'):
            BackupRestoreService().preview_restore(changed)

    def test_missing_referenced_file_blocks_complete_backup(self):
        document = self.document()
        default_storage.delete(document.filepath)
        with self.assertRaisesRegex(ValueError, 'missing or inconsistent'):
            BackupCreatorService().create_full_backup()

    def test_json_signature_count_types_and_empty_scope(self):
        service = BackupValidationService()
        for signature in ('غير صالح', None, 'a' * 63, 'G' * 64):
            self.assertFalse(service.verify_signature(b'synthetic', signature))
        envelope = json.loads(BackupCreatorService().create_json_backup())
        envelope['data']['metadata']['counts']['patients.patient'] = True
        envelope['signature'] = service._sign_data(payload_bytes(envelope['data']))
        with self.assertRaisesRegex(ValueError, 'schema'):
            BackupRestoreService().preview_restore(io.BytesIO(json.dumps(envelope).encode()))
        with self.assertRaises(ValueError):
            BackupRestoreService().execute_restore(io.BytesIO(b'{}'), False, False, False)

    def test_unsafe_archive_path_rejected_before_parsing(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('../escape.txt', 'Synthetic')
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            BackupRestoreService().preview_restore(stream)

    def test_catalog_restore_preserves_patient_inventory(self):
        DiagnosisOption.objects.create(code='SYN', english_name='Synthetic', arabic_name='تجريبي')
        backup = BackupCreatorService().create_full_backup().getvalue()
        extra = self.patient_for(first_name='Extra')
        result = BackupRestoreService().preview_restore(io.BytesIO(backup), False, True, False)
        self.assertEqual(result['will_replace'], [])
        BackupRestoreService().execute_restore(io.BytesIO(backup), False, True, False)
        self.assertTrue(Patient.objects.filter(pk=extra.pk).exists())
        self.assertEqual(Patient.objects.count(), 2)

    def test_restore_http_requires_exact_confirmation_scope_and_digest(self):
        backup = BackupCreatorService().create_full_backup().getvalue()
        def upload(payload=backup):
            return SimpleUploadedFile('backup.zip', payload, content_type='application/zip')
        response = self.api.post('/api/v1/backup/restore/execute/', {'backup_file': upload()}, HTTP_X_IDEMPOTENCY_KEY='suite-restore-missing')
        self.assertEqual(response.status_code, 400)
        preview = self.api.post('/api/v1/backup/restore/preview/', {'backup_file': upload()}, HTTP_X_IDEMPOTENCY_KEY='suite-restore-preview')
        self.assertEqual(preview.status_code, 200)
        token = preview.json()['data']['preview_token']
        response = self.api.post('/api/v1/backup/restore/execute/', {'backup_file': upload(), 'confirm_clear': 'true', 'confirmation_phrase': 'RESTORE CLINIC',
            'preview_token': token, 'restore_patients': 'false'}, HTTP_X_IDEMPOTENCY_KEY='suite-restore-scope')
        self.assertEqual(response.status_code, 409)
        response = self.api.post('/api/v1/backup/restore/execute/', {'backup_file': upload(backup + b'changed'), 'confirm_clear': 'true',
            'confirmation_phrase': 'RESTORE CLINIC', 'preview_token': token}, HTTP_X_IDEMPOTENCY_KEY='suite-restore-digest')
        self.assertEqual(response.status_code, 409)

    def test_mime_size_and_macro_checks_use_actual_upload_bytes(self):
        with self.settings(MAX_ATTACHMENT_SIZE=8):
            with self.assertRaises(ValidationError):
                validate_upload(SimpleUploadedFile('large.pdf', b'%PDF-1.4 synthetic large'))
        with self.assertRaises(ValidationError):
            validate_upload(SimpleUploadedFile('fake.pdf', b'<html>synthetic</html>', content_type='application/pdf'))
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('word/vbaProject.bin', b'Synthetic macro')
        with self.assertRaises(ValidationError):
            detect_macros(SimpleUploadedFile('macro.docx', stream.getvalue()))


class FullRecoveryTests(ClinicTransactionTestCase):
    def test_backup_and_restore_preserve_full_signed_timestamp_precision(self):
        timestamp = (timezone.now() + timezone.timedelta(seconds=1)).replace(microsecond=123456)
        with patch('apps.visits.services.timezone.now', return_value=timestamp):
            visit = self.visit_for(status='final')
        revision = visit.revisions.get()
        original = revision.signed_at
        self.assertNotEqual(original.microsecond % 1000, 0)
        backup = BackupCreatorService().create_full_backup().getvalue()
        with zipfile.ZipFile(io.BytesIO(backup)) as archive:
            rows = json.loads(archive.read('backup.json'))['data']['records']
        saved = next(row for row in rows if row['model'] == 'visits.visitrevision')
        self.assertEqual(saved['fields']['signed_at'], original.isoformat())
        BackupRestoreService().execute_restore(io.BytesIO(backup))
        revision.refresh_from_db()
        self.assertEqual(revision.signed_at, original)

    def test_full_recovery_replaces_inventory_retains_signed_history_and_revokes_sessions(self):
        visit = self.visit_for(status='final')
        snapshot = visit.revisions.get().snapshot
        backup = BackupCreatorService().create_full_backup().getvalue()
        extra = self.patient_for(first_name='After backup')
        self.assertTrue(Session.objects.exists())
        BackupRestoreService().execute_restore(io.BytesIO(backup))
        self.assertFalse(Patient.objects.filter(pk=extra.pk).exists())
        visit.refresh_from_db()
        self.assertEqual(visit.revisions.get().snapshot, snapshot)
        self.assertEqual(Session.objects.count(), 0)
