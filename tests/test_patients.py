from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from core.access import accessible_patients
from core.exceptions import ConflictError
from apps.patients.models import Patient, PatientCorrection, PatientCareTeam, PatientIdentifier
from apps.patients.services import PatientService
from apps.patients.record_services import PatientRecordService
from apps.patients.merge_services import PatientMergeService
from .base import ClinicTestCase


class PatientTests(ClinicTestCase):
    def test_unknown_birth_and_clinical_summaries_remain_unknown(self):
        self.assertIsNone(self.patient.dob_year)
        self.assertEqual(self.patient.allergy_status, 'unknown')
        self.assertEqual(self.patient.medication_status, 'unknown')

    def test_permanent_file_number_cannot_change(self):
        self.patient.patient_number = 'P-CHANGED'
        with self.assertRaises(ValidationError):
            self.patient.save()

    def test_duplicate_national_identifiers_preserved_and_reported(self):
        one = self.patient_for(national_id='1234567890')
        two = self.patient_for(national_id='1234567890')
        self.assertEqual(one.national_id, two.national_id)
        self.assertNotEqual(one.patient_number, two.patient_number)
        self.assertIn(one, PatientService().find_duplicates(self.admin, {'national_id': two.national_id}, two.pk))

    def test_identity_corrections_require_reason_and_record_history(self):
        service = PatientService()
        with self.assertRaises(ValidationError):
            service.update_patient(self.patient, {'first_name': 'تصحيح'}, self.doctor, 1)
        updated = service.update_patient(self.patient, {'first_name': 'تصحيح', 'correction_reason': 'Synthetic correction'}, self.doctor, 1)
        self.assertEqual(updated.version, 2)
        correction = PatientCorrection.objects.get(patient=updated)
        self.assertEqual(correction.changes['first_name']['after'], 'تصحيح')
        with self.assertRaises(ConflictError):
            service.update_patient(updated, {'occupation': 'Teacher'}, self.doctor, 1)

    def test_service_ignores_protected_ownership_and_lifecycle_fields(self):
        updated = PatientService().update_patient(self.patient, {
            'created_by': self.other_doctor, 'doctor': self.other_doctor,
            'is_active': False, 'version': 100, 'patient_number': 'P-INJECTED',
        }, self.doctor, 1)
        self.assertEqual(updated.created_by_id, self.doctor.pk)
        self.assertTrue(updated.is_active)
        self.assertEqual(updated.version, 2)
        self.assertNotEqual(updated.patient_number, 'P-INJECTED')

    def test_invalid_birth_year_and_profile_choice_rejected(self):
        for data in ({'dob_year': True}, {'dob_year': '1990'}, {'dob_year': 1899}, {'gender': 'invalid'}):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                self.patient_for(**data)

    def test_team_membership_controls_access_and_retains_dated_history(self):
        service = PatientService()
        self.assertFalse(accessible_patients(self.other_doctor).filter(pk=self.patient.pk).exists())
        member, version = service.add_care_team_member(self.patient, self.other_doctor.pk, 'doctor', 1, self.admin)
        self.assertEqual(version, 2)
        self.assertTrue(accessible_patients(self.other_doctor).filter(pk=self.patient.pk).exists())
        service.remove_care_team_member(self.patient, self.other_doctor.pk, version, self.admin, 'Synthetic reassignment')
        member.refresh_from_db()
        self.assertIsNotNone(member.ended_at)
        self.assertFalse(accessible_patients(self.other_doctor).filter(pk=self.patient.pk).exists())

    def test_historical_author_keeps_access_after_team_removal_and_archive(self):
        self.visit_for()
        member = PatientCareTeam.objects.get(patient=self.patient, user=self.doctor)
        member.ended_at = timezone.now()
        member.save()
        PatientService().soft_delete_patient(self.patient, self.admin, 1)
        self.assertFalse(Patient.objects.filter(pk=self.patient.pk).exists())
        self.assertTrue(accessible_patients(self.doctor, True).filter(pk=self.patient.pk).exists())

    def test_team_rejects_invalid_ids_stale_versions_and_duplicate_members(self):
        service = PatientService()
        for identifier in (True, [], 'invalid'):
            with self.subTest(identifier=identifier), self.assertRaises(ValidationError):
                service.add_care_team_member(self.patient, identifier, 'doctor', 1, self.admin)
        with self.assertRaises(ValidationError):
            service.add_care_team_member(self.patient, self.doctor.pk, 'doctor', 1, self.admin)
        with self.assertRaises(ConflictError):
            service.add_care_team_member(self.patient, self.other_doctor.pk, 'doctor', 9, self.admin)

    def test_only_admin_archives_and_restore_checks_version(self):
        service = PatientService()
        with self.assertRaises(ValidationError):
            service.soft_delete_patient(self.patient, self.doctor, 1)
        service.soft_delete_patient(self.patient, self.admin, 1)
        self.patient.refresh_from_db()
        with self.assertRaises(ConflictError):
            service.restore_patient(self.patient, self.admin, 1)
        restored = service.restore_patient(self.patient, self.admin, self.patient.version)
        self.assertTrue(restored.is_active)
        self.assertIsNone(restored.deleted_at)


