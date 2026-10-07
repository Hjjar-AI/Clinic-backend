from django.core.exceptions import ValidationError
from .exceptions import ConflictError


def check_mutation(instance, expected_version):
    if getattr(instance, 'deleted_at', None) is not None or not getattr(instance, 'is_active', True):
        raise ConflictError('السجل مؤرشف؛ أعد تحميل البيانات')
    if type(expected_version) is not int or expected_version < 1:
        raise ValidationError({'version': ['رقم إصدار صحيح مطلوب']})
    if instance.version != expected_version:
        raise ConflictError('تم تعديل السجل بواسطة مستخدم آخر؛ أعد تحميل البيانات')


def request_version(request):
    value = request.data.get('version')
    if value is None:
        value = request.headers.get('If-Match', '').strip('"')
    if isinstance(value, bool):
        raise ValidationError({'version': ['رقم إصدار صحيح مطلوب']})
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValidationError({'version': ['رقم الإصدار مطلوب']})
    if value < 1:
        raise ValidationError({'version': ['رقم الإصدار غير صالح']})
    return value
