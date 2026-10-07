# backend/core/management/commands/run_scheduler.py
"""
Run the periodic scheduler loop (development only).

The interval is read from settings.SCHEDULER_INTERVAL_HOURS, which
in turn reads the SCHEDULER_INTERVAL_HOURS key from .env. Previously
this command hardcoded `time.sleep(3600)`, silently ignoring the
configured interval.

This is a development convenience. In production, wire the individual
commands (send_appointment_reminders, send_task_reminders, auto_backup,
cleanup_backups) into cron or systemd timers — one long-running loop
per process is fragile and hard to monitor.
"""

import time

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Run scheduler loop (development only)'

    def handle(self, *args, **options):
        interval_hours = float(getattr(settings, 'SCHEDULER_INTERVAL_HOURS', 2))
        interval_seconds = max(60, int(interval_hours * 3600))
        self.stdout.write(
            f'Starting scheduler loop (interval: {interval_hours}h / {interval_seconds}s)'
        )
        while True:
            for name in (
                'send_appointment_reminders',
                'send_task_reminders',
                'auto_backup',
                'cleanup_backups',
            ):
                try:
                    call_command(name)
                except Exception as e:
                    # A failure in one command must not stop the others.
                    self.stderr.write(self.style.ERROR(f'{name} failed: {e}'))
            time.sleep(interval_seconds)