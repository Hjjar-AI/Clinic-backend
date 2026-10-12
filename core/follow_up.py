"""Terminal follow-up outcomes are retained; scheduling a new occurrence is explicit."""
from django.core.exceptions import ValidationError


def follow_up_transition(previous, target):
    if not isinstance(target, str) or target not in {'pending', 'completed', 'missed', 'cancelled', 'waived'}:
        raise ValidationError({'status': ['نتيجة متابعة غير صالحة']})
    if previous == target:
        return False
    if previous != 'pending':
        raise ValidationError({'status': ['أضف متابعة جديدة بدلاً من تغيير نتيجة مكتملة']})
    return True
