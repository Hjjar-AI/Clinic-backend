from django.core.management.base import BaseCommand, CommandError
from core.models import RecoveryOperation
from core.operation_gate import gated


class Command(BaseCommand):
    help = 'Acknowledge operator reconciliation of interrupted DB/media recovery'

    def add_arguments(self, parser):
        parser.add_argument('--key', required=True)
        parser.add_argument('--reason', required=True)
        parser.add_argument('--confirm-inventory-and-media', action='store_true')

    @gated(exclusive=True)
    def handle(self, *args, **options):
        if not options['confirm_inventory_and_media'] or not options['reason'].strip() or len(options['reason']) > 500:
            raise CommandError('Confirm reconciled database AND media and give a reason up to 500 characters')
        row = RecoveryOperation.objects.filter(key=options['key'], state__in=['processing', 'interrupted']).first()
        if row is None:
            raise CommandError('No interrupted receipt for this key')
        row.state = 'reconciled'
        row.result = {**row.result, 'reconciliation_reason': options['reason'].strip()}
        row.save(update_fields=['state', 'result'])
        self.stdout.write('Interrupted recovery acknowledged; use a new preview/key for further recovery')
