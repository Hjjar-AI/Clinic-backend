# Configuration by owning file

`config/settings/base.py` loads ignored `backend/.env`; `.env.example` is an example, source defaults below are authoritative. `manage.py` loads `.env` before selecting `DJANGO_SETTINGS_MODULE` (development fallback); shell variables and `--settings` override it; explicit `config.settings.testing` skips clinic `.env`. WSGI defaults production. Explicitly export `DJANGO_SETTINGS_MODULE=config.settings.production` and set environment `DJANGO_DEBUG=false` for deployment. Development honors configured debug/hosts; production forces debug/demo/auto-seed off and secure session/CSRF cookies, rejects empty hosts/SQLite/LocMemCache.

## Environment (`config/settings/base.py`)

| Variables | Source default / purpose |
| --- | --- |
| `DJANGO_SECRET_KEY`, `BACKUP_HMAC_KEY` | Empty; required when environment debug is false. Keep separate keys; retain backup keys needed for existing archives. |
| `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` | `false`, empty; comma-separated production hosts, no wildcard. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173`; exact credentialed origins. |
| `DATABASE_ENGINE` | Defaults SQLite; aliases `sqlite/sqlite3`, `postgres/postgresql`, `mysql/maria/mariadb`, or an installed full Django backend path. |
| `DATABASE_NAME` | SQLite: backend-relative/absolute path, `:memory:` or `file:` URI; blank defaults `data/clinic.db`. External DB: blank defaults `clinic`. |
| `DATABASE_USER/PASSWORD/HOST/PORT`, `DATABASE_CONN_MAX_AGE` | External credentials/server, default max age `600`; SQLite ignores them. |
| `DATABASE_TIMEOUT` | SQLite seconds, default `20`; foreign keys native, WAL initialization only on Django 5.1+. |
| `DATABASE_SSLMODE`, `DATABASE_SSL_CA`, `DATABASE_OPTIONS` | Optional PostgreSQL SSL mode/CA or MySQL CA; JSON object overrides driver options. MySQL/MariaDB defaults utf8mb4/strict mode; use InnoDB. |
| `CACHE_BACKEND`, `CACHE_LOCATION` | Unset backend means development LocMemCache `unique-snowflake`; Blank location defaults to local-memory name, Redis URL or Memcached address according to backend. Production needs shared cache/driver, e.g. PyMemcacheCache or RedisCache. |
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
| `SCHEDULER_INTERVAL_HOURS`, `BACKUP_CHECK_INTERVAL_HOURS` | `2`, `6`; scheduler caps reminder polling at half its shortest hour window and independently limits automatic backup cadence to the latter setting. Direct `auto_backup` creates a backup on every invocation. |
| `BACKUP_SAFETY_DAYS`, `BACKUP_WEEKLY_DAYS`, `BACKUP_MONTHLY_DAYS` | `30`, `90`, `365`; [retention](../operations/guide.md). `BACKUP_WEEKDAY_MIN_DAYS` removed/unused. |
| `NOTIFICATION_READ_RETENTION_DAYS`, `NOTIFICATION_UNREAD_RETENTION_DAYS` | `90`, `365` |
| `ADMIN_PASSWORD`, `DOCTOR_PASSWORD`, `RECEPTIONIST_PASSWORD` | Optional seed inputs; blank generates random password printed once. |

Secret generation (save privately, never in source/output shared with others):

```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
python -c 'import secrets; print(secrets.token_hex(32))'
```

Memcached Linux: `sudo systemctl enable --now memcached`; macOS: `brew services start memcached`. Probe with `echo stats | nc 127.0.0.1 11211`. Configure environment backend instead of editing shared settings; LocMemCache is per-process and unsuitable for production cache generations.

## Dependency profiles and switching

| Profile (from backend) | Includes |
| --- | --- |
| `pip install -r requirements/sqlite.txt` | Shared pinned `requirements.txt`; SQLite is included with Python, no DB driver. |
| `pip install -r requirements/postgresql.txt` | Shared pins + psycopg binary driver. |
| `pip install -r requirements/mysql.txt` or `requirements/mariadb.txt` | Shared pins + mysqlclient; system client headers/build tools needed when no wheel exists. MariaDB uses Django MySQL backend. |
| `pip install -r requirements/cache-memcached.txt` or `requirements/cache-redis.txt` | Optional cache client only; cache server installed/running separately. |

Replace active DB/cache assignments with the commented alternative in `.env`, supply server/name/credentials/SSL, restart and run via `python manage.py COMMAND`. Switching selects a connection; it does not transfer data or initialize schema. Existing values are preserved when organizing environment files. Other Django backends need their own installed driver/options; application/schema/locking compatibility is not implied by selection. [Django backend guidance](https://docs.djangoproject.com/en/5.0/ref/databases/), [SQLite init commands added in 5.1](https://docs.djangoproject.com/en/5.1/ref/databases/#setting-pragma-options).

## Storage, templates and fonts

| Source / setting | Contract |
| --- | --- |
| `MEDIA_ROOT`, `MEDIA_URL` | `backend/media/`, `/media/`; debug-only Django serving. Production must protect patient bytes through authorized downloads; public media alias is unsuitable. |
| `STATIC_ROOT`, `STATICFILES_DIRS`, `STATIC_URL` | `backend/staticfiles/`, sibling `frontend/dist/`, `/static/`; authorized `collectstatic --noinput` gathers existing assets. Development WhiteNoise finders/autorefresh enabled. |
| Template search | `backend/templates/`, sibling `frontend/dist/`, app templates; canonical PDF/email templates in backend. |
| `core/pdf_utils.py`, optional Django `PDF_FONT_DIR` setting | Both Cairo/Inter variable fonts must resolve together from frontend `public/static/fonts`, `dist/static/fonts` or `dist/fonts`, or explicit deployed setting directory. Not a currently parsed `.env` variable. Missing fonts fail renderer instead of silent substitution. |
| Runtime privacy | Ignore `.env`, data/media/backups/staticfiles; protect off-site copies/signing keys and avoid patient/credential logs. |

System libraries/import check: [development](development.md); hosting/HTTPS: [deployment](deployment.md); API/commands: [reference](../reference.md).
