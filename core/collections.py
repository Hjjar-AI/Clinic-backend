"""Normalize only collection responses, preserving endpoint-specific metadata."""
from django.core.exceptions import ValidationError

COLLECTION_KEYS = ('items', 'results', 'patients', 'appointments', 'visits', 'attachments',
    'care_team', 'risk_history', 'timeline', 'slots', 'documents', 'users', 'doctors')


def normalize_collection(payload, request=None):
    if isinstance(payload, (list, tuple)):
        return {'items': payload, 'meta': {'pagination': 'none', 'total': len(payload), 'has_more': False}}
    if not isinstance(payload, dict):
        return payload
    key = next((key for key in COLLECTION_KEYS if isinstance(payload.get(key), (list, tuple))), None)
    if key is None:
        return payload
    # Multi-series reports and document snapshots are not collection endpoints.
    if request and request.path.startswith(('/api/v1/reports/', '/api/v1/dashboard/', '/api/v1/prescription/visit/')):
        return payload
    items = payload[key]
    meta = {**{name: value for name, value in payload.items() if name not in {key, 'meta'}}, **payload.get('meta', {})}
    if 'limit' in meta:
        meta['per_page'] = meta.pop('limit')
    if 'next_cursor' in meta or 'previous_cursor' in meta:
        meta['pagination'] = 'cursor'
    elif 'offset' in meta or ('total' in meta and request and request.path.endswith(('/records/', '/corrections/'))):
        meta['pagination'] = 'offset'
        if 'offset' not in meta:
            try:
                meta['offset'] = max(0, int(request.GET.get('offset', 0))) if request else 0
            except (ValueError, TypeError):
                meta['offset'] = 0
        meta.setdefault('per_page', 100)
        meta['has_more'] = meta['offset'] + len(items) < meta.get('total', len(items))
    else:
        meta.setdefault('pagination', 'none')
        meta.setdefault('total', len(items))
        meta.setdefault('has_more', False)
    return {'items': items, 'meta': meta}


def offset_page(queryset, params, default=20):
    try:
        limit = max(1, min(int(params.get('per_page', default)), 200))
        offset = max(0, int(params.get('offset', 0)))
    except (ValueError, TypeError):
        raise ValidationError('إعدادات صفحات غير صالحة')
    return list(queryset[offset:offset + limit]), queryset.count(), limit, offset
