"""Real HTTP permission boundaries across feature families, not hidden UI checks."""
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient
from apps.accounts.models import User
from .base import ClinicTestCase, ClinicTransactionTestCase


FEATURE_READS = {
    'patients': '/api/v1/patients/',
    'visits': '/api/v1/visits/',
    'appointments': '/api/v1/appointments/',
    'invoices': '/api/v1/billing/',
    'tasks': '/api/v1/tasks/',
    'notifications': '/api/v1/notifications/',
    'users': '/api/v1/auth/users/',
    'diagnoses': '/api/v1/options/diagnoses/',
    'medications': '/api/v1/options/medications/',
    'scales': '/api/v1/scales/',
    'templates': '/api/v1/templates/',
    'settings': '/api/v1/settings/',
    'statistics': '/api/v1/reports/statistics/',
    'dashboard': '/api/v1/dashboard/',
}


class AuthenticationMatrixTests(ClinicTestCase):
    pass


def anonymous_feature(name, path):
    def check(self):
        response = APIClient().get(path)
        self.assertIn(response.status_code, (401, 403), name)
        self.assertNotIn('data', response.json())
    return check


for name, path in FEATURE_READS.items():
    setattr(AuthenticationMatrixTests, f'test_anonymous_cannot_read_{name}', anonymous_feature(name, path))


class EffectiveGrantTests(ClinicTestCase):
    def test_admin_role_alone_does_not_restore_removed_action_grants(self):
        self.admin.is_superuser = False; self.admin.save(update_fields=['is_superuser'])
        self.admin.groups.clear(); self.admin.user_permissions.clear(); self.admin.clear_permission_cache()
        for path in ('/api/v1/patients/', '/api/v1/visits/', '/api/v1/tasks/', '/api/v1/auth/users/'):
            with self.subTest(path=path):
                self.assertEqual(self.api.get(path).status_code, 403)

    def test_direct_nonadmin_grant_enables_action_without_broadening_patient_scope(self):
        self.api.force_login(self.other_doctor)
        self.other_doctor.groups.clear()
        self.other_doctor.user_permissions.add(Permission.objects.get(codename='view_patients'))
        result = self.api.get('/api/v1/patients/')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['data']['items'], [])
        self.assertIn(self.api.get(f'/api/v1/patients/{self.patient.pk}/').status_code, (403, 404))



class InactiveAccountTests(ClinicTransactionTestCase):
    def test_inactive_authenticated_user_cannot_access_protected_features(self):
        self.admin.is_active = False; self.admin.save(update_fields=['is_active'])
        for path in ('/api/v1/patients/', '/api/v1/tasks/', '/api/v1/auth/me/'):
            with self.subTest(path=path):
                self.assertIn(self.api.get(path).status_code, (401, 403))
