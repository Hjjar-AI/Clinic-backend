from datetime import datetime
from django.core.exceptions import ValidationError
from django.db.models import Q
from core.query_utils import apply_ordering
from .models import Visit


def list_queryset(actor, params, kwargs=None):
    kwargs = kwargs or {}
    user = actor
    qs = Visit.objects.select_related(
        'patient', 'author', 'signed_by', 'supervisor', 'follow_up',
    ).prefetch_related(
        'visit_diagnoses__diagnosis',
        'visit_medications__medication',
        'scale_responses',
    )
    from core.access import accessible_visits
    qs = qs.filter(pk__in=accessible_visits(user).values('pk'))
    status_param = params.get('status')
    if status_param:
        qs = qs.filter(status=status_param)
    clinical_status = params.get('clinical_status')
    if clinical_status:
        qs = qs.filter(clinical_status=clinical_status)
    date_from = params.get('date_from')
    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            qs = qs.filter(visit_date__gte=date_from_parsed)
        except ValueError:
            raise ValidationError({'date_from': ['صيغة التاريخ يجب أن تكون YYYY-MM-DD']})
    date_to = params.get('date_to')
    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            qs = qs.filter(visit_date__lte=date_to_parsed)
        except ValueError:
            raise ValidationError({'date_to': ['صيغة التاريخ يجب أن تكون YYYY-MM-DD']})
    patient_pk = kwargs.get('patient_pk')
    if patient_pk:
        qs = qs.filter(patient_id=patient_pk)
    search = params.get('search', '').strip()
    if search:
        qs = qs.filter(
            Q(patient__first_name__icontains=search)
            | Q(patient__surname__icontains=search)
            | Q(main_complaints__icontains=search)
        )
    return apply_ordering(qs, params, {
        'date': 'visit_date', 'status': 'status', 'clinical_status': 'clinical_status',
        'patient': 'patient__surname',
        'created_at': 'created_at', 'updated_at': 'updated_at',
    }, default='-visit_date')



def revision_history(visit, params):
    from core.collections import offset_page
    rows, total, limit, offset = offset_page(visit.revisions.select_related('signer').order_by('-number'), params)
    return {'items': [{'id': row.pk, 'number': row.number, 'snapshot': row.snapshot,
        'signer_id': row.signer_id, 'signer_name': row.signer.full_name or row.signer.username,
        'signed_at': row.signed_at, 'reason': row.reason} for row in rows],
        'meta': {'pagination': 'offset', 'total': total, 'per_page': limit, 'offset': offset}}


def issued_documents(visit, actor, params):
    from apps.prescriptions.models import IssuedDocument
    from core.collections import offset_page
    rows = IssuedDocument.objects.filter(revision__visit=visit).select_related('revision', 'issued_by').order_by('-issued_at', '-id')
    if not actor.has_perm('export_pdf'):
        rows = rows.exclude(document_type='prescription')
    if not actor.has_perm('view_referrals'):
        rows = rows.exclude(document_type='referral')
    page, total, limit, offset = offset_page(rows, params)
    return {'items': [{'id': row.pk, 'document_type': row.document_type, 'revision_id': row.revision_id,
        'revision_number': row.revision.number, 'issued_by_id': row.issued_by_id,
        'issued_by_name': row.issued_by.full_name or row.issued_by.username,
        'issued_at': row.issued_at, 'checksum': row.checksum} for row in page],
        'meta': {'pagination': 'offset', 'total': total, 'per_page': limit, 'offset': offset}}
