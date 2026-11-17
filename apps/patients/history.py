"""Clinical history is projected from approved snapshots when available."""
from django.db.models import OuterRef, Subquery, CharField
from django.db.models.functions import Coalesce, Cast
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from core.access import accessible_visits
from core.collections import offset_page
from apps.visits.models import VisitRevision
from apps.visits.revisions import latest_approved_revisions, order_by_approved_date


def risk_history(patient, actor, params):
    revisions = order_by_approved_date(latest_approved_revisions(accessible_visits(actor).filter(patient=patient)))
    rows, total, limit, offset = offset_page(revisions, params)
    items = []
    for row in rows:
        fields = row.snapshot.get('fields', {})
        items.append({'visit_id': row.visit_id, 'revision_id': row.pk, 'revision_number': row.number,
            'signed_at': row.signed_at, **{key: fields.get(key) for key in (
                'visit_date', 'suicide_risk_level', 'violence_risk_level', 'firearm_access')}})
    return {'items': items, 'meta': {'pagination': 'offset', 'total': total, 'per_page': limit, 'offset': offset}}


def timeline(patient, actor, params):
    latest = VisitRevision.objects.filter(visit_id=OuterRef('pk')).order_by('-number')
    approved_date = latest.annotate(date_text=KeyTextTransform('visit_date', KeyTransform('fields', 'snapshot'))).values('date_text')[:1]
    visits = accessible_visits(actor).filter(patient=patient).annotate(
        history_date=Coalesce(Subquery(approved_date, output_field=CharField()), Cast('visit_date', CharField()))
    ).order_by('-history_date', '-pk')
    rows, total, limit, offset = offset_page(visits, params)
    latest_rows = {row.visit_id: row for row in latest_approved_revisions(accessible_visits(actor).filter(pk__in=[v.pk for v in rows]))}
    items = []
    for visit in rows:
        revision = latest_rows.get(visit.pk)
        fields = revision.snapshot.get('fields', {}) if revision else {}
        items.append({'id': visit.pk, 'visit_date': fields.get('visit_date', visit.visit_date),
            'main_complaints': fields.get('main_complaints', visit.main_complaints),
            'approval': 'approved' if revision else 'working', 'status': visit.status,
            'revision_number': revision.number if revision else None,
            'signed_at': revision.signed_at if revision else None})
    return {'items': items, 'meta': {'pagination': 'offset', 'total': total, 'per_page': limit, 'offset': offset}}


def correction_history(patient, actor, params):
    from .record_services import require_access, history_patient_ids, CLINICAL_KINDS
    from .models import PatientCorrection, PatientMerge
    from django.db.models import Q
    from django.core.exceptions import ValidationError
    require_access(patient, actor)
    history_ids = history_patient_ids(patient)
    rows = PatientCorrection.objects.filter(patient_id__in=history_ids).select_related('actor', 'patient').order_by('-created_at', '-pk')
    merges = PatientMerge.objects.filter(Q(source_id__in=history_ids) | Q(survivor_id__in=history_ids)).select_related('actor', 'source', 'survivor').order_by('-created_at', '-pk')
    if not actor.has_perm('view_visits'):
        rows = rows.exclude(record_type__in=CLINICAL_KINDS | {'clinical-profile'})
    try:
        offset = max(0, int(params.get('offset', 0)))
        limit = max(1, min(int(params.get('per_page', 100)), 200))
    except (TypeError, ValueError):
        raise ValidationError('إزاحة غير صالحة')
    return {'items': [{'id': row.pk, 'actor': row.actor.full_name or row.actor.username,
        'reason': row.reason, 'record_type': row.record_type, 'record_id': row.record_id, 'patient_number': row.patient.patient_number,
        'changes': row.changes, 'created_at': row.created_at} for row in rows[offset:offset + limit]],
        'total': rows.count(), 'offset': offset, 'limit': limit, 'merges': [{'id': event.pk, 'source': event.source.patient_number,
            'survivor': event.survivor.patient_number, 'actor': event.actor.full_name or event.actor.username,
            'reason': event.reason, 'created_at': event.created_at} for event in merges[:100]]}


def team_candidates():
    from apps.accounts.models import User
    rows = User.objects.filter(is_active=True).order_by('full_name', 'id')
    return [{'id': user.pk, 'full_name': user.full_name or user.username, 'role': user.role} for user in rows]
