"""Bridge the existing visit follow-up into the multi-action patient register."""
from django.utils import timezone
from .models import PatientFollowUp


def sync_visit_follow_up(visit, actor):
    row = PatientFollowUp.objects.filter(source_visit=visit, legacy_visit_follow_up=True, is_active=True).first()
    if not visit.follow_up_date or visit.deleted_at is not None:
        if row:
            row.is_active = False
            row.retired_at, row.retired_by, row.retirement_reason = timezone.now(), actor, 'Follow-up removed from visit'
            row.save()
        return
    if not row:
        row = PatientFollowUp(patient=visit.patient, source_visit=visit, title='متابعة الزيارة',
            due_date=visit.follow_up_date, legacy_visit_follow_up=True, created_by=actor)
    row.due_date = visit.follow_up_date
    row.status = visit.follow_up_outcome
    row.completed_at, row.completed_by = visit.follow_up_completed_at, visit.follow_up_completed_by
    row.updated_by = actor
    if row.status != 'pending':
        row.outcome_reason = 'Visit follow-up outcome: ' + row.status
    row.full_clean()
    row.save()


def accessible_follow_ups(actor):
    from core.access import accessible_patients
    from django.db.models import Q
    return PatientFollowUp.objects.filter(patient__in=accessible_patients(actor), is_active=True).filter(
        Q(source_visit__isnull=True) | Q(source_visit__deleted_at__isnull=True, source_visit__is_active=True))
