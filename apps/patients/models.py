# backend/apps/patients/models.py
from django.db import models
from django.db.models import Q
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.utils import timezone
from core.models import TimeStampedModel, SoftDeleteModel
from core.normalization import normalize_identifier, normalize_name, normalize_phone, normalized_search_text


def current_year():
    return timezone.localdate().year

class Patient(SoftDeleteModel, TimeStampedModel):
    GENDER_CHOICES = [
        ('ذكر', 'ذكر'),
        ('أنثى', 'أنثى'),
    ]
    first_name = models.CharField(max_length=100)
    father_name = models.CharField(max_length=100, blank=True, null=True)
    surname = models.CharField(max_length=100)   # made required
    mother_name = models.CharField(max_length=100, blank=True, null=True)
    normalised_full_name = models.CharField(
        max_length=400,
        blank=True,
        null=True,
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
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    national_id = models.CharField(max_length=50, blank=True, null=True)  # removed unique=True
    marital_status = models.CharField(max_length=50, blank=True, null=True)
    occupation = models.CharField(max_length=100, blank=True, null=True)
    permanent_address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_relation = models.CharField(max_length=50, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True)
    family_history = models.TextField(blank=True, null=True)
    important_notes = models.TextField(blank=True, null=True)
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='patients',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_patients',
    )
    admission_date = models.DateField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        indexes = [
            models.Index(fields=['doctor', 'deleted_at']),
            models.Index(fields=['national_id']),
            models.Index(fields=['phone']),
            models.Index(fields=['admission_date']),
            models.Index(fields=['dob_year']),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(version__gte=1), name='patient_version_positive'),
            models.UniqueConstraint(
                fields=['national_id'],
                condition=Q(deleted_at__isnull=True, is_active=True),
                name='unique_active_national_id'
            ),
        ]

    def __str__(self):
        return f"{self.first_name} {self.surname or ''}".strip()

    def save(self, *args, **kwargs):
        for field in ('first_name', 'father_name', 'surname', 'mother_name'):
            value = getattr(self, field)
            setattr(self, field, normalize_name(value) if value else value)
        self.national_id = normalize_identifier(self.national_id)
        self.phone = normalize_phone(self.phone)
        self.emergency_contact_phone = normalize_phone(self.emergency_contact_phone)
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

    def get_completeness(self):
        recommended = {
            'dob_year': self.dob_year,
            'gender': self.gender,
            'national_id': self.national_id,
            'phone': self.phone,
            'doctor': self.doctor_id,
            'admission_date': self.admission_date,
        }
        missing = [field for field, value in recommended.items() if not value]
        return {
            'complete': not missing,
            'missing_fields': missing,
            'percent': round((len(recommended) - len(missing)) / len(recommended) * 100),
        }


class PatientDocument(SoftDeleteModel, TimeStampedModel):
    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name='documents',
    )
    filename = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    filepath = models.CharField(max_length=500)
    file_size = models.PositiveBigIntegerField(null=True, blank=True)
    checksum = models.CharField(max_length=64, blank=True, editable=False)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    category = models.CharField(max_length=50, blank=True, null=True)
    description = models.CharField(max_length=200, blank=True, null=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_patient_documents',
    )

    def __str__(self):
        return self.original_filename


class PatientCareTeam(TimeStampedModel):
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
    role = models.CharField(max_length=50)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['patient', 'user'],
                name='unique_patient_care_team_member',
            ),
        ]
        indexes = [models.Index(fields=['user'])]

    def __str__(self):
        return f"{self.patient} - {self.user} ({self.role})"
