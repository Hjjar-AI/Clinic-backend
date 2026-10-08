"""Longitudinal patient records; encounter facts stay on visits/signed snapshots."""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.core.validators import RegexValidator
from core.models import TimeStampedModel, ImmutableModel

VERIFICATION = [('unknown', 'Unknown'), ('reported', 'Reported'), ('verified', 'Document verified')]
CARE_ROLES = [(value, value.replace('_', ' ').title()) for value in
              ('doctor', 'nurse', 'therapist', 'assistant', 'coordinator')]
MARITAL_STATUSES = [(value, value) for value in ('أعزب', 'عزباء', 'متزوج', 'متزوجة', 'مطلق', 'مطلقة', 'أرمل', 'أرملة')]


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
    identifier_type = models.CharField(max_length=30, choices=[('national_id', 'National ID'), ('passport', 'Passport'), ('other', 'Other')])
    value = models.CharField(max_length=100)
    issuer = models.CharField(max_length=100, blank=True, default='')
    issuing_country = models.CharField(max_length=2, blank=True, default='', validators=[RegexValidator(r'^[A-Z]{2}$', 'Use a two-letter country code')])
    verification = models.CharField(max_length=20, choices=VERIFICATION, default='reported')
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        indexes = [models.Index(fields=['identifier_type', 'value'])]
        constraints = [models.UniqueConstraint(fields=['patient', 'identifier_type', 'value', 'issuer', 'issuing_country'],
                       condition=Q(is_active=True), name='unique_patient_identifier')]


class PatientContact(PatientRecord):
    name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=100, blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    is_emergency = models.BooleanField(default=False)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default='')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['patient'], condition=Q(is_active=True, is_primary=True),
                                              name='one_primary_patient_contact')]


class PatientRepresentative(PatientRecord):
    name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True, default='')
    authority_scope = models.CharField(max_length=30, choices=[('contact', 'Contact'), ('records', 'Record access'),
        ('decisions', 'Decisions'), ('records_and_decisions', 'Records and decisions')])
    verification = models.CharField(max_length=20, choices=VERIFICATION, default='unknown')
    evidence = models.CharField(max_length=500, blank=True, default='')
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        constraints = [models.CheckConstraint(check=Q(valid_from__isnull=True) | Q(valid_until__isnull=True) |
                       Q(valid_until__gte=models.F('valid_from')), name='representative_dates_valid')]


class ClinicalPatientRecord(PatientRecord):
    source = models.CharField(max_length=30, choices=[('patient', 'Patient'), ('contact', 'Contact'),
        ('clinician', 'Clinician'), ('document', 'Document'), ('other', 'Other')], default='patient')
    source_details = models.CharField(max_length=500, blank=True, default='')
    source_visit = models.ForeignKey('visits.Visit', on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    recorded_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')

    class Meta:
        abstract = True


class PatientAllergy(ClinicalPatientRecord):
    substance = models.CharField(max_length=200)
    reaction = models.CharField(max_length=500, blank=True, default='')
    severity = models.CharField(max_length=20, default='unknown', choices=[('unknown', 'Unknown'),
        ('mild', 'Mild'), ('moderate', 'Moderate'), ('severe', 'Severe')])
    status = models.CharField(max_length=30, default='suspected', choices=[('suspected', 'Suspected'),
        ('confirmed', 'Confirmed'), ('refuted', 'Refuted'), ('resolved', 'Resolved'), ('entered_in_error', 'Entered in error')])


class PatientMedication(ClinicalPatientRecord):
    name = models.CharField(max_length=200)
    dosage = models.CharField(max_length=100, blank=True, default='')
    schedule = models.CharField(max_length=200, blank=True, default='')
    status = models.CharField(max_length=30, default='active', choices=[('active', 'Active'), ('on_hold', 'On hold'),
        ('stopped', 'Stopped'), ('entered_in_error', 'Entered in error')])
    started_on = models.DateField(null=True, blank=True)
    ended_on = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(check=Q(started_on__isnull=True) | Q(ended_on__isnull=True) |
                       Q(ended_on__gte=models.F('started_on')), name='patient_medication_dates_valid')]


class PatientFollowUp(PatientRecord):
    title = models.CharField(max_length=200)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='patient_follow_ups')
    due_date = models.DateField()
    status = models.CharField(max_length=20, default='pending', choices=[('pending', 'Pending'), ('completed', 'Completed'),
        ('missed', 'Missed'), ('cancelled', 'Cancelled'), ('waived', 'Waived')])
    source_visit = models.ForeignKey('visits.Visit', on_delete=models.PROTECT, null=True, blank=True, related_name='follow_up_actions')
    appointment = models.ForeignKey('appointments.Appointment', on_delete=models.PROTECT, null=True, blank=True, related_name='follow_up_actions')
    completed_visit = models.ForeignKey('visits.Visit', on_delete=models.PROTECT, null=True, blank=True, related_name='completed_actions')
    notes = models.TextField(blank=True, default='')
    outcome_reason = models.CharField(max_length=500, blank=True, default='')
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    legacy_visit_follow_up = models.BooleanField(default=False, editable=False)

    class Meta:
        indexes = [models.Index(fields=['patient', 'status', 'due_date'])]
        constraints = [models.UniqueConstraint(fields=['source_visit'], condition=Q(legacy_visit_follow_up=True, is_active=True),
                       name='one_legacy_followup_per_visit'), models.CheckConstraint(
                       check=~Q(status='completed') | Q(completed_at__isnull=False, completed_by__isnull=False),
                       name='followup_completion_metadata')]


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
    status = models.CharField(max_length=20, default='dismissed', choices=[('dismissed', 'Review later'), ('different', 'Different people'), ('merged', 'Merged')])
    reason = models.CharField(max_length=500, blank=True, default='')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['patient', 'other_patient'], name='unique_patient_duplicate_review'),
                       models.CheckConstraint(check=Q(patient__lt=models.F('other_patient')), name='ordered_duplicate_pair')]


class PatientMerge(ImmutableModel):
    source = models.ForeignKey('patients.Patient', on_delete=models.PROTECT, related_name='merge_events_as_source')
    survivor = models.ForeignKey('patients.Patient', on_delete=models.PROTECT, related_name='merge_events_as_survivor')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    reason = models.CharField(max_length=500)
    manifest = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
