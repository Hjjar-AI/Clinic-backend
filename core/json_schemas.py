"""Bounded document schemas shared by ordinary writes and recovery.

Signed snapshots are validated as stored; validation never rewrites evidence.
Optional namespaced extensions are the only open-ended clinical section.
"""
import json
import re
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder


def object_schema(value, allowed, field, *, maximum=200_000):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValidationError({field: ['كائن غير صالح أو حقول غير معروفة']})
    try:
        encoded = json.dumps(value, cls=DjangoJSONEncoder, allow_nan=False)
    except (ValueError, TypeError, RecursionError, OverflowError):
        raise ValidationError({field: ['بيانات غير صالحة']})
    if len(encoded.encode('utf-8')) > maximum:
        raise ValidationError({field: ['البيانات كبيرة جداً']})
    return value


def bounded_text(value, maximum, field):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValidationError({field: ['يلزم نص ضمن الحد المسموح']})
    return value


def narrative_schema(value, field, *, template=False):
    allowed = {'schema_version', 'mse', 'formulation', 'risk_notes', 'plan_details', 'extensions'}
    allowed |= {'treatment_text', 'doctor_notes'} if template else {'applied_template', 'instruction_acknowledgement', 'goals'}
    object_schema(value, allowed, field, maximum=100_000 if template else 200_000)
    if type(value.get('schema_version', 1)) is not int or value.get('schema_version', 1) != 1:
        raise ValidationError({field: ['إصدار بيانات غير مدعوم']})
    for name in ('mse', 'risk_notes', 'plan_details', 'treatment_text', 'doctor_notes'):
        if name in value:
            bounded_text(value[name], 50_000, field)
    if 'formulation' in value:
        formulation = object_schema(value['formulation'],
            {'predisposing', 'precipitating', 'perpetuating', 'protective'}, field)
        for text in formulation.values():
            bounded_text(text, 20_000, field)
    if 'extensions' in value:
        extensions = value['extensions']
        if (not isinstance(extensions, dict) or len(extensions) > 30
                or any(not isinstance(key, str) or not re.fullmatch(r'[a-z][a-z0-9_.-]{0,79}', key)
                       for key in extensions)):
            raise ValidationError({field: ['امتدادات غير صالحة']})
    if not template and 'goals' in value:
        goals = value['goals']
        if not isinstance(goals, list) or len(goals) > 100:
            raise ValidationError({field: ['قائمة أهداف غير صالحة']})
        from core.numeric_validation import finite_number
        for goal in goals:
            object_schema(goal, {'title', 'percentage'}, field)
            bounded_text(goal.get('title', ''), 2000, field)
            percentage = goal.get('percentage')
            if percentage is not None:
                try:
                    if not 0 <= finite_number(percentage) <= 100:
                        raise ValueError()
                except ValueError:
                    raise ValidationError({field: ['نسبة هدف غير صالحة']})
    if not template and 'applied_template' in value:
        applied = object_schema(value['applied_template'], {'id', 'name', 'updated_at', 'content'}, field)
        if type(applied.get('id')) is not int or applied['id'] < 1:
            raise ValidationError({field: ['مرجع قالب غير صالح']})
        bounded_text(applied.get('name', ''), 100, field)
        if applied.get('updated_at') is not None:
            bounded_text(applied['updated_at'], 50, field)
        narrative_schema(applied.get('content', {}), field, template=True)
    if not template and value.get('instruction_acknowledgement') is not None:
        ack = object_schema(value['instruction_acknowledgement'],
            {'explained_at', 'recipient', 'recipient_name', 'clarification_needed', 'notes', 'recorded_by_id', 'recorded_at'}, field)
        from django.utils.dateparse import parse_datetime
        from django.utils import timezone
        try:
            explained = parse_datetime(ack.get('explained_at', ''))
        except (TypeError, ValueError):
            explained = None
        if (explained is None or timezone.is_naive(explained)
                or not isinstance(ack.get('recipient'), str)
                or ack['recipient'] not in {'patient', 'representative', 'both'}):
            raise ValidationError({field: ['وقت أو متلقي شرح التعليمات غير صالح']})
        if type(ack.get('clarification_needed')) not in (type(None), bool):
            raise ValidationError({field: ['حالة التوضيح غير صالحة']})
        bounded_text(ack.get('recipient_name', ''), 150, field)
        bounded_text(ack.get('notes', ''), 2000, field)
        if 'recorded_by_id' in ack and (type(ack['recorded_by_id']) is not int or ack['recorded_by_id'] < 1):
            raise ValidationError({field: ['مرجع مسجل التعليمات غير صالح']})
        if 'recorded_at' in ack:
            try:
                recorded = parse_datetime(ack['recorded_at'])
            except (TypeError, ValueError):
                recorded = None
            if recorded is None or timezone.is_naive(recorded):
                raise ValidationError({field: ['وقت التسجيل غير صالح']})
    return value


