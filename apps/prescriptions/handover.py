from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from core.access import accessible_visits
from core.pdf_utils import render_pdf_from_html


def approved_handover(actor, visit_id):
    visit = get_object_or_404(accessible_visits(actor), pk=visit_id)
    revision = visit.revisions.order_by('-number').first()
    if not revision:
        raise ValidationError({'visit': ['لا توجد نسخة معتمدة لهذه الزيارة']})
    source = revision.snapshot
    fields = source['fields']
    return {'visit_id': visit.pk, 'revision_id': revision.pk, 'revision_number': revision.number,
        'signed_at': revision.signed_at, 'patient': source['patient'],
        'clinician': source.get('clinician', {}), 'longitudinal': source.get('longitudinal', {}),
        'medications': source.get('medications', []), 'diagnoses': source.get('diagnoses', []),
        'lab_values': source.get('lab_values', []),
        'fields': {key: fields.get(key) for key in ('visit_date', 'main_complaints', 'history_presenting_complaint',
            'treatment_text', 'follow_up_date', 'suicide_risk_level', 'violence_risk_level', 'firearm_access',
            'level_of_care', 'care_basis', 'clinical_data')}}


def latest_approved_handover(actor, patient_id, exclude_visit=None):
    from core.access import accessible_patients
    from apps.visits.models import VisitRevision
    patient = get_object_or_404(accessible_patients(actor, True), pk=patient_id)
    revisions = VisitRevision.objects.filter(visit__in=accessible_visits(actor), visit__patient=patient)
    if exclude_visit:
        if not str(exclude_visit).isdecimal() or len(str(exclude_visit)) > 9 or int(exclude_visit) < 1:
            raise ValidationError({'exclude_visit': ['معرف غير صالح']})
        revisions = revisions.exclude(visit_id=exclude_visit)
    revision = revisions.order_by('-visit__visit_date', '-signed_at', '-pk').first()
    return approved_handover(actor, revision.visit_id) if revision else None


def handover_pdf(data):
    from django.utils.dateparse import parse_datetime
    labels = {'High': 'مرتفع', 'Moderate': 'متوسط', 'Low': 'منخفض'}
    ack = (data['fields'].get('clinical_data') or {}).get('instruction_acknowledgement') or {}
    if not isinstance(ack, dict):
        ack = {}
    try:
        ack_at = parse_datetime(ack['explained_at']) if isinstance(ack.get('explained_at'), str) else None
    except ValueError:
        ack_at = None
    return render_pdf_from_html(render_to_string('prescriptions/handover.html', {
        'data': data, 'suicide_label': labels.get(data['fields'].get('suicide_risk_level'), 'غير مقيم'),
        'violence_label': labels.get(data['fields'].get('violence_risk_level'), 'غير مقيم'),
        'recipient_label': {'patient': 'المريض', 'representative': 'المرافق / الممثل', 'both': 'كلاهما'}.get(ack.get('recipient'), 'غير مسجل'),
        'ack_at': ack_at,
        'allergy_label': {'unknown': 'غير معروف', 'none_known': 'لا توجد حساسية معروفة',
            'recorded': 'حساسيات مسجلة'}.get(data.get('longitudinal', {}).get('allergy_status'), 'غير معروف'),
    }))
