import uuid
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.patients.models import Patient
from apps.tasks.models import UserTask
from core.models import IdempotencyOperation
from .base import ClinicTestCase, ClinicTransactionTestCase, PASSWORD


class AuthenticationAPITests(ClinicTransactionTestCase):
    def csrf_client(self):
        api = APIClient(enforce_csrf_checks=True)
        result = api.get('/api/v1/system/config/')
        self.assertEqual(result.status_code, 200)
        return api, api.cookies['csrftoken'].value

    def test_protected_auth_actions_reject_anonymous_sessions(self):
        api = APIClient()
        for method, path in [('get', 'me'), ('post', 'logout'), ('post', 'change-password')]:
            with self.subTest(action=path):
                response = getattr(api, method)(f'/api/v1/auth/{path}/')
                self.assertIn(response.status_code, (401, 403))
                self.assertNotIn('user', response.json().get('data', {}))

    def test_csrf_bootstrap_then_login_and_me(self):
        api, token = self.csrf_client()
        result = api.post('/api/v1/auth/login/', {'username': self.doctor.username, 'password': PASSWORD}, format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['data']['user']['id'], self.doctor.pk)
        self.assertEqual(api.get('/api/v1/auth/me/').status_code, 200)

    def test_anonymous_login_without_csrf_rejected(self):
        api = APIClient(enforce_csrf_checks=True)
        result = api.post('/api/v1/auth/login/', {'username': self.doctor.username, 'password': PASSWORD}, format='json')
        self.assertEqual(result.status_code, 403)
        self.assertNotIn('sessionid', api.cookies)

    def test_failed_login_attempts_persist_and_lock_account(self):
        api, token = self.csrf_client()
        with self.settings(MAX_LOGIN_ATTEMPTS=2):
            for _ in range(2):
                result = api.post('/api/v1/auth/login/', {'username': self.doctor.username, 'password': 'wrong'}, format='json', HTTP_X_CSRFTOKEN=token)
                self.assertIn(result.status_code, (401, 403))
        self.doctor.refresh_from_db()
        self.assertEqual(self.doctor.failed_login_attempts, 2)
        self.assertIsNotNone(self.doctor.locked_until)
        result = api.post('/api/v1/auth/login/', {'username': self.doctor.username, 'password': PASSWORD}, format='json', HTTP_X_CSRFTOKEN=token)
        self.assertIn(result.status_code, (401, 403))

    def test_force_password_change_blocks_clinical_api(self):
        self.admin.force_password_change = True
        self.admin.save(update_fields=['force_password_change'])
        response = self.api.get('/api/v1/patients/')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['error']['code'], 'password_change_required')
        self.assertEqual(self.api.get('/api/v1/auth/me/').status_code, 200)

    def test_security_change_revokes_existing_session(self):
        self.admin.session_revoked_at = timezone.now() + timedelta(seconds=1)
        self.admin.save(update_fields=['session_revoked_at'])
        response = self.api.get('/api/v1/auth/me/')
        self.assertEqual(response.status_code, 401)
        self.assertFalse(self.api.session.get('_auth_user_id'))

    def test_doctor_lookup_contains_no_private_account_fields(self):
        result = self.api.get('/api/v1/auth/users/doctors/')
        self.assertEqual(result.status_code, 200)
        for user in result.json()['data']:
            self.assertEqual(set(user), {'id', 'username', 'full_name', 'role'})

    def test_password_change_revokes_session_and_clears_forced_change(self):
        response = self.api.post('/api/v1/auth/change-password/', {'current_password': PASSWORD, 'new_password': 'Synthetic-New-Pass!84'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password('Synthetic-New-Pass!84'))
        self.assertIsNotNone(self.admin.session_revoked_at)
        self.assertFalse(self.api.session.get('_auth_user_id'))


class VersionScopeAPITests(ClinicTestCase):
    def test_patient_create_and_stale_patch_envelopes(self):
        response = self.write('post', '/api/v1/patients/', {'first_name': 'Synthetic', 'surname': 'Suite'})
        self.assertEqual(response.status_code, 201)
        identifier = response.json()['data']['id']
        response = self.write('patch', f'/api/v1/patients/{identifier}/', {'occupation': 'Teacher', 'version': 1})
        self.assertEqual(response.status_code, 200)
        response = self.write('patch', f'/api/v1/patients/{identifier}/', {'occupation': 'Stale', 'version': 1})
        self.assertEqual(response.status_code, 409)
        self.assertIn('message', response.json()['error'])
        self.assertEqual(Patient.objects.get(pk=identifier).occupation, 'Teacher')

    def test_missing_boolean_or_conflicting_version_is_400(self):
        path = f'/api/v1/patients/{self.patient.pk}/'
        for data, headers in (({'occupation': 'Teacher'}, {}), ({'version': True}, {}), ({'version': 1}, {'HTTP_IF_MATCH': '2'})):
            with self.subTest(data=data):
                result = self.write('patch', path, data, **headers)
                self.assertEqual(result.status_code, 400)
                self.assertIn('version', result.json()['error']['errors'])

    def test_if_match_only_update_accepted(self):
        result = self.write('patch', f'/api/v1/patients/{self.patient.pk}/', {'occupation': 'Teacher'}, HTTP_IF_MATCH='"1"')
        self.assertEqual(result.status_code, 200)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.version, 2)

    def test_inaccessible_patient_and_nested_visits_are_denied(self):
        self.api.force_login(self.other_doctor)
        for path in (f'/api/v1/patients/{self.patient.pk}/', f'/api/v1/patients/{self.patient.pk}/records/?kind=contacts'):
            with self.subTest(path=path):
                self.assertIn(self.api.get(path).status_code, (403, 404))
        nested = self.api.get(f'/api/v1/patients/{self.patient.pk}/visits/')
        self.assertEqual(nested.status_code, 200)
        self.assertEqual(nested.json()['data']['items'], [])
        items = self.api.get('/api/v1/patients/').json()['data']['items']
        self.assertNotIn(self.patient.pk, [row['id'] for row in items])

    def test_parent_record_version_header(self):
        result = self.write('post', f'/api/v1/patients/{self.patient.pk}/records/', {'kind': 'contacts', 'fields': {'name': 'Synthetic'}, 'version': 1})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result['X-Resource-Version'], '2')
        self.assertEqual(result.json()['data']['version'], 2)
        result = self.write('post', f'/api/v1/patients/{self.patient.pk}/records/', {'kind': 'contacts', 'fields': {'name': 'Stale'}, 'version': 1})
        self.assertEqual(result.status_code, 409)

    def test_invalid_sort_and_cursor_are_structured_errors(self):
        for params in ({'sort_by': 'password'}, {'cursor': 'invalid-cursor'}):
            result = self.api.get('/api/v1/patients/', params)
            self.assertEqual(result.status_code, 404 if 'cursor' in params else 400)
            self.assertIn('error', result.json())

    def test_cursor_pagination_honors_limit_without_duplicate_rows(self):
        for index in range(4):
            self.patient_for(first_name=f'Synthetic{index}')
        first = self.api.get('/api/v1/patients/', {'per_page': 2}).json()['data']
        second = self.api.get('/api/v1/patients/', {'per_page': 2, 'cursor': first['meta']['next_cursor']}).json()['data']
        self.assertEqual(len(first['items']), 2)
        self.assertTrue(first['meta']['has_more'])
        self.assertFalse({r['id'] for r in first['items']} & {r['id'] for r in second['items']})


