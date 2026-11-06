from core.access import require_actor_permission
from core.operation_gate import gated
from django.core.exceptions import ValidationError
from django.db import transaction
from core.mutation import check_mutation
from core.exceptions import ConflictError
from .models import DiagnosisOption, MedicationOption, ClinicalScale, ScaleField, ClinicalNoteTemplate
from .identity import MEDICATION_TEXT_FIELDS, MEDICATION_IDENTITY_FIELDS, catalog_identity_lookup


def validate_catalog(instance):
    if isinstance(instance, MedicationOption):
        for key in MEDICATION_TEXT_FIELDS:
            value = getattr(instance, key)
            if value is not None and not isinstance(value, str):
                raise ValidationError({key: ['يلزم نص']})
            setattr(instance, key, (value or '').strip())
    instance.full_clean()
    if isinstance(instance, MedicationOption):
        duplicate = catalog_identity_lookup(MedicationOption.all_objects.all(),
            {field: getattr(instance, field) for field in MEDICATION_IDENTITY_FIELDS})
        if duplicate.exclude(pk=instance.pk).exists():
            raise ValidationError({'generic_english': ['الدواء موجود؛ أعد تفعيله إن كان متقاعداً']})


@gated(exclusive=True)
@transaction.atomic
def create_catalog(model, data, *, actor):
    require_actor_permission(actor, 'manage_templates' if model is ClinicalNoteTemplate else 'manage_options')
    data = data.copy()
    data.pop('version', None)
    data.pop('is_active', None)
    instance = model(**data)
    validate_catalog(instance)
    instance.save()
    return instance


@gated(exclusive=True)
@transaction.atomic
def update_catalog(model, pk, data, expected_version=None, *, actor):
    data = data.copy()
    expected_version = data.pop('version', expected_version)
    instance = model.all_objects.select_for_update().get(pk=pk)
    require_actor_permission(actor, 'manage_templates' if model is ClinicalNoteTemplate else 'manage_options')
    check_mutation(instance, expected_version)
    allowed = {f.name for f in model._meta.concrete_fields} - {'id','created_at','updated_at','version','is_active','deleted_at','archived_by','archive_reason'}
    for key, value in data.items():
        if key not in allowed:
            raise ValidationError({key: ['حقل غير قابل للتعديل']})
        setattr(instance, key, value)
    validate_catalog(instance)
    instance.version += 1
    instance.save()
    return instance


@gated(exclusive=True)
@transaction.atomic
def archive_catalog(model, pk, version, *, actor):
    instance = model.all_objects.select_for_update().get(pk=pk)
    require_actor_permission(actor, 'manage_templates' if model is ClinicalNoteTemplate else 'manage_options')
    check_mutation(instance, version)
    instance.soft_delete()
    return True


@gated(exclusive=True)
@transaction.atomic
def restore_catalog(instance, version, *, actor):
    instance = instance.__class__.all_objects.select_for_update().get(pk=instance.pk)
    require_actor_permission(actor, 'manage_templates' if isinstance(instance, ClinicalNoteTemplate) else 'manage_options')
    if type(version) is not int or instance.version != version:
        raise ConflictError('تغير السجل؛ أعد تحميله')
    if not instance.is_active or instance.deleted_at:
        instance.restore()
    return instance


class DiagnosisService:
    def create_diagnosis(self, *, actor, **data):
        return create_catalog(DiagnosisOption, data, actor=actor)
    def update_diagnosis(self, diag_id, expected_version=None, *, actor, **data):
        return update_catalog(DiagnosisOption, diag_id, data, expected_version, actor=actor)
    def soft_delete(self, diag_id, expected_version=None, *, actor):
        return archive_catalog(DiagnosisOption, diag_id, expected_version, actor=actor)

class MedicationService:
    def create_medication(self, *, actor, **data):
        return create_catalog(MedicationOption, data, actor=actor)
    def update_medication(self, med_id, expected_version=None, *, actor, **data):
        return update_catalog(MedicationOption, med_id, data, expected_version, actor=actor)
    def soft_delete(self, med_id, expected_version=None, *, actor):
        return archive_catalog(MedicationOption, med_id, expected_version, actor=actor)

class ScaleService:
    @gated(exclusive=True)
    @transaction.atomic
    def add_field(self, scale, data, expected_version=None, *, actor):
        scale = ClinicalScale.all_objects.select_for_update().get(pk=scale.pk)
        require_actor_permission(actor, 'manage_options')
        check_mutation(scale, expected_version)
        if scale.fields.filter(is_active=True).count() >= 100:
            raise ValidationError({'fields': ['الحد الأقصى 100 سؤال نشط']})
        data = data.copy()
        data.setdefault('default', data.get('min_val', 0))
        field = ScaleField(scale=scale, **data)
        field.full_clean()
        field.save()
        scale.version += 1
        scale.save(update_fields=['version', 'updated_at'])
        return field
    def delete_scale(self, scale_id, expected_version=None, *, actor):
        return archive_catalog(ClinicalScale, scale_id, expected_version, actor=actor)

class TemplateService:
    def create_template(self, data, *, actor):
        return create_catalog(ClinicalNoteTemplate, data, actor=actor)
    def update_template(self, template_id, data, expected_version=None, *, actor):
        return update_catalog(ClinicalNoteTemplate, template_id, data, expected_version, actor=actor)
    def delete_template(self, template_id, expected_version=None, *, actor):
        return archive_catalog(ClinicalNoteTemplate, template_id, expected_version, actor=actor)
