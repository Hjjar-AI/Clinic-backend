from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notifications.services import NotificationService


class Command(BaseCommand):
    help = 'Delete notifications older than the configured read/unread retention windows.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        now = timezone.now()
        read_before = now - timedelta(days=settings.NOTIFICATION_READ_RETENTION_DAYS)
        unread_before = now - timedelta(days=settings.NOTIFICATION_UNREAD_RETENTION_DAYS)

        from apps.notifications.models import Notification
        from django.db.models import Q

        queryset = Notification.objects.filter(
            Q(is_read=True, created_at__lt=read_before)
            | Q(is_read=False, created_at__lt=unread_before)
        )
        count = queryset.count()
        if options['dry_run']:
            self.stdout.write(f'{count} notification(s) would be deleted.')
            return

        deleted = NotificationService().cleanup(read_before, unread_before)
        self.stdout.write(self.style.SUCCESS(f'Deleted {deleted} notification(s).'))
