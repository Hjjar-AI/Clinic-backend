from django.core.exceptions import ValidationError

from apps.clinical.models import ClinicalScale


def normalize_scale_response(item, definition_snapshot=None, name_snapshot=None):
    """Validate scale answers and persist an immutable definition snapshot."""
    if not isinstance(item, dict):
        raise ValidationError({'scale_responses': ['استجابة المقياس غير صالحة']})
    try:
        scale_id = int(item.get('scale_id'))
    except (TypeError, ValueError):
        raise ValidationError({'scale_responses': ['معرّف المقياس غير صالح']})

    scale = ClinicalScale.all_objects.prefetch_related('fields').filter(pk=scale_id).first()
    if not scale:
        raise ValidationError({'scale_responses': ['تعريف المقياس غير موجود']})
    responses = item.get('responses')
    if not isinstance(responses, dict):
        raise ValidationError({'scale_responses': ['إجابات المقياس يجب أن تكون كائناً منظماً']})

    definitions = definition_snapshot or list(scale.fields.all().order_by('order', 'id'))
    if not definitions:
        raise ValidationError({'scale_responses': [f'المقياس {scale.name} لا يحتوي على أسئلة']})
    if len(definitions) > 100:
        raise ValidationError({'scale_responses': ['عدد أسئلة المقياس يتجاوز الحد المسموح']})

    normalized = {}
    snapshot = []
    score = 0.0
    for field in definitions:
        def field_value(name, default=None):
            return field.get(name, default) if isinstance(field, dict) else getattr(field, name, default)

        field_id = field_value('id')
        if field_id is None:
            raise ValidationError({'scale_responses': ['تعريف سؤال المقياس غير صالح']})
        label = str(field_value('label', ''))[:200]
        field_type = field_value('field_type', 'slider')
        minimum = float(field_value('min_val', 0))
        maximum = float(field_value('max_val', 10))
        if maximum <= minimum:
            raise ValidationError({'scale_responses': [f'نطاق غير صالح للسؤال: {label}']})
        default = field_value('default', minimum)
        key = str(field_id)
        value = responses.get(key, responses.get(field_id, default))
        if field_type == 'slider':
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise ValidationError({'scale_responses': [f'قيمة غير رقمية للسؤال: {label}']})
            if value < minimum or value > maximum:
                raise ValidationError({'scale_responses': [f'قيمة السؤال خارج النطاق: {label}']})
            score += value
        else:
            value = str(value or '')
            if len(value) > 5000:
                raise ValidationError({'scale_responses': [f'إجابة السؤال طويلة جداً: {label}']})
        normalized[key] = value
        snapshot.append({
            'id': field_id,
            'label': label,
            'field_type': field_type,
            'min_val': minimum,
            'max_val': maximum,
            'step': float(field_value('step', 1)),
            'default': default,
            'options': field_value('options'),
            'order': int(field_value('order', 0)),
        })

    normalized['__definition'] = snapshot
    normalized['__score'] = score
    return {
        'scale_id': scale.id,
        'scale_name': name_snapshot or scale.name,
        'responses': normalized,
    }
