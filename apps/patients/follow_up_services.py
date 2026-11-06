"""PatientFollowUp owns each occurrence; visits only select their current occurrence."""
from datetime import date
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import Patient, PatientFollowUp
from core.follow_up import follow_up_transition

FOLLOW_UP_FIELDS = ['title', 'owner', 'due_date', 'method', 'status', 'source_visit', 'appointment',
                    'completed_visit', 'notes', 'outcome_reason']


def follow_up_data(row):
    if row is None:
        return None
    fields = ['id', *FOLLOW_UP_FIELDS, 'is_active', 'outcome_at', 'outcome_by', 'completed_revision']
    result = {}
    for name in fields:
        value = getattr(row, row._meta.get_field(name).attname)
        result[name] = value.isoformat() if hasattr(value, 'isoformat') else value
    return result


def validate_follow_up(row, previous, actor, linked_visits):
    if not row.due_date:
        raise ValidationError({'due_date': ['تاريخ الاستحقاق مطلوب']})
    previous_status = previous.get('status', 'pending')
    follow_up_transition(previous_status, row.status)
    if previous_status != 'pending':
        for name in ('due_date', 'method', 'outcome_reason', 'completed_visit', 'source_visit', 'appointment'):
            field = row._meta.get_field(name)
            current = getattr(row, field.attname)
            current = current.isoformat() if hasattr(current, 'isoformat') else current
            if previous.get(name) != current:
                raise ValidationError({'status': ['نتيجة المتابعة محفوظة؛ أضف متابعة جديدة']})
    if linked_visits and previous.get('source_visit') != row.source_visit_id:
        raise ValidationError({'source_visit': ['لا يمكن تغيير مصدر متابعة مرتبطة بخطة زيارة']})
    if row.status != 'pending' and not row.outcome_reason.strip():
        raise ValidationError({'outcome_reason': ['سبب نتيجة المتابعة مطلوب']})
    if row.status != 'pending' and (not row.pk or previous_status == 'pending'):
        row.outcome_at, row.outcome_by = timezone.now(), actor
        row.completed_revision = (row.completed_visit.revisions.order_by('-number').first()
                                  if row.completed_visit_id else None)
    if row.completed_visit_id and row.status != 'completed':
        raise ValidationError({'completed_visit': ['تربط الزيارة المنجزة بمتابعة مكتملة فقط']})
    if row.source_visit_id and row.due_date < row.source_visit.visit_date:
        raise ValidationError({'due_date': ['المتابعة لا تسبق الزيارة']})
    for visit in linked_visits:
        if row.due_date < visit.visit_date:
            raise ValidationError({'due_date': ['المتابعة لا تسبق الزيارة']})


@transaction.atomic
def set_visit_follow_up(visit, plan, actor, action='edit_visit'):
    """Called inside the patient/visit lock; there is no mirrored visit state."""
    from .record_services import PatientRecordService
    record_service = PatientRecordService()
    patient = Patient.all_objects.select_for_update().get(pk=visit.patient_id)
    current = visit.follow_up
    if plan is not None and (not isinstance(plan, dict) or set(plan) - {'due_date', 'method', 'reason'}):
        raise ValidationError({'follow_up_input': ['خطة متابعة غير صالحة']})
    reason = (plan or {}).get('reason', '')
    if plan is None:
        if current is None:
            return
        # Clearing a pending plan retires its occurrence; terminal history remains.
        raise ValidationError({'follow_up_input': ['أرسل سبب إزالة المتابعة مع تاريخ استحقاق فارغ']})
    if not isinstance(reason, str) or len(reason.strip()) > 500:
        raise ValidationError({'follow_up_input': ['يلزم سبب نصي لا يتجاوز 500 محرف']})
    reason = reason.strip()
    raw_due_date = plan.get('due_date')
    if raw_due_date is not None and not isinstance(raw_due_date, (str, date)):
        raise ValidationError({'follow_up_input': ['تاريخ متابعة غير صالح']})
    due_date = PatientFollowUp._meta.get_field('due_date').to_python(raw_due_date) if raw_due_date else None
    method = plan.get('method', '')
    if method is None:
        method = ''
    if not isinstance(method, str):
        raise ValidationError({'follow_up_input': ['نوع متابعة غير صالح']})
    method = method.strip()
    if method and method not in dict(PatientFollowUp.METHOD_CHOICES):
        raise ValidationError({'follow_up_input': ['نوع متابعة غير صالح']})
    if due_date is None:
        if current is None:
            if method:
                raise ValidationError({'follow_up_input': ['تاريخ المتابعة مطلوب عند تحديد نوعها']})
            return
        if not reason:
            raise ValidationError({'follow_up_input': ['سبب إزالة المتابعة مطلوب']})
        if current.status == 'pending':
            record_service.save(patient, 'follow-ups', {}, actor, patient.version,
                                current.pk, retire=True, reason=reason, _visit_action=action)
        else:
            from .models import PatientCorrection
            PatientCorrection.objects.create(patient=patient, actor=actor, reason=reason,
                record_type='follow-ups', record_id=current.pk,
                changes={'planned_visit': {'before': visit.pk, 'after': None}})
            patient.version += 1
            patient.save(update_fields=['version', 'updated_at'])
        visit.follow_up = None
        visit.save(update_fields=['follow_up'])
        visit.refresh_from_db(fields=['version', 'follow_up'])
        return
    if due_date < visit.visit_date:
        raise ValidationError({'follow_up_input': ['المتابعة لا تسبق الزيارة']})
    if current and current.due_date == due_date and current.method == method:
        return
    if current and not reason:
        raise ValidationError({'follow_up_input': ['سبب تغيير المتابعة مطلوب']})
    if current and current.status == 'pending':
        row, _ = record_service.save(patient, 'follow-ups', {'due_date': due_date, 'method': method},
                                    actor, patient.version, current.pk, reason=reason, _visit_action=action)
    else:
        row, _ = record_service.save(patient, 'follow-ups', {'title': 'متابعة الزيارة', 'due_date': due_date,
                                    'method': method, 'source_visit': visit}, actor, patient.version,
                                    reason=reason, _visit_action=action)
    visit.follow_up = row
    visit.save(update_fields=['follow_up'])
    visit.refresh_from_db(fields=['version', 'follow_up'])


def accessible_follow_ups(actor):
    from core.access import accessible_patients
    return PatientFollowUp.objects.filter(patient__in=accessible_patients(actor), is_active=True).filter(
        Q(source_visit__isnull=True) | Q(source_visit__deleted_at__isnull=True, source_visit__is_active=True))
