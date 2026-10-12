import io
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from apps.appointments.services import AppointmentService
from apps.tasks.services import TaskService
from apps.notifications.models import Notification
from core.cache_utils import get_group_version, get_grouped_key, set_grouped_key, invalidate_group
from core.management.commands.bootstrap import Command as Bootstrap
from core.models import AuditLog
from core.spreadsheets import csv_cell
from .base import ClinicTestCase


class InfrastructureTests(ClinicTestCase):
    def test_cache_generation_changes_with_mutation_and_blocks_stale_publication(self):
        generation = get_group_version('suite')
        self.assertTrue(set_grouped_key('suite', 'report', {'value': 1}, version=generation))
        with self.captureOnCommitCallbacks(execute=True):
            invalidate_group('suite')
            self.assertNotEqual(get_group_version('suite'), generation)
        self.assertNotEqual(get_group_version('suite'), generation)
        self.assertIsNone(get_grouped_key('suite', 'report'))
        self.assertFalse(set_grouped_key('suite', 'report', {'value': 2}, version=generation))

    def test_rollback_does_not_invalidate_cache(self):
        generation = get_group_version('suite')
        with self.captureOnCommitCallbacks(execute=True):
            with transaction.atomic():
                invalidate_group('suite')
                transaction.set_rollback(True)
        self.assertEqual(get_group_version('suite'), generation)

    def test_audit_records_actor_and_protects_identifiers(self):
        response = self.write('post', '/api/v1/patients/', {'first_name': 'Synthetic', 'surname': 'Audit', 'national_id': '1234567890', 'phone': '0944123456'})
        self.assertEqual(response.status_code, 201)
        log = AuditLog.objects.get(entity_type='Patient', entity_id=response.json()['data']['id'], action='create')
        self.assertEqual(log.user_id, self.admin.pk)
        self.assertTrue(log.details['changes']['national_id']['to'].startswith('[protected:'))
        self.assertNotIn('1234567890', str(log.details))

    def test_csv_export_neutralizes_formula_prefixes(self):
        for value in ('=1+1', '+SUM(A1)', '-1+2', '@SUM(A1)', '  =1+1'):
            with self.subTest(value=value):
                self.assertEqual(csv_cell(value), "'" + value)
        self.assertEqual(csv_cell(42), 42)
        self.assertEqual(csv_cell('Synthetic'), 'Synthetic')

    def test_task_reminders_deduplicate_and_ignore_completed_tasks(self):
        service = TaskService()
        pending = service.create_task(self.doctor, {'title': 'Synthetic reminder', 'due_date': timezone.localdate()})
        completed = service.create_task(self.doctor, {'title': 'Completed', 'due_date': timezone.localdate()})
        service.complete_task(completed, self.doctor, completed.version)
        call_command('send_task_reminders', stdout=io.StringIO())
        count = Notification.objects.filter(dedupe_key__startswith=f'task-due:{pending.pk}:').count()
        self.assertEqual(count, 1)
        call_command('send_task_reminders', stdout=io.StringIO())
        self.assertEqual(Notification.objects.filter(dedupe_key__startswith=f'task-due:{pending.pk}:').count(), 1)
        self.assertFalse(Notification.objects.filter(dedupe_key__startswith=f'task-due:{completed.pk}:').exists())

    def test_cancelled_appointments_do_not_send_reminders(self):
        service = AppointmentService()
        row = service.create_appointment({'patient': self.patient, 'doctor': self.doctor,
            'appointment_date': timezone.localdate() + timedelta(days=1), 'appointment_time': '10:00'})
        service.cancel(row, row.version, 'Synthetic cancellation')
        call_command('send_appointment_reminders', stdout=io.StringIO())
        self.assertFalse(Notification.objects.filter(dedupe_key__contains=f':{row.pk}:').exists())

    def test_media_reconciliation_is_read_only_without_delete(self):
        path = default_storage.save('patient_docs/orphan.pdf', ContentFile(b'Synthetic orphan'))
        with patch.object(default_storage, 'get_modified_time', return_value=timezone.now() - timedelta(days=3)):
            output = io.StringIO()
            call_command('reconcile_media', stdout=output)
        self.assertIn(f'ORPHAN {path}', output.getvalue())
        self.assertTrue(default_storage.exists(path))

    def test_bootstrap_prepares_sqlite_parent_before_system_checks(self):
        root = Path(self.workspace.name) / 'missing' / 'nested'
        database = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': root / 'clinic.db'}}
        def check_directory(*args, **kwargs):
            self.assertTrue(root.is_dir())
        with self.settings(DATABASES=database), patch.object(BaseCommand, 'execute', side_effect=check_directory):
            Bootstrap().execute()
        self.assertFalse((root / 'clinic.db').exists())
