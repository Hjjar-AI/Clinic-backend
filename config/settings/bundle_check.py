"""Disposable, database-free settings for source and frozen runtime checks."""
import atexit
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

with patch('dotenv.load_dotenv'), patch.dict(os.environ, {
    'DJANGO_DEBUG': 'true',
    'DJANGO_SECRET_KEY': 'synthetic-runtime-check',
    'BACKUP_HMAC_KEY': 'synthetic-runtime-check-backup',
}, clear=True):
    from .base import *  # noqa: F403

_workspace = TemporaryDirectory(prefix='clinic-runtime-')
atexit.register(_workspace.cleanup)
DEBUG = False
ALLOW_DEMO_DATA = False
AUTO_SEED = False
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
MEDIA_ROOT = Path(_workspace.name) / 'media'
BACKUP_DIR = Path(_workspace.name) / 'backups'
OPERATION_LOCK_DIR = Path(_workspace.name) / 'locks'
STATIC_ROOT = Path(_workspace.name) / 'static'
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
LOGGING = {'version': 1, 'disable_existing_loggers': False,
           'handlers': {'console': {'class': 'logging.StreamHandler'}},
           'root': {'handlers': ['console'], 'level': 'WARNING'}}
if getattr(sys, 'frozen', False):
    _resources = Path(sys._MEIPASS) / 'resources'
    TEMPLATES[0]['DIRS'] = [_resources / 'templates', _resources / 'frontend']
    STATICFILES_DIRS = [_resources / 'frontend']
    PDF_FONT_DIR = _resources / 'frontend' / 'static' / 'fonts'
