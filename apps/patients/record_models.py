from core.constraints import check_constraint, retirement_constraint, verification_constraint
from .choices import (Verification, CareRole, MaritalStatus, FollowUpMethod, FollowUpStatus, IdentifierType, AuthorityScope, RecordSource, AllergySeverity, AllergyStatus, MedicationStatus, DuplicateStatus)
"""Longitudinal patient records; encounter facts stay on visits/signed snapshots."""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.core.validators import RegexValidator
from core.models import TimeStampedModel, ImmutableModel

VERIFICATION = Verification.choices
CARE_ROLES = CareRole.choices
MARITAL_STATUSES = MaritalStatus.choices


class PatientRecord(TimeStampedModel):
    patient = models.ForeignKey('patients.Patient', on_delete=models.PROTECT, related_name='%(class)s_records')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    is_active = models.BooleanField(default=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    retired_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    retirement_reason = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        abstract = True


class PatientIdentifier(PatientRecord):
    identifier_type = models.CharField(max_length=30, choices=IdentifierType.choices)
    value = models.CharField(max_length=100)
    issuer = models.CharField(max_length=100, blank=True, default='')
    issuing_country = models.CharField(max_length=2, blank=True, default='', validators=[RegexValidator(r'^[A-Z]{2}$', 'Use a two-letter country code')])
    verification = models.CharField(max_length=20, choices=VERIFICATION, default='reported')
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    @property
    def is_primary(self):
        return self.patient.primary_identifier_id == self.pk

    class Meta:
        indexes = [models.Index(fields=['identifier_type', 'value'])]
        constraints = [
            retirement_constraint('patients_patientidentifier_retirement_valid'),
            verification_constraint('patients_patientidentifier_verification_valid', ''),
            check_constraint(condition=models.Q(identifier_type__in=IdentifierType.values), name='patients_patientidentifier_identifier_type_valid'),
            check_constraint(condition=models.Q(verification__in=[item[0] for item in VERIFICATION]), name='patients_patientidentifier_verification_valid'),
            models.UniqueConstraint(fields=['patient', 'identifier_type', 'value', 'issuer', 'issuing_country'], condition=Q(is_active=True), name='unique_patient_identifier'),
        ]


class PatientContact(PatientRecord):
    name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=100, blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    is_emergency = models.BooleanField(default=False)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default='')

    class Meta:
        constraints = [
            retirement_constraint('patients_patientcontact_retirement_valid'),
            models.UniqueConstraint(fields=['patient'], condition=Q(is_active=True, is_primary=True), name='one_primary_patient_contact'),
        ]


class PatientRepresentative(PatientRecord):
    name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True, default='')
    authority_scope = models.CharField(max_length=30, choices=AuthorityScope.choices)
    verification = models.CharField(max_length=20, choices=VERIFICATION, default='unknown')
    evidence = models.CharField(max_length=500, blank=True, default='')
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        constraints = [
            retirement_constraint('patients_patientrepresentative_retirement_valid'),
            verification_constraint('patients_patientrepresentative_verification_valid', ''),
            check_constraint(condition=models.Q(authority_scope__in=AuthorityScope.values), name='patients_patientrepresentative_authority_scope_valid'),
            check_constraint(condition=models.Q(verification__in=[item[0] for item in VERIFICATION]), name='patients_patientrepresentative_verification_valid'),
            check_constraint(condition=Q(valid_from__isnull=True) | Q(valid_until__isnull=True) | Q(valid_until__gte=models.F('valid_from')), name='representative_dates_valid'),
        ]


class ClinicalPatientRecord(PatientRecord):
    source = models.CharField(max_length=30, choices=RecordSource.choices, default='patient')
    source_details = models.CharField(max_length=500, blank=True, default='')
    source_visit = models.ForeignKey('visits.Visit', on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    recorded_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')

    class Meta:
        abstract = True


class PatientAllergy(ClinicalPatientRecord):
    substance = models.CharField(max_length=200)
    reaction = models.CharField(max_length=500, blank=True, default='')
    severity = models.CharField(max_length=20, default='unknown', choices=AllergySeverity.choices)
    status = models.CharField(max_length=30, default='suspected', choices=AllergyStatus.choices)

    class Meta:
        constraints = [
            retirement_constraint('patients_patientallergy_retirement_valid'),
            check_constraint(condition=models.Q(severity__in=AllergySeverity.values), name='patients_patientallergy_severity_valid'),
            check_constraint(condition=models.Q(status__in=AllergyStatus.values), name='patients_patientallergy_status_valid'),
        ]


class PatientMedication(ClinicalPatientRecord):
    name = models.CharField(max_length=200)
    dosage = models.CharField(max_length=100, blank=True, default='')
    schedule = models.CharField(max_length=200, blank=True, default='')
    status = models.CharField(max_length=30, default='active', choices=MedicationStatus.choices)
    started_on = models.DateField(null=True, blank=True)
    ended_on = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            retirement_constraint('patients_patientmedication_retirement_valid'),
            check_constraint(condition=models.Q(status__in=MedicationStatus.values), name='patients_patientmedication_status_valid'),
            check_constraint(condition=Q(started_on__isnull=True) | Q(ended_on__isnull=True) | Q(ended_on__gte=models.F('started_on')), name='patient_medication_dates_valid'),
        ]