class LongitudinalRecordTests(ClinicTestCase):
    def test_record_creation_bumps_parent_and_rejects_stale_edit(self):
        service = PatientRecordService()
        row, version = service.save(self.patient, 'contacts', {'name': 'Synthetic Contact'}, self.doctor, 1)
        self.assertEqual(version, 2)
        with self.assertRaises(ConflictError):
            service.save(self.patient, 'contacts', {'name': 'Changed'}, self.doctor, 1, row.pk, reason='Correction')
        changed, version = service.save(self.patient, 'contacts', {'name': 'Changed'}, self.doctor, version, row.pk, reason='Correction')
        self.assertEqual(changed.name, 'Changed')
        self.assertEqual(version, 3)

    def test_record_cannot_move_to_another_patient(self):
        service = PatientRecordService()
        row, _ = service.save(self.patient, 'contacts', {'name': 'Synthetic'}, self.doctor, 1)
        other = self.patient_for()
        with self.assertRaises(ValidationError):
            service.save(other, 'contacts', {'name': 'Changed'}, self.admin, 1, row.pk, reason='Correction')

    def test_scope_and_clinical_permissions_are_independent(self):
        with self.assertRaises(PermissionDenied):
            PatientRecordService().list(self.patient, 'contacts', self.other_doctor)
        patient = self.patient_for(self.receptionist)
        with self.assertRaises(PermissionDenied):
            PatientRecordService().save(patient, 'allergies', {'substance': 'Synthetic'}, self.receptionist, 1)

    def test_retirement_requires_reason_and_never_implies_negative_summary(self):
        service = PatientRecordService()
        row, version = service.save(self.patient, 'allergies', {'substance': 'Synthetic', 'status': 'confirmed'}, self.doctor, 1)
        with self.assertRaises(ValidationError):
            service.save(self.patient, 'allergies', {}, self.doctor, version, row.pk, retire=True)
        service.save(self.patient, 'allergies', {}, self.doctor, version, row.pk, retire=True, reason='Resolved')
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.allergy_status, 'recorded')
        row.refresh_from_db()
        self.assertFalse(row.is_active)

    def test_active_allergy_blocks_none_known_summary(self):
        PatientRecordService().save(self.patient, 'allergies', {'substance': 'Synthetic', 'status': 'confirmed'}, self.doctor, 1)
        with self.assertRaises(ValidationError):
            PatientService().update_patient(self.patient, {'allergy_status': 'none_known'}, self.doctor, 2)

    def test_record_boolean_and_field_allowlist(self):
        for data in ({'name': 'Synthetic', 'is_primary': 'true'}, {'name': 'Synthetic', 'patient': 5}):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                PatientRecordService().save(self.patient, 'contacts', data, self.doctor, 1)

    def test_followup_completion_records_actor_and_cannot_reopen(self):
        service = PatientRecordService()
        row, version = service.save(self.patient, 'follow-ups', {'title': 'Review', 'due_date': timezone.localdate()}, self.doctor, 1)
        row, version = service.save(self.patient, 'follow-ups', {'status': 'completed', 'outcome_reason': 'Reviewed'}, self.doctor, version, row.pk, reason='Review completed')
        self.assertEqual(row.completed_by_id, self.doctor.pk)
        with self.assertRaises(ValidationError):
            service.save(self.patient, 'follow-ups', {'status': 'pending'}, self.doctor, version, row.pk, reason='Reopen')


class MergeTests(ClinicTestCase):
    def test_merge_moves_records_without_rewriting_signed_snapshot(self):
        source, target = self.patient, self.patient_for()
        visit = self.visit_for(status='final')
        snapshot = visit.revisions.get().snapshot
        preview = PatientMergeService().preview(source, target.pk, self.admin)
        result = PatientMergeService().merge(source, preview['token'], 'Duplicate confirmed', self.admin, source.version, target.version)
        visit.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual(result.pk, target.pk)
        self.assertEqual(visit.patient_id, target.pk)
        self.assertEqual(visit.revisions.get().snapshot, snapshot)
        self.assertEqual(source.merged_into_id, target.pk)
        self.assertFalse(source.is_active)

    def test_changed_content_invalidates_preview(self):
        target = self.patient_for()
        preview = PatientMergeService().preview(self.patient, target.pk, self.admin)
        self.visit_for()
        with self.assertRaises(ConflictError):
            PatientMergeService().merge(self.patient, preview['token'], 'Duplicate', self.admin, 1, 1)

    def test_nonadmin_cannot_preview_and_tampered_token_rejected(self):
        target = self.patient_for()
        with self.assertRaises(PermissionDenied):
            PatientMergeService().preview(self.patient, target.pk, self.doctor)
        with self.assertRaises(ValidationError):
            PatientMergeService().merge(self.patient, 'tampered', 'Duplicate', self.admin, 1, 1)

    def test_duplicate_review_hides_match_without_changing_identifier(self):
        one = self.patient_for(national_id='1234567890')
        two = self.patient_for(national_id='1234567890')
        PatientMergeService().dismiss(one, two.pk, 'different', 'Different people', self.admin, 1)
        self.assertFalse(PatientService().find_duplicates(self.admin, {'national_id': one.national_id}, one.pk).exists())
        self.assertEqual(PatientIdentifier.objects.filter(value='1234567890', is_active=True).count(), 2)
