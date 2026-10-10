"""Disposable HTTP backend for Playwright; never loads the clinic environment."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.testing'
import django
from django.conf import settings
# SQLite needs a temporary file because HTTP requests use separate connections.
settings.DATABASES['default']['NAME'] = str(settings.TEST_WORKSPACE / 'browser.sqlite3')
settings.CSRF_TRUSTED_ORIGINS = ['http://127.0.0.1:5174']
django.setup()
from django.core.management import call_command
from apps.accounts.services import UserService
from apps.patients.services import PatientService
from tests.base import PASSWORD

if __name__ == '__main__':
    call_command('migrate', run_syncdb=True, verbosity=0)
    users = {}
    for role in ('admin', 'doctor', 'receptionist'):
        user = UserService().create_user(f'browser_{role}', PASSWORD, f'Synthetic {role}', role)
        user.force_password_change = False
        if role == 'admin':
            user.is_superuser = True
            user.is_staff = True
        user.save()
        users[role] = user
    PatientService().create_patient({'first_name': 'اختبار', 'surname': 'المتصفح'}, users['doctor'])
    call_command('runserver', '127.0.0.1:5018', use_reloader=False, verbosity=0)
