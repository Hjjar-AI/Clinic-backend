from core.operation_gate import gated
# backend/core/management/commands/send_task_reminders.py
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from apps.tasks.models import UserTask
from apps.tasks.reminders import notify_task_due
from apps.settings.services import SettingsService


class Command(BaseCommand):
    help = 'Send task reminders for tasks due tomorrow'

    @gated()
    def handle(self, *args, **options):
        today = timezone.localdate()
        reminder_days = SettingsService().get_clinic_info()['task_reminder_days']
        due_on = today + timedelta(days=reminder_days)

        # Same row-lock pattern as send_appointment_reminders; see that file
        # for the rationale and the SQLite no-op note.
        with transaction.atomic():
            tasks = (
                UserTask.objects
                .select_for_update()
                .filter(
                    due_date__lte=due_on,
                    status__in=['open', 'in_progress'],
                    reminder_sent=False,
                )
            )
            for task in tasks:
                notify_task_due(task)
                task.reminder_sent = True
                task.save(update_fields=['reminder_sent', 'updated_at'])
