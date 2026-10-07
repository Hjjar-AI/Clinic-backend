import json
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder


def text(value, field, maximum):
    if value is None:
        return ''
    if not isinstance(value, str):
        raise ValidationError({field: ['يجب أن تكون القيمة نصاً']})
    value = value.strip()
    if len(value) > maximum:
        raise ValidationError({field: [f'الحد الأقصى {maximum} محرف']})
    return value


def clinical_object(value):
    if not isinstance(value, dict):
        raise ValidationError({'clinical_data': ['يجب أن تكون البيانات كائناً منظماً']})
    if 'formulation' in value:
        formulation = value['formulation']
        if not isinstance(formulation, dict):
            raise ValidationError({'clinical_data': ['الصياغة السريرية يجب أن تكون كائناً']})
        for key in ('predisposing', 'precipitating', 'perpetuating', 'protective'):
            if key in formulation: text(formulation[key], 'clinical_data', 20_000)
    for key in ('mse', 'risk_notes', 'plan_details'):
        if key in value: text(value[key], 'clinical_data', 50_000)
    try:
        encoded = json.dumps(value, cls=DjangoJSONEncoder, allow_nan=False)
    except (ValueError, TypeError, RecursionError):
        raise ValidationError({'clinical_data': ['بيانات غير صالحة']})
    if len(encoded.encode()) > 200_000:
        raise ValidationError({'clinical_data': ['البيانات كبيرة جداً']})
    return value


def normalize_rows(values, kind, visit=None):
    from apps.clinical.models import DiagnosisOption, MedicationOption
    if not isinstance(values, list) or len(values) > 200:
        raise ValidationError({kind: ['قائمة غير صالحة أو تتجاوز 200 صف']})
    diagnosis = kind == 'diagnoses'
    model = DiagnosisOption if diagnosis else MedicationOption
    existing = {}
    if visit and visit.pk:
        related = visit.visit_diagnoses if diagnosis else visit.visit_medications
        key = 'diagnosis_id' if diagnosis else 'medication_id'
        existing = {getattr(row, key): row for row in related.all() if getattr(row, key)}
    result = []
    for row in values:
        if not isinstance(row, dict):
            raise ValidationError({kind: ['كل صف يجب أن يكون كائناً منظماً']})
        identifier = row.get('id')
        option = None
        if identifier is not None:
            if type(identifier) is not int or identifier <= 0:
                raise ValidationError({kind: ['معرف غير صالح']})
            option = model.all_objects.filter(pk=identifier).first()
            if not option or ((not option.is_active or option.deleted_at) and identifier not in existing):
                raise ValidationError({kind: ['الخيار غير موجود أو متقاعد']})
        fields = {'code': 50, 'name': 200, 'arabic_name': 200} if diagnosis else {
            'name': 200, 'dosage': 100, 'brand': 200, 'schedule': 200,
        }
        normalized = {key: text(row.get(key), kind, maximum) for key, maximum in fields.items()}
        normalized['id'] = identifier
        if diagnosis and option:
            normalized['code'] = normalized['code'] or option.code
            normalized['name'] = normalized['name'] or option.english_name
            normalized['arabic_name'] = normalized['arabic_name'] or option.arabic_name
        if not diagnosis:
            custom = row.get('is_custom', option is None)
            if type(custom) is not bool or (custom and option):
                raise ValidationError({kind: ['نوع الدواء لا يطابق مرجع الكتالوج']})
            normalized['is_custom'] = option is None
            if option:
                normalized['name'] = normalized['name'] or option.generic_arabic or option.generic_english
                normalized['dosage'] = normalized['dosage'] or option.dosage or ''
                normalized['brand'] = normalized['brand'] or option.brand_arabic or option.brand_english or ''
            previous = existing.get(identifier)
            normalized['controlled'] = previous.controlled_snapshot if previous else bool(option and option.is_controlled)
        result.append(normalized)
    return result
