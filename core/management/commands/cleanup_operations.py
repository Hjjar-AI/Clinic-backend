from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import IdempotencyOperation, RecoveryOperation
from core.operation_gate import gated


class Command(BaseCommand):
    help = 'Expire completed operation responses after their 30-day retry window'

    @gated()
    def handle(self, *args, **options):
        now = timezone.now()
        ordinary, _ = IdempotencyOperation.objects.filter(state='completed', expires_at__lte=now).delete()
        recovery, _ = RecoveryOperation.objects.filter(state='completed', expires_at__lte=now).delete()
        self.stdout.write(f'Expired {ordinary + recovery} completed receipts; interrupted operations retained')
