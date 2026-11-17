from datetime import datetime
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from core.query_utils import apply_ordering
from .models import Invoice


def list_queryset(actor, params, kwargs=None):
    kwargs = kwargs or {}
    user = actor
    qs = Invoice.objects.select_related('patient', 'visit').prefetch_related('lines')
    from core.access import accessible_invoices
    qs = qs.filter(pk__in=accessible_invoices(user).values('pk'))
    status_param = params.get('status')
    if status_param == 'overdue':
        qs = qs.filter(status='issued', due_date__lt=timezone.localdate())
    elif status_param:
        qs = qs.filter(status=status_param)
    date_from = params.get('date_from')
    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            qs = qs.filter(issued_date__gte=date_from_parsed)
        except ValueError:
            raise ValidationError({'date_from': ['صيغة التاريخ يجب أن تكون YYYY-MM-DD']})
    date_to = params.get('date_to')
    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            qs = qs.filter(issued_date__lte=date_to_parsed)
        except ValueError:
            raise ValidationError({'date_to': ['صيغة التاريخ يجب أن تكون YYYY-MM-DD']})
    search = params.get('search', '').strip()
    if search:
        qs = qs.filter(
            Q(invoice_number__icontains=search)
            | Q(patient__first_name__icontains=search)
            | Q(patient__surname__icontains=search)
        )
    return apply_ordering(qs, params, {
        'invoice_number': 'invoice_number', 'patient': 'patient__surname',
        'amount': 'final_amount', 'status': 'status', 'issued_date': 'issued_date',
    })



def visits_for_patient(actor, patient_id):
    from django.shortcuts import get_object_or_404
    from core.access import accessible_patients, accessible_visits
    patient = get_object_or_404(accessible_patients(actor), pk=patient_id)
    return list(accessible_visits(actor).filter(patient=patient).order_by('-visit_date', '-id').values('id', 'visit_date', 'status'))
