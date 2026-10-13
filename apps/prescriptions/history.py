"""Read-only access to issued prescriptions and their patient handouts."""
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from core.access import accessible_patients, accessible_visits
from core.pdf_utils import render_pdf_from_html
from .models import IssuedDocument


def prescriptions_for(actor):
    return IssuedDocument.objects.filter(document_type='prescription',
        revision__visit__in=accessible_visits(actor)).select_related('revision')


def prescription_document(actor, document_id):
    return get_object_or_404(prescriptions_for(actor), pk=document_id)


def prescription_history(actor, patient_id, params):
    patient = get_object_or_404(accessible_patients(actor, True), pk=patient_id)
    raw = params.get('offset', '0')
    if not isinstance(raw, str) or not raw.isdecimal() or len(raw) > 9:
        raise ValidationError({'offset': ['أدخل إزاحة صحيحة غير سالبة']})
    offset, limit = int(raw), 20
    documents = prescriptions_for(actor).filter(revision__visit__patient=patient).order_by('-issued_at', '-id')
    if params.get('visit_id'):
        raw_visit = params['visit_id']
        if not raw_visit.isdecimal() or len(raw_visit) > 9 or int(raw_visit) < 1:
            raise ValidationError({'visit_id': ['معرف الزيارة غير صالح']})
        visit = get_object_or_404(accessible_visits(actor), pk=int(raw_visit), patient=patient)
        documents = documents.filter(revision__visit=visit)
    total = documents.count()
    items = []
    for document in documents[offset:offset + limit]:
        snapshot = document.snapshot
        items.append({
            'id': document.pk, 'issued_at': document.issued_at, 'checksum': document.checksum,
            'revision_id': document.revision_id, 'revision_number': document.revision.number,
            'visit_id': document.revision.visit_id, 'visit_date': snapshot.get('visit_date', ''),
            'patient_name': snapshot.get('patient_name', ''), 'doctor_name': snapshot.get('doctor_name', ''),
            'medication_count': len(snapshot.get('medications') or []),
            'print_options': snapshot.get('print_options') or {'mode': 'blank', 'width_mm': 210, 'height_mm': 297},
        })
    return {'items': items, 'total': total, 'offset': offset, 'limit': limit}


def render_patient_instructions(document):
    return render_pdf_from_html(render_to_string('prescriptions/patient_instructions.html', {
        'prescription': document.snapshot, 'document_id': document.pk,
        'issued_at': document.issued_at, 'revision_number': document.revision.number,
    }))
