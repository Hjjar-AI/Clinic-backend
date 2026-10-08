"""Optional, explicit patient reconciliation; identifiers are never suffixed."""
import hashlib
import json
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction, models
from core.mutation import parse_version, check_mutation
from core.exceptions import ConflictError
from .models import (Patient, PatientCareTeam, PatientDuplicateReview, PatientMerge,
                     PatientIdentifier, PatientContact, PatientDocument)
from .record_services import RECORDS, json_value, require_access


def merge_models():
    from apps.visits.models import Visit
    from apps.appointments.models import Appointment
    from apps.billing.models import Invoice
    return [Visit, Appointment, Invoice, PatientDocument] + [value[0] for value in RECORDS.values()]


def manifest(source):
    return {model._meta.label_lower: list(model._base_manager.filter(patient=source).order_by('pk').values_list('pk', flat=True))
            for model in merge_models()}


def content_digest(source):
    values = {model._meta.label_lower: list(model._base_manager.filter(patient=source).order_by('pk').values()) for model in merge_models()}
    return hashlib.sha256(json.dumps(json_value(values), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class PatientMergeService:
    def preview(self, source, target_id, actor):
        if actor.role != 'admin' or not actor.has_perm('edit_patient') or not actor.has_perm('delete_patient'):
            raise PermissionDenied('الدمج مخصص للمدير المخول')
        target_id = parse_version(target_id)
        target = Patient.objects.filter(pk=target_id).first()
        if target is None:
            raise ValidationError('الملف الباقي غير موجود أو مؤرشف')
        if source.pk == target.pk or source.merged_into_id or target.merged_into_id:
            raise ValidationError('يلزم ملفان منفصلان غير مدمجين')
        require_access(source, actor)
        require_access(target, actor)
        data = {'source': source.pk, 'target': target.pk, 'source_version': source.version,
                'target_version': target.version, 'actor': actor.pk, 'records': manifest(source), 'digest': content_digest(source),
                'team': list(source.care_team.order_by('pk').values_list('pk', 'user_id', 'ended_at'))}
        token = signing.dumps(json_value(data), salt='patient-merge-preview', compress=True)
        return {'token': token, 'source': source.patient_number, 'survivor': target.patient_number,
                'version': source.version, 'target_version': target.version,
                'counts': {key: len(value) for key, value in data['records'].items()},
                'notice': 'Signed snapshots stay unchanged. Current team access is combined; profile fields are not overwritten.'}

    @transaction.atomic
    def merge(self, source, token, reason, actor, expected_version, target_version):
        if actor.role != 'admin' or not actor.has_perm('edit_patient') or not actor.has_perm('delete_patient'):
            raise PermissionDenied('الدمج مخصص للمدير المخول')
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
            raise ValidationError({'reason': ['سبب الدمج مطلوب']})
        try:
            preview = signing.loads(token, salt='patient-merge-preview', max_age=600)
        except (signing.BadSignature, TypeError):
            raise ValidationError('انتهت معاينة الدمج؛ أعد المعاينة')
        if preview.get('actor') != actor.pk or preview.get('source') != source.pk:
            raise ValidationError('معاينة الدمج لا تخص هذا الطلب')
        locked = {row.pk: row for row in Patient.all_objects.select_for_update().filter(pk__in=[source.pk, preview['target']]).order_by('pk')}
        source, target = locked[source.pk], locked.get(preview['target'])
        if not target or source.pk == target.pk or source.merged_into_id or target.merged_into_id:
            raise ValidationError('ملفات الدمج غير صالحة')
        # Archived duplicates may be merged without restoring them.
        if parse_version(expected_version) != source.version or source.version != preview['source_version']:
            raise ConflictError('تغير الملف المصدر؛ أعد المعاينة')
        check_mutation(target, parse_version(target_version))
        if target.version != preview['target_version']:
            raise ConflictError('تغير الملف الباقي؛ أعد المعاينة')
        require_access(source, actor)
        require_access(target, actor)
        for model in merge_models():
            list(model._base_manager.select_for_update().filter(patient=source).order_by('pk'))
        current = manifest(source)
        team = json_value(list(source.care_team.order_by('pk').values_list('pk', 'user_id', 'ended_at')))
        if current != preview['records'] or team != preview['team'] or content_digest(source) != preview['digest']:
            raise ConflictError('تغير محتوى الملف؛ أعد المعاينة')
        before = {'source': json_value({f.name: f.value_from_object(source) for f in source._meta.concrete_fields}),
                  'survivor': json_value({f.name: f.value_from_object(target) for f in target._meta.concrete_fields}),
                  'records': current, 'team': team, 'adjustments': []}
        for model in merge_models():
            for row in model._base_manager.select_for_update().filter(patient=source).order_by('pk'):
                if model == PatientIdentifier and row.is_active and PatientIdentifier.objects.filter(patient=target,
                        is_active=True, identifier_type=row.identifier_type, value=row.value, issuer=row.issuer, issuing_country=row.issuing_country).exists():
                    from django.utils import timezone
                    before['adjustments'].append({'model': model._meta.label_lower, 'id': row.pk, 'field': 'is_active', 'before': True, 'after': False})
                    row.is_active = False
                    row.retired_at, row.retired_by = timezone.now(), actor
                    row.retirement_reason = 'Duplicate identifier retained during patient merge'
                if model == PatientContact and row.is_primary and PatientContact.objects.filter(patient=target, is_active=True, is_primary=True).exists():
                    before['adjustments'].append({'model': model._meta.label_lower, 'id': row.pk, 'field': 'is_primary', 'before': True, 'after': False})
                    row.is_primary = False
                row.patient = target
                if hasattr(row, 'version'):
                    row.version += 1
                row.save()
        from django.utils import timezone
        for member in source.care_team.select_for_update().filter(ended_at__isnull=True).order_by('pk'):
            if member.user.is_active:
                PatientCareTeam.objects.get_or_create(patient=target, user=member.user, ended_at__isnull=True,
                    defaults={'role': member.role, 'assigned_by': actor})
            member.ended_at, member.ended_by, member.removal_reason = timezone.now(), actor, 'Patient merged: ' + reason.strip()[:470]
            member.save()
        # Do not copy mutable demographics over the survivor or fabricate negative summaries.
        if target.patientallergy_records.filter(is_active=True, status__in=['suspected', 'confirmed']).exists():
            target.allergy_status = 'recorded'
        if target.patientmedication_records.filter(is_active=True, status__in=['active', 'on_hold']).exists():
            target.medication_status = 'recorded'
        target.version += 1
        target.save()
        source.merged_into = target
        source.save(update_fields=['merged_into'])
        source.soft_delete(actor, 'Merged into ' + target.patient_number)
        PatientMerge.objects.create(source=source, survivor=target, actor=actor, reason=reason.strip(), manifest=before)
        left, right = sorted([source.pk, target.pk])
        PatientDuplicateReview.objects.update_or_create(patient_id=left, other_patient_id=right,
            defaults={'status': 'merged', 'reason': reason.strip(), 'reviewed_by': actor})
        return target

    @transaction.atomic
    def dismiss(self, patient, other_id, status, reason, actor, version):
        patient = Patient.all_objects.select_for_update().get(pk=patient.pk)
        require_access(patient, actor, write=True)
        check_mutation(patient, version)
        other = Patient.all_objects.filter(pk=parse_version(other_id)).first()
        if other is None:
            raise ValidationError('الملف الآخر غير موجود')
        require_access(other, actor)
        if other.pk == patient.pk or status not in {'dismissed', 'different'}:
            raise ValidationError('قرار مراجعة غير صالح')
        if not isinstance(reason, str) or len(reason) > 500:
            raise ValidationError('سبب غير صالح')
        left, right = sorted([patient.pk, other.pk])
        PatientDuplicateReview.objects.update_or_create(patient_id=left, other_patient_id=right,
            defaults={'status': status, 'reason': reason.strip(), 'reviewed_by': actor})
        patient.version += 1
        patient.save(update_fields=['version', 'updated_at'])
        return patient.version
