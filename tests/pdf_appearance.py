"""Render synthetic print fixtures, inspect PDF geometry/fonts, retain review images.

Run separately from ORM tests: python -B tests/pdf_appearance.py --output /tmp/clinic-pdf-review
Requires optional test tooling PyMuPDF; never reads clinic data or opens a database.
"""
import argparse
import json
import io
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.testing'
import django
django.setup()
from django.template.loader import render_to_string
from django.test import SimpleTestCase
from core.pdf_utils import render_pdf_from_html
from apps.prescriptions.services import PrescriptionService
from apps.prescriptions.printing import normalize_print_options, render_calibration
from django.core.exceptions import ValidationError
import pymupdf
from fontTools.ttLib import TTFont

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=Path('/tmp/clinic-pdf-review'))
parser.add_argument('--downloads', type=Path)
parser.add_argument('--projects', default='desktop,tablet,mobile')
parser.add_argument('--kinds', default='prescription,referral,patient,visit,invoice,print-referral')
options, unittest_args = parser.parse_known_args()
options.output.mkdir(parents=True, exist_ok=True)

ARABIC = 'مراجعة اصطناعية للأعراض والخطة العلاجية مع تعليمات المتابعة. '
MIXED = ARABIC + 'Medicine ABC-123 · 10 mg · 2026-10-11 · +963944123456. '
clinic = {'name': 'عيادة الاختبار الاصطناعي', 'address': 'عنوان اصطناعي دمشق', 'phone': '+963944123456'}


