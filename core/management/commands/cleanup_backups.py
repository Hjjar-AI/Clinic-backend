# backend/core/management/commands/cleanup_backups.py
"""
Apply the backup retention policy to the backups directory.

Usage:
    python manage.py cleanup_backups
    python manage.py cleanup_backups --dry-run
    python manage.py cleanup_backups --dir /custom/path

The retention windows come from Django settings
(BACKUP_SAFETY_DAYS, BACKUP_WEEKLY_DAYS, BACKUP_MONTHLY_DAYS), which
in turn read the same-named keys from .env with sensible defaults.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.backup.retention import apply_backup_retention


class Command(BaseCommand):
    help = (
        'Delete old backups according to the daily/weekly/monthly/yearly '
        'retention policy defined in settings.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would be deleted without unlinking any files.',
        )
        parser.add_argument(
            '--dir',
            default=None,
            help='Override the backup directory (default: settings.BACKUP_DIR).',
        )

    def handle(self, *args, **options):
        directory = options['dir'] or str(settings.BACKUP_DIR)
        dry_run = options['dry_run']

        result = apply_backup_retention(directory, dry_run=dry_run)

        prefix = '[dry-run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}kept {result["kept"]} backup(s), '
            f'deleted {result["deleted"]} backup(s) in {directory}'
        ))