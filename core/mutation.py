from django.core.exceptions import ValidationError
from .exceptions import ConflictError


def check_mutation(instance, expected_version):
    if getattr(instance, 'deleted_at', None) is not None or not getattr(instance, 'is_active', True):
        raise ConflictError('السجل مؤرشف؛ أعد تحميل البيانات')
    if type(expected_version) is not int or expected_version < 1:
        raise ValidationError({'version': ['رقم إصدار صحيح مطلوب']})
    if instance.version != expected_version:
        raise ConflictError('تم تعديل السجل بواسطة مستخدم آخر؛ أعد تحميل البيانات')


def parse_version(value):
    """Accept positive integer versions without lossy numeric coercion."""
    if type(value) is int and value > 0:
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit() and len(value) <= 20:
        number = int(value)
        if number > 0:
            return number
    raise ValidationError({'version': ['رقم إصدار صحيح موجب مطلوب']})


def request_version(request):
    body = request.data.get('version')
    header = request.headers.get('If-Match')
    if header is not None:
        if len(header) >= 2 and header.startswith('"') and header.endswith('"'):
            header = header[1:-1]
        header = parse_version(header)
    if body is None:
        return parse_version(header)
    body = parse_version(body)
    if header is not None and header != body:
        raise ValidationError({'version': ['رقم الإصدار في الطلب لا يطابق If-Match']})
    return body
