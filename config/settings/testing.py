"""Isolated settings: never load clinic .env, database, media, cache or secrets."""
import atexit
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

with patch('dotenv.load_dotenv'), patch.dict(os.environ, {
    'DJANGO_DEBUG': 'true', 'DJANGO_SECRET_KEY': 'synthetic-test-secret',
    'BACKUP_HMAC_KEY': 'synthetic-test-backup-key',
}, clear=True):
    from .base import *  # noqa: F403

_workspace = TemporaryDirectory(prefix='clinic-suite-')
atexit.register(_workspace.cleanup)
TEST_WORKSPACE = Path(_workspace.name)
DEBUG = False
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:',
                         'TEST': {'NAME': ':memory:'}, 'ATOMIC_REQUESTS': True}}
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                       'LOCATION': 'clinic-test-suite'}}
MEDIA_ROOT = TEST_WORKSPACE / 'media'
BACKUP_DIR = TEST_WORKSPACE / 'backups'
STATIC_ROOT = TEST_WORKSPACE / 'static'
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
ALLOW_DEMO_DATA = False
AUTO_SEED = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
# Exercise current models without reading/generating/applying migration files.
MIGRATION_MODULES = {name.rsplit('.', 1)[-1]: None for name in INSTALLED_APPS if name.startswith('apps.')}
MIGRATION_MODULES.update({name: None for name in ('core', 'auth', 'admin', 'contenttypes', 'sessions')})
TEST_RUNNER = 'tests.runner.IsolatedRunner'
LOGGING = {'version': 1, 'disable_existing_loggers': False,
           'handlers': {'null': {'class': 'logging.NullHandler'}},
           'loggers': {'django.request': {'handlers': ['null'], 'propagate': False}}}
