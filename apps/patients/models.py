from core.constraints import archive_constraint, check_constraint, verification_constraint
from .choices import Gender, SummaryStatus, ContactChannel
# backend/apps/patients/models.py
from django.db import models
from django.db.models import Q
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone
from core.models import TimeStampedModel, SoftDeleteModel, StoredFileMetadata
from .record_models import VERIFICATION, CARE_ROLES, MARITAL_STATUSES
from .querysets import CareTeamQuerySet
import uuid
from core.normalization import normalized_search_text


def patient_number():
    return "P-" + uuid.uuid4().hex[:16].upper()

def current_year():
    return timezone.localdate().year

class Patient(SoftDeleteModel, TimeStampedModel):
    GENDER_CHOICES = Gender.choices
    patient_number = models.CharField(max_length=18, unique=True, default=patient_number, editable=False)
    identity_verification = models.CharField(max_length=20, choices=VERIFICATION, default='reported')
    identity_verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    identity_verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    preferred_language = models.CharField(max_length=30, blank=True, default='')
    preferred_contact_channel = models.CharField(max_length=20, blank=True, default='', choices=[('', 'Unspecified'), *ContactChannel.choices])
    communication_restrictions = models.TextField(blank=True, default='')
    allergy_status = models.CharField(max_length=20, default='unknown', choices=SummaryStatus.choices)
    medication_status = models.CharField(max_length=20, default='unknown', choices=SummaryStatus.choices)
    merged_into = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='merged_records', editable=False)
    first_name = models.CharField(max_length=100)
    father_name = models.CharField(max_length=100, blank=True, default='')
    surname = models.CharField(max_length=100)   # made required
    mother_name = models.CharField(max_length=100, blank=True, default='')
    normalised_full_name = models.CharField(
        max_length=400,
        blank=True,
        default='',
        db_index=True,
        editable=False,
    )
    # Unknown dates must remain unknown. A fabricated default year makes an
    # incomplete clinical identity look complete and produces a false age.
    dob_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1900), MaxValueValidator(current_year)],
    )
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, default='')
    primary_identifier = models.OneToOneField('patients.PatientIdentifier', on_delete=models.PROTECT, null=True, blank=True, editable=False, related_name='+')
    marital_status = models.CharField(max_length=50, choices=MARITAL_STATUSES, blank=True, default='')
    occupation = models.CharField(max_length=100, blank=True, default='')
    permanent_address = models.TextField(blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    family_history = models.TextField(blank=True, default='')
    important_notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_patients',
    )
    registration_date = models.DateField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['registration_date']),
            models.Index(fields=['dob_year']),
        ]
        constraints = [
            archive_constraint('patients_patient_archive_valid'),
            verification_constraint('patients_patient_verification_valid', 'identity_'),
            check_constraint(condition=models.Q(identity_verification__in=[item[0] for item in VERIFICATION]), name='patients_patient_identity_verification_valid'),
            check_constraint(condition=models.Q(preferred_contact_channel__in=[*ContactChannel.values, '']), name='patients_patient_preferred_contact_channel_valid'),
            check_constraint(condition=models.Q(allergy_status__in=SummaryStatus.values), name='patients_patient_allergy_status_valid'),
            check_constraint(condition=models.Q(medication_status__in=SummaryStatus.values), name='patients_patient_medication_status_valid'),
            check_constraint(condition=models.Q(gender__in=[*Gender.values, '']), name='patients_patient_gender_valid'),
            check_constraint(condition=models.Q(marital_status__in=[*[item[0] for item in MARITAL_STATUSES], '']), name='patients_patient_marital_status_valid'),
            check_constraint(condition=models.Q(version__gte=1), name='patient_version_positive'),
        ]

    def __str__(self):
        return f"{self.first_name} {self.surname or ''}".strip()

    def save(self, *args, **kwargs):
        self.__dict__.pop('_summary_team', None)
        self.__dict__.pop('_summary_contacts', None)
        if self.pk and not self._state.adding:
            original = type(self).all_objects.filter(pk=self.pk).values_list('patient_number', flat=True).first()
            if original and original != self.patient_number:
                from django.core.exceptions import ValidationError
                raise ValidationError('رقم الملف دائم ولا يمكن تغييره')
        from .validation import IDENTITY_FIELDS, normalize_identity_data
        fields = (*IDENTITY_FIELDS, 'phone')
        for field, value in normalize_identity_data({field: getattr(self, field) for field in fields}).items():
            setattr(self, field, value)
        self.normalised_full_name = normalized_search_text(self.get_full_name())
        update_fields = kwargs.get('update_fields')
        if update_fields is not None and set(update_fields) & {'first_name', 'father_name', 'surname'}:
            kwargs['update_fields'] = set(update_fields) | {'normalised_full_name'}
        super().save(*args, **kwargs)

    def get_full_name(self):
        parts = [self.first_name]
        if self.father_name:
            parts.append(self.father_name)
        if self.surname:
            parts.append(self.surname)
        return " ".join(parts)

    @property
    def national_id(self):
        row = self.primary_identifier if self.primary_identifier_id else None
        return row.value if row and row.is_active else ''

    def _emergency_contact(self):
        if hasattr(self, '_summary_contacts'):
            return next(iter(self._summary_contacts), None)
        return self.patientcontact_records.filter(is_active=True, is_primary=True, is_emergency=True).first() if self.pk else None

    @property
    def emergency_contact_name(self):
        row = self._emergency_contact()
        return row.name if row else ''

    @property
    def emergency_contact_relation(self):
        row = self._emergency_contact()
        return row.relationship if row else ''

    @property
    def emergency_contact_phone(self):
        row = self._emergency_contact()
        return row.phone if row else ''

    @property
    def doctor(self):
        if hasattr(self, '_summary_team'):
            member = next((row for row in self._summary_team if row.role == 'doctor'), None)
            return member.user if member else None
        member = self.care_team.effective_at().filter(role='doctor').select_related('user').order_by('started_at', 'pk').first() if self.pk else None
        return member.user if member else None

    def refresh_from_db(self, *args, **kwargs):
        self.__dict__.pop('_summary_team', None)
        self.__dict__.pop('_summary_contacts', None)
        return super().refresh_from_db(*args, **kwargs)

    @property
    def doctor_id(self):
        doctor = self.doctor
        return doctor.pk if doctor else None

    # Compatibility aliases for previously issued templates/API consumers.
    @property
    def admission_date(self):
        return self.registration_date

    @admission_date.setter
    def admission_date(self, value):
        self.registration_date = value

    def get_completeness(self):
        from .completeness import completeness
        return completeness(self)


