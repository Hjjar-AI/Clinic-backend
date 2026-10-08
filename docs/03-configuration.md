# Configuration

Environment variables, cache, storage.

## .env

`backend/.env`: loaded by `config/settings/base.py` via `python-dotenv`.

Never commit gitignored `.env`; rotate all secrets if committed.

### Variables

#### Security

| Variable | Default | Effect |
|---|---|---|
| `DJANGO_SECRET_KEY` | *(empty)* | Django session/crypto key. Required when `DJANGO_DEBUG=false`; `base.py` raises `RuntimeError` at import if blank. |
| `BACKUP_HMAC_KEY` | *(empty)* | HMAC key for signing backups. Same enforcement as above. |

Generate fresh values:

```bash
# SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# BACKUP_HMAC_KEY
python -c "import secrets; print(secrets.token_hex(32))"
```

#### Server

| Variable | Default | Effect |
|---|---|---|
| `DJANGO_DEBUG` | `False` | `true` enables debug pages. **Never `true` in production.** |
| `DJANGO_ALLOWED_HOSTS` | *(empty)* | Comma-separated hostnames. Required when `DEBUG=false`. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated origins allowed to send credentialed cross-origin requests. |

#### Database

Historical default: SQLite `backend/data/clinic.db`; `DATABASES` in `base.py` assumed direct PostgreSQL edits, not env configuration.

#### Session & auth

| Variable | Default | Effect |
|---|---|---|
| `SESSION_COOKIE_AGE` | `10800` (3 h) | Session lifetime in seconds. `0` means "until browser close" when `remember=False`. |
| `MAX_LOGIN_ATTEMPTS` | `10` | Failed attempts before lockout. |
| `LOGIN_LOCKOUT_MINUTES` | `15` | Lockout duration in minutes. |

#### Clinic metadata

| Variable | Default | Effect |
|---|---|---|
| `CLINIC_NAME` | `عيادة الإتزان` | Shown on PDFs and the frontend header. |
| `CLINIC_ADDRESS` | *(empty)* | PDF header line 2. |
| `CLINIC_PHONE` | *(empty)* | PDF header line 2. |
| `DEFAULT_PRESCRIPTION_INSTRUCTION` | `حسب تعليمات الطبيب` | Fallback medication instruction. |
| `ALLOW_DEMO_DATA` | `true` | If `false`, `GenerateDemoDataView` returns 403. |
| `AUTO_SEED` | `false` | Reserved; not currently enforced at startup. |

#### Working hours & appointments

| Variable | Default |
|---|---|
| `WORK_START_HOUR` / `WORK_START_MINUTE` | `8` / `0` |
| `WORK_END_HOUR` / `WORK_END_MINUTE` | `23` / `30` |
| `DEFAULT_APPOINTMENT_DURATION` | `30` (minutes) |
| `MAX_APPOINTMENTS_PER_VIEW` | `500` |

#### Uploads

All in MB.

| Variable | Default |
|---|---|
| `MAX_BULK_IMPORT_SIZE` | `200` |
| `MAX_ATTACHMENT_SIZE` | `10` |
| `MAX_CONTENT_LENGTH` | `210` |

#### Demo data

| Variable | Default |
|---|---|
| `DEMO_PATIENTS_COUNT` | `10` |
| `DEMO_VISITS_PER_PATIENT` | `3` |

#### Scheduler & backups

| Variable | Default |
|---|---|
| `SCHEDULER_INTERVAL_HOURS` | `2` |
| `BACKUP_CHECK_INTERVAL_HOURS` | `6` |
| `BACKUP_SAFETY_DAYS` | `30` |
| `BACKUP_WEEKDAY_MIN_DAYS` | `5` |
| `BACKUP_WEEKLY_DAYS` | `90` |
| `BACKUP_MONTHLY_DAYS` | `365` |

Retention: `05-operations.md#backup-retention`.

#### Cache

| Variable | Default |
|---|---|
| `CACHE_LOCATION` | `127.0.0.1:11211` |

See Cache below.

### Seed passwords (optional)

`seed_db` uses supplied passwords verbatim:

```ini
ADMIN_PASSWORD=
DOCTOR_PASSWORD=
RECEPTIONIST_PASSWORD=
```

Blank passwords generate random values printed **once** to stdout.

## Cache

Historical `config/settings/base.py` default:

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
        'LOCATION': os.environ.get('CACHE_LOCATION', '127.0.0.1:11211'),
    }
}
```

### Option A — memcached (default)

Start:

```bash
# Linux
sudo systemctl enable --now memcached

# macOS
brew services start memcached
```

Verify: `echo stats | nc 127.0.0.1 11211`.

### Option B — local memory (single-process dev only)

In `base.py`, replace the default block with the alternate:

```python
# CACHES = {
#     'default': {
#         'BACKEND': 'django.core.cache.backends.memcached.PyMemcacheCache',
#         'LOCATION': os.environ.get('CACHE_LOCATION', '127.0.0.1:11211'),
#     }
# }

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}
```

LocMemCache is per-process/unshared; `runserver` restarts clear it. Dev only, **never production**.

## File storage

`base.py`:

- `MEDIA_ROOT = BASE_DIR / 'media'` — where uploads land
- `MEDIA_URL = '/media/'` — served only when `DEBUG=true`

Historical production options: reverse-proxy `/media/` from `MEDIA_ROOT` or S3; Django media serving is slow/unsafe. See `04-deployment.md#media-files`; current README requires patient-media access control.

## Static files

- `STATIC_ROOT = BASE_DIR / 'staticfiles'` — `collectstatic` target
- `STATICFILES_DIRS = [BASE_DIR.parent / 'frontend' / 'dist']`
- `WHITENOISE_USE_FINDERS = True` and `WHITENOISE_AUTOREFRESH = True` (dev)

Authorized production collection: `python manage.py collectstatic --noinput`; serve `/static/` via installed WhiteNoise or reverse proxy.

## Templates

Template search order:

1. `backend/templates/`
2. `backend/../frontend/dist/`
3. Every app's `templates/` directory (via `APP_DIRS`)

Canonical PDF/email templates: `backend/templates/`.

## Settings modules

| Module | Use |
|---|---|
| `config.settings.base` | Shared; imported by the other two |
| `config.settings.development` | `DEBUG=True`, `ALLOWED_HOSTS=['*']` |
| `config.settings.production` | `DEBUG=False`, requires `DJANGO_ALLOWED_HOSTS` |

`DJANGO_SETTINGS_MODULE` defaults: `manage.py` → `development`, `wsgi.py` → `production`; override explicitly for nonstandard environments:

```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
```

## Next

- Operations → `05-operations.md`
- Deployment → `04-deployment.md`
