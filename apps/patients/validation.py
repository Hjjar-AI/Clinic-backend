from django.core.exceptions import ValidationError
from django.db.models import CharField, TextField
from django.utils import timezone
from core.normalization import (
    NATIONAL_ID_MIN_LENGTH, NATIONAL_ID_MAX_LENGTH, normalize_name,
    normalize_identifier, normalize_phone,
)
from .models import Patient
from .choices import MaritalStatus
from .projections import PROFILE_RECORD_FIELDS


EDITABLE_FIELDS = {
    'first_name', 'father_name', 'surname', 'mother_name', 'dob_year', 'gender',
    'national_id', 'marital_status', 'occupation', 'permanent_address', 'phone',
    'emergency_contact_name', 'emergency_contact_relation', 'emergency_contact_phone',
    'family_history', 'important_notes', 'registration_date', 'identity_verification',
    'preferred_language', 'preferred_contact_channel', 'communication_restrictions', 'allergy_status', 'medication_status',
}
IDENTITY_FIELDS = ('first_name', 'father_name', 'surname', 'mother_name')
CORRECTION_FIELDS = set(EDITABLE_FIELDS)
CLINICAL_PROFILE_FIELDS = {'family_history', 'important_notes', 'allergy_status', 'medication_status'}


def normalize_identity_data(data):
    data = data.copy()
    for field in IDENTITY_FIELDS:
        if field in data and data[field] is not None:
            data[field] = normalize_name(data[field])
    for field in ('phone', 'emergency_contact_phone'):
        if field in data:
            data[field] = normalize_phone(data[field]) or ''
    if 'national_id' in data:
        data['national_id'] = normalize_identifier(data['national_id']) or ''
    return data


def normalize_profile_data(data):
    data = data.copy()
    if 'admission_date' in data:
        data.setdefault('registration_date', data.pop('admission_date'))
    for field in EDITABLE_FIELDS:
        model_field = None if field in PROFILE_RECORD_FIELDS else Patient._meta.get_field(field)
        if (field in PROFILE_RECORD_FIELDS or isinstance(model_field, (CharField, TextField))) and field in data:
            data[field] = '' if data[field] is None else data[field].strip() if isinstance(data[field], str) else data[field]
    aliases = {'أعزب': 'single', 'عزباء': 'single', 'متزوج': 'married', 'متزوجة': 'married',
               'مطلق': 'divorced', 'مطلقة': 'divorced', 'أرمل': 'widowed', 'أرملة': 'widowed'}
    if isinstance(data.get('marital_status'), str):
        data['marital_status'] = aliases.get(data['marital_status'], data['marital_status'])
    return normalize_identity_data(data)


def validate_profile_data(data, is_edit=False, existing=None):
    errors = []
    if not is_edit:
        if not data.get('first_name'):
            errors.append('الاسم الأول مطلوب')
        if not data.get('surname'):
            errors.append('اسم العائلة مطلوب')
    else:
        if 'first_name' in data and not data.get('first_name'):
            errors.append('الاسم الأول مطلوب')
        if 'surname' in data and not data.get('surname'):
            errors.append('اسم العائلة مطلوب')

    if data.get('national_id'):
        if not (NATIONAL_ID_MIN_LENGTH <= len(data['national_id']) <= NATIONAL_ID_MAX_LENGTH):
            errors.append('الرقم الوطني غير صالح')
    if data.get('phone'):
        phone = data['phone'].strip()
        if not (phone.startswith('0') or phone.startswith('+963')):
            errors.append('رقم الهاتف غير صالح')
    dob_year = data.get('dob_year')
    if dob_year is not None and (type(dob_year) is not int or not (1900 <= dob_year <= timezone.localdate().year)):
        errors.append('سنة الميلاد غير صالحة')
    limits = {'national_id': 100, 'emergency_contact_name': 150, 'emergency_contact_relation': 100, 'emergency_contact_phone': 20}
    for name, limit in limits.items():
        if name in data and (not isinstance(data[name], str) or len(data[name]) > limit):
            errors.append('قيمة نصية غير صالحة أو طويلة جداً')
    if data.get('marital_status') and data['marital_status'] not in MaritalStatus.values:
        errors.append('حالة اجتماعية غير صالحة')
    emergency_name = data.get('emergency_contact_name', getattr(existing, 'emergency_contact_name', ''))
    if not emergency_name and any(data.get(key, getattr(existing, key, '')) for key in ('emergency_contact_relation', 'emergency_contact_phone')):
        errors.append('اسم جهة اتصال الطوارئ مطلوب عند تسجيل بيانات الاتصال')
    if errors:
        raise ValidationError(errors)