class PatientDocument(SoftDeleteModel, TimeStampedModel, StoredFileMetadata):
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name='documents',
    )
    document_date = models.DateField(null=True, blank=True)
    source = models.CharField(max_length=200, blank=True, default='')
    provider = models.CharField(max_length=200, blank=True, default='')
    verification = models.CharField(max_length=20, choices=VERIFICATION, default='unknown')
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    category = models.CharField(max_length=50, blank=True, default='')
    description = models.CharField(max_length=200, blank=True, default='')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_patient_documents',
    )

    def __str__(self):
        return self.original_filename

    class Meta:
        constraints = [
            archive_constraint('patients_patientdocument_archive_valid'),
            verification_constraint('patients_patientdocument_verification_valid', ''),
            check_constraint(condition=models.Q(verification__in=[item[0] for item in VERIFICATION]), name='patients_patientdocument_verification_valid'),
        ]


class PatientCareTeam(TimeStampedModel):
    objects = CareTeamQuerySet.as_manager()

    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name='care_team',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='care_teams',
    )
    role = models.CharField(max_length=50, choices=CARE_ROLES)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    ended_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    removal_reason = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        constraints = [
            check_constraint(condition=Q(ended_at__isnull=True, ended_by__isnull=True, removal_reason='') | Q(ended_at__isnull=False) & ~Q(removal_reason=''), name='care_team_end_metadata_valid'),
            check_constraint(condition=models.Q(role__in=[item[0] for item in CARE_ROLES]), name='patients_patientcareteam_role_valid'),
            models.UniqueConstraint(fields=['patient', 'user'], condition=Q(ended_at__isnull=True), name='unique_active_care_team_member'),
            check_constraint(condition=Q(ended_at__isnull=True) | Q(ended_at__gte=models.F('started_at')), name='care_team_dates_valid'),
        ]

    def __str__(self):
        return f"{self.patient} - {self.user} ({self.role})"

# Registered with Django through the app's models module; no migrations generated.
from .record_models import (PatientIdentifier, PatientContact, PatientRepresentative, PatientAllergy,
    PatientMedication, PatientFollowUp, PatientCorrection, PatientDuplicateReview, PatientMerge)