def validate_preferences(value):
    object_schema(value, {'schema_version', 'density', 'splitView', 'progressive'}, 'preferences', maximum=4096)
    if type(value.get('schema_version', 1)) is not int or value.get('schema_version', 1) != 1:
        raise ValidationError({'preferences': ['إصدار غير مدعوم']})
    if 'density' in value and value['density'] not in {'comfortable', 'compact'}:
        raise ValidationError({'preferences': ['كثافة عرض غير صالحة']})
    for name in ('splitView', 'progressive'):
        if name in value and type(value[name]) is not bool:
            raise ValidationError({'preferences': ['يلزم نعم أو لا']})
    return value


def validate_revision_snapshot(value):
    object_schema(value, {'schema_version', 'follow_up', 'fields', 'diagnoses', 'medications',
                         'lab_values', 'scales', 'attachments', 'patient', 'longitudinal', 'clinician'},
                  'snapshot', maximum=4_000_000)
    if type(value.get('schema_version')) is not int or value['schema_version'] not in {3, 4}:
        raise ValidationError({'snapshot': ['إصدار نسخة سريرية غير مدعوم']})
    for name in ('fields', 'patient', 'longitudinal', 'clinician'):
        if not isinstance(value.get(name), dict):
            raise ValidationError({'snapshot': ['قسم نسخة سريرية غير صالح']})
    for name in ('diagnoses', 'medications', 'lab_values', 'scales', 'attachments'):
        if not isinstance(value.get(name), list) or len(value[name]) > 200:
            raise ValidationError({'snapshot': ['صفوف نسخة سريرية غير صالحة']})
    if value.get('follow_up') is not None and not isinstance(value['follow_up'], dict):
        raise ValidationError({'snapshot': ['متابعة نسخة سريرية غير صالحة']})
    narrative_schema(value['fields'].get('clinical_data', {}), 'snapshot')
    return value


def validate_issued_snapshot(value):
    object_schema(value, {'schema_version', 'clinic', 'revision_id', 'patient_version', 'visit_id', 'visit_version',
        'template_version', 'patient_id', 'patient_number', 'patient_name', 'patient_age', 'patient_gender',
        'patient_address', 'patient_national_id', 'visit_date', 'medications', 'diagnoses', 'doctor_name',
        'generated_at', 'timezone', 'generator', 'print_options', 'issue_date', 'main_complaints',
        'referral_reason', 'clinician'}, 'snapshot', maximum=4_000_000)
    if type(value.get('schema_version', 1)) is not int or value.get('schema_version', 1) != 1:
        raise ValidationError({'snapshot': ['إصدار مستند غير مدعوم']})
    for name in ('revision_id', 'visit_id', 'visit_version'):
        if type(value.get(name)) is not int or value[name] < 1:
            raise ValidationError({'snapshot': ['مرجع مستند غير صالح']})
    if not isinstance(value.get('clinic'), dict) or not isinstance(value.get('medications'), list) or not isinstance(value.get('diagnoses'), list):
        raise ValidationError({'snapshot': ['بيانات مستند غير صالحة']})
    return value
