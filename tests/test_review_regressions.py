"""Permanent regressions for current clinical/reporting/ownership contracts."""
import io
import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from apps.accounts.models import User
from apps.accounts.services import UserService
from apps.appointments.services import AppointmentService
from apps.billing.services import BillingService
from apps.clinical.models import ClinicalScale, ScaleField, DiagnosisOption
from apps.clinical.services import ScaleService
from apps.import_export.services import OptionsImportService
from apps.patients.models import PatientIdentifier, PatientContact, PatientFollowUp
from apps.patients.services import PatientService
from apps.patients.record_services import PatientRecordService
from apps.reports.services import StatisticsService
from apps.tasks.services import TaskService
from apps.visits.services import VisitService
from apps.visits.scale_validation import normalize_scale_response
from core.exceptions import ConflictError
from .base import ClinicTestCase


class ClinicalOwnershipRegressions(ClinicTestCase):
    def test_unchanged_national_id_does_not_retire_other_country_identifiers(self):
        patient = self.patient_for(national_id='1234567890')
        foreign = PatientIdentifier.objects.create(patient=patient, identifier_type='national_id', value='1234567890', issuing_country='SY', created_by=self.admin)
        PatientService().update_patient(patient, {'occupation': 'Synthetic teacher', 'national_id': patient.national_id}, self.admin, patient.version)
        foreign.refresh_from_db()
        self.assertTrue(foreign.is_active)
        self.assertEqual(PatientIdentifier.objects.filter(patient=patient, is_active=True).count(), 2)

    def test_profile_and_primary_emergency_contact_have_bidirectional_history(self):
        patient = self.patient_for(emergency_contact_name='First synthetic contact')
        patient = PatientService().update_patient(patient, {'emergency_contact_name': 'Second synthetic contact', 'correction_reason': 'Synthetic profile correction'}, self.admin, patient.version)
        contact = PatientContact.objects.get(patient=patient, is_active=True, is_primary=True)
        self.assertEqual(contact.name, patient.emergency_contact_name)
        PatientRecordService().save(patient, 'contacts', {'name': 'Third synthetic contact'}, self.admin, patient.version, contact.pk, reason='Synthetic register correction')
        patient.refresh_from_db()
        self.assertEqual(patient.emergency_contact_name, 'Third synthetic contact')
        self.assertTrue(patient.corrections.exists())

    def test_clinical_narrative_requires_edit_permission_even_for_profile_writers(self):
        patient = self.patient_for()
        from django.contrib.auth.models import Permission
        self.receptionist.user_permissions.add(Permission.objects.get(codename='edit_patient'))
        self.receptionist.clear_permission_cache()
        with self.assertRaises(PermissionDenied):
            PatientService().update_patient(patient, {'important_notes': 'Synthetic clinical narrative', 'correction_reason': 'Synthetic correction'}, self.receptionist, patient.version)
        patient.refresh_from_db()
        self.assertEqual(patient.important_notes, '')

    def test_followup_repeat_is_noop_and_different_terminal_outcome_is_rejected(self):
        visit = self.visit_for(follow_up_date=timezone.localdate() + timedelta(days=1))
        visit = VisitService().complete_follow_up(visit, self.doctor, visit.version, 'completed')
        state = (visit.version, visit.follow_up_completed_at, visit.follow_up_completed_by_id)
        repeated = VisitService().complete_follow_up(visit, self.doctor, visit.version, 'completed')
        self.assertEqual((repeated.version, repeated.follow_up_completed_at, repeated.follow_up_completed_by_id), state)
        with self.assertRaises(ValidationError):
            VisitService().complete_follow_up(repeated, self.doctor, repeated.version, 'missed')

    def test_rescheduled_followup_retains_terminal_occurrence_and_clears_evidence(self):
        visit = self.visit_for(follow_up_date=timezone.localdate() + timedelta(days=1))
        visit = VisitService().complete_follow_up(visit, self.doctor, visit.version, 'completed')
        VisitService().update_visit(visit, {'follow_up_date': timezone.localdate() + timedelta(days=2)}, self.doctor, visit.version)
        rows = PatientFollowUp.objects.filter(source_visit=visit)
        current = rows.get(is_active=True)
        self.assertEqual(current.status, 'pending')
        self.assertIsNone(current.completed_visit_id)
        self.assertEqual(current.outcome_reason, '')
        self.assertEqual(rows.filter(is_active=False, status='completed').count(), 1)

    def test_unapproved_visit_cannot_be_attached_as_completed_followup_evidence(self):
        visit = self.visit_for()
        self.patient.refresh_from_db()
        with self.assertRaises(ValidationError):
            PatientRecordService().save(self.patient, 'follow-ups', {'title': 'Synthetic action', 'due_date': timezone.localdate(), 'status': 'completed', 'outcome_reason': 'Synthetic completion', 'completed_visit': visit}, self.admin, self.patient.version)
        self.assertFalse(PatientFollowUp.objects.filter(completed_visit=visit).exists())


