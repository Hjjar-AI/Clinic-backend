from django.core.exceptions import ValidationError
from datetime import datetime


def apply_ordering(queryset, params, allowed, default='-id'):
    requested = params.get('sort_by')
    direction = params.get('sort_order', 'asc').lower()
    if not requested:
        return queryset.order_by(default) if default.lstrip('-') == 'id' else queryset.order_by(default, '-id')
    field = allowed.get(requested)
    if not field:
        raise ValidationError({'sort_by': ['حقل الفرز غير مدعوم']})
    if direction not in {'asc', 'desc'}:
        raise ValidationError({'sort_order': ['اتجاه الفرز يجب أن يكون asc أو desc']})
    prefix = '-' if direction == 'desc' else ''
    return queryset.order_by(f'{prefix}{field}', '-id')


def parse_date_range(params):
    values = {}
    for key in ('date_from', 'date_to'):
        raw = params.get(key)
        if not raw:
            values[key] = None
            continue
        try:
            values[key] = datetime.strptime(raw, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            raise ValidationError({key: ['صيغة التاريخ يجب أن تكون YYYY-MM-DD']})
    if values['date_from'] and values['date_to'] and values['date_from'] > values['date_to']:
        raise ValidationError({'date_to': ['تاريخ النهاية يجب ألا يسبق تاريخ البداية']})
    return values['date_from'], values['date_to']
