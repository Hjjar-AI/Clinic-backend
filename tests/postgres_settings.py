"""Only the owned disposable PostgreSQL runner may select this profile."""
import os
from pathlib import Path
from django.test.runner import DiscoverRunner
from config.settings.testing import *  # noqa: F403

_owned = Path(os.environ.get('CLINIC_OWNED_PG_ROOT', ''))
_socket = _owned / 'socket'
if not _owned.is_absolute() or _owned.parent != Path('/tmp') or not _owned.name.startswith('clinic-postgres-') or not (_owned / 'owned-by-test-runner').is_file():
    raise RuntimeError('PostgreSQL tests require the owned disposable test cluster')
DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'clinic_suite',
    'USER': 'clinic_suite', 'PASSWORD': '', 'HOST': str(_socket), 'PORT': '5432',
    'ATOMIC_REQUESTS': True, 'TEST': {'NAME': 'test_clinic_suite'}}}


class OwnedPostgresRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        database = DATABASES['default']
        if database['HOST'] != str(_socket) or not (_owned / 'owned-by-test-runner').is_file() or database['NAME'] != 'clinic_suite':
            raise RuntimeError('Refusing unowned database access')
        return super().setup_databases(**kwargs)


TEST_RUNNER = 'tests.postgres_settings.OwnedPostgresRunner'
