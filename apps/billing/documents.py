from django.utils import timezone
from django.template.loader import render_to_string
from core.pdf_utils import render_pdf_from_html
from core.signals import log_action
from core.lifecycle import STATUS_PRESENTATION
from apps.settings.services import SettingsService


def invoice_pdf(invoice, actor):
    clinic_info = invoice.issue_snapshot.get('clinic') or SettingsService().get_clinic_info()
    clinic = {
        'name': clinic_info.get('clinic_name', ''),
        'address': clinic_info.get('clinic_address', ''),
        'phone': clinic_info.get('clinic_phone', ''),
    }
    html = render_to_string('billing/invoice_pdf.html', {
        'invoice': invoice,
        'billed_patient_name': invoice.issue_snapshot.get('patient_name') or invoice.patient.get_full_name(),
        'clinic': clinic,
        'generated_at': timezone.localtime().strftime('%d/%m/%Y %H:%M'),
        'timezone': timezone.get_current_timezone_name(),
        'status_label': STATUS_PRESENTATION['invoice'][invoice.status]['label'],
    })
    pdf = render_pdf_from_html(html)
    if not pdf:
        return None
    log_action(actor.pk, 'export', 'Invoice', invoice.id, {
        'summary': f'Invoice PDF export {invoice.invoice_number}',
        'version': invoice.version,
    })
    return pdf