def contexts():
    medications = [{'name': f'دواء اصطناعي RX{i:03d}', 'dosage': '10 mg',
                    'schedule': MIXED * 2, 'instructions': MIXED * 2} for i in range(45)]
    visit = {'visit_id': 1, 'visit_version': 2, 'patient_name': 'أحمد الاختبار الاصطناعي',
             'visit_date': '11/10/2026', 'generated_at': '11/10/2026 12:00', 'timezone': 'Asia/Damascus',
             'clinical_status': 'تحسن', 'status': 'معتمد', 'main_complaints': MIXED * 20,
             'history_presenting_complaint': MIXED * 30, 'mse': ARABIC * 10,
             'medications': medications, 'diagnoses': ['تشخيص اصطناعي'],
             'treatment_text': MIXED * 20, 'doctor_notes': ARABIC * 10,
             'risk_assessment': {}, 'treatment_plan': {}, 'administrative': {'author': 'طبيب اصطناعي', 'signed_by': 'طبيب اصطناعي'}}
    prescription = {**visit, 'patient_id': 1, 'patient_age': 36, 'patient_gender': 'غير محدد',
                    'doctor_name': 'طبيب اصطناعي', 'template_version': 'synthetic-v1',
                    'patient_national_id': '1234567890', 'diagnoses': [], 'generator': 'Synthetic renderer',
                    'signature_data': 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aS1sAAAAASUVORK5CYII='}
    referral = {**visit, 'clinician': 'طبيب اصطناعي', 'referral_reason': MIXED * 80,
                'medications': [], 'diagnoses': [], 'generator': 'Synthetic renderer'}
    lines = [SimpleNamespace(description=f'خدمة اصطناعية BILL{i:03d} ' + MIXED, quantity='1.00', unit_price='10.00', amount='10.00') for i in range(45)]
    invoice = SimpleNamespace(invoice_number='SYNTHETIC-001', version=3, patient_id=1, visit_id=None,
        issued_date='2026-10-11', due_date='2026-10-20', total_amount='450.00', tax='0.00', discount='0.00',
        final_amount='450.00', payment_method='card', currency='SYP', notes=MIXED * 40,
        lines=SimpleNamespace(all=lambda: lines))
    patient_visits = [{**visit, 'date': '11/10/2026', 'age': 36, 'main_complaints': MIXED * 20,
                       'history_presenting_complaint': MIXED * 20, 'medications': [], 'treatment_text': MIXED * 20} for _ in range(3)]
    report = {'patient_number': 'P-SYNTHETIC', 'patient_name': visit['patient_name'], 'dob_year': 1990,
              'gender': 'غير محدد', 'national_id': '1234567890', 'phone': '+963944123456',
              'visits': patient_visits, 'family_history': ARABIC, 'allergy_status': 'غير معروف', 'medication_status': 'غير معروف'}
    return {
        'prescription': ('prescriptions/prescription_pdf.html', {'clinic': clinic, 'prescription': prescription}),
        'referral': ('referral_letter.html', {'clinic': clinic, 'data': referral}),
        'visit': ('visit_pdf.html', {'clinic': clinic, 'data': visit}),
        'invoice': ('billing/invoice_pdf.html', {'clinic': clinic, 'invoice': invoice, 'billed_patient_name': visit['patient_name'], 'status_label': 'مدفوعة'}),
        'patient': ('exports/patient_pdf.html', {'clinic': clinic, 'report_data': report}),
    }


class PrintAppearanceTests(SimpleTestCase):
    def inspect(self, name, pdf, multipage=True, size_mm=(210, 297)):
        target = options.output / f'{name}.pdf'
        target.write_bytes(pdf)
        pages = []
        with pymupdf.open(stream=pdf, filetype='pdf') as document:
            if multipage:
                self.assertGreater(len(document), 1, name)
            for index, page in enumerate(document):
                self.assertAlmostEqual(page.rect.width, size_mm[0] * 72 / 25.4, delta=1)
                self.assertAlmostEqual(page.rect.height, size_mm[1] * 72 / 25.4, delta=1)
                words = page.get_text('words')
                self.assertFalse(any(ord(char) < 32 and char not in '\t\r\n' for char in page.get_text()), f'{name}: corrupt text mapping')
                self.assertTrue(words, f'{name} page {index + 1} is blank')
                self.assertTrue(any(word[3] < page.rect.height - 40 for word in words), f'{name}: footer-only page')
                if multipage:
                    self.assertGreater(sum(word[3] < page.rect.height - 40 for word in words), 4, f'{name}: heading-only page')
                for x0, y0, x1, y1, word, *_ in words:
                    self.assertGreaterEqual(x0, -1, (name, index, word))
                    self.assertGreaterEqual(y0, -1, (name, index, word))
                    self.assertLessEqual(x1, page.rect.width + 1, (name, index, word))
                    self.assertLessEqual(y1, page.rect.height + 1, (name, index, word))
                fonts = page.get_fonts()
                self.assertTrue(fonts)
                browser_print = name.endswith('print-referral')
                self.assertTrue(any('Clinic-Arabic' in font[3] or 'Cairo' in font[3] or (browser_print and font[2] == 'Type3') for font in fonts), (name, 'bundled Arabic font not used'))
                for font in fonts:
                    if font[2] == 'Type3':
                        # Chromium embeds variable-font glyph outlines as
                        # CharProcs rather than a separate TrueType program.
                        self.assertNotEqual(document.xref_get_key(font[0], 'CharProcs'), ('null', 'null'))
                        continue
                    program = document.extract_font(font[0])[3]
                    self.assertTrue(program, f'{name}: font not embedded: {font[3]}')
                    if 'Clinic-Arabic' in font[3] or 'Cairo' in font[3]:
                        self.assertEqual(TTFont(io.BytesIO(program))['name'].getDebugName(1), 'Cairo')
                traces = page.get_texttrace()
                arabic = [char for span in traces for char in span['chars'] if 0x600 <= char[0] <= 0x6ff]
                self.assertTrue(arabic, (name, index, 'missing Arabic text'))
                if not browser_print:
                    self.assertTrue(all(char[1] != 0 for char in arabic), (name, index, 'missing Arabic glyph'))
                if index in {0, 1, len(document) - 1}:
                    page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(options.output / f'{name}-page-{index + 1}.png')
                pages.append({'page': index + 1, 'words': len(words), 'fonts': [font[3] for font in fonts]})
            (options.output / f'{name}.json').write_text(json.dumps(pages, ensure_ascii=False, indent=2))
            return [page.get_text() for page in document]

    def render(self, name):
        template, context = contexts()[name]
        pdf = render_pdf_from_html(render_to_string(template, context))
        self.assertIsInstance(pdf, bytes)
        return self.inspect(name, pdf)

    def test_prescription_rows_and_repeated_headers(self):
        pages = self.render('prescription')
        for index in range(45):
            self.assertEqual(sum(f'RX{index:03d}' in text for text in pages), 1)
        for text in pages:
            if 'RX' in text:
                self.assertIn('الجرعة', text)

    def test_long_referral_and_closing(self):
        pages = self.render('referral')
        self.assertIn('الطبيب المعالج', pages[-1])

    def test_visit_tables_paginate_without_losing_medications(self):
        pages = self.render('visit')
        for index in range(45):
            self.assertEqual(sum(f'RX{index:03d}' in text for text in pages), 1)

    def test_invoice_rows_and_totals_survive_page_breaks(self):
        pages = self.render('invoice')
        for index in range(45):
            self.assertEqual(sum(f'BILL{index:03d}' in text for text in pages), 1)
        self.assertTrue(any('450.00' in text for text in pages))
        with pymupdf.open(options.output / 'invoice.pdf') as pdf:
            self.assertGreaterEqual(sum(word[4] == '10.00' for page in pdf for word in page.get_text('words')), 90)

    def test_patient_report_long_visits(self):
        self.render('patient')

    def paper_snapshot(self):
        prescription = contexts()['prescription'][1]['prescription']
        return {**prescription, 'patient_name': 'مريض اصطناعي', 'patient_number': 'FILE-SYNTH-123', 'patient_address': 'عنوان اصطناعي',
                'patient_national_id': 'SYNTH-123', 'issue_date': '12/10/2026',
                'clinic': {'clinic_name': clinic['name'], 'clinic_address': clinic['address'], 'clinic_phone': clinic['phone']}}

    def paper_pdf(self, snapshot, **paper):
        return PrescriptionService().generate_prescription_pdf(
            {**snapshot, 'print_options': normalize_print_options(paper)}, snapshot['signature_data'])

    def test_a6_blank_preserves_all_medications_and_long_instruction_tail(self):
        snapshot = self.paper_snapshot()
        snapshot['medications'] = [*snapshot['medications'], {'name': 'Long instruction', 'dosage': '10 mg', 'instructions': MIXED * 100 + 'END-OF-INSTRUCTION'}]
        pages = self.inspect('blank-a6', self.paper_pdf(snapshot), size_mm=(105, 148))
        for index in range(45):
            self.assertEqual(sum(f'RX{index:03d}' in text for text in pages), 1)
        self.assertEqual(sum('END-OF-INSTRUCTION' in text for text in pages), 1)
        for text in pages:
            if 'RX' in text:
                self.assertIn('10 mg', text, 'Medication headings must not be orphaned')

    def test_preprinted_paginated_summaries_match_body_without_stationery_images(self):
        snapshot = self.paper_snapshot()
        snapshot['medications'] = [{'name': f'RX{i:03d}', 'dosage': '10 mg', 'instructions': ARABIC} for i in range(10)]
        pdf = self.paper_pdf(snapshot, mode='preprinted')
        pages = self.inspect('preprinted-a6', pdf, size_mm=(105, 148))
        for index in range(10):
            self.assertEqual(sum(text.count(f'RX{index:03d}') for text in pages), 2)
            self.assertEqual(sum(f'RX{index:03d}' in text for text in pages), 1)
        with pymupdf.open(stream=pdf, filetype='pdf') as document:
            for page in document:
                self.assertEqual(len(page.get_images()), 1, 'Only the signature image belongs in the PDF')
                self.assertIn('12/10/2026', page.get_text())
                self.assertIn('FILE-SYNTH-123', page.get_text())
                self.assertTrue(page.search_for(f'{page.number + 1} / {len(document)}'))
                for word in page.get_text('words'):
                    if word[4].startswith('RX'):
                        self.assertLess(word[3], page.rect.height * .75)

    def test_custom_paper_offsets_move_identity_by_exact_millimetres(self):
        snapshot = {**self.paper_snapshot(), 'medications': []}
        base = self.paper_pdf(snapshot, mode='preprinted', height_mm=198)
        shifted = self.paper_pdf(snapshot, mode='preprinted', height_mm=198, offset_x_mm=2, offset_y_mm=1)
        self.inspect('preprinted-custom', shifted, multipage=False, size_mm=(105, 198))
        with pymupdf.open(stream=base, filetype='pdf') as original, pymupdf.open(stream=shifted, filetype='pdf') as aligned:
            first = original[0].search_for('SYNTH-123')[0]
            second = aligned[0].search_for('SYNTH-123')[0]
            self.assertAlmostEqual(second.x0 - first.x0, 2 * 72 / 25.4, delta=.01)
            self.assertAlmostEqual(second.y0 - first.y0, 72 / 25.4, delta=.01)

    def test_preprinted_rejects_oversize_instructions_and_patient_fields(self):
        snapshot = self.paper_snapshot()
        snapshot['medications'] = [{'name': 'RX', 'dosage': '10 mg', 'instructions': MIXED * 100}]
        with self.assertRaises(ValidationError):
            self.paper_pdf(snapshot, mode='preprinted')
        with self.assertRaises(ValidationError):
            self.paper_pdf({**snapshot, 'medications': [], 'patient_name': ARABIC * 10}, mode='preprinted')

    def test_calibration_has_actual_size_50mm_ruler_and_no_patient_data(self):
        for width, height in [(105, 148), (80, 120), (105, 198)]:
            with self.subTest(size=(width, height)):
                pdf = render_calibration(normalize_print_options({'mode': 'preprinted', 'width_mm': width, 'height_mm': height, 'offset_x_mm': 2, 'offset_y_mm': 1}))
                self.inspect(f'calibration-{width}-{height}', pdf, multipage=False, size_mm=(width, height))
                with pymupdf.open(stream=pdf, filetype='pdf') as document:
                    self.assertEqual(len(document), 1)
                    self.assertIn('ليست وصفة طبية', document[0].get_text())
                    self.assertNotIn('SYNTH', document[0].get_text())
                    self.assertTrue(any(abs(drawing['rect'].width - 50 * 72 / 25.4) < .1 for drawing in document[0].get_drawings()))

    def test_actual_browser_downloads(self):
        if options.downloads is None:
            self.skipTest('Pass --downloads after the browser run to inspect actual issued/exported documents.')
        pdfs = sorted(options.downloads.glob('*.pdf'))
        self.assertTrue(pdfs, 'No browser PDFs found')
        for project in options.projects.split(','):
            for kind in options.kinds.split(','):
                self.assertTrue((options.downloads / f'{project}-{kind}.pdf').is_file(), f'Missing {project} {kind} browser PDF')
        for pdf in pdfs:
            with self.subTest(pdf=pdf.name):
                self.inspect('download-' + pdf.stem, pdf.read_bytes(), multipage=False,
                             size_mm=(105, 148) if pdf.stem.endswith(('-prescription', '-calibration')) else (105, 198) if pdf.stem.endswith('-preprinted') else (210, 297))


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0], *unittest_args])
