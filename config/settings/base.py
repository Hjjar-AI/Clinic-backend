import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / '.env')

# Item #4 / #1: read DEBUG first so the SECRET_KEY guard below can key off it.
DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',') if os.environ.get('DJANGO_ALLOWED_HOSTS') else []

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
BACKUP_HMAC_KEY = os.environ.get('BACKUP_HMAC_KEY', '')

# Item #1: fail loudly if the rotated keys are missing in production.
# DEBUG=True can still boot with a dev key, but production must not.
if not DEBUG:
    if not SECRET_KEY:
        raise RuntimeError(
            'DJANGO_SECRET_KEY is not set. Generate one with: '
            'python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"'
        )
    if not BACKUP_HMAC_KEY:
        raise RuntimeError(
            'BACKUP_HMAC_KEY is not set. Generate one with: '
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )

BACKUP_DIR = BASE_DIR / 'backups'
CLINIC_NAME = os.environ.get('CLINIC_NAME', 'عيادة الإتزان')
CLINIC_ADDRESS = os.environ.get('CLINIC_ADDRESS', '')
CLINIC_PHONE = os.environ.get('CLINIC_PHONE', '')
DEFAULT_PRESCRIPTION_INSTRUCTION = os.environ.get('DEFAULT_PRESCRIPTION_INSTRUCTION', 'حسب تعليمات الطبيب')
ALLOW_DEMO_DATA = os.environ.get('ALLOW_DEMO_DATA', 'false').lower() == 'true'
AUTO_SEED = os.environ.get('AUTO_SEED', 'false').lower() == 'true'

# Item #9: demo data volume, previously declared in .env but never read.
DEMO_PATIENTS_COUNT = int(os.environ.get('DEMO_PATIENTS_COUNT', 10))
DEMO_VISITS_PER_PATIENT = int(os.environ.get('DEMO_VISITS_PER_PATIENT', 3))

WORK_START_HOUR = int(os.environ.get('WORK_START_HOUR', 8))
WORK_START_MINUTE = int(os.environ.get('WORK_START_MINUTE', 0))
WORK_END_HOUR = int(os.environ.get('WORK_END_HOUR', 23))
WORK_END_MINUTE = int(os.environ.get('WORK_END_MINUTE', 30))
DEFAULT_APPOINTMENT_DURATION = int(os.environ.get('DEFAULT_APPOINTMENT_DURATION', 30))
MAX_APPOINTMENTS_PER_VIEW = int(os.environ.get('MAX_APPOINTMENTS_PER_VIEW', 500))

MAX_BULK_IMPORT_SIZE = int(os.environ.get('MAX_BULK_IMPORT_SIZE', 200)) * 1024 * 1024
MAX_ATTACHMENT_SIZE = int(os.environ.get('MAX_ATTACHMENT_SIZE', 10)) * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get('MAX_CONTENT_LENGTH', 210)) * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = FILE_UPLOAD_MAX_MEMORY_SIZE

# ---------------------------------------------------------------------
# Scheduler & backup retention
# ---------------------------------------------------------------------
# Consumed by:
#   - core/management/commands/run_scheduler.py       (SCHEDULER_INTERVAL_HOURS)
#   - core/management/commands/auto_backup.py         (BACKUP_CHECK_INTERVAL_HOURS, if used)
#   - core/management/commands/cleanup_backups.py     (retention windows)
#   - apps/backup/retention.py                        (retention windows)
#
# BACKUP_WEEKDAY_MIN_DAYS was previously declared here but read by nothing
# in the codebase. It has been removed to stop it appearing tunable.
SCHEDULER_INTERVAL_HOURS = float(os.environ.get('SCHEDULER_INTERVAL_HOURS', 2))
BACKUP_CHECK_INTERVAL_HOURS = float(os.environ.get('BACKUP_CHECK_INTERVAL_HOURS', 6))
BACKUP_SAFETY_DAYS = int(os.environ.get('BACKUP_SAFETY_DAYS', 30))
BACKUP_WEEKLY_DAYS = int(os.environ.get('BACKUP_WEEKLY_DAYS', 90))
BACKUP_MONTHLY_DAYS = int(os.environ.get('BACKUP_MONTHLY_DAYS', 365))
NOTIFICATION_READ_RETENTION_DAYS = int(os.environ.get('NOTIFICATION_READ_RETENTION_DAYS', 90))
NOTIFICATION_UNREAD_RETENTION_DAYS = int(os.environ.get('NOTIFICATION_UNREAD_RETENTION_DAYS', 365))

