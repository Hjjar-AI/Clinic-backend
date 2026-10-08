"""Scoped, versioned mutations for the patient's longitudinal facts."""
import json
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.utils import timezone
from core.access import accessible_patients
from core.mutation import check_mutation, parse_version
from core.normalization import normalize_identifier, normalize_phone
from .models import (Patient, PatientIdentifier, PatientContact, PatientRepresentative, PatientAllergy,
                     PatientMedication, PatientFollowUp, PatientCorrection)

RECORDS = {
    'identifiers': (PatientIdentifier, ['identifier_type', 'value', 'issuer', 'issuing_country', 'verification']),
    'contacts': (PatientContact, ['name', 'relationship', 'phone', 'email', 'is_emergency', 'is_primary', 'notes']),
    'representatives': (PatientRepresentative, ['name', 'relationship', 'phone', 'authority_scope', 'verification', 'evidence', 'valid_from', 'valid_until']),
    'allergies': (PatientAllergy, ['substance', 'reaction', 'severity', 'status', 'source', 'source_details', 'source_visit', 'recorded_on', 'notes']),
    'medications': (PatientMedication, ['name', 'dosage', 'schedule', 'status', 'started_on', 'ended_on', 'source', 'source_details', 'source_visit', 'recorded_on', 'notes']),
    'follow-ups': (PatientFollowUp, ['title', 'owner', 'due_date', 'status', 'source_visit', 'appointment', 'completed_visit', 'notes', 'outcome_reason']),
}
CLINICAL_KINDS = {'allergies', 'medications', 'follow-ups'}


def json_value(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder, allow_nan=False))


def history_patient_ids(patient):
    """Keep original immutable ownership while exposing reconciled history."""
    ids, frontier = {patient.pk}, {patient.pk}
    while frontier:
        frontier = set(Patient.all_objects.filter(merged_into_id__in=frontier).values_list('pk', flat=True)) - ids
        ids.update(frontier)
    return ids


def require_access(patient, actor, clinical=False, write=False):
    if not accessible_patients(actor, True).filter(pk=patient.pk).exists():
        raise PermissionDenied('غير مصرح بالوصول إلى الملف')
    permissions = ['view_patients', 'edit_visit' if clinical and write else 'view_visits' if clinical else 'edit_patient' if write else 'view_patients']
    if any(not actor.has_perm(permission) for permission in permissions):
        raise PermissionDenied('غير مصرح بهذا الإجراء')


def record_values(row, fields):
    return json_value({name: getattr(row, row._meta.get_field(name).attname) for name in fields})


def stamp_verification(row, actor, previous=None):
    if hasattr(row, 'verification'):
        if row.verification == 'verified' and previous != 'verified':
            if actor is None:
                raise ValidationError('المستخدم المنفذ مطلوب للتحقق')
            if actor.role not in {'admin', 'doctor'}:
                raise PermissionDenied('تأكيد المستندات مخصص للطبيب أو المدير')
            if previous != 'verified':
                row.verified_at, row.verified_by = timezone.now(), actor
        elif row.verification != 'verified':
            row.verified_at, row.verified_by = None, None


