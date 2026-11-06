from django.core.exceptions import ValidationError
from core.numeric_validation import finite_number, valid_scale_range, step_aligned


def validate_scale_definition(minimum, maximum, step, default, field_type='slider'):
    try:
        for value in (minimum, maximum, step, default):
            finite_number(value)
    except ValueError:
        raise ValidationError({'min_val': ['تعريف المقياس يتطلب أرقاماً ونطاقاً محدودين']})
    if not valid_scale_range(minimum, maximum, step):
        raise ValidationError({'step': ['نطاق أو خطوة المقياس غير صالحة']})
    if not minimum <= default <= maximum:
        raise ValidationError({'default': ['القيمة الافتراضية خارج النطاق']})
    if field_type == 'slider' and not step_aligned(default, minimum, step):
        raise ValidationError({'default': ['القيمة الافتراضية لا تطابق الخطوة']})


def validate_template_content(value):
    from core.json_schemas import narrative_schema
    return narrative_schema(value, 'content', template=True)
