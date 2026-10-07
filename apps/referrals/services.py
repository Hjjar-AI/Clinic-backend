from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils import timezone

from apps.settings.services import SettingsService
from apps.visits.models import Visit
from core.exceptions import ConflictError
from core.pdf_utils import render_pdf_from_html
from core.signals import log_action


class ReferralService:
    TEMPLATE_VERSION = 'referral-v1'

    def get_visit(self, visit_id):
        return Visit.objects.select_related('patient', 'author').prefetch_related(
            'visit_diagnoses__diagnosis',
            'visit_medications__medication',
        ).filter(id=visit_id).first()

    def build_snapshot(self, visit, requested_version, referral_reason):
        from apps.prescriptions.issuance import finalized_revision
        revision = finalized_revision(visit)

        try:
            requested_version = int(requested_version)
        except (TypeError, ValueError):
            raise ValidationError({
                'version': ['رقم إصدار الزيارة مطلوب لإنشاء خطاب مطابق للمعاينة'],
            })
        if requested_version != visit.version:
            raise ConflictError(
                'تغيرت الزيارة بعد المعاينة؛ راجع البيانات المحدثة قبل إنشاء خطاب التحويل'
            )

        referral_reason = str(referral_reason or '').strip()
        if not referral_reason:
            raise ValidationError({'reason': ['أدخل سبب التحويل قبل إنشاء الخطاب']})
        if len(referral_reason) > 2000:
            raise ValidationError({'reason': ['الحد الأقصى 2000 محرف']})

        generated_at = timezone.localtime()
        return {
            'clinic': SettingsService().get_clinic_info(),
            'revision_id': revision.pk,
            'visit_id': visit.id,
            'visit_version': visit.version,
            'template_version': self.TEMPLATE_VERSION,
            'patient_name': revision.snapshot['patient']['name'],
            'visit_date': visit.visit_date.strftime('%d/%m/%Y'),
            'main_complaints': revision.snapshot['fields']['main_complaints'] or '',
            'diagnoses': revision.snapshot['diagnoses'],
            'medications': revision.snapshot['medications'],
            # Referral documents deliberately exclude unrestricted doctor notes.
            'referral_reason': referral_reason,
            'clinician': revision.snapshot['clinician']['name'],
            'generated_at': generated_at.strftime('%Y-%m-%d %H:%M'),
            'timezone': settings.TIME_ZONE,
            'generator': 'Clinic referral renderer',
        }

    def generate_pdf(self, visit, requested_version, referral_reason, user_id):
        snapshot = self.build_snapshot(visit, requested_version, referral_reason)
        clinic_info = snapshot['clinic']
        html = render_to_string('referral_letter.html', {
            'data': snapshot,
            'clinic': {
                'name': clinic_info['clinic_name'],
                'address': clinic_info['clinic_address'],
                'phone': clinic_info['clinic_phone'],
            },
        })
        pdf = render_pdf_from_html(html)
        if pdf:
            from apps.accounts.models import User
            from apps.prescriptions.issuance import record_document
            record_document(visit, User.objects.get(pk=user_id), 'referral', snapshot, pdf)
            log_action(user_id, 'generate_referral', 'Visit', visit.id, {
                'summary': f'Generated referral from visit version {visit.version}',
                'visit_version': visit.version,
                'template_version': snapshot['template_version'],
            })
        return pdf