class ScaleAndApprovedRiskRegressions(ClinicTestCase):
    def test_amendment_draft_does_not_replace_last_approved_high_risk(self):
        visit = self.visit_for(status='final', suicide_risk_level='High')
        visit = VisitService().transition(visit, 'amended', self.doctor, visit.version, reason='Synthetic amendment')
        visit = VisitService().update_visit(visit, {'suicide_risk_level': 'Low'}, self.doctor, visit.version)
        self.assertEqual(list(StatisticsService().get_high_risk_patients(self.admin).values_list('pk', flat=True)), [self.patient.pk])
        VisitService().transition(visit, 'final', self.doctor, visit.version)
        self.assertNotIn(self.patient.pk, [row.pk for row in StatisticsService().get_high_risk_patients(self.admin)])

    def test_more_than_100_questions_is_rejected_without_changing_scale_version(self):
        scale = ClinicalScale.objects.create(name='Synthetic hundred-question scale')
        ScaleField.objects.bulk_create([ScaleField(scale=scale, label=f'Synthetic {index}') for index in range(100)])
        with self.assertRaises(ValidationError):
            ScaleService().add_field(scale, {'label': 'Question 101'}, scale.version)
        scale.refresh_from_db()
        self.assertEqual(scale.version, 1)
        self.assertEqual(scale.fields.count(), 100)

    def test_large_off_step_defaults_and_answers_are_not_rounded_into_validity(self):
        scale = ClinicalScale.objects.create(name='Synthetic large scale')
        with self.assertRaises(ValidationError):
            ScaleField(scale=scale, label='Synthetic', min_val=0, max_val=2_000_000_000, step=1, default=1_000_000_000.25).clean()
        field = ScaleField.objects.create(scale=scale, label='Synthetic', min_val=0, max_val=2_000_000_000, step=1, default=0)
        with self.assertRaises(ValidationError):
            normalize_scale_response({'scale_id': scale.pk, 'responses': {str(field.pk): 1_000_000_000.25}})

    def test_retired_scale_preserves_existing_snapshot_answers_but_cannot_be_newly_added(self):
        scale = ClinicalScale.objects.create(name='Synthetic snapshot')
        field = ScaleField.objects.create(scale=scale, label='Original label', min_val=0, max_val=10, step=1)
        normalized = normalize_scale_response({'scale_id': scale.pk, 'responses': {str(field.pk): 7}})
        scale.is_active = False; scale.save(update_fields=['is_active'])
        with self.assertRaises(ValidationError):
            normalize_scale_response({'scale_id': scale.pk, 'responses': {str(field.pk): 7}})
        restored = normalize_scale_response({'scale_id': scale.pk, 'responses': {str(field.pk): 8}}, normalized['responses']['__definition'], 'Original name')
        self.assertEqual(restored['responses'][str(field.pk)], 8)
        self.assertEqual(restored['scale_name'], 'Original name')
        self.assertEqual(restored['responses']['__definition'][0]['label'], 'Original label')


