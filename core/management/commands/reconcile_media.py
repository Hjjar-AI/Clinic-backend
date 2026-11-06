from core.operation_gate import gated
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from django.utils import timezone
from apps.backup.backup_creator import media_paths
from core.file_inventory import referenced_file_paths

class Command(BaseCommand):
    help = 'Report missing media and old unreferenced uploads; use --delete to remove only orphaned uploads'
    def add_arguments(self, parser):
        parser.add_argument('--delete', action='store_true')
        parser.add_argument('--older-than-hours', type=int, default=24)
    @gated()
    def handle(self, *args, **options):
        age = max(24, options['older_than_hours'])
        cutoff = timezone.now() - timedelta(hours=age)
        referenced = referenced_file_paths()
        for path in sorted(referenced):
            if not default_storage.exists(path): self.stdout.write(f'MISSING {path}')
        for prefix in ('patient_docs', 'visit_attachments'):
            for path in media_paths(prefix):
                if path in referenced: continue
                try:
                    modified = default_storage.get_modified_time(path)
                except (NotImplementedError, OSError):
                    continue
                if modified > cutoff: continue
                self.stdout.write(f'ORPHAN {path}')
                if options['delete']: default_storage.delete(path)
