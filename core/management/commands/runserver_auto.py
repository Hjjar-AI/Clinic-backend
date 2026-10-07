from django.core.management import call_command
from django.core.management.commands.runserver import Command as RunserverCommand

class Command(RunserverCommand):
    help = 'Runs makemigrations, migrate, then starts the development server'

    def handle(self, *args, **options):
        # Generate migration files from model changes
        call_command('makemigrations')
        # Apply all pending migrations
        call_command('migrate')
        # Start the server
        super().handle(*args, **options)