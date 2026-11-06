from django.template.loader import render_to_string
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from core.pdf_utils import render_pdf_from_html
from core.image_data import validate_embedded_image
from core.exceptions import ConflictError
from apps.settings.services import SettingsService
from core.age import display_year_only_age
from datetime import date
from django.db import transaction
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
        approved_date = date.fromisoformat(revision.snapshot['fields']['visit_date'])
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
            'patient_number': revision.snapshot['patient']['patient_number'],
            'patient_name': revision.snapshot['patient']['name'],
            'patient_age': display_year_only_age(revision.snapshot['patient']['dob_year'], approved_date),
            'patient_gender': revision.snapshot['patient']['gender'] or 'غير محدد',
            'patient_address': patient.permanent_address or 'غير مسجل',
            'patient_national_id': revision.snapshot['patient']['national_id'] or 'غير محدد',
            'visit_date': approved_date.strftime('%d/%m/%Y'),
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
        from django.core.exceptions import PermissionDenied
        from apps.accounts.models import User
        from core.access import require_actor_permission, accessible_visits
        actor = require_actor_permission(User(pk=user_id), 'export_pdf')
        visit = accessible_visits(actor).select_related('patient').filter(pk=visit.pk).first()
        if visit is None:
            raise PermissionDenied('غير مصرح بالوصول إلى الزيارة')
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
        options = snapshot.get('print_options')
        if options:
            from .printing import normalize_print_options, render_preprinted
            options = normalize_print_options(options)
            if options['mode'] == 'preprinted':
                try:
                    return render_preprinted(prescription, options)
                except ValidationError:
                    raise
                except Exception:
                    logger.error('Preprinted prescription rendering failed')
                    return None
            if (options['width_mm'], options['height_mm']) != (210, 297):
                context['paper'] = options
                return render_pdf_from_html(render_to_string('prescriptions/prescription_blank.html', context))
        html = render_to_string('prescriptions/prescription_pdf.html', context)
        pdf = render_pdf_from_html(html)
        return pdf

    def issue_prescription(self, visit, actor, preview_token, signature=None, stamp=None, **options):
        """Render first; issued evidence and audit commit together before consuming preview."""
        from django.core.exceptions import PermissionDenied
        from core.access import require_actor_permission, accessible_visits
        from core.signals import log_action
        from .issuance import record_document
        actor = require_actor_permission(actor, 'export_pdf')
        if actor.role not in {'admin', 'doctor'} or not actor.has_perm('edit_visit'):
            raise PermissionDenied('إصدار المستندات مخصص للطبيب المخول')
        current = accessible_visits(actor).select_related('patient').filter(pk=visit.pk).first()
        if current is None:
            raise PermissionDenied('غير مصرح بالوصول إلى الزيارة')
        snapshot = self.get_preview(preview_token, actor.pk, current)
        if 'print_options' in options:
            from .printing import normalize_print_options
            snapshot = {**snapshot, 'print_options': normalize_print_options(options['print_options']),
                        'issue_date': timezone.localdate().strftime('%d/%m/%Y')}
        pdf = self.generate_prescription_pdf(snapshot, signature, stamp)
        if not isinstance(pdf, bytes) or not pdf:
            return None
        with transaction.atomic():
            record_document(current, actor, 'prescription', snapshot, pdf, signature, stamp)
            log_action(actor.pk, 'generate_prescription', 'Visit', current.pk, {
                'summary': f'Generated prescription from visit version {current.version}',
                'visit_version': current.version, 'template_version': snapshot['template_version'],
            })
            transaction.on_commit(lambda: self.discard_preview(preview_token), robust=True)
        return pdf

    def discard_preview(self, token):
        if token:
            cache.delete(f'prescription-preview:{token}')

    def _calculate_age(self, patient, visit_date=None):
        return display_year_only_age(patient.dob_year, visit_date)