class IdempotencyAPITests(ClinicTestCase):
    def test_missing_or_invalid_operation_key_rejected(self):
        for key in ('', 'short', 'bad key with spaces'):
            response = self.api.post('/api/v1/tasks/', {'title': 'Synthetic'}, format='json', HTTP_X_IDEMPOTENCY_KEY=key)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()['error']['code'], 'idempotency_key_required')
        self.assertEqual(UserTask.objects.count(), 0)

    def test_replay_preserves_response_and_has_one_side_effect(self):
        key = 'suite-replay-operation'
        data = {'title': 'Synthetic task'}
        first = self.write('post', '/api/v1/tasks/', data, key)
        second = self.write('post', '/api/v1/tasks/', data, key)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, first.status_code)
        self.assertEqual(second.content, first.content)
        self.assertEqual(second['X-Idempotency-Replayed'], 'true')
        self.assertEqual(UserTask.objects.count(), 1)

    def test_same_key_different_payload_or_endpoint_rejected(self):
        key = 'suite-reuse-operation'
        self.assertEqual(self.write('post', '/api/v1/tasks/', {'title': 'Synthetic'}, key).status_code, 201)
        response = self.write('post', '/api/v1/tasks/', {'title': 'Different'}, key)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error']['code'], 'idempotency_key_reused')
        self.assertEqual(UserTask.objects.count(), 1)

    def test_json_key_order_does_not_change_request_identity(self):
        key = 'suite-canonical-operation'
        first = self.write('post', '/api/v1/tasks/', {'title': 'Synthetic', 'description': 'Suite'}, key)
        second = self.write('post', '/api/v1/tasks/', {'description': 'Suite', 'title': 'Synthetic'}, key)
        self.assertEqual(first.content, second.content)
        self.assertEqual(second['X-Idempotency-Replayed'], 'true')

    def test_failed_validation_leaves_key_available_for_correction(self):
        key = 'suite-failed-operation'
        response = self.write('post', '/api/v1/tasks/', {'title': ''}, key)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(IdempotencyOperation.objects.filter(key=key).exists())
        self.assertEqual(self.write('post', '/api/v1/tasks/', {'title': 'Corrected'}, key).status_code, 201)

    def test_authenticated_csrf_failure_cannot_create_operation(self):
        api = APIClient(enforce_csrf_checks=True)
        api.force_login(self.admin)
        response = api.post('/api/v1/tasks/', {'title': 'Synthetic'}, format='json', HTTP_X_IDEMPOTENCY_KEY='suite-csrf-operation')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(IdempotencyOperation.objects.filter(key='suite-csrf-operation').exists())
        self.assertEqual(UserTask.objects.count(), 0)


