from datetime import timedelta, time
from decimal import Decimal
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from apps.appointments.services import AppointmentService
from apps.billing.services import BillingService
from apps.billing.models import Invoice
from apps.tasks.services import TaskService
from apps.tasks.models import UserTask
from apps.notifications.services import NotificationService
from apps.notifications.models import Notification
from core.exceptions import ConflictError
from .base import ClinicTestCase


class AppointmentTests(ClinicTestCase):
    def appointment(self, **changes):
        return AppointmentService().create_appointment({'patient': self.patient, 'doctor': self.doctor,
            'appointment_date': timezone.localdate(), 'appointment_time': '10:00', 'duration_minutes': 30, **changes})

    def test_overlaps_rejected_and_adjacent_slot_allowed(self):
        self.appointment()
        with self.assertRaises(ValidationError):
            self.appointment(appointment_time='10:15')
        self.assertEqual(self.appointment(appointment_time='10:30').appointment_time, time(10, 30))

    def test_workday_bounds_and_duration_types(self):
        for changes in ({'appointment_time': '07:30'}, {'appointment_time': '23:59'}, {'duration_minutes': True},
                        {'duration_minutes': 0}, {'appointment_date': 'bad'}, {'appointment_time': '10:00+03:00'}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.appointment(**changes)

    def test_cancel_reason_releases_slot_but_reactivation_checks_it(self):
        service = AppointmentService()
        one = self.appointment()
        with self.assertRaises(ValidationError):
            service.cancel(one, 1)
        one = service.cancel(one, 1, 'Patient cancelled')
        self.appointment()
        with self.assertRaises(ValidationError):
            service.transition(one, 'scheduled', one.version)

    def test_completed_appointment_cannot_move_or_archive(self):
        service = AppointmentService()
        row = self.appointment()
        row = service.transition(row, 'arrived', row.version)
        row = service.complete(row, row.version)
        with self.assertRaises(ValidationError):
            service.update_appointment(row, {'appointment_time': '12:00'}, row.version)
        with self.assertRaises(ValidationError):
            service.archive(row, row.version)

    def test_schedule_update_preserves_associations_and_resets_reminders(self):
        service = AppointmentService()
        row = self.appointment()
        row.reminder_sent = row.reminder_sent_hour = True
        row.save()
        updated = service.update_appointment(row, {'patient': self.patient, 'doctor': self.doctor, 'appointment_time': '12:00'}, 1)
        self.assertFalse(updated.reminder_sent)
        self.assertFalse(updated.reminder_sent_hour)
        self.assertEqual(updated.version, 2)
        with self.assertRaises(ConflictError):
            service.update_appointment(updated, {'notes': 'stale'}, 1)

    def test_calendar_includes_only_requested_day_and_scope(self):
        self.appointment()
        self.appointment(appointment_date=timezone.localdate() + timedelta(days=1))
        self.assertEqual(AppointmentService().get_calendar(self.doctor, 'day', timezone.localdate()).count(), 1)
        self.assertEqual(AppointmentService().get_calendar(self.other_doctor, 'day', timezone.localdate()).count(), 0)

    def test_time_slots_mark_occupied_and_free_slots(self):
        self.appointment()
        slots = {row['time']: row['available'] for row in AppointmentService().generate_time_slots(self.doctor.pk, timezone.localdate())}
        self.assertFalse(slots['10:00'])
        self.assertTrue(slots['10:30'])


class BillingTests(ClinicTestCase):
    def invoice(self, **changes):
        return BillingService().create_invoice({'patient': self.patient,
            'lines': [{'description': 'Synthetic service', 'quantity': 1, 'unit_price': '0.10'}], 'tax': '0.20', **changes})

    def test_fractional_total_and_full_discount_satisfy_database_constraints(self):
        self.assertEqual(self.invoice().final_amount, Decimal('0.30'))
        self.assertEqual(self.invoice(discount='0.30').final_amount, Decimal('0.00'))

    def test_nonfinite_overflow_fractional_cents_and_excess_discount(self):
        for changes in ({'tax': 'NaN'}, {'tax': 'Infinity'}, {'tax': '0.001'}, {'tax': '100000000'}, {'discount': '0.31'}, {'currency': 'BADCODE'}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.invoice(**changes)

    def test_line_totals_override_client_supplied_totals(self):
        row = self.invoice(total_amount=999, final_amount=999)
        self.assertEqual(row.total_amount, Decimal('0.10'))
        self.assertEqual(row.final_amount, Decimal('0.30'))
        self.assertEqual(row.lines.get().amount, Decimal('0.10'))

    def test_issued_snapshot_and_paid_actor_then_immutability(self):
        service = BillingService()
        row = self.invoice()
        row = service.transition(row, 'issued', self.admin, row.version)
        self.assertEqual(row.issue_snapshot['patient_name'], self.patient.get_full_name())
        with self.assertRaises(ValidationError):
            service.transition(row, 'paid', self.admin, row.version)
        row = service.transition(row, 'paid', self.admin, row.version, payment_method='cash')
        self.assertEqual(row.paid_by_id, self.admin.pk)
        self.assertIsNotNone(row.paid_at)
        with self.assertRaises(ValidationError):
            service.update_invoice(row, {'notes': 'Changed'}, row.version)
        with self.assertRaises(ValidationError):
            service.delete_invoice(row, row.version)

    def test_mismatched_visit_or_archived_patient_rejected(self):
        other = self.patient_for()
        visit = self.visit_for(patient=other, actor=self.admin)
        with self.assertRaises(ValidationError):
            self.invoice(visit=visit)
        self.patient.soft_delete(self.admin)
        with self.assertRaises(ValidationError):
            self.invoice()

    def test_database_rejects_inconsistent_final_amount(self):
        row = self.invoice()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Invoice.objects.filter(pk=row.pk).update(final_amount=42)


class TaskNotificationTests(ClinicTestCase):
    def test_nonadmin_assignment_and_scope(self):
        service = TaskService()
        row = service.create_task(self.doctor, {'title': 'Synthetic task'})
        self.assertEqual(row.assigned_to_id, self.doctor.pk)
        with self.assertRaises(ValidationError):
            service.create_task(self.doctor, {'title': 'Task', 'assigned_to': self.other_doctor})
        self.assertFalse(service.get_for_user(self.other_doctor).filter(pk=row.pk).exists())

    def test_completion_reopen_and_active_deletion_guards(self):
        service = TaskService()
        row = service.create_task(self.doctor, {'title': 'Synthetic task'})
        with self.assertRaises(ValidationError):
            service.delete_task(row, row.version)
        row = service.complete_task(row, self.doctor, row.version)
        self.assertEqual(row.completed_by_id, self.doctor.pk)
        with self.assertRaises(ValidationError):
            service.update_task(row, {'title': 'Changed'}, row.version)
        row = service.activate_task(row, self.doctor, row.version)
        self.assertIsNone(row.completed_at)
        self.assertIsNone(row.completed_by_id)

    def test_task_update_protected_fields_and_stale_version(self):
        service = TaskService()
        row = service.create_task(self.doctor, {'title': 'Synthetic task'})
        changed = service.update_task(row, {'status': 'completed', 'user': self.other_doctor, 'order': 99}, 1)
        self.assertEqual(changed.status, 'open')
        self.assertEqual(changed.user_id, self.doctor.pk)
        self.assertNotEqual(changed.order, 99)
        with self.assertRaises(ConflictError):
            service.update_task(changed, {'title': 'Stale'}, 1)

    def test_reorder_validates_duplicates_and_scope(self):
        service = TaskService()
        one = service.create_task(self.doctor, {'title': 'One'})
        two = service.create_task(self.doctor, {'title': 'Two'})
        for ids in ([one.pk, one.pk], [True], 'bad'):
            with self.subTest(ids=ids), self.assertRaises(ValidationError):
                service.reorder_tasks(ids, self.doctor)
        with self.assertRaises(PermissionDenied):
            service.reorder_tasks([one.pk], self.other_doctor)
        service.reorder_tasks([two.pk, one.pk], self.doctor)
        self.assertEqual(list(service.get_for_user(self.doctor).values_list('pk', flat=True)), [two.pk, one.pk])

    def test_notifications_deduplicate_per_user_and_enforce_mutation_scope(self):
        service = NotificationService()
        one = service.create(self.doctor.pk, 'Synthetic', 'Message', dedupe_key='suite-key')
        repeated = service.create(self.doctor.pk, 'Synthetic', 'Message', dedupe_key='suite-key')
        other = service.create(self.other_doctor.pk, 'Synthetic', 'Message', dedupe_key='suite-key')
        self.assertEqual(one.pk, repeated.pk)
        self.assertNotEqual(one.pk, other.pk)
        service.mark_read(one.pk, self.other_doctor.pk)
        one.refresh_from_db()
        self.assertFalse(one.is_read)
        service.delete(one.pk, self.other_doctor.pk)
        self.assertTrue(Notification.objects.filter(pk=one.pk).exists())
        service.mark_all_read(self.doctor.pk)
        self.assertEqual(service.get_for_user(self.doctor.pk, True).count(), 0)
