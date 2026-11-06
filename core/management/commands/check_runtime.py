import platform
from django.core.management.base import BaseCommand, CommandError
from core.runtime_checks import runtime_report


class Command(BaseCommand):
    help = 'Check OS locks, WSGI, MIME, PDF/fonts and time zones without accessing clinic storage.'
    requires_system_checks = []
    requires_migrations_checks = False

    def add_arguments(self, parser):
        parser.add_argument('--render-pdf', action='store_true', help='Also render a synthetic Arabic/Latin PDF in memory.')

    def handle(self, *args, **options):
        self.stdout.write(f'{platform.system()} / Python {platform.python_version()}')
        results = runtime_report(render_pdf=options['render_pdf'])
        for name, passed, detail in results:
            self.stdout.write(f'{"OK" if passed else "FAIL"} {name}: {detail}')
        if any(not passed for _, passed, _ in results):
            raise CommandError('Runtime dependencies are incomplete; follow the reported remedies and docs/setup.md.')
