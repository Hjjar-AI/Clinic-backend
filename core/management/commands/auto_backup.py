# backend/core/management/commands/auto_backup.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.backup.backup_creator import BackupCreatorService
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Perform automatic backup'

    def handle(self, *args, **options):
        service = BackupCreatorService()
        buffer = service.create_full_backup()
        backup_dir = settings.BACKUP_DIR if hasattr(settings, 'BACKUP_DIR') else os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filepath = os.path.join(backup_dir, f'clinic_backup_{timestamp}.zip')
        with open(filepath, 'wb') as f:
            f.write(buffer.getvalue())
        self.stdout.write(self.style.SUCCESS(f'Backup saved to {filepath}'))