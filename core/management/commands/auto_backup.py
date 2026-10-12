from core.operation_gate import gated
# backend/core/management/commands/auto_backup.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.backup.backup_creator import BackupCreatorService
from django.conf import settings
import os
import tempfile
import uuid

class Command(BaseCommand):
    help = 'Perform automatic backup'

    @gated(exclusive=True)
    def handle(self, *args, **options):
        service = BackupCreatorService()
        buffer = service.create_full_backup()
        backup_dir = settings.BACKUP_DIR if hasattr(settings, 'BACKUP_DIR') else os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S_%f')
        filepath = os.path.join(backup_dir, f'clinic_backup_{timestamp}_{uuid.uuid4().hex[:8]}.zip')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=backup_dir, prefix='.backup-', delete=False) as file:
                temporary = file.name
                file.write(buffer.getvalue())
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, filepath)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
        self.stdout.write(self.style.SUCCESS(f'Backup saved to {filepath}'))