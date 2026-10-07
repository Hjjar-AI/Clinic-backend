from django.core.exceptions import ValidationError
from django.db import transaction
from core.mutation import check_mutation
from core.exceptions import ConflictError
from .models import DiagnosisOption, MedicationOption, ClinicalScale, ScaleField, ClinicalNoteTemplate


def _validate(instance):
    if isinstance(instance, MedicationOption):
        for key in ('generic_english','generic_arabic','dosage','brand_english','brand_arabic'):
            value = getattr(instance, key)
            if value is not None and not isinstance(value, str):
                raise ValidationError({key: ['يلزم نص']})
            setattr(instance, key, (value or '').strip())
    instance.full_clean()
    if isinstance(instance, MedicationOption):
        duplicate = MedicationOption.all_objects.filter(
            generic_english__iexact=instance.generic_english.strip(),
            dosage__iexact=instance.dosage or '', brand_english__iexact=instance.brand_english or '')
        if duplicate.exclude(pk=instance.pk).exists():
            raise ValidationError({'generic_english': ['الدواء موجود؛ أعد تفعيله إن كان متقاعداً']})


@transaction.atomic
def create_catalog(model, data):
    data = data.copy()
    data.pop('version', None)
    data.pop('is_active', None)
    instance = model(**data)
    _validate(instance)
    instance.save()
    return instance


@transaction.atomic
def update_catalog(model, pk, data, expected_version=None):
    data = data.copy()
    expected_version = data.pop('version', expected_version)
    instance = model.all_objects.select_for_update().get(pk=pk)
    check_mutation(instance, expected_version)
    allowed = {f.name for f in model._meta.concrete_fields} - {'id','created_at','updated_at','version','is_active','deleted_at','archived_by','archive_reason'}
    for key, value in data.items():
        if key not in allowed:
            raise ValidationError({key: ['حقل غير قابل للتعديل']})
        setattr(instance, key, value)
    _validate(instance)
    instance.version += 1
    instance.save()
    return instance


@transaction.atomic
def archive_catalog(model, pk, version):
    instance = model.all_objects.select_for_update().get(pk=pk)
    check_mutation(instance, version)
    instance.soft_delete()
    return True


@transaction.atomic
def restore_catalog(instance, version):
    instance = instance.__class__.all_objects.select_for_update().get(pk=instance.pk)
    if type(version) is not int or instance.version != version:
        raise ConflictError('تغير السجل؛ أعد تحميله')
    if not instance.is_active or instance.deleted_at:
        instance.restore()
    return instance


class DiagnosisService:
    def create_diagnosis(self, **data):
        return create_catalog(DiagnosisOption, data)
    def update_diagnosis(self, diag_id, expected_version=None, **data):
        return update_catalog(DiagnosisOption, diag_id, data, expected_version)
    def soft_delete(self, diag_id, expected_version=None):
        return archive_catalog(DiagnosisOption, diag_id, expected_version)

class MedicationService:
    def create_medication(self, **data):
        return create_catalog(MedicationOption, data)
    def update_medication(self, med_id, expected_version=None, **data):
        return update_catalog(MedicationOption, med_id, data, expected_version)
    def soft_delete(self, med_id, expected_version=None):
        return archive_catalog(MedicationOption, med_id, expected_version)

class ScaleService:
    @transaction.atomic
    def add_field(self, scale, data, expected_version=None):
        scale = ClinicalScale.all_objects.select_for_update().get(pk=scale.pk)
        check_mutation(scale, expected_version)
        field = ScaleField(scale=scale, **data)
        field.full_clean()
        field.save()
        scale.version += 1
        scale.save(update_fields=['version', 'updated_at'])
        return field
    def delete_scale(self, scale_id, expected_version=None):
        return archive_catalog(ClinicalScale, scale_id, expected_version)

class TemplateService:
    def create_template(self, data):
        return create_catalog(ClinicalNoteTemplate, data)
    def update_template(self, template_id, data, expected_version=None):
        return update_catalog(ClinicalNoteTemplate, template_id, data, expected_version)
    def delete_template(self, template_id, expected_version=None):
        return archive_catalog(ClinicalNoteTemplate, template_id, expected_version)
