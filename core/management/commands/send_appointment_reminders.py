# backend/core/management/commands/send_appointment_reminders.py
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.appointments.models import Appointment
from apps.notifications.services import NotificationService
from datetime import datetime, timedelta
from django.utils import timezone
from apps.settings.services import SettingsService


class Command(BaseCommand):
    help = 'Send appointment reminders'

    def handle(self, *args, **options):
        service = NotificationService()
        today = timezone.now().date()
        reminder_settings = SettingsService().get_clinic_info()
        reminder_days = reminder_settings['appointment_reminder_days']
        reminder_hours = reminder_settings['appointment_reminder_hours']
        reminder_date = today + timedelta(days=reminder_days)

        # Wrap each read → notify → mark sequence in a transaction with a
        # row lock on the reminder queue. Two concurrent runs of this command
        # (e.g., an overlapping retry) would otherwise both read
        # reminder_sent=False and both send the same notification.
        # On Postgres/MySQL select_for_update() blocks the second run until
        # the first commits; the second then re-reads and finds nothing
        # pending. On SQLite the modifier is a documented no-op (single
        # writer already serializes), so local dev is unaffected.
        with transaction.atomic():
            appointments = (
                Appointment.objects
                .select_for_update()
                .filter(
                    appointment_date=reminder_date,
                    status__in=['scheduled', 'confirmed'],
                    reminder_sent=False,
                    deleted_at__isnull=True,
                )
            )
            for apt in appointments:
                service.create(
                    apt.doctor_id,
                    f'تذكير موعد: {apt.patient.get_full_name()}',
                    f'لديك موعد بعد {reminder_days} يوم/أيام الساعة {apt.appointment_time}',
                    link=f'/appointments?date={apt.appointment_date}',
                    type='info',
                    dedupe_key=f'appointment-day:{apt.pk}:{apt.appointment_date.isoformat()}',
                )
                apt.reminder_sent = True
                apt.save(update_fields=['reminder_sent'])

        # Hour-before reminders
        now = timezone.now()
        hour_later = now + timedelta(hours=reminder_hours)
        with transaction.atomic():
            appointments = (
                Appointment.objects
                .select_for_update()
                .filter(
                    appointment_date=today,
                    status__in=['scheduled', 'confirmed'],
                    reminder_sent_hour=False,
                    deleted_at__isnull=True,
                )
            )
            for apt in appointments:
                apt_datetime = datetime.combine(today, apt.appointment_time)
                # D5: single branch — make_aware is idempotent for already-aware
                # datetimes only if we guard; combine() produces naive, so we always
                # need the conversion. The old if/else did the same thing twice.
                if timezone.is_naive(apt_datetime):
                    apt_datetime = timezone.make_aware(apt_datetime, timezone.get_current_timezone())
                if now <= apt_datetime <= hour_later:
                    service.create(
                        apt.doctor_id,
                        f'موعد قريب: {apt.patient.get_full_name()}',
                        f'لديك موعد خلال {reminder_hours} ساعة/ساعات عند الساعة {apt.appointment_time}',
                        link=f'/appointments?date={apt.appointment_date}',
                        type='warning',
                        dedupe_key=f'appointment-hour:{apt.pk}:{apt.appointment_date.isoformat()}:{apt.appointment_time}',
                    )
                    apt.reminder_sent_hour = True
                    apt.save(update_fields=['reminder_sent_hour'])
