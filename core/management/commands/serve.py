from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.wsgi import get_wsgi_application
from core.runtime_checks import runtime_report


class Command(BaseCommand):
    help = 'Serve Django with Waitress on Linux/Windows, without migrations or seeding.'
    requires_system_checks = []
    requires_migrations_checks = False

    def add_arguments(self, parser):
        parser.add_argument('--host', default='127.0.0.1')
        parser.add_argument('--port', type=int, default=5019)
        parser.add_argument('--threads', type=int, default=8)

    def handle(self, *args, **options):
        if not 1 <= options['port'] <= 65535 or not 1 <= options['threads'] <= 128:
            raise CommandError('Port must be 1–65535; threads must be 1–128.')
        failures = [name for name, passed, _ in runtime_report() if not passed]
        if failures:
            raise CommandError('Runtime checks failed: ' + ', '.join(failures) + '. Run python manage.py check_runtime.')
        self.check()
        from waitress import serve
        self.stdout.write(f'Waitress listening on {options["host"]}:{options["port"]}')
        if settings.DEBUG:
            self.stdout.write(self.style.WARNING('Development settings are active; production requires explicit production settings.'))
        serve(get_wsgi_application(), host=options['host'], port=options['port'], threads=options['threads'],
              max_request_body_size=settings.FILE_UPLOAD_MAX_MEMORY_SIZE, expose_tracebacks=False)
