# backend/apps/exports/base.py
from django.template.loader import render_to_string
from core.pdf_utils import render_pdf_from_html
from apps.reports.services import StatisticsService
from .word_generator import export_patient_to_word
from apps.settings.services import SettingsService
from datetime import datetime
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.query_utils import apply_ordering
from core.lifecycle import STATUS_PRESENTATION

class BaseExportService:
    def __init__(self):
        self.stats = StatisticsService()
        self.settings_service = SettingsService()

    def get_clinic_info(self):
        return {
            'name': self.settings_service.get_setting('clinic_name', 'عيادة الإتزان'),
            'address': self.settings_service.get_setting('clinic_address', ''),
            'phone': self.settings_service.get_setting('clinic_phone', ''),
        }

    def render_to_string(self, template, context):
        return render_to_string(template, context)

    def render_pdf(self, html):
        return render_pdf_from_html(html)

    def filtered_visits(self, user, filters=None):
        filters = filters or {}
        visits = self.stats.get_accessible_visits(user)
        if filters.get('status'):
            visits = visits.filter(status=filters['status'])
        if filters.get('clinical_status'):
            visits = visits.filter(clinical_status=filters['clinical_status'])
        for key, lookup in (('date_from', 'visit_date__gte'), ('date_to', 'visit_date__lte')):
            raw = filters.get(key)
            if raw:
                try:
                    value = datetime.strptime(raw, '%Y-%m-%d').date()
                except (TypeError, ValueError):
                    raise ValidationError({key: ['صيغة التاريخ يجب أن تكون YYYY-MM-DD']})
                visits = visits.filter(**{lookup: value})
        search = str(filters.get('search', '')).strip()
        if search:
            visits = visits.filter(
                Q(patient__first_name__icontains=search)
                | Q(patient__surname__icontains=search)
                | Q(main_complaints__icontains=search)
            )
        return apply_ordering(visits, filters, {
            'date': 'visit_date', 'status': 'status',
            'clinical_status': 'clinical_status', 'patient': 'patient__surname',
            'created_at': 'created_at', 'updated_at': 'updated_at',
        }, default='-visit_date')

    @staticmethod
    def stamp_response(response):
        response['X-Report-Generated-At'] = timezone.now().isoformat()
        response['X-Report-Timezone'] = timezone.get_current_timezone_name()
        return response

    def build_patient_report_data(self, patient):
        visits_data = []
        visits = patient.visits.filter(deleted_at__isnull=True).prefetch_related(
            'visit_diagnoses__diagnosis', 'visit_medications__medication', 'scale_responses'
        ).order_by('-visit_date')
        for visit in visits:
            visit_data = {
                'date': visit.visit_date.strftime('%d/%m/%Y') if visit.visit_date else '',
                'age': self._calculate_age(patient, visit.visit_date),
                'main_complaints': visit.main_complaints or '',
                'history_presenting_complaint': visit.history_presenting_complaint or '',
                'diagnoses': [diag.get('arabic_name') or diag.get('name', '') for diag in visit.get_diagnoses()],
                'status': STATUS_PRESENTATION['visit'].get(visit.status, {}).get('label', visit.status or 'غير محدد'),
                'clinical_status': visit.clinical_status or 'غير محدد',
                'accompanied_by': visit.accompanied_by or '',
                'companion_relation': visit.companion_relation or '',
                'lab_values': visit.get_lab_values(),
                'medications': visit.get_medications(),
                'treatment_text': visit.treatment_text or '',
                'doctor_notes': visit.doctor_notes or '',
                'scale_responses': self._scale_response_data(visit),
                'risk_assessment': {
                    'suicide_level': visit.suicide_risk_level,
                    'violence_level': visit.violence_risk_level,
                    'firearm_access': 'غير مقيم' if visit.firearm_access is None else 'نعم' if visit.firearm_access else 'لا',
                    'detailed': visit.clinical_data.get('risk_notes', '') if visit.clinical_data else '',
                },
                'treatment_plan': {
                    'level_of_care': visit.level_of_care or 'غير محدد', 'care_basis': visit.care_basis,
                    'follow_up_type': visit.follow_up_type or 'غير محدد',
                    'detailed': visit.clinical_data.get('plan_details', '') if visit.clinical_data else '',
                },
                'administrative': {
                    'date_signed': visit.date_signed.strftime('%d/%m/%Y') if visit.date_signed else '',
                    'signed_by': visit.signed_by.full_name if visit.signed_by else '',
                    'supervisor': visit.supervisor.full_name if visit.supervisor else '',
                    'diagnosis_discussed': 'غير مسجل' if visit.diagnosis_discussed is None else 'نعم' if visit.diagnosis_discussed else 'لا',
                    'plan_discussed': 'غير مسجل' if visit.plan_discussed is None else 'نعم' if visit.plan_discussed else 'لا',
                },
                'formulation': {
                    'predisposing': visit.clinical_data.get('formulation', {}).get('predisposing', ''),
                    'precipitating': visit.clinical_data.get('formulation', {}).get('precipitating', ''),
                    'perpetuating': visit.clinical_data.get('formulation', {}).get('perpetuating', ''),
                    'protective': visit.clinical_data.get('formulation', {}).get('protective', ''),
                },
                'mse': visit.clinical_data.get('mse', ''),
            }
            visits_data.append(visit_data)

        report_data = {
            'patient_id': patient.id,
            'patient_name': patient.get_full_name(),
            'dob_year': patient.dob_year,
            'gender': patient.gender or 'غير محدد',
            'national_id': patient.national_id or 'غير محدد',
            'phone': patient.phone or 'غير محدد',
            'address': patient.permanent_address or 'غير محدد',
            'emergency_contact': f"{patient.emergency_contact_name or ''} ({patient.emergency_contact_relation or ''}) - {patient.emergency_contact_phone or ''}",
            'registration_date': patient.registration_date.strftime('%d/%m/%Y') if patient.registration_date else 'غير محدد',
            'patient_number': patient.patient_number,
            'allergy_status': patient.get_allergy_status_display(),
            'medication_status': patient.get_medication_status_display(),
            'allergies': list(patient.patientallergy_records.filter(is_active=True)),
            'ongoing_medications': list(patient.patientmedication_records.filter(is_active=True)),
            'contacts': list(patient.patientcontact_records.filter(is_active=True)),
            'family_history': patient.family_history or 'غير مسجل',
            'important_notes': patient.important_notes or 'غير مسجل',
            'visits': visits_data,
            'generated_at': timezone.localtime().strftime('%d/%m/%Y %H:%M'),
            'timezone': timezone.get_current_timezone_name(),
        }
        return report_data

    def build_visit_pdf_data(self, visit):
        data = {
            'visit_id': visit.id,
            'visit_version': visit.version,
            'visit_date': visit.visit_date.strftime('%d/%m/%Y') if visit.visit_date else '',
            'generated_at': timezone.localtime().strftime('%d/%m/%Y %H:%M'),
            'timezone': timezone.get_current_timezone_name(),
            'patient_name': visit.patient.get_full_name(),
            'main_complaints': visit.main_complaints or '',
            'history_presenting_complaint': visit.history_presenting_complaint or '',
            'diagnoses': [diag.get('arabic_name') or diag.get('name', '') for diag in visit.get_diagnoses()],
            'treatment_text': visit.treatment_text or '',
            'medications': visit.get_medications(),
            'lab_values': visit.get_lab_values(),
            'status': STATUS_PRESENTATION['visit'].get(visit.status, {}).get('label', visit.status or 'غير محدد'),
            'clinical_status': visit.clinical_status or 'غير محدد',
            'accompanied_by': visit.accompanied_by or '',
            'companion_relation': visit.companion_relation or '',
            'doctor_notes': visit.doctor_notes or '',
            'scale_responses': self._scale_response_data(visit),
            'risk_assessment': {
                'suicide_level': visit.suicide_risk_level,
                'violence_level': visit.violence_risk_level,
                'firearm_access': 'غير مقيم' if visit.firearm_access is None else 'نعم' if visit.firearm_access else 'لا',
            },
            'treatment_plan': {
                'level_of_care': visit.level_of_care or 'غير محدد', 'care_basis': visit.care_basis,
                'follow_up_type': visit.follow_up_type or 'غير محدد',
            },
            'administrative': {
                'date_signed': visit.date_signed.strftime('%d/%m/%Y') if visit.date_signed else '',
                'signed_by': visit.signed_by.full_name if visit.signed_by else '',
                'supervisor': visit.supervisor.full_name if visit.supervisor else '',
                'diagnosis_discussed': 'غير مسجل' if visit.diagnosis_discussed is None else 'نعم' if visit.diagnosis_discussed else 'لا',
                'plan_discussed': 'غير مسجل' if visit.plan_discussed is None else 'نعم' if visit.plan_discussed else 'لا',
                'author': visit.author.full_name if visit.author else '',
            },
            'formulation': {
                'predisposing': visit.clinical_data.get('formulation', {}).get('predisposing', ''),
                'precipitating': visit.clinical_data.get('formulation', {}).get('precipitating', ''),
                'perpetuating': visit.clinical_data.get('formulation', {}).get('perpetuating', ''),
                'protective': visit.clinical_data.get('formulation', {}).get('protective', ''),
            },
            'mse': visit.clinical_data.get('mse', ''),
        }
        return data

    @staticmethod
    def _scale_response_data(visit):
        scales = []
        for response in visit.scale_responses.all():
            values = response.responses_json or {}
            answers = []
            for field in values.get('__definition', []):
                key = str(field.get('id'))
                answers.append({
                    'label': field.get('label', ''),
                    'value': values.get(key, ''),
                })
            scales.append({
                'name': response.scale_name_snapshot,
                'score': values.get('__score'),
                'answers': answers,
            })
        return scales

    def _calculate_age(self, patient, visit_date=None):
        if not patient.dob_year:
            return 'غير محدد'
        year = visit_date.year if visit_date else datetime.now().year
        return year - patient.dob_year

    def export_patient_to_word(self, patient, clinic_info):
        return export_patient_to_word(patient, clinic_info)
