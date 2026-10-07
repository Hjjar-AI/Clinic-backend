import base64
import binascii

from django.core.exceptions import ValidationError


MAX_EMBEDDED_IMAGE_BYTES = 2 * 1024 * 1024


def validate_embedded_image(value, field_name='image', required=False):
    """Validate a small PNG/JPEG data URL before it reaches HTML/PDF storage."""
    if not value:
        if required:
            raise ValidationError({field_name: ['الصورة مطلوبة']})
        return value
    if not isinstance(value, str):
        raise ValidationError({field_name: ['بيانات الصورة غير صالحة']})

    allowed_prefixes = {
        'data:image/png;base64,': b'\x89PNG\r\n\x1a\n',
        'data:image/jpeg;base64,': b'\xff\xd8\xff',
    }
    prefix = next((item for item in allowed_prefixes if value.startswith(item)), None)
    if not prefix:
        raise ValidationError({field_name: ['صيغة الصورة غير مدعومة؛ استخدم PNG أو JPEG']})

    encoded = value[len(prefix):]
    # Reject an oversized payload before allocating memory to decode it.
    if len(encoded) > ((MAX_EMBEDDED_IMAGE_BYTES + 2) // 3) * 4 + 4:
        raise ValidationError({field_name: ['حجم الصورة يتجاوز 2 ميغابايت']})
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise ValidationError({field_name: ['بيانات الصورة غير صالحة']})
    if len(decoded) > MAX_EMBEDDED_IMAGE_BYTES:
        raise ValidationError({field_name: ['حجم الصورة يتجاوز 2 ميغابايت']})
    if not decoded.startswith(allowed_prefixes[prefix]):
        raise ValidationError({field_name: ['محتوى الصورة لا يطابق صيغتها']})
    return value
