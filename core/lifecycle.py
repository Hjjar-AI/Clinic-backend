"""Canonical lifecycle definitions shared by services and API metadata.

Keep workflow rules here rather than scattering string comparisons through
views, serializers, reports, and notification jobs.
"""
from django.core.exceptions import ValidationError


LIFECYCLES = {
    'appointment': {
        'initial': 'scheduled',
        'transitions': {
            'scheduled': {'confirmed', 'arrived', 'cancelled', 'no-show'},
            'confirmed': {'arrived', 'cancelled', 'no-show'},
            'arrived': {'completed', 'cancelled'},
            'completed': set(),
            'cancelled': {'scheduled'},
            'no-show': {'scheduled'},
        },
    },
    'visit': {
        'initial': 'draft',
        'transitions': {
            'draft': {'final'},
            'final': {'amended', 'locked'},
            'amended': {'final', 'locked'},
            'locked': set(),
        },
    },
    'task': {
        'initial': 'open',
        'transitions': {
            'open': {'in_progress', 'completed', 'cancelled'},
            'in_progress': {'open', 'completed', 'cancelled'},
            'completed': {'open'},
            'cancelled': {'open'},
        },
    },
    'invoice': {
        'initial': 'draft',
        'transitions': {
            'draft': {'issued', 'cancelled'},
            'issued': {'paid', 'cancelled'},
            'paid': set(),
            'cancelled': set(),
        },
    },
    'notification': {
        'initial': 'unread',
        'transitions': {
            'unread': {'read'},
            'read': {'unread'},
        },
    },
}


STATUS_PRESENTATION = {
    'appointment': {
        'scheduled': {'label': 'مجدول', 'color': 'info', 'icon': 'calendar-check'},
        'confirmed': {'label': 'مؤكد', 'color': 'primary', 'icon': 'check'},
        'arrived': {'label': 'وصل', 'color': 'warning', 'icon': 'user-check'},
        'completed': {'label': 'مكتمل', 'color': 'success', 'icon': 'check-circle'},
        'cancelled': {'label': 'ملغي', 'color': 'danger', 'icon': 'times-circle'},
        'no-show': {'label': 'لم يحضر', 'color': 'warning', 'icon': 'exclamation-circle'},
    },
    'visit': {
        'draft': {'label': 'مسودة', 'color': 'grey', 'icon': 'edit'},
        'final': {'label': 'نهائية', 'color': 'success', 'icon': 'check-circle'},
        'amended': {'label': 'معدلة', 'color': 'warning', 'icon': 'history'},
        'locked': {'label': 'مقفلة', 'color': 'danger', 'icon': 'lock'},
    },
    'task': {
        'open': {'label': 'مفتوحة', 'color': 'warning', 'icon': 'circle'},
        'in_progress': {'label': 'قيد التنفيذ', 'color': 'info', 'icon': 'spinner'},
        'completed': {'label': 'مكتملة', 'color': 'success', 'icon': 'check-circle'},
        'cancelled': {'label': 'ملغية', 'color': 'grey', 'icon': 'ban'},
    },
    'invoice': {
        'draft': {'label': 'مسودة', 'color': 'grey', 'icon': 'file-alt'},
        'issued': {'label': 'صادرة', 'color': 'info', 'icon': 'file-invoice'},
        'paid': {'label': 'مدفوعة', 'color': 'success', 'icon': 'check-circle'},
        'cancelled': {'label': 'ملغية', 'color': 'danger', 'icon': 'times-circle'},
    },
    'notification': {
        'unread': {'label': 'غير مقروء', 'color': 'info', 'icon': 'envelope'},
        'read': {'label': 'مقروء', 'color': 'grey', 'icon': 'envelope-open'},
    },
}


def valid_statuses(workflow):
    return set(LIFECYCLES[workflow]['transitions'])


def allowed_transitions(workflow, current):
    return LIFECYCLES[workflow]['transitions'].get(current, set())


def enforce_transition(workflow, current, target):
    if target not in valid_statuses(workflow):
        raise ValidationError({'status': [f'حالة {workflow} غير صالحة: {target}']})
    if target == current:
        return False
    if target not in allowed_transitions(workflow, current):
        raise ValidationError({
            'status': [f'لا يمكن تغيير الحالة من {current} إلى {target}']
        })
    return True


def lifecycle_payload():
    payload = {}
    for workflow, definition in LIFECYCLES.items():
        payload[f'{workflow}_status'] = {
            status: {
                **STATUS_PRESENTATION[workflow][status],
                'allowed_transitions': sorted(definition['transitions'][status]),
                'terminal': not bool(definition['transitions'][status]),
            }
            for status in definition['transitions']
        }
    return payload