class EndpointMatrixTests(ClinicTransactionTestCase):
    def test_authenticated_admin_read_endpoints(self):
        paths = ['/api/v1/patients/', '/api/v1/visits/', '/api/v1/appointments/', '/api/v1/tasks/',
                 '/api/v1/billing/', '/api/v1/notifications/', '/api/v1/options/diagnoses/',
                 '/api/v1/options/medications/', '/api/v1/scales/', '/api/v1/templates/',
                 '/api/v1/dashboard/', '/api/v1/dashboard/charts/', '/api/v1/dashboard/summary/',
                 '/api/v1/reports/statistics/', '/api/v1/reports/reconciliation/', '/api/v1/settings/',
                 '/api/v1/auth/users/', '/api/v1/audit-logs/']
        for path in paths:
            with self.subTest(path=path):
                response = self.api.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn('data', response.json())

    def test_anonymous_protected_endpoints_and_public_config(self):
        api = APIClient()
        for path in ('patients', 'visits', 'appointments', 'tasks', 'billing', 'notifications', 'dashboard', 'settings'):
            with self.subTest(path=path):
                self.assertIn(api.get(f'/api/v1/{path}/').status_code, (401, 403))
        config = api.get('/api/v1/system/config/').json()['data']
        self.assertNotIn('secret_key', config)
        self.assertNotIn('backup_hmac_key', config)

    def test_receptionist_cannot_manage_users_options_or_restore(self):
        self.api.force_login(self.receptionist)
        for path in ('/api/v1/auth/users/', '/api/v1/backup/restore/execute/', '/api/v1/settings/'):
            with self.subTest(path=path):
                self.assertEqual(self.write('put' if path == '/api/v1/settings/' else 'post', path, {}).status_code, 403)
