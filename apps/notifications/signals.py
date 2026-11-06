# backend/apps/notifications/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from apps.appointments.models import Appointment
from apps.tasks.models import UserTask
from apps.tasks.reminders import task_recipient, task_reminder_prefix, notify_task_due
from apps.appointments.reminders import appointment_reminder_prefix
from .services import NotificationService
from apps.settings.services import SettingsService


def _safe_url(path, **params):
    """Build a safe relative URL (avoid reverse mismatch)."""
    from urllib.parse import urlencode
    query = urlencode(params)
    return f"{path}?{query}" if query else path


@receiver(post_save, sender=Appointment)
def appointment_reminders(sender, instance, created, **kwargs):
    if kwargs.get('raw'):
        return
    service = NotificationService()
    if instance.status not in {'scheduled', 'confirmed'}:
        service.retire_related(appointment_reminder_prefix(instance, 'day'))
        service.retire_related(appointment_reminder_prefix(instance, 'hour'))
    elif not created:
        if not instance.reminder_sent:
            service.retire_related(appointment_reminder_prefix(instance, 'day'))
        if not instance.reminder_sent_hour:
            service.retire_related(appointment_reminder_prefix(instance, 'hour'))
    if created and instance.status == 'scheduled':
        service.create(
            instance.doctor_id,
            f'موعد جديد',
            f'لديك موعد مع {instance.patient.get_full_name()} في {instance.appointment_date} الساعة {instance.appointment_time}',
            link=_safe_url('/appointments', date=instance.appointment_date.isoformat()),
            type='info',
            dedupe_key=f'appointment-created:{instance.pk}',
        )

@receiver(post_save, sender=UserTask)
def task_reminders(sender, instance, created, **kwargs):
    if kwargs.get('raw'):
        return
    service = NotificationService()
    reminder_prefix = task_reminder_prefix(instance)
    target_user_id = task_recipient(instance)
    if instance.status not in {'open', 'in_progress'}:
        service.retire_related(reminder_prefix)
    elif target_user_id:
        service.retire_related(reminder_prefix, keep_user_id=target_user_id)
        if not created and not instance.reminder_sent:
            service.retire_related(reminder_prefix)
    if created and instance.due_date:
        reminder_days = SettingsService().get_clinic_info()['task_reminder_days']
        reminder_date = timezone.localdate() + timedelta(days=reminder_days)
        if instance.due_date == reminder_date and not instance.completed_at and not instance.cancelled_at:
            notify_task_due(instance, days=reminder_days)
