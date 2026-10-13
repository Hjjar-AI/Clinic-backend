from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime


def stamp_instruction_acknowledgement(clinical, actor, previous=None):
    if 'instruction_acknowledgement' not in clinical:
        return clinical
    value = clinical['instruction_acknowledgement']
    if value is None:
        return clinical
    allowed = {'explained_at', 'recipient', 'recipient_name', 'clarification_needed', 'notes', 'recorded_by_id', 'recorded_at'}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValidationError({'clinical_data': ['سجل شرح التعليمات غير صالح']})
    try:
        explained = parse_datetime(value.get('explained_at', '')) if isinstance(value.get('explained_at'), str) else None
    except ValueError:
        explained = None
    if explained is None or timezone.is_naive(explained) or explained > timezone.now():
        raise ValidationError({'clinical_data': ['وقت شرح التعليمات مطلوب بتوقيت محدد ولا يجوز أن يكون مستقبلياً']})
    if not isinstance(value.get('recipient'), str) or value.get('recipient') not in {'patient', 'representative', 'both'} or type(value.get('clarification_needed')) not in (type(None), bool):
        raise ValidationError({'clinical_data': ['المتلقي أو حالة التوضيح غير صالحة']})
    result = {'explained_at': explained.isoformat(), 'recipient': value['recipient'], 'clarification_needed': value.get('clarification_needed')}
    for key, limit in [('recipient_name', 150), ('notes', 2000)]:
        text = value.get(key, '')
        if not isinstance(text, str) or len(text) > limit:
            raise ValidationError({'clinical_data': ['اسم المتلقي أو الملاحظات غير صالحة']})
        result[key] = text.strip()
    old = (previous or {}).get('instruction_acknowledgement') or {}
    if not isinstance(old, dict):
        old = {}
    if {key: old.get(key) for key in result} == result and old.get('recorded_by_id') and old.get('recorded_at'):
        result.update(recorded_by_id=old['recorded_by_id'], recorded_at=old['recorded_at'])
    else:
        result.update(recorded_by_id=actor.pk, recorded_at=timezone.now().isoformat())
    return {**clinical, 'instruction_acknowledgement': result}
