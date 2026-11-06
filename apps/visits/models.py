from .choices import VisitStatus, RiskLevel, LevelOfCare, CareBasis, AccompaniedBy
# backend/apps/visits/models.py
from django.db import models, transaction
from core.constraints import check_constraint
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from core.models import TimeStampedModel, SoftDeleteModel, StoredFileMetadata, ImmutableModel

class Visit(SoftDeleteModel, TimeStampedModel):
    STATUS_CHOICES = VisitStatus.choices
    ACCOMPANIED_BY_CHOICES = AccompaniedBy.choices
    RISK_LEVEL_CHOICES = RiskLevel.choices
    LEVEL_OF_CARE_CHOICES = LevelOfCare.choices
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.PROTECT,
        related_name='visits',
    )
    visit_date = models.DateField()
    main_complaints = models.TextField(blank=True, default='')
    history_presenting_complaint = models.TextField(blank=True, default='')
    treatment_text = models.TextField(blank=True, default='')
    doctor_notes = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    status_reason = models.CharField(max_length=500, blank=True, default='')
    clinical_status = models.CharField(max_length=100, blank=True, default='')
    accompanied_by = models.CharField(
        max_length=20,
        choices=ACCOMPANIED_BY_CHOICES,
        blank=True,
        default='',
    )
    companion_relation = models.CharField(max_length=100, blank=True, default='')
    follow_up = models.OneToOneField('patients.PatientFollowUp', on_delete=models.PROTECT,
        null=True, blank=True, editable=False, related_name='planned_visit')
    pain_level = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    anxiety_level = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
    )
    suicide_risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        blank=True,
        default='',
    )
    violence_risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES,
        blank=True,
        default='',
    )
    firearm_access = models.BooleanField(null=True, blank=True, default=None)
    care_basis = models.CharField(max_length=20, default='unknown', choices=CareBasis.choices)
    level_of_care = models.CharField(
        max_length=50,
        choices=LEVEL_OF_CARE_CHOICES,
        blank=True,
        default='',
    )
    signed_at = models.DateTimeField(null=True, blank=True, editable=False)
    amendment_reason = models.CharField(max_length=500, blank=True, default='')
    date_signed = models.DateField(null=True, blank=True)
    signed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='signed_visits',
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='supervised_visits',
    )
    diagnosis_discussed = models.BooleanField(null=True, blank=True, default=None)
    plan_discussed = models.BooleanField(null=True, blank=True, default=None)
    clinical_data = models.JSONField(default=dict, blank=True)
    lab_values = models.JSONField(default=list, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='authored_visits',
    )

    class Meta:
        indexes = [
            models.Index(fields=['patient', 'visit_date']),
            models.Index(fields=['status', '-visit_date']),
            models.Index(fields=['deleted_at']),
        ]
        constraints = [
            check_constraint(condition=models.Q(version__gte=1, status__in=['draft', 'final', 'amended', 'locked']), name='visit_version_status_valid'),
            check_constraint(
                condition=(
                    models.Q(pain_level__isnull=True)
                    | models.Q(pain_level__gte=0, pain_level__lte=10)
                ),
                name='visit_pain_level_valid',
            ),
            check_constraint(
                condition=(
                    models.Q(anxiety_level__isnull=True)
                    | models.Q(anxiety_level__gte=0, anxiety_level__lte=10)
                ),
                name='visit_anxiety_level_valid',
            ),
        ]

    def __str__(self):
        return f"Visit {self.id} for {self.patient} on {self.visit_date}"

    def get_diagnoses(self):
        return [{'id': row.diagnosis_id, 'code': row.custom_code, 'name': row.custom_name,
                 'arabic_name': row.custom_arabic} for row in self.visit_diagnoses.all()]

    def get_medications(self):
        return [{'id': row.medication_id, 'name': row.custom_name, 'dosage': row.custom_dosage,
                 'brand': row.custom_brand, 'is_custom': row.is_custom, 'schedule': row.schedule,
                 'controlled': row.controlled_snapshot} for row in self.visit_medications.all()]

    @transaction.atomic
    def set_diagnoses(self, diagnoses_list):
        from .input_validation import normalize_rows
        from .nested import replace_diagnoses
        return replace_diagnoses(self, normalize_rows(diagnoses_list, 'diagnoses', self))

    @transaction.atomic
    def set_medications(self, medications_list):
        from .input_validation import normalize_rows
        from .nested import replace_medications
        return replace_medications(self, normalize_rows(medications_list, 'medications', self))

    def get_lab_values(self):
        return self.lab_values

    def set_lab_values(self, lab_list):
        from .lab_validation import normalize_lab_values
        from .nested import replace_lab_values
        return replace_lab_values(self, normalize_lab_values(lab_list))


class VisitDiagnosis(models.Model):
    visit = models.ForeignKey(
        Visit,
        on_delete=models.CASCADE,
        related_name='visit_diagnoses',
    )
    diagnosis = models.ForeignKey(
        'clinical.DiagnosisOption',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    custom_code = models.CharField(max_length=50, blank=True)
    custom_name = models.CharField(max_length=200, blank=True)
    custom_arabic = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

class VisitMedication(models.Model):
    visit = models.ForeignKey(
        Visit,
        on_delete=models.CASCADE,
        related_name='visit_medications',
    )
    medication = models.ForeignKey(
        'clinical.MedicationOption',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    custom_name = models.CharField(max_length=200, blank=True)
    custom_dosage = models.CharField(max_length=100, blank=True)
    custom_brand = models.CharField(max_length=200, blank=True)
    controlled_snapshot = models.BooleanField(default=False)
    is_custom = models.BooleanField(default=False)
    schedule = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

class VisitAttachment(SoftDeleteModel, TimeStampedModel, StoredFileMetadata):
    visit = models.ForeignKey(
        Visit,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_visit_attachments',
    )

class VisitScaleResponse(models.Model):
    visit = models.ForeignKey(
        Visit,
        on_delete=models.CASCADE,
        related_name='scale_responses',
    )
    # Keep the identifier as an immutable snapshot rather than a foreign key;
    # historical responses must survive retirement of a scale definition.
    scale_id = models.PositiveBigIntegerField()
    scale_name_snapshot = models.CharField(max_length=200, blank=True)
    responses_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['visit', 'scale_id'],
                name='unique_visit_scale_response',
            ),
        ]


class VisitRevision(ImmutableModel):
    visit = models.ForeignKey(Visit, on_delete=models.PROTECT, related_name='revisions')
    number = models.PositiveIntegerField()
    snapshot = models.JSONField()
    signer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='visit_revisions')
    signed_at = models.DateTimeField()
    reason = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['number']
        constraints = [models.UniqueConstraint(fields=['visit', 'number'], name='unique_visit_revision')]

