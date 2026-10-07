from django.core.exceptions import ValidationError
from .models import (
    DiagnosisOption,
    MedicationOption,
    ClinicalScale,
    ScaleField,
    ClinicalNoteTemplate,
)

class DiagnosisService:
    def create_diagnosis(self, **data):
        code = data.get('code')
        english_name = data.get('english_name')
        arabic_name = data.get('arabic_name')
        if not code or not english_name or not arabic_name:
            raise ValidationError(['الكود والاسم الإنجليزي والعربي مطلوبة'])
        if DiagnosisOption.all_objects.filter(code=code).exists():
            raise ValidationError(["تشخيص بهذا الكود موجود؛ أعد تفعيله إن كان متقاعداً"])
        diag = DiagnosisOption.objects.create(
            code=code,
            english_name=english_name,
            arabic_name=arabic_name,
            is_active=True
        )
        return diag

    def update_diagnosis(self, diag_id, **data):
        diag = DiagnosisOption.all_objects.get(id=diag_id)
        code = data.get('code', diag.code)
        english_name = data.get('english_name', diag.english_name)
        arabic_name = data.get('arabic_name', diag.arabic_name)
        if code != diag.code and DiagnosisOption.all_objects.filter(code=code).exists():
            raise ValidationError(["الكود موجود بالفعل"])
        diag.code = code
        diag.english_name = english_name
        diag.arabic_name = arabic_name
        diag.save()
        return diag

    def soft_delete(self, diag_id):
        diag = DiagnosisOption.objects.get(id=diag_id)
        diag.soft_delete()
        return True

class MedicationService:
    def create_medication(self, **data):
        generic_english = data.get('generic_english')
        generic_arabic = data.get('generic_arabic', '')
        dosage = data.get('dosage', '')
        brand_english = data.get('brand_english', '')
        brand_arabic = data.get('brand_arabic', '')
        if not generic_english:
            raise ValidationError(['الاسم العام الإنجليزي مطلوب'])
        if MedicationOption.all_objects.filter(
            generic_english=generic_english,
            dosage=dosage,
            brand_english=brand_english
        ).exists():
            raise ValidationError(["الدواء موجود؛ أعد تفعيله إن كان متقاعداً"])
        med = MedicationOption.objects.create(
            generic_english=generic_english,
            generic_arabic=generic_arabic,
            dosage=dosage,
            brand_english=brand_english,
            brand_arabic=brand_arabic,
        )
        return med

    def update_medication(self, med_id, **data):
        med = MedicationOption.all_objects.get(id=med_id)
        for k, v in data.items():
            if hasattr(med, k):
                setattr(med, k, v)
        med.save()
        return med

    def soft_delete(self, med_id):
        med = MedicationOption.objects.get(id=med_id)
        med.soft_delete()
        return True

class ScaleService:
    def add_field(self, scale, data):
        field = ScaleField.objects.create(scale=scale, **data)
        return field

    def delete_scale(self, scale_id):
        scale = ClinicalScale.objects.get(id=scale_id)
        scale.soft_delete()
        return True

class TemplateService:
    def create_template(self, data):
        template = ClinicalNoteTemplate.objects.create(**data)
        return template

    def update_template(self, template_id, data):
        template = ClinicalNoteTemplate.all_objects.get(id=template_id)
        for k, v in data.items():
            setattr(template, k, v)
        template.save()
        return template

    def delete_template(self, template_id):
        template = ClinicalNoteTemplate.objects.get(id=template_id)
        template.soft_delete()
        return True