SESSION_COOKIE_AGE = int(os.environ.get('SESSION_COOKIE_AGE', 10800))
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'

# Item #8: login lockout thresholds were declared in .env but hardcoded in
# apps/accounts/models.py. Now sourced from settings so the .env values apply.
MAX_LOGIN_ATTEMPTS = int(os.environ.get('MAX_LOGIN_ATTEMPTS', 10))
LOGIN_LOCKOUT_MINUTES = int(os.environ.get('LOGIN_LOCKOUT_MINUTES', 15))

CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in os.environ.get(
        'CORS_ORIGINS',
        'http://localhost:5173,http://127.0.0.1:5173'
    ).split(',')
]
CORS_ALLOW_CREDENTIALS = True

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'whitenoise.runserver_nostatic',
    'rest_framework',
    'corsheaders',
    'core.apps.CoreConfig',
    'apps.accounts',
    'apps.patients',
    'apps.visits',
    'apps.appointments',
    'apps.clinical',
    'apps.billing',
    'apps.tasks',
    'apps.notifications',
    'apps.backup',
    'apps.reports',
    'apps.import_export',
    'apps.prescriptions',
    'apps.referrals',
    'apps.dashboard',
    'apps.settings',
    'apps.exports',
    'apps.system',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # Session revocation must run after AuthenticationMiddleware so request.user is available
    'core.middleware.SessionRevocationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.RequestContextMiddleware',
]
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True
ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
            BASE_DIR.parent / 'frontend' / 'dist',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------
# Default is SQLite for local development. Production must override via
# DATABASE_ENGINE (see config/settings/production.py, which refuses to boot
# on SQLite). Accepts any Django database backend name; for non-SQLite
# backends the standard DATABASE_NAME / USER / PASSWORD / HOST / PORT env
# vars are read.
DATABASE_ENGINE = os.environ.get('DATABASE_ENGINE', 'django.db.backends.sqlite3')

if DATABASE_ENGINE == 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': DATABASE_ENGINE,
            'NAME': BASE_DIR / 'data' / 'clinic.db',
            'OPTIONS': {
                'init_command': 'PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL;',
                'timeout': 20,
            },
            'ATOMIC_REQUESTS': True,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': DATABASE_ENGINE,
            'NAME': os.environ.get('DATABASE_NAME', 'clinic'),
            'USER': os.environ.get('DATABASE_USER', ''),
            'PASSWORD': os.environ.get('DATABASE_PASSWORD', ''),
            'HOST': os.environ.get('DATABASE_HOST', ''),
            'PORT': os.environ.get('DATABASE_PORT', ''),
            'CONN_MAX_AGE': int(os.environ.get('DATABASE_CONN_MAX_AGE', 600)),
            'ATOMIC_REQUESTS': True,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        # Item #11: make the effective minimum explicit so it matches the
        # serializer's min_length and the docs. Default was 8.
        'OPTIONS': {'min_length': 8},
    },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = os.environ.get('TIME_ZONE', 'Asia/Damascus')
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR.parent / 'frontend' / 'dist',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'accounts.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'core.renderers.EnvelopeJSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
    'EXCEPTION_HANDLER': 'core.exceptions.custom_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    },
}

# ---------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------
# Default is process-local LocMemCache for development. Production must
# override via CACHE_BACKEND (see config/settings/production.py, which
# refuses to boot on LocMemCache).
#
# Why this matters beyond "use a real cache in prod": the invalidate_group()
# version-counter scheme in core/cache_utils.py relies on a single shared
# store. With LocMemCache and multiple worker processes, each worker keeps
# its own counter and its own cached values, so a write that invalidates
# a group in worker A leaves workers B/C/D serving stale dashboard/report/
# settings data until their process restarts.
CACHE_BACKEND = os.environ.get('CACHE_BACKEND', '')

if CACHE_BACKEND:
    CACHES = {
        'default': {
            'BACKEND': CACHE_BACKEND,
            'LOCATION': os.environ.get('CACHE_LOCATION', '127.0.0.1:11211'),
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}
