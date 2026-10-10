from datetime import timedelta
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from apps.clinical.models import ClinicalScale, ScaleField, MedicationOption, DiagnosisOption
from apps.clinical.services import MedicationService, DiagnosisService
from apps.visits.services import VisitService
from apps.visits.models import VisitRevision
from apps.visits.scale_validation import normalize_scale_response
from apps.prescriptions.issuance import finalized_revision, record_document
from core.exceptions import ConflictError
from .base import ClinicTestCase


class VisitWorkflowTests(ClinicTestCase):
    def test_draft_can_be_incomplete_but_signing_requires_complaint(self):
        visit = self.visit_for(main_complaints='')
        self.assertEqual(visit.status, 'draft')
        with self.assertRaises(ValidationError):
            VisitService().transition(visit, 'final', self.doctor, 1)
        visit.refresh_from_db()
        self.assertEqual(visit.status, 'draft')
        self.assertEqual(visit.revisions.count(), 0)

    def test_signature_is_server_authorized_not_client_supplied(self):
        with self.assertRaises(ValidationError):
            self.visit_for(signed_by=self.admin)
        with self.assertRaises(PermissionDenied):
            self.visit_for(actor=self.receptionist, status='final')

    def test_signed_visit_edit_requires_amendment_and_reason(self):
        service = VisitService()
        visit = self.visit_for(status='final')
        with self.assertRaises(ValidationError):
            service.update_visit(visit, {'main_complaints': 'Changed'}, self.doctor, 1)
        with self.assertRaises(ValidationError):
            service.transition(visit, 'amended', self.doctor, 1)
        old = visit.revisions.get().snapshot
        visit = service.transition(visit, 'amended', self.doctor, 1, 'Clinical correction')
        visit = service.update_visit(visit, {'main_complaints': 'Changed'}, self.doctor, visit.version)
        visit = service.transition(visit, 'final', self.doctor, visit.version)
        self.assertEqual(visit.revisions.count(), 2)
        self.assertEqual(visit.revisions.get(number=1).snapshot, old)
        self.assertEqual(visit.revisions.get(number=2).snapshot['fields']['main_complaints'], 'Changed')

    def test_lock_preserves_existing_signed_revision_and_blocks_amendment(self):
        visit = self.visit_for(status='final')
        visit = VisitService().transition(visit, 'locked', self.doctor, 1)
        self.assertEqual(visit.revisions.count(), 1)
        with self.assertRaises(ValidationError):
            VisitService().transition(visit, 'amended', self.doctor, visit.version, 'Correction')

    def test_revision_cannot_be_saved_or_deleted(self):
        revision = self.visit_for(status='final').revisions.get()
        revision.reason = 'Tampering'
        with self.assertRaises(ValidationError):
            revision.save()
        with self.assertRaises(ValidationError):
            revision.delete()

    def test_followup_date_validation_and_completed_sync(self):
        today = timezone.localdate()
        with self.assertRaises(ValidationError):
            self.visit_for(follow_up_date=today - timedelta(days=1))
        visit = self.visit_for(follow_up_date=today + timedelta(days=7))
        row = self.patient.patientfollowup_records.get(source_visit=visit)
        self.assertEqual(row.status, 'pending')
        VisitService().complete_follow_up(visit, self.doctor, 1)
        row.refresh_from_db()
        self.assertEqual(row.status, 'completed')
        self.assertEqual(row.completed_by_id, self.doctor.pk)

    def test_unsigned_or_stale_document_issuance_rejected(self):
        draft = self.visit_for()
        with self.assertRaises(ValidationError):
            finalized_revision(draft)
        visit = self.visit_for(status='final')
        revision = finalized_revision(visit)
        with self.assertRaises(ConflictError):
            record_document(visit, self.doctor, 'prescription', {'visit_version': 0, 'revision_id': revision.pk}, b'%PDF-synthetic')
        with self.assertRaises(ValidationError):
            record_document(visit, self.doctor, 'prescription', {'visit_version': 1, 'revision_id': 0}, b'%PDF-synthetic')

    def test_issued_pdf_bytes_checksum_and_snapshot_retained(self):
        import hashlib
        visit = self.visit_for(status='final')
        pdf = b'%PDF-synthetic-suite'
        snapshot = {'visit_version': visit.version, 'revision_id': finalized_revision(visit).pk}
        document = record_document(visit, self.doctor, 'prescription', snapshot, pdf)
        self.assertEqual(bytes(document.pdf_data), pdf)
        self.assertEqual(document.checksum, hashlib.sha256(pdf).hexdigest())
        self.assertEqual(document.snapshot, snapshot)
        with self.assertRaises(PermissionDenied):
            record_document(visit, self.receptionist, 'prescription', snapshot, pdf)

    def test_pseudonymization_does_not_erase_signed_identity(self):
        from apps.patients.services import PatientService
        visit = self.visit_for(status='final')
        original = visit.revisions.get().snapshot['patient']
        PatientService().anonymize(self.patient, self.admin, 1)
        self.assertEqual(visit.revisions.get().snapshot['patient'], original)
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.is_active)
        self.assertEqual(self.patient.national_id, '')


