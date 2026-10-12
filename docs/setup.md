# Setup and hosting

Local entry commands are in [README](../README.md); [operations](operations.md) covers data-changing maintenance. `manage.py` loads `.env` before settings selection (development fallback); shell/`--settings` override it; isolated testing skips clinic `.env`. WSGI defaults production. Restart for environment changes; DB selection does not initialize schema or move data.

## Dependencies and environment

Python 3.10–3.12 for pinned Django 5.0.6/DRF 3.15.1. `requirements/{sqlite,postgresql,mysql,mariadb}.txt` include shared pins plus selected driver; `cache-{memcached,redis}.txt` adds only client. SQLite is built in, PostgreSQL uses psycopg, MySQL/MariaDB mysqlclient needs client headers if no wheel. External/cache servers and WSGI driver are separate. Other installed Django backends do not imply schema/locking compatibility.

Debian/Ubuntu system libraries: libmagic1, Pango/Cairo/GObject, libffi-dev, shared-mime-info; macOS: libmagic/pango/cairo/gdk-pixbuf/libffi. WeasyPrint is the PDF renderer; both bundled Cairo/Inter fonts must resolve together from frontend `public/static/fonts`, `dist/static/fonts` or `dist/fonts`, or Django `PDF_FONT_DIR` (not a parsed env variable). Missing assets fail rendering; [inspection](verification.md#pdf-inspection).

`config/settings/base.py`, `database.py` and `.env.example` own defaults. Copy example only when `.env` is absent; never overwrite private values. Generate separate secrets privately and retain original backup signing keys.

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
| `BACKUP_SAFETY_DAYS`, `BACKUP_WEEKLY_DAYS`, `BACKUP_MONTHLY_DAYS` | `30`, `90`, `365`; [retention](operations.md#retention).  |
| `NOTIFICATION_READ_RETENTION_DAYS`, `NOTIFICATION_UNREAD_RETENTION_DAYS` | `90`, `365` |
| `ADMIN_PASSWORD`, `DOCTOR_PASSWORD`, `RECEPTIONIST_PASSWORD` | Optional seed inputs; blank generates random password printed once. |

| Storage/config | Contract |
| --- | --- |
| MEDIA_ROOT / MEDIA_URL | `backend/media/`, `/media/`; clinical bytes only through authorized API downloads in DEBUG and production. |
| Static/templates | `staticfiles/`, `/static/`, existing sibling `frontend/dist/`; templates in backend and existing frontend bundle. Authorized collectstatic gathers existing assets. |
| OPERATION_LOCK_DIR | For non-PostgreSQL production, common reliable POSIX lock storage across every worker/job. PostgreSQL uses DB session advisory gates. |
| Runtime directories | Ignored `.env`, `data/`, `media/`, `backups/`, `staticfiles/`; protect backups/fonts/keys and patient data. Creating folders is not schema initialization. |

Schema work needs explicit authorization. `bootstrap`/`runserver_auto` prepare migrations; bootstrap `--with-demo-data` seeds, `--with-frontend` installs/builds, `--clean` deletes SQLite/custom migrations and needs destructive scope. Deliberate `seed_db` creates/updates role defaults/users/catalogs/tasks; passwords print once and new users require rotation. Default seed usernames admin/doctor1/receptionist1 are not fixed passwords. Never invoke these helpers only to fix a folder/check source.

## Production

All processes/jobs explicitly use `DJANGO_SETTINGS_MODULE=config.settings.production`, environment debug false, allowed hosts, external DB/shared cache, HTTPS and secure cookies. Production rejects empty hosts/SQLite/LocMemCache and non-PostgreSQL without common lock storage. Disable demo/auto-seed; keep credentials in protected environment. Shared cache is required for cross-worker preview/state, even though cache generations are durable DB state.

Apply authorized schema before starting changed models, especially CacheGeneration/RecoveryOperation/reminder-generation fields. Authorized assets: frontend frozen install/build then backend collectstatic; collecting first misses new assets. Current Vite output has source maps/minification disabled; choose release policy under build scope.

Example loopback service command (installed Gunicorn):

```bash
gunicorn --workers 3 --bind 127.0.0.1:5019 config.wsgi:application
```

Use a deployment-owned systemd unit with backend WorkingDirectory, production module/private EnvironmentFile, deploy user/group, restart-on-failure and explicit DB/cache dependencies. Three workers is an example, not measured capacity. Monitor service status/journal; reload deliberately.

Nginx HTTPS location essentials (configured certificates/server name/upstream required):

```nginx
client_max_body_size 220M;
location /static/ { alias /srv/myclinic/backend/staticfiles/; expires 30d; }
location /media/ { return 403; }
location / {
    proxy_pass http://127.0.0.1:5019;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_redirect off;
}
```

Redirect port 80 to HTTPS, validate/reload Nginx and check login/CSRF/assets/protected downloads on actual topology. Django final fallback serves existing frontend index; API/admin precede it. Direct SPA hosting instead needs `try_files` plus explicit API/admin proxy and static route; unknown API errors must not become SPA success.

Monitor individual production timers: reminders hourly (task offset five minutes), daily backup/retention and daily completed-operation cleanup. Development scheduler is not production orchestration. Update with last-good code/config and authenticated off-site backup, approved schema/assets, restart and [release checks](verification.md#release-checks); rollback may require deliberate compatible data recovery. No deployment action is implied by these examples.
