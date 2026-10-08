# backend/apps/visits/models.py
from django.db import models, transaction
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from core.models import TimeStampedModel, SoftDeleteModel, ImmutableModel

class Visit(SoftDeleteModel, TimeStampedModel):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('final', 'Final'),
        ('amended', 'Amended'),
        ('locked', 'Locked'),
    ]
    ACCOMPANIED_BY_CHOICES = [
        ('alone', 'Alone'),
        ('companion', 'With companion'),
    ]
    RISK_LEVEL_CHOICES = [
        ('Low', 'Low'),
        ('Moderate', 'Moderate'),
        ('High', 'High'),
    ]
    LEVEL_OF_CARE_CHOICES = [
        ('Outpatient', 'Outpatient'),
        ('IOP', 'IOP'),
        ('PHP', 'PHP'),
        ('Inpatient', 'Inpatient'),
        ('Residential', 'Residential'),
    ]
    FOLLOW_UP_TYPE_CHOICES = [
        ('In-person', 'In-person'),
        ('Telehealth', 'Telehealth'),
        ('Phone', 'Phone'),
    ]
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
    follow_up_date = models.DateField(null=True, blank=True)
    follow_up_completed = models.BooleanField(default=False)
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
    care_basis = models.CharField(max_length=20, default='unknown', choices=[('unknown', 'Unknown'), ('voluntary', 'Voluntary'), ('involuntary', 'Involuntary')])
    level_of_care = models.CharField(
        max_length=50,
        choices=LEVEL_OF_CARE_CHOICES,
        blank=True,
        default='',
    )
    follow_up_type = models.CharField(
        max_length=30,
        choices=FOLLOW_UP_TYPE_CHOICES,
        blank=True,
        default='',
    )
    signed_at = models.DateTimeField(null=True, blank=True, editable=False)
    amendment_reason = models.CharField(max_length=500, blank=True, default='')
    follow_up_outcome = models.CharField(max_length=20, default='pending', choices=[
        ('pending', 'Pending'), ('completed', 'Completed'), ('missed', 'Missed'),
        ('cancelled', 'Cancelled'), ('waived', 'Waived'),
    ])
    follow_up_completed_at = models.DateTimeField(null=True, blank=True)
    follow_up_completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='completed_follow_ups')
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
    version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
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
            models.Index(fields=['follow_up_date']),
            models.Index(fields=['deleted_at']),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(version__gte=1, status__in=['draft', 'final', 'amended', 'locked']), name='visit_version_status_valid'),
            models.CheckConstraint(
                check=(
                    models.Q(pain_level__isnull=True)
                    | models.Q(pain_level__gte=0, pain_level__lte=10)
                ),
                name='visit_pain_level_valid',
            ),
            models.CheckConstraint(
                check=(
                    models.Q(anxiety_level__isnull=True)
                    | models.Q(anxiety_level__gte=0, anxiety_level__lte=10)
                ),
                name='visit_anxiety_level_valid',
            ),
            models.CheckConstraint(
                check=(
                    models.Q(follow_up_date__isnull=True)
                    | models.Q(follow_up_date__gte=models.F('visit_date'))
                ),
                name='visit_follow_up_not_before_visit',
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
        diagnoses_list = normalize_rows(diagnoses_list, 'diagnoses', self)
        self.visit_diagnoses.all().delete()
        for idx, d in enumerate(diagnoses_list):
            diagnosis_id = d.get('id') if d.get('id') else None
            self.visit_diagnoses.create(
                visit=self,
                diagnosis_id=diagnosis_id,
                custom_code=d.get('code', ''),
                custom_name=d.get('name', ''),
                custom_arabic=d.get('arabic_name', ''),
                order=idx,
            )

    @transaction.atomic
    def set_medications(self, medications_list):
        from .input_validation import normalize_rows
        medications_list = normalize_rows(medications_list, 'medications', self)
        self.visit_medications.all().delete()
        for idx, m in enumerate(medications_list):
            medication_id = m.get('id') if m.get('id') else None
            is_custom = m.get('is_custom', False)
            self.visit_medications.create(
                visit=self,
                medication_id=medication_id,
                custom_name=m.get('name', ''),
                custom_dosage=m.get('dosage', ''),
                custom_brand=m.get('brand', ''),
                is_custom=is_custom,
                controlled_snapshot=m['controlled'],
                schedule=m.get('schedule', ''),
                order=idx,
            )

    def get_lab_values(self):
        return self.lab_values

    def set_lab_values(self, lab_list):
        """
        Persist lab values immediately.

        Previous implementation only assigned the in-memory attribute and
        relied on a later caller to save. But every caller in the codebase
        (VisitService.create_visit/update_visit, VisitSerializer.create/update)
        calls visit.save() *before* this method runs, and nothing saves
        afterwards — so lab values entered through the UI were accepted,
        returned 200/201, and silently discarded. Match the sibling
        set_diagnoses / set_medications behaviour and persist here.

        The pk guard keeps this safe if called on an unsaved instance
        (save(update_fields=...) would raise on a row with no primary key).
        """
        from .lab_validation import normalize_lab_values
        self.lab_values = normalize_lab_values(lab_list)
        if self.pk is not None:
            self.save(update_fields=['lab_values'])

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

class VisitAttachment(SoftDeleteModel, TimeStampedModel):
    visit = models.ForeignKey(
        Visit,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    filename = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    filepath = models.CharField(max_length=500)
    file_size = models.PositiveBigIntegerField(null=True, blank=True)
    checksum = models.CharField(max_length=64, blank=True, editable=False)
    mime_type = models.CharField(max_length=100, blank=True, default='')
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

