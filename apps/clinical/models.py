import math
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower, Trim
from django.core.validators import MinValueValidator
from core.models import SoftDeleteModel, TimeStampedModel

class DiagnosisOption(SoftDeleteModel):
    code = models.CharField(max_length=50, unique=True)
    english_name = models.CharField(max_length=200)
    arabic_name = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.CheckConstraint(check=models.Q(version__gte=1), name='diagnosisoption_version_positive')]
        ordering = ['order', 'code', 'id']

    def __str__(self):
        return f"{self.code} - {self.english_name}"


class MedicationOption(SoftDeleteModel):
    generic_english = models.CharField(max_length=200)
    generic_arabic = models.CharField(max_length=200, blank=True, default='')
    dosage = models.CharField(max_length=100, blank=True, default='')
    brand_english = models.CharField(max_length=200, blank=True, default='')
    brand_arabic = models.CharField(max_length=200, blank=True, default='')
    order = models.PositiveIntegerField(default=0)
    is_controlled = models.BooleanField(default=False)   # NEW FIELD

    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(version__gte=1), name='medicationoption_version_positive'),
            models.UniqueConstraint(Lower(Trim('generic_english')), Lower(Trim('dosage')), Lower(Trim('brand_english')), name='medication_identity_unique'),
        ]
        ordering = ['order', 'generic_english', 'id']

    def display_name(self):
        parts = []
        if self.generic_arabic:
            parts.append(self.generic_arabic)
        elif self.generic_english:
            parts.append(self.generic_english)
        if self.dosage:
            parts.append(f"({self.dosage})")
        if self.brand_arabic:
            parts.append(f"- {self.brand_arabic}")
        elif self.brand_english:
            parts.append(f"- {self.brand_english}")
        return " ".join(parts) if parts else self.generic_english

    def __str__(self):
        return self.generic_english


class ClinicalScale(SoftDeleteModel, TimeStampedModel):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)

    class Meta:
        constraints = [models.CheckConstraint(check=models.Q(version__gte=1), name='clinicalscale_version_positive')]
        ordering = ['name', 'id']

    def __str__(self):
        return self.name


class ScaleField(SoftDeleteModel, TimeStampedModel):
    FIELD_TYPE_CHOICES = [
        ('slider', 'Slider'),
        ('text', 'Text'),
    ]
    scale = models.ForeignKey(
        ClinicalScale,
        on_delete=models.CASCADE,
        related_name='fields'
    )
    label = models.CharField(max_length=200)
    field_type = models.CharField(
        max_length=20,
        choices=FIELD_TYPE_CHOICES,
        default='slider',
    )
    min_val = models.FloatField(default=0)
    max_val = models.FloatField(default=10)
    step = models.FloatField(default=1, validators=[MinValueValidator(0.000001)])
    default = models.FloatField(default=0)
    options = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    def clean(self):
        super().clean()
        values = (self.min_val, self.max_val, self.step, self.default)
        if (any(type(value) not in (int, float) or not math.isfinite(value) for value in values)
                or not math.isfinite(self.max_val - self.min_val)):
            raise ValidationError({'min_val': ['تعريف المقياس يتطلب أرقاماً ونطاقاً محدودين']})
        if self.max_val <= self.min_val or not 0 < self.step <= self.max_val - self.min_val:
            raise ValidationError({'step': ['نطاق أو خطوة المقياس غير صالحة']})
        if not self.min_val <= self.default <= self.max_val:
            raise ValidationError({'default': ['القيمة الافتراضية خارج النطاق']})
        if self.field_type == 'slider':
            increments = (self.default - self.min_val) / self.step
            if not math.isfinite(increments) or not math.isclose(increments, round(increments), abs_tol=1e-7):
                raise ValidationError({'default': ['القيمة الافتراضية لا تطابق الخطوة']})

    class Meta:
        ordering = ['order', 'id']
        constraints = [
            models.CheckConstraint(check=models.Q(version__gte=1), name='scalefield_version_positive'),
            models.CheckConstraint(
                check=models.Q(max_val__gt=models.F('min_val')),
                name='scale_field_range_valid',
            ),
            models.CheckConstraint(
                check=models.Q(step__gt=0),
                name='scale_field_step_positive',
            ),
            models.CheckConstraint(
                check=models.Q(step__lte=models.F('max_val') - models.F('min_val')),
                name='scale_field_step_within_range',
            ),
            models.CheckConstraint(
                check=(
                    models.Q(default__gte=models.F('min_val'))
                    & models.Q(default__lte=models.F('max_val'))
                ),
                name='scale_field_default_in_range',
            ),
        ]


class ClinicalNoteTemplate(SoftDeleteModel, TimeStampedModel):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=50)
    content = models.JSONField(default=dict)

    def __str__(self):
        return self.name
