"""Packaged production runtime; writable clinic files live outside the bundle."""
import os
from pathlib import Path
import sys

from .production import *  # noqa: F403

_directory = os.environ.get('CLINIC_DATA_DIR', '').strip()
if not _directory or not Path(_directory).is_absolute() or not Path(_directory).is_dir():
    raise RuntimeError('CLINIC_DATA_DIR must be an existing absolute directory outside the application bundle.')
_data = Path(_directory).resolve()
_application = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else BASE_DIR
if _data == _application or _application in _data.parents:
    raise RuntimeError('CLINIC_DATA_DIR must be outside the application directory so upgrades preserve clinic files.')

MEDIA_ROOT = _data / 'media'
BACKUP_DIR = _data / 'backups'
STATIC_ROOT = _data / 'staticfiles'
if getattr(sys, 'frozen', False):
    _resources = Path(sys._MEIPASS) / 'resources'
    FRONTEND_DIST = Path(os.environ['FRONTEND_DIST']).expanduser() if os.environ.get('FRONTEND_DIST') else _resources / 'frontend'
    TEMPLATES[0]['DIRS'] = [_resources / 'templates', FRONTEND_DIST]
    STATICFILES_DIRS = [FRONTEND_DIST]
    # Serve immutable packaged assets directly, without development finders.
    WHITENOISE_ROOT = FRONTEND_DIST
    PDF_FONT_DIR = _resources / 'frontend' / 'static' / 'fonts'
