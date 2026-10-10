from pathlib import Path
from tempfile import TemporaryDirectory
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from apps.accounts.services import UserService
from apps.patients.services import PatientService
from apps.visits.services import VisitService

PASSWORD = 'Synthetic-Suite-Pass!42'


class ClinicFixtures:
    @classmethod
    def setUpTestData(cls):
        service = UserService()
        cls.admin = service.create_user('suite_admin', PASSWORD, 'Suite Admin', 'admin')
        cls.admin.is_superuser = True
        cls.admin.is_staff = True
        cls.admin.force_password_change = False
        cls.admin.save()
        cls.doctor = service.create_user('suite_doctor', PASSWORD, 'Suite Doctor', 'doctor')
        cls.other_doctor = service.create_user('suite_other', PASSWORD, 'Other Doctor', 'doctor')
        cls.receptionist = service.create_user('suite_reception', PASSWORD, 'Suite Reception', 'receptionist')
        for user in (cls.doctor, cls.other_doctor, cls.receptionist):
            user.force_password_change = False
            user.save(update_fields=['force_password_change'])
        cls.patient = PatientService().create_patient({'first_name': 'مريض', 'surname': 'تجريبي'}, cls.doctor)

    def setUp(self):
        cache.clear()
        self.workspace = TemporaryDirectory(prefix='clinic-case-')
        self.addCleanup(self.workspace.cleanup)
        root = Path(self.workspace.name)
        self.settings_override = override_settings(MEDIA_ROOT=root / 'media', BACKUP_DIR=root / 'backups')
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.api = APIClient()
        self.api.force_login(self.admin)
        session = self.api.session
        session['login_time'] = timezone.now().isoformat()
        session.save()

    def patient_for(self, actor=None, **changes):
        return PatientService().create_patient({'first_name': 'مريض', 'surname': 'اصطناعي', **changes}, actor or self.admin)

    def visit_for(self, patient=None, actor=None, **changes):
        return VisitService().create_visit(patient or self.patient, {
            'visit_date': timezone.localdate(), 'main_complaints': 'Synthetic complaint', **changes,
        }, actor or self.doctor)

    def write(self, method, path, data=None, key=None, **extra):
        import uuid
        return getattr(self.api, method)(path, data or {}, format='json',
            HTTP_X_IDEMPOTENCY_KEY=key or f'suite-{uuid.uuid4()}', **extra)


class ClinicTestCase(ClinicFixtures, TestCase):
    pass


class ClinicTransactionTestCase(ClinicFixtures, TransactionTestCase):
    def setUp(self):
        type(self).setUpTestData()
        super().setUp()
