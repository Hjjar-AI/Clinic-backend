from hashlib import sha256
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from apps.prescriptions.models import IssuedDocument
from apps.prescriptions.printing import normalize_print_options
from apps.prescriptions.services import PrescriptionService
from .base import ClinicTestCase
from .test_documents import SIGNATURE


class PrescriptionPaperOptionsTests(SimpleTestCase):
    def test_defaults_and_custom_dimensions(self):
        self.assertEqual(normalize_print_options({}), {
            'mode': 'blank', 'width_mm': 105, 'height_mm': 148,
            'offset_x_mm': 0, 'offset_y_mm': 0,
        })
        options = normalize_print_options({'mode': 'preprinted', 'height_mm': '198.25', 'offset_x_mm': -2.5})
        self.assertEqual(options['height_mm'], 198.25)
        self.assertEqual(options['offset_x_mm'], -2.5)
        self.assertEqual(normalize_print_options({'offset_x_mm': 4})['offset_x_mm'], 0)

    def test_rejects_invalid_shapes_precision_and_physical_limits(self):
        for value in [None, [], {'mode': []}, {'mode': 'scan'}, {'background': 'url'},
                      {'width_mm': True}, {'width_mm': 'NaN'}, {'height_mm': 'Infinity'},
                      {'width_mm': 79}, {'height_mm': 351}, {'offset_y_mm': 6}, {'width_mm': 105.001}]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                normalize_print_options(value)


class PrescriptionPaperIssuanceTests(ClinicTestCase):
    def prepare(self):
        visit = self.visit_for(status='final')
        preview = self.api.get(f'/api/v1/prescription/visit/{visit.pk}/').json()['data']
        return visit, {'visit_id': visit.pk, 'preview_token': preview['preview_token'], 'signature': SIGNATURE}

    def test_custom_options_saved_with_exact_bytes_without_mutating_cached_preview(self):
        visit, payload = self.prepare()
        options = {'mode': 'preprinted', 'height_mm': 198, 'offset_x_mm': 2}
        with patch('apps.prescriptions.printing.render_preprinted', return_value=b'%PDF-synthetic-paper') as render:
            response = self.write('post', '/api/v1/prescription/generate/', {**payload, 'print_options': options})
        self.assertEqual(response.status_code, 200, response.content)
        document = IssuedDocument.objects.get()
        self.assertEqual(document.snapshot['print_options'], normalize_print_options(options))
        self.assertIn('issue_date', document.snapshot)
        self.assertEqual(bytes(document.pdf_data), response.content)
        self.assertEqual(document.checksum, sha256(response.content).hexdigest())
        self.assertEqual(render.call_args.args[0]['issue_date'], document.snapshot['issue_date'])
        self.assertEqual(document.revision.visit_id, visit.pk)

    def test_invalid_options_and_overflow_preserve_preview_and_do_not_issue(self):
        visit, payload = self.prepare()
        for options in [None, {'width_mm': 0}]:
            response = self.write('post', '/api/v1/prescription/generate/', {**payload, 'print_options': options})
            self.assertEqual(response.status_code, 400, response.content)
        with patch('apps.prescriptions.printing.render_preprinted', side_effect=ValidationError('Synthetic overflow')):
            response = self.write('post', '/api/v1/prescription/generate/', {**payload, 'print_options': {'mode': 'preprinted'}})
        self.assertEqual(response.status_code, 400, response.content)
        self.assertFalse(IssuedDocument.objects.exists())
        self.assertNotIn('print_options', PrescriptionService().get_preview(payload['preview_token'], self.admin.pk, visit))

    def test_preprinted_renderer_failure_is_retryable_without_issuance(self):
        visit, payload = self.prepare()
        with patch('apps.prescriptions.printing.render_preprinted', side_effect=RuntimeError('Synthetic renderer failure')):
            response = self.write('post', '/api/v1/prescription/generate/', {**payload, 'print_options': {'mode': 'preprinted'}})
        self.assertEqual(response.status_code, 503, response.content)
        self.assertFalse(IssuedDocument.objects.exists())
        PrescriptionService().get_preview(payload['preview_token'], self.admin.pk, visit)
