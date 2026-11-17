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
