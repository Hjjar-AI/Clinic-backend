"""Disposable HTTP backend for Playwright; never loads the clinic environment."""
import os
import sys
import signal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.testing'
import django
from django.conf import settings
# SQLite needs a temporary file because HTTP requests use separate connections.
settings.DATABASES['default']['NAME'] = str(settings.TEST_WORKSPACE / 'browser.sqlite3')
settings.CSRF_TRUSTED_ORIGINS = ['http://127.0.0.1:5174']
# All viewport cases share synthetic accounts and a localhost IP. Keep the
# application throttles enabled with browser-fixture quotas; production quotas
# would measure aggregate suite traffic rather than an individual workflow.
settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, 'DEFAULT_THROTTLE_RATES': {
    'anon': '10000/hour', 'user': '100000/hour',
}}
django.setup()
from django.core.management import call_command
from apps.accounts.services import UserService
from apps.patients.services import PatientService
from apps.notifications.services import NotificationService
from tests.base import PASSWORD

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
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
    # Each viewport owns unread notices so read/delete checks do not share state.
    for viewport in ('desktop', 'tablet', 'mobile'):
        user = UserService().create_user(f'browser_panel_{viewport}', PASSWORD, 'Synthetic panel user', 'admin')
        user.force_password_change = False
        user.save()
        for index in range(2):
            NotificationService().create(user.pk, f'Synthetic notice {index}', 'Synthetic panel message')
    call_command('runserver', '127.0.0.1:5018', use_reloader=False, verbosity=0)
