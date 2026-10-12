"""Real simultaneous writers; explicitly skipped by the default SQLite profile."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from django.core.exceptions import ValidationError
from django.db import connection, connections
from django.utils import timezone
from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.appointments.services import AppointmentService
from apps.patients.models import Patient
from apps.patients.services import PatientService
from apps.tasks.models import UserTask
from apps.tasks.services import TaskService
from core.exceptions import ConflictError
from .base import ClinicTransactionTestCase


@skipUnless(connection.vendor == 'postgresql', 'requires owned PostgreSQL concurrency profile')
class ConcurrentMutationTests(ClinicTransactionTestCase):
    def run_pair(self, operation):
        barrier = Barrier(2)
        def worker(index):
            connections.close_all()
            try:
                barrier.wait(timeout=10)
                try:
                    return ('ok', operation(index))
                except (ValidationError, ConflictError) as error:
                    return ('rejected', type(error).__name__)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, index) for index in range(2)]
            return [future.result(timeout=20) for future in futures]

    def test_same_doctor_overlapping_creations_commit_only_one_booking(self):
        patient_id, doctor_id = self.patient.pk, self.doctor.pk
        def operation(index):
            return AppointmentService().create_appointment({'patient': Patient.objects.get(pk=patient_id), 'doctor': User.objects.get(pk=doctor_id), 'appointment_date': timezone.localdate() + timedelta(days=1), 'appointment_time': '10:00', 'duration_minutes': 30}).pk
        results = self.run_pair(operation)
        self.assertEqual([state for state, _ in results].count('ok'), 1)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_same_opening_patient_version_cannot_commit_two_profile_edits(self):
        patient_id, actor_id = self.patient.pk, self.admin.pk
        def operation(index):
            return PatientService().update_patient(Patient.objects.get(pk=patient_id), {'occupation': f'Synthetic {index}'}, User.objects.get(pk=actor_id), 1).version
        results = self.run_pair(operation)
        self.assertEqual([state for state, _ in results].count('ok'), 1)
        self.patient.refresh_from_db(); self.assertEqual(self.patient.version, 2)

    def test_same_opening_task_version_cannot_commit_two_updates(self):
        row = TaskService().create_task(self.admin, {'title': 'Synthetic concurrent task'})
        row_id, actor_id = row.pk, self.admin.pk
        def operation(index):
            return TaskService().update_task(UserTask.objects.get(pk=row_id), {'title': f'Synthetic {index}'}, 1, User.objects.get(pk=actor_id)).version
        results = self.run_pair(operation)
        self.assertEqual([state for state, _ in results].count('ok'), 1)
        row.refresh_from_db(); self.assertEqual(row.version, 2)