class PatientFollowUp(PatientRecord):
    METHOD_CHOICES = FollowUpMethod.choices
    title = models.CharField(max_length=200)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='patient_follow_ups')
    due_date = models.DateField()
    status = models.CharField(max_length=20, default='pending', choices=FollowUpStatus.choices)
    source_visit = models.ForeignKey('visits.Visit', on_delete=models.PROTECT, null=True, blank=True, related_name='follow_up_actions')
    appointment = models.ForeignKey('appointments.Appointment', on_delete=models.PROTECT, null=True, blank=True, related_name='follow_up_actions')
    completed_visit = models.ForeignKey('visits.Visit', on_delete=models.PROTECT, null=True, blank=True, related_name='completed_actions')
    completed_revision = models.ForeignKey('visits.VisitRevision', on_delete=models.PROTECT, null=True, blank=True, editable=False, related_name='completed_follow_ups')
    notes = models.TextField(blank=True, default='')
    outcome_reason = models.CharField(max_length=500, blank=True, default='')
    outcome_at = models.DateTimeField(null=True, blank=True, editable=False)
    outcome_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    method = models.CharField(max_length=30, blank=True, default='', choices=METHOD_CHOICES)

    class Meta:
        indexes = [models.Index(fields=['patient', 'status', 'due_date'])]
        constraints = [
            retirement_constraint('patients_patientfollowup_retirement_valid'),
            check_constraint(condition=models.Q(status__in=FollowUpStatus.values), name='patients_patientfollowup_status_valid'),
            check_constraint(condition=models.Q(method__in=[*FollowUpMethod.values, '']), name='patients_patientfollowup_method_valid'),
            check_constraint(condition=models.Q(completed_visit__isnull=True, completed_revision__isnull=True) | models.Q(status='completed', completed_visit__isnull=False, completed_revision__isnull=False), name='followup_revision_evidence_valid'),
            check_constraint(condition=Q(status='pending', outcome_at__isnull=True, outcome_by__isnull=True) | Q(status__in=['completed', 'missed', 'cancelled', 'waived'], outcome_at__isnull=False, outcome_by__isnull=False) & ~Q(outcome_reason=''), name='followup_completion_metadata'),
        ]


class PatientCorrection(ImmutableModel):
    patient = models.ForeignKey('patients.Patient', on_delete=models.PROTECT, related_name='corrections')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    reason = models.CharField(max_length=500)
    changes = models.JSONField()
    record_type = models.CharField(max_length=50, default='profile')
    record_id = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PatientDuplicateReview(TimeStampedModel):
    patient = models.ForeignKey('patients.Patient', on_delete=models.PROTECT, related_name='duplicate_reviews')
    other_patient = models.ForeignKey('patients.Patient', on_delete=models.PROTECT, related_name='+')
    status = models.CharField(max_length=20, default='dismissed', choices=DuplicateStatus.choices)
    reason = models.CharField(max_length=500, blank=True, default='')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')

    class Meta:
        constraints = [
            check_constraint(condition=models.Q(status__in=DuplicateStatus.values), name='patients_patientduplicatereview_status_valid'),
            models.UniqueConstraint(fields=['patient', 'other_patient'], name='unique_patient_duplicate_review'),
            check_constraint(condition=Q(patient__lt=models.F('other_patient')), name='ordered_duplicate_pair'),
        ]


class PatientMerge(ImmutableModel):
    source = models.ForeignKey('patients.Patient', on_delete=models.PROTECT, related_name='merge_events_as_source')
    survivor = models.ForeignKey('patients.Patient', on_delete=models.PROTECT, related_name='merge_events_as_survivor')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    reason = models.CharField(max_length=500)
    manifest = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            check_constraint(condition=~models.Q(source=models.F('survivor')), name='merge_distinct_patients'),
        ]