class ReportsAndOccurrenceRegressions(ClinicTestCase):
    def test_paid_totals_keep_separate_currencies_and_exclude_unpaid_invoices(self):
        service = BillingService()
        for currency, amount in [('SYP', '12.50'), ('USD', '3.25'), ('SYP', '2.50')]:
            row = service.create_invoice({'patient': self.patient, 'currency': currency, 'total_amount': amount})
            row = service.transition(row, 'issued', self.admin, row.version)
            service.transition(row, 'paid', self.admin, row.version, payment_method='cash')
        service.create_invoice({'patient': self.patient, 'currency': 'USD', 'total_amount': '99.00'})
        report = StatisticsService().get_reconciliation()['invoices']
        self.assertEqual({key: Decimal(value) for key, value in report['paid_by_currency'].items()}, {'SYP': Decimal('15.00'), 'USD': Decimal('3.25')})
        self.assertNotIn('paid_amount', report)

    def test_unknown_birth_produces_null_average_without_zero_age(self):
        self.assertIsNone(StatisticsService().get_average_age(self.doctor))
        self.assertEqual(sum(StatisticsService().get_age_distribution(self.doctor)[1]), 0)

    def test_patient_membership_and_visit_authorship_statistics_are_distinct(self):
        visit = self.visit_for(actor=self.doctor)
        PatientService().add_care_team_member(self.patient, self.other_doctor.pk, 'doctor', expected_version=self.patient.version, actor=self.admin)
        rows = {row['doctor_id']: row for row in StatisticsService().get_doctor_performance(self.admin)}
        self.assertEqual(rows[self.doctor.pk]['visit_count'], 1)
        self.assertEqual(rows[self.other_doctor.pk]['visit_count'], 0)

    def test_task_reopen_creates_new_reminder_occurrence_even_on_same_due_date(self):
        service = TaskService(); row = service.create_task(self.doctor, {'title': 'Synthetic reminder', 'due_date': timezone.localdate()})
        generation = row.reminder_generation
        row = service.complete_task(row, self.doctor, row.version)
        row = service.activate_task(row, self.doctor, row.version)
        self.assertNotEqual(row.reminder_generation, generation)
        self.assertFalse(row.reminder_sent)

    def test_appointment_reopen_refreshes_occurrence_and_rechecks_clinician_eligibility(self):
        service = AppointmentService(); row = service.create_appointment({'patient': self.patient, 'doctor': self.doctor, 'appointment_date': timezone.localdate() + timedelta(days=1), 'appointment_time': '10:00'})
        row = service.cancel(row, row.version, 'Synthetic cancellation'); generation = row.reminder_generation
        row = service.transition(row, 'scheduled', row.version)
        self.assertNotEqual(row.reminder_generation, generation)
        row = service.cancel(row, row.version, 'Synthetic cancellation')
        self.doctor.is_active = False; self.doctor.save(update_fields=['is_active'])
        with self.assertRaises(ValidationError):
            service.transition(row, 'scheduled', row.version)
        row.refresh_from_db(); self.assertEqual(row.status, 'cancelled')

    def test_configured_appointment_duration_is_used_when_omitted(self):
        with self.settings(DEFAULT_APPOINTMENT_DURATION=45):
            row = AppointmentService().create_appointment({'patient': self.patient, 'doctor': self.doctor, 'appointment_date': timezone.localdate() + timedelta(days=1), 'appointment_time': '11:00'})
        self.assertEqual(row.duration_minutes, 45)

    def test_stale_catalog_preview_cannot_replace_current_inventory(self):
        service = OptionsImportService(); digest = service.inventory_digest('diagnosis')
        DiagnosisOption.objects.create(code='KEEP', english_name='Synthetic existing', arabic_name='اصطناعي')
        with self.assertRaises(ConflictError):
            service.import_diagnoses(io.BytesIO(b'code,english,arabic\nNEW,Synthetic new,Synthetic\n'), 'replace', expected_inventory=digest)
        self.assertEqual(list(DiagnosisOption.objects.values_list('code', flat=True)), ['KEEP'])
