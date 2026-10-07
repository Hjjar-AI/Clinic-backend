from django.template.loader import render_to_string
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from apps.visits.models import Visit
from .models import PrescriptionSignature
from core.pdf_utils import render_pdf_from_html
from core.image_data import validate_embedded_image
from core.exceptions import ConflictError
from apps.settings.services import SettingsService
from datetime import date
import logging
import secrets
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

class PrescriptionService:
    TEMPLATE_VERSION = 'prescription-v1'
    PREVIEW_TTL_SECONDS = 15 * 60

    def build_snapshot(self, visit):
        from .issuance import finalized_revision
        revision = finalized_revision(visit)
        patient = visit.patient
        medications = revision.snapshot['medications']

        invalid = [
            index + 1 for index, med in enumerate(medications)
            if not str(med.get('name', '')).strip()
            or not str(med.get('dosage', '')).strip()
            or not str(med.get('schedule', '')).strip()
        ]
        if invalid:
            raise ValidationError({
                'medications': [f'بيانات الاسم والجرعة والتعليمات ناقصة للأدوية: {invalid}']
            })

        return {
            'clinic': SettingsService().get_clinic_info(),
            'revision_id': revision.pk,
            'patient_version': patient.version,
            'visit_id': visit.id,
            'visit_version': visit.version,
            'template_version': self.TEMPLATE_VERSION,
            'patient_id': patient.id,
            'patient_name': revision.snapshot['patient']['name'],
            'patient_age': visit.visit_date.year - revision.snapshot['patient']['dob_year'] if revision.snapshot['patient']['dob_year'] else 'غير محدد',
            'patient_gender': revision.snapshot['patient']['gender'] or 'غير محدد',
            'patient_national_id': revision.snapshot['patient']['national_id'] or 'غير محدد',
            'visit_date': visit.visit_date.strftime('%d/%m/%Y'),
            'medications': [
                {
                    'name': med.get('name', ''),
                    'dosage': med.get('dosage', ''),
                    'brand': med.get('brand', ''),
                    'instructions': med.get('schedule', 'حسب تعليمات الطبيب'),
                    'controlled': bool(med.get('controlled')),
                }
                for med in medications
            ],
            'diagnoses': revision.snapshot['diagnoses'],
            'doctor_name': revision.snapshot['clinician']['name'],
            'generated_at': timezone.localtime().strftime('%Y-%m-%d %H:%M'),
            'timezone': settings.TIME_ZONE,
            'generator': 'Clinic prescription renderer',
        }

    def create_preview(self, visit, user_id):
        snapshot = self.build_snapshot(visit)
        token = secrets.token_urlsafe(24)
        cache.set(
            f'prescription-preview:{token}',
            {'user_id': user_id, 'snapshot': snapshot},
            timeout=self.PREVIEW_TTL_SECONDS,
        )
        return {'preview_token': token, **snapshot}

    def get_preview(self, token, user_id, visit):
        preview = cache.get(f'prescription-preview:{token}') if token else None
        if not preview or preview.get('user_id') != user_id:
            raise ValidationError({
                'preview_token': ['المعاينة مطلوبة أو انتهت صلاحيتها؛ افتح صفحة الوصفة مجدداً'],
            })
        snapshot = preview.get('snapshot') or {}
        if snapshot.get('visit_id') != visit.id:
            raise ValidationError({'preview_token': ['المعاينة لا تخص هذه الزيارة']})
        if snapshot.get('template_version') != self.TEMPLATE_VERSION:
            raise ConflictError('تغير قالب الوصفة؛ أعد فتح المعاينة قبل الإنشاء')
        if snapshot.get('visit_version') != visit.version:
            raise ConflictError('تغيرت الزيارة بعد المعاينة؛ راجع البيانات المحدثة قبل إنشاء الوصفة')
        from .issuance import finalized_revision
        if finalized_revision(visit).pk != snapshot.get('revision_id') or visit.patient.version != snapshot.get('patient_version'):
            raise ConflictError('تغيرت بيانات الزيارة أو المريض؛ أعد المعاينة')
        return snapshot

    def generate_prescription_pdf(self, snapshot, signature_data=None, stamp_data=None):
        validate_embedded_image(signature_data, 'signature', required=True)
        validate_embedded_image(stamp_data, 'stamp')
        prescription = {
            **snapshot,
            'signature_data': signature_data,
            'stamp_data': stamp_data,
        }
        clinic_info = snapshot['clinic']
        context = {
            'prescription': prescription,
            'clinic': {
                'name': clinic_info['clinic_name'],
                'address': clinic_info['clinic_address'],
                'phone': clinic_info['clinic_phone'],
            }
        }
        html = render_to_string('prescriptions/prescription_pdf.html', context)
        pdf = render_pdf_from_html(html)
        return pdf

    def discard_preview(self, token):
        if token:
            cache.delete(f'prescription-preview:{token}')

    def _calculate_age(self, patient, visit_date=None):
        if not patient.dob_year:
            return 'غير محدد'
        year = visit_date.year if visit_date else date.today().year
        return year - patient.dob_year

    def save_signature(self, user, visit_id, signature_data, stamp_data):
        validate_embedded_image(signature_data, 'signature', required=True)
        validate_embedded_image(stamp_data, 'stamp')
        sig, created = PrescriptionSignature.objects.get_or_create(
            user=user, visit_id=visit_id, signature_data=signature_data, stamp_data=stamp_data
        )
        return sig
