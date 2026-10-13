from datetime import timedelta
from django.utils import timezone
from unittest.mock import patch
from apps.visits.services import VisitService
from apps.prescriptions.handover import approved_handover
from .base import ClinicTestCase


class ClinicalWorkspaceTests(ClinicTestCase):
    def acknowledgement(self, **changes):
        return {'explained_at': (timezone.now() - timedelta(minutes=1)).isoformat(),
                'recipient': 'patient', 'recipient_name': '', 'clarification_needed': False, 'notes': 'Synthetic explanation', **changes}

    def test_acknowledgement_is_versioned_and_server_owned(self):
        visit = self.visit_for()
        ack = self.acknowledgement(recorded_by_id=self.other_doctor.pk, recorded_at='forged')
        service = VisitService()
        service.update_visit(visit, {'clinical_data': {'instruction_acknowledgement': ack}}, self.doctor, expected_version=visit.version)
        visit.refresh_from_db()
        recorded = visit.clinical_data['instruction_acknowledgement']
        self.assertEqual(recorded['recorded_by_id'], self.doctor.pk)
        self.assertNotEqual(recorded['recorded_at'], 'forged')
        self.assertIs(recorded['clarification_needed'], False)
        service.update_visit(visit, {'clinical_data': visit.clinical_data}, self.doctor, expected_version=visit.version)
        visit.refresh_from_db()
        self.assertEqual(visit.clinical_data['instruction_acknowledgement'], recorded)
        service.transition(visit, 'final', self.doctor, expected_version=visit.version)
        self.assertEqual(visit.revisions.latest('number').snapshot['fields']['clinical_data']['instruction_acknowledgement'], recorded)

    def test_invalid_acknowledgements_do_not_save(self):
        visit = self.visit_for()
        for changes in [{'explained_at': 'invalid'}, {'explained_at': '2026-99-99T00:00:00Z'},
                        {'explained_at': (timezone.now() + timedelta(days=1)).isoformat()},
                        {'recipient': []}, {'recipient': 'unknown'}, {'clarification_needed': 1}, {'notes': 'x' * 2001}]:
            with self.subTest(changes=changes):
                response = self.write('patch', f'/api/v1/visits/{visit.pk}/', {'version': visit.version,
                    'clinical_data': {'instruction_acknowledgement': self.acknowledgement(**changes)}})
                self.assertEqual(response.status_code, 400, response.content)
        visit.refresh_from_db()
        self.assertNotIn('instruction_acknowledgement', visit.clinical_data)

    def test_handover_uses_approved_facts_during_amendment(self):
        visit = self.visit_for(status='final', treatment_text='APPROVED-PLAN')
        service = VisitService()
        service.transition(visit, 'amended', self.doctor, expected_version=visit.version, reason='Synthetic correction')
        visit.refresh_from_db()
        service.update_visit(visit, {'treatment_text': 'UNSIGNED-PLAN'}, self.doctor, expected_version=visit.version)
        data = approved_handover(self.doctor, visit.pk)
        self.assertEqual(data['fields']['treatment_text'], 'APPROVED-PLAN')
        with patch('apps.prescriptions.handover.render_pdf_from_html', return_value=b'%PDF-handover') as render:
            response = self.api.get(f'/api/v1/prescription/visit/{visit.pk}/handover/pdf/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('APPROVED-PLAN', render.call_args.args[0])
        self.assertNotIn('UNSIGNED-PLAN', render.call_args.args[0])
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_handover_scope_no_approval_and_renderer_failure(self):
        visit = self.visit_for(status='final')
        draft = self.visit_for()
        self.assertEqual(self.api.get(f'/api/v1/prescription/visit/{draft.pk}/handover/').status_code, 400)
        path = f'/api/v1/prescription/patient/{self.patient.pk}/handover/'
        self.assertEqual(self.api.get(path).json()['data']['visit_id'], visit.pk)
        self.assertIsNone(self.api.get(path, {'exclude_visit': visit.pk}).json()['data'])
        self.api.force_login(self.other_doctor)
        self.assertEqual(self.api.get(path).status_code, 404)
        self.api.force_login(self.receptionist)
        self.assertEqual(self.api.get(path).status_code, 403)
        self.api.force_login(self.admin)
        with patch('apps.prescriptions.handover.render_pdf_from_html', return_value=None):
            self.assertEqual(self.api.get(f'/api/v1/prescription/visit/{visit.pk}/handover/pdf/').status_code, 503)
