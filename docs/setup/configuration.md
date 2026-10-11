# Configuration by owning file

`config/settings/base.py` loads ignored `backend/.env`; `.env.example` is an example, source defaults below are authoritative. `manage.py` defaults development; WSGI defaults production. Explicitly export `DJANGO_SETTINGS_MODULE=config.settings.production` and set environment `DJANGO_DEBUG=false` for deployment. Development forces debug/all hosts; production forces debug/demo/auto-seed off and secure session/CSRF cookies, rejects empty hosts/SQLite/LocMemCache.

## Environment (`config/settings/base.py`)

| Variables | Source default / purpose |
| --- | --- |
| `DJANGO_SECRET_KEY`, `BACKUP_HMAC_KEY` | Empty; required when environment debug is false. Keep separate keys; retain backup keys needed for existing archives. |
| `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` | `false`, empty; comma-separated production hosts, no wildcard. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173`; exact credentialed origins. |
| `DATABASE_ENGINE` | `django.db.backends.sqlite3`; SQLite path fixed at `data/clinic.db`, WAL/foreign keys/20s timeout. |
| `DATABASE_NAME/USER/PASSWORD/HOST/PORT`, `DATABASE_CONN_MAX_AGE` | External backend: `clinic` / empty credentials/host/port, max age `600`; install database driver separately. |
| `CACHE_BACKEND`, `CACHE_LOCATION` | Unset backend means development LocMemCache `unique-snowflake`; explicit backend location defaults `127.0.0.1:11211`. Production needs shared cache/driver, e.g. PyMemcacheCache or RedisCache. |
| `TIME_ZONE` | `Asia/Damascus`; aware timestamps, clinic-local business dates. |
| `SESSION_COOKIE_AGE`, `SESSION_COOKIE_SECURE` | `10800` seconds, `false` in base; session HttpOnly/SameSite Lax, CSRF readable by client. Production forces secure cookies. |
| `MAX_LOGIN_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES` | `10`, `15`; durable lockout. |
| `CLINIC_NAME/ADDRESS/PHONE` | `عيادة الإتزان` / empty / empty; UI/PDF identity defaults. |
| `DEFAULT_PRESCRIPTION_INSTRUCTION` | `حسب تعليمات الطبيب` |
| `ALLOW_DEMO_DATA`, `AUTO_SEED` | Both `false`; production forces false. `AUTO_SEED` is declared/reserved, not automatic startup seeding. |
| `DEMO_PATIENTS_COUNT`, `DEMO_VISITS_PER_PATIENT` | `10`, `3`; bounded service validation still applies. |
| `WORK_START_HOUR/MINUTE`, `WORK_END_HOUR/MINUTE` | `8/0`, `23/30`; scheduling bounds. |
| `DEFAULT_APPOINTMENT_DURATION`, `MAX_APPOINTMENTS_PER_VIEW` | `30` minutes, `500` rows. |
| `MAX_BULK_IMPORT_SIZE`, `MAX_ATTACHMENT_SIZE`, `MAX_CONTENT_LENGTH` | `200`, `10`, `210` MB; last bounds both file/data memory limits. Proxy upload limit must accommodate it. |
| `SCHEDULER_INTERVAL_HOURS`, `BACKUP_CHECK_INTERVAL_HOURS` | `2`, `6`; scheduler/settings declarations. `auto_backup` itself creates a backup on every invocation. |
| `BACKUP_SAFETY_DAYS`, `BACKUP_WEEKLY_DAYS`, `BACKUP_MONTHLY_DAYS` | `30`, `90`, `365`; [retention](../operations/guide.md). `BACKUP_WEEKDAY_MIN_DAYS` removed/unused. |
| `NOTIFICATION_READ_RETENTION_DAYS`, `NOTIFICATION_UNREAD_RETENTION_DAYS` | `90`, `365` |
| `ADMIN_PASSWORD`, `DOCTOR_PASSWORD`, `RECEPTIONIST_PASSWORD` | Optional seed inputs; blank generates random password printed once. |

Secret generation (save privately, never in source/output shared with others):

```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
python -c 'import secrets; print(secrets.token_hex(32))'
```

Memcached Linux: `sudo systemctl enable --now memcached`; macOS: `brew services start memcached`. Probe with `echo stats | nc 127.0.0.1 11211`. Configure environment backend instead of editing shared settings; LocMemCache is per-process and unsuitable for production cache generations.

## Storage, templates and fonts

| Source / setting | Contract |
| --- | --- |
| `MEDIA_ROOT`, `MEDIA_URL` | `backend/media/`, `/media/`; debug-only Django serving. Production must protect patient bytes through authorized downloads; public media alias is unsuitable. |
| `STATIC_ROOT`, `STATICFILES_DIRS`, `STATIC_URL` | `backend/staticfiles/`, sibling `frontend/dist/`, `/static/`; authorized `collectstatic --noinput` gathers existing assets. Development WhiteNoise finders/autorefresh enabled. |
| Template search | `backend/templates/`, sibling `frontend/dist/`, app templates; canonical PDF/email templates in backend. |
| `core/pdf_utils.py`, optional Django `PDF_FONT_DIR` setting | Both Cairo/Inter variable fonts must resolve together from frontend `public/static/fonts`, `dist/static/fonts` or `dist/fonts`, or explicit deployed setting directory. Not a currently parsed `.env` variable. Missing fonts fail renderer instead of silent substitution. |
| Runtime privacy | Ignore `.env`, data/media/backups/staticfiles; protect off-site copies/signing keys and avoid patient/credential logs. |

System libraries/import check: [development](development.md); hosting/HTTPS: [deployment](deployment.md); API/commands: [reference](../reference.md).
