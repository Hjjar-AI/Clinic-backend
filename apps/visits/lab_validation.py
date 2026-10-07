from datetime import date
from django.core.exceptions import ValidationError
from .input_validation import text

LAB_STATUSES = {'pending', 'normal', 'abnormal', 'critical'}


def normalize_lab_values(values, require_complete=False):
    if values is None:
        return []
    if not isinstance(values, list) or len(values) > 200:
        raise ValidationError({'lab_values': ['قائمة التحاليل غير صالحة أو كبيرة جداً']})
    normalized = []
    for index, item in enumerate(values, start=1):
        if not isinstance(item, dict):
            raise ValidationError({'lab_values': [f'نتيجة التحليل رقم {index} غير صالحة']})
        row = {key: text(item.get(key), 'lab_values', maximum) for key, maximum in {
            'name': 200, 'value': 200, 'unit': 50, 'reference_range': 100,
            'status': 20, 'date': 10,
        }.items()}
        row['status'] = row['status'].lower()
        if row['date']:
            try:
                row['date'] = date.fromisoformat(row['date']).isoformat()
            except ValueError:
                raise ValidationError({'lab_values': [f'تاريخ التحليل رقم {index} غير صالح']})
        if row['status'] and row['status'] not in LAB_STATUSES:
            raise ValidationError({'lab_values': ['حالة التحليل غير صالحة']})
        required = ('name', 'date', 'status') if row['status'] == 'pending' else ('name', 'value', 'date', 'status')
        if require_complete and any(not row[key] for key in required):
            raise ValidationError({'lab_values': [f'نتيجة التحليل رقم {index} ناقصة']})
        normalized.append(row)
    return normalized