class CatalogScaleTests(ClinicTestCase):
    def test_medication_identity_is_case_and_space_insensitive(self):
        service = MedicationService()
        service.create_medication(generic_english='Synthetic', dosage='10mg', brand_english='Brand')
        with self.assertRaises(ValidationError):
            service.create_medication(generic_english=' synthetic ', dosage='10mg', brand_english='brand')

    def test_catalog_updates_require_version_and_protect_metadata(self):
        service = DiagnosisService()
        row = service.create_diagnosis(code='SYN', english_name='Synthetic', arabic_name='تجريبي')
        with self.assertRaises(ConflictError):
            service.update_diagnosis(row.pk, expected_version=2, english_name='Changed')
        with self.assertRaises(ValidationError):
            service.update_diagnosis(row.pk, expected_version=1, is_active=False)
        updated = service.update_diagnosis(row.pk, expected_version=1, english_name='Changed')
        self.assertEqual(updated.version, 2)

    def test_scale_rejects_nonfinite_range_and_off_step_default(self):
        scale = ClinicalScale.objects.create(name='Synthetic')
        for changes in ({'max_val': float('inf')}, {'step': 0}, {'default': 0.5}, {'min_val': 10, 'max_val': 0}):
            field = ScaleField(scale=scale, label='Question', min_val=0, max_val=10, step=1, default=0)
            for key, value in changes.items():
                setattr(field, key, value)
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                field.full_clean()

    def test_answers_validate_bounds_step_and_snapshot_definition(self):
        scale = ClinicalScale.objects.create(name='Synthetic')
        field = ScaleField.objects.create(scale=scale, label='Question', min_val=0, max_val=10, step=2, default=0)
        row = normalize_scale_response({'scale_id': scale.pk, 'responses': {str(field.pk): 4}})
        self.assertEqual(row['responses']['__score'], 4)
        self.assertEqual(row['responses']['__definition'][0]['step'], 2)
        for answer in (True, float('inf'), 3, 12, None):
            with self.subTest(answer=answer), self.assertRaises(ValidationError):
                normalize_scale_response({'scale_id': scale.pk, 'responses': {str(field.pk): answer}})
        field.step = 1
        field.save()
        again = normalize_scale_response({'scale_id': scale.pk, 'responses': {str(field.pk): 4}}, row['responses']['__definition'], 'Original name')
        self.assertEqual(again['responses']['__definition'][0]['step'], 2)
        self.assertEqual(again['scale_name'], 'Original name')

    def test_database_rejects_zero_version(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            DiagnosisOption.objects.create(code='INVALID', english_name='Synthetic', arabic_name='تجريبي', version=0)
