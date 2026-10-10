from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from apps.patients.services import PatientService
from apps.prescriptions.models import IssuedDocument
from apps.prescriptions.services import PrescriptionService
from core.exceptions import ConflictError
from core.pdf_utils import render_pdf_from_html
from .base import ClinicTestCase


class DocumentWorkflowTests(ClinicTestCase):
    def test_unsigned_visit_cannot_create_prescription_preview(self):
        with self.assertRaises(ValidationError):
            PrescriptionService().create_preview(self.visit_for(), self.doctor.pk)

    def test_preview_is_bound_to_user_visit_and_signed_revision(self):
        service = PrescriptionService()
        visit = self.visit_for(status='final')
        preview = service.create_preview(visit, self.doctor.pk)
        self.assertEqual(service.get_preview(preview['preview_token'], self.doctor.pk, visit)['revision_id'], preview['revision_id'])
        for actor in (self.other_doctor.pk, self.admin.pk):
            with self.subTest(actor=actor), self.assertRaises(ValidationError):
                service.get_preview(preview['preview_token'], actor, visit)
        with self.assertRaises(ValidationError):
            service.get_preview(preview['preview_token'], self.doctor.pk, self.visit_for(status='final'))

    def test_patient_edit_invalidates_prepared_document(self):
        service = PrescriptionService()
        visit = self.visit_for(status='final')
        preview = service.create_preview(visit, self.doctor.pk)
        PatientService().update_patient(self.patient, {'occupation': 'Synthetic'}, self.doctor, expected_version=1)
        visit.refresh_from_db()
        with self.assertRaises(ConflictError):
            service.get_preview(preview['preview_token'], self.doctor.pk, visit)

    def test_failed_renderer_returns_503_and_does_not_issue_document(self):
        visit = self.visit_for(status='final')
        preview = self.api.get(f'/api/v1/prescription/visit/{visit.pk}/').json()['data']
        with patch('apps.prescriptions.services.render_pdf_from_html', return_value=None):
            response = self.write('post', '/api/v1/prescription/generate/', {'visit_id': visit.pk, 'preview_token': preview['preview_token']})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(IssuedDocument.objects.exists())

    def test_successful_http_issuance_retains_bytes_and_consumes_preview(self):
        visit = self.visit_for(status='final')
        preview = self.api.get(f'/api/v1/prescription/visit/{visit.pk}/').json()['data']
        pdf = b'%PDF-synthetic-http'
        payload = {'visit_id': visit.pk, 'preview_token': preview['preview_token']}
        with patch('apps.prescriptions.services.render_pdf_from_html', return_value=pdf):
            response = self.write('post', '/api/v1/prescription/generate/', payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response.content, pdf)
        document = IssuedDocument.objects.get()
        self.assertEqual(document.revision_id, preview['revision_id'])
        self.assertEqual(bytes(document.pdf_data), pdf)
        repeated = self.write('post', '/api/v1/prescription/generate/', payload)
        self.assertEqual(repeated.status_code, 400)
        self.assertEqual(IssuedDocument.objects.count(), 1)


class PDFRendererTests(SimpleTestCase):
    def test_real_renderer_produces_pdf_bytes_from_arabic_html(self):
        pdf = render_pdf_from_html('<!doctype html><html lang="ar" dir="rtl"><body><p>وثيقة اختبار اصطناعية</p></body></html>', base_url='/tmp')
        self.assertIsInstance(pdf, bytes)
        self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertGreater(len(pdf), 1000)