class PatientRecordService:
    def list(self, patient, kind, actor):
        if kind not in RECORDS:
            raise ValidationError({'kind': ['نوع سجل غير صالح']})
        require_access(patient, actor, kind in CLINICAL_KINDS)
        return RECORDS[kind][0].objects.filter(patient=patient).order_by('-created_at', '-pk')

    @transaction.atomic
    def save(self, patient, kind, data, actor, expected_version, record_id=None, retire=False, reason=''):
        if kind not in RECORDS or not isinstance(data, dict):
            raise ValidationError('سجل غير صالح')
        patient = Patient.all_objects.select_for_update().get(pk=patient.pk)
        require_access(patient, actor, kind in CLINICAL_KINDS, True)
        check_mutation(patient, expected_version)
        model, fields = RECORDS[kind]
        row = model.objects.select_for_update().filter(patient=patient, pk=parse_version(record_id)).first() if record_id else model(patient=patient, created_by=actor)
        if row is None:
            raise ValidationError('السجل غير موجود في هذا الملف')
        if row.pk and not row.is_active:
            raise ValidationError('السجل متقاعد؛ أضف سجلاً جديداً')
        if any(key not in fields for key in data):
            raise ValidationError('حقول غير مسموحة')
        if row.pk and (not isinstance(reason, str) or not reason.strip() or len(reason) > 500):
            raise ValidationError({'reason': ['سبب تعديل السجل مطلوب']})
        old = record_values(row, fields) if row.pk else {}
        previous_verification = getattr(row, 'verification', None)
        for name, value in data.items():
            field = row._meta.get_field(name)
            if isinstance(field, (models.CharField, models.TextField)):
                if value is None and field.blank:
                    value = ''
                if not isinstance(value, str):
                    raise ValidationError({name: ['يلزم نص']})
                value = value.strip()
            if isinstance(field, models.BooleanField) and type(value) is not bool:
                raise ValidationError({name: ['يلزم نعم أو لا']})
            if field.is_relation and value is not None:
                identifier = value.pk if isinstance(value, field.remote_field.model) else parse_version(value)
                related = field.remote_field.model._base_manager.filter(pk=identifier).first()
                if not related or (hasattr(related, 'patient_id') and related.patient_id != patient.pk):
                    raise ValidationError({name: ['المرجع لا يخص هذا المريض']})
                if name == 'owner' and old.get('owner') != related.pk and (not related.is_active or not patient.care_team.filter(user=related, ended_at__isnull=True).exists()):
                    raise ValidationError({name: ['المسؤول يجب أن يكون عضواً حالياً في فريق الرعاية']})
                value = related
            if isinstance(field, models.DateField) and not field.is_relation:
                value = field.to_python(value)
            setattr(row, name, value)
        if hasattr(row, 'phone'):
            row.phone = normalize_phone(row.phone) or ''
        if kind == 'identifiers':
            row.value = normalize_identifier(row.value) or ''
            row.issuing_country = row.issuing_country.upper()
            if row.identifier_type == 'national_id' and row.value and not (10 <= len(row.value) <= 12):
                raise ValidationError({'value': ['رقم وطني غير صالح']})
        if kind == 'follow-ups':
            if not row.due_date:
                raise ValidationError({'due_date': ['تاريخ الاستحقاق مطلوب']})
            previous_status = old.get('status', 'pending')
            if previous_status != row.status and previous_status != 'pending':
                raise ValidationError({'status': ['أضف متابعة جديدة بدلاً من إعادة فتح نتيجة مكتملة']})
            if row.status != 'pending' and not row.outcome_reason.strip():
                raise ValidationError({'outcome_reason': ['سبب نتيجة المتابعة مطلوب']})
            if row.status != 'pending' and (not row.pk or previous_status == 'pending'):
                row.completed_at, row.completed_by = timezone.now(), actor
            # A legacy scheduled follow-up is edited through VisitService only.
            if row.legacy_visit_follow_up and (retire or any(name in data for name in ('due_date', 'source_visit', 'status'))):
                raise ValidationError('عدّل متابعة الزيارة من شاشة الزيارة')
            if row.completed_visit_id and row.status != 'completed':
                raise ValidationError({'completed_visit': ['تربط الزيارة المنجزة بمتابعة مكتملة فقط']})
            if row.source_visit_id and row.due_date < row.source_visit.visit_date:
                raise ValidationError({'due_date': ['المتابعة لا تسبق الزيارة']})
        if retire:
            if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
                raise ValidationError({'reason': ['سبب التقاعد مطلوب (حتى 500 محرف)']})
            row.is_active, row.retired_at, row.retired_by, row.retirement_reason = False, timezone.now(), actor, reason.strip()
        elif kind == 'contacts' and row.is_primary:
            # Do not silently demote another contact; user makes that change explicitly.
            if model.objects.filter(patient=patient, is_active=True, is_primary=True).exclude(pk=row.pk).exists():
                raise ValidationError({'is_primary': ['يوجد اتصال أساسي؛ عدّله أولاً']})
        verification_fields = ('identifier_type', 'value', 'issuer', 'issuing_country') if kind == 'identifiers' else (
            'name', 'relationship', 'phone', 'authority_scope', 'evidence', 'valid_from', 'valid_until')
        normalized = record_values(row, fields)
        verification_changed = any(name in normalized and old.get(name) != normalized[name] for name in verification_fields)
        if previous_verification == 'verified' and verification_changed and 'verification' not in data:
            row.verification = 'reported'
        stamp_verification(row, actor, None if verification_changed else previous_verification)
        row.updated_by = actor
        row.full_clean()
        row.save()
        was_primary_identifier = kind == 'identifiers' and old.get('identifier_type') == 'national_id' and old.get('value') == patient.national_id
        new_primary_identifier = kind == 'identifiers' and not patient.national_id and row.identifier_type == 'national_id' and not retire
        if was_primary_identifier or new_primary_identifier:
            patient.national_id = row.value if row.identifier_type == 'national_id' and not retire else ''
            patient.identity_verification = 'reported'
            patient.identity_verified_at = None
            patient.identity_verified_by = None
        new = record_values(row, fields)
        changes = {name: {'before': old.get(name), 'after': value} for name, value in new.items() if old.get(name) != value}
        if retire:
            changes['is_active'] = {'before': True, 'after': False}
        if changes:
            PatientCorrection.objects.create(patient=patient, actor=actor, reason=reason.strip() or ('Record created' if not old else 'Record updated'),
                record_type=kind, record_id=row.pk, changes=changes)
        # Copy only explicit current evidence into the patient summary; never infer a negative from an empty list.
        if kind in {'allergies', 'medications'} and not retire:
            positive = row.status in ({'suspected', 'confirmed'} if kind == 'allergies' else {'active', 'on_hold'})
            if positive:
                setattr(patient, 'allergy_status' if kind == 'allergies' else 'medication_status', 'recorded')
        patient.version += 1
        patient.save(update_fields=['version', 'updated_at', 'allergy_status', 'medication_status', 'national_id', 'identity_verification', 'identity_verified_at', 'identity_verified_by'])
        return row, patient.version
