from hashlib import sha256
from unittest.mock import patch
from apps.prescriptions.issuance import record_document
from apps.prescriptions.models import IssuedDocument
from apps.prescriptions.services import PrescriptionService
from apps.patients.services import PatientService
from apps.visits.services import VisitService
from .base import ClinicTestCase
from .test_documents import SIGNATURE


class PrescriptionHistoryTests(ClinicTestCase):
    def issue(self, patient=None, pdf=b'%PDF-exact-synthetic-history'):
        visit = self.visit_for(patient=patient, status='final')
        snapshot = PrescriptionService().build_snapshot(visit)
        document = record_document(visit, self.admin, 'prescription', snapshot, pdf, SIGNATURE)
        return visit, document

    def test_download_retains_exact_bytes_checksum_and_never_reissues(self):
        visit, document = self.issue()
        with patch('apps.prescriptions.services.PrescriptionService.generate_prescription_pdf', side_effect=AssertionError('Reprint must not render')):
            for _ in range(2):
                response = self.api.get(f'/api/v1/prescription/documents/{document.pk}/pdf/')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, bytes(document.pdf_data))
                self.assertEqual(response['X-Document-Checksum'], sha256(response.content).hexdigest())
                self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(IssuedDocument.objects.count(), 1)

    def test_history_paginates_all_saved_copies_and_filters_visits(self):
        visit, first = self.issue()
        for _ in range(20):
            record_document(visit, self.admin, 'prescription', first.snapshot, b'%PDF-other-copy', SIGNATURE)
        other_visit, other = self.issue()
        url = f'/api/v1/prescription/patient/{self.patient.pk}/history/'
        response = self.api.get(url, {'visit_id': visit.pk})
        data = response.json()['data']
        self.assertEqual(data['total'], 21)
        self.assertEqual(len(data['items']), 20)
        self.assertNotIn(other.pk, [item['id'] for item in data['items']])
        tail = self.api.get(url, {'visit_id': visit.pk, 'offset': 20}).json()['data']['items']
        self.assertEqual([item['id'] for item in tail], [first.pk])
        self.assertNotIn('snapshot', tail[0])
        self.assertEqual(tail[0]['print_options']['width_mm'], 210)
        self.assertEqual(self.api.get(url).json()['data']['total'], 22)

    def test_reads_use_current_scope_and_permissions(self):
        visit, document = self.issue()
        paths = [f'/api/v1/prescription/patient/{self.patient.pk}/history/',
                 f'/api/v1/prescription/documents/{document.pk}/pdf/',
                 f'/api/v1/prescription/documents/{document.pk}/instructions/']
        self.api.force_login(self.other_doctor)
        for path in paths:
            self.assertEqual(self.api.get(path).status_code, 404)
        self.api.force_login(self.receptionist)
        for path in paths:
            self.assertEqual(self.api.get(path).status_code, 403)
        self.api.force_login(self.doctor)
        self.assertEqual(self.api.get(paths[1]).status_code, 200)
        self.api.logout()
        for path in paths:
            self.assertEqual(self.api.get(path).status_code, 403)

    def test_invalid_paging_and_cross_patient_filter_are_rejected(self):
        visit, document = self.issue()
        other_visit, _ = self.issue(self.patient_for(self.doctor))
        url = f'/api/v1/prescription/patient/{self.patient.pk}/history/'
        for params in [{'offset': '-1'}, {'offset': 'NaN'}, {'offset': '1.5'}, {'visit_id': '0'}]:
            self.assertEqual(self.api.get(url, params).status_code, 400)
        self.assertEqual(self.api.get(url, {'visit_id': other_visit.pk}).status_code, 404)

    def test_handout_uses_issued_snapshot_after_patient_changes_without_consuming_preview(self):
        visit, document = self.issue()
        original = document.snapshot.copy()
        PatientService().update_patient(self.patient, {'first_name': 'تغيير لاحق', 'correction_reason': 'Synthetic correction'}, self.doctor, expected_version=self.patient.version)
        visit.refresh_from_db()
        service = PrescriptionService()
        preview = service.create_preview(visit, self.admin.pk)
        with patch('apps.prescriptions.history.render_pdf_from_html', return_value=b'%PDF-handout') as render:
            response = self.api.get(f'/api/v1/prescription/documents/{document.pk}/instructions/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(original['patient_name'], render.call_args.args[0])
        self.assertNotIn('تغيير لاحق', render.call_args.args[0])
        service.get_preview(preview['preview_token'], self.admin.pk, visit)
        document.refresh_from_db()
        self.assertEqual(document.snapshot, original)
        self.assertEqual(bytes(document.pdf_data), b'%PDF-exact-synthetic-history')
        self.assertEqual(IssuedDocument.objects.count(), 1)

    def test_team_revocation_blocks_previously_available_saved_files(self):
        visit, document = self.issue()
        service = PatientService()
        _, version = service.add_care_team_member(self.patient, self.other_doctor.pk, 'doctor',
            expected_version=self.patient.version, actor=self.admin)
        self.api.force_login(self.other_doctor)
        path = f'/api/v1/prescription/documents/{document.pk}/pdf/'
        self.assertEqual(self.api.get(path).status_code, 200)
        service.remove_care_team_member(self.patient, self.other_doctor.pk, expected_version=version, actor=self.admin, reason='Synthetic scope ended')
        self.assertEqual(self.api.get(path).status_code, 404)
        self.assertEqual(self.api.get(f'/api/v1/prescription/documents/{document.pk}/instructions/').status_code, 404)

    def test_old_issued_pdf_remains_available_during_an_unsigned_amendment(self):
        visit, document = self.issue()
        VisitService().transition(visit, 'amended', self.admin, expected_version=visit.version, reason='Synthetic amendment')
        response = self.api.get(f'/api/v1/prescription/documents/{document.pk}/pdf/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, bytes(document.pdf_data))
        self.assertEqual(IssuedDocument.objects.count(), 1)

    def test_handout_renderer_failure_does_not_write_and_other_document_types_are_hidden(self):
        visit, document = self.issue()
        with patch('apps.prescriptions.history.render_pdf_from_html', return_value=None):
            self.assertEqual(self.api.get(f'/api/v1/prescription/documents/{document.pk}/instructions/').status_code, 503)
        referral = IssuedDocument.objects.create(document_type='referral', revision=document.revision,
            issued_by=self.admin, snapshot=document.snapshot, checksum='synthetic', pdf_data=b'%PDF-referral')
        self.assertEqual(self.api.get(f'/api/v1/prescription/documents/{referral.pk}/pdf/').status_code, 404)
        self.assertEqual(self.api.get(f'/api/v1/prescription/patient/{self.patient.pk}/history/').json()['data']['total'], 1)
        self.assertEqual(IssuedDocument.objects.count(), 2)
