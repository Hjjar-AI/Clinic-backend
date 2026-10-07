from datetime import date

from django.core.exceptions import ValidationError


LAB_STATUSES = {'pending', 'normal', 'abnormal', 'critical'}


def normalize_lab_values(values, require_complete=False):
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValidationError({'lab_values': ['قائمة التحاليل غير صالحة']})
    if len(values) > 200:
        raise ValidationError({'lab_values': ['عدد نتائج التحاليل يتجاوز الحد المسموح']})

    normalized = []
    for index, item in enumerate(values, start=1):
        if not isinstance(item, dict):
            raise ValidationError({'lab_values': [f'نتيجة التحليل رقم {index} غير صالحة']})
        row = {
            'name': str(item.get('name', '')).strip()[:200],
            'value': str(item.get('value', '')).strip()[:200],
            'unit': str(item.get('unit', '')).strip()[:50],
            'reference_range': str(item.get('reference_range', '')).strip()[:100],
            'status': str(item.get('status', '')).strip().lower(),
            'date': str(item.get('date', '')).strip(),
        }
        if row['date']:
            try:
                parsed_date = date.fromisoformat(row['date'])
            except (TypeError, ValueError):
                raise ValidationError({'lab_values': [f'تاريخ التحليل رقم {index} يجب أن يكون YYYY-MM-DD']})
            row['date'] = parsed_date.isoformat()
        if row['status'] and row['status'] not in LAB_STATUSES:
            raise ValidationError({'lab_values': [f'حالة نتيجة التحليل رقم {index} غير صالحة']})
        if require_complete:
            missing = [key for key in ('name', 'value', 'date', 'status') if not row[key]]
            if missing:
                raise ValidationError({
                    'lab_values': [f'نتيجة التحليل رقم {index} ناقصة: {", ".join(missing)}'],
                })
        normalized.append(row)
    return normalized
