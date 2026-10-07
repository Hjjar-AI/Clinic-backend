# MyClinic backend

Django REST backend for clinic management: patients, clinical visits, appointments, billing, tasks, notifications, prescriptions, referrals, reports, imports, and backups. The sibling [Vue frontend](../frontend/README.md) provides the Arabic interface.

## Requirements

- Python compatible with the pinned Django 5.0.6 release (Python 3.10–3.12).
- A virtual environment and the packages in [requirements.txt](requirements.txt).
- System libraries for `python-magic` and WeasyPrint, plus fonts supporting Arabic for PDF output.
- SQLite for local development. Production requires an external database and a shared cache, with their matching Python drivers installed separately.

## Local setup

Run these commands from `backend/` on a POSIX shell:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
mkdir -p data media backups
```

If `.env` already exists, edit it instead of replacing it. Set `DJANGO_DEBUG=True`, then generate separate secrets and put their output into `DJANGO_SECRET_KEY` and `BACKUP_HMAC_KEY`:

```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
python -c 'import secrets; print(secrets.token_hex(32))'
```

The example enables `ALLOW_DEMO_DATA` and `AUTO_SEED`; set both to `false` for an empty clinic setup. Keep the backup signing key available when recovering backups.

**Database prerequisite:** prepare a fresh database schema matching the current models before seeding or starting normal workflows. Schema initialization is a separate, explicitly authorized step under this project's rules; this guide does not generate or apply migrations. Existing `bootstrap` and `runserver_auto` helpers perform migration work, so they are outside this setup sequence.

After the schema is ready, initialize the application and start Django:

```bash
python manage.py seed_db
python manage.py runserver 127.0.0.1:5019
```

`seed_db` creates permissions, role groups, default users, clinic settings, catalogs, and tasks. New account passwords are generated and printed once unless `ADMIN_PASSWORD`, `DOCTOR_PASSWORD`, and `RECEPTIONIST_PASSWORD` are supplied through the environment. New users must change their passwords. Re-running the command updates role permissions and default clinic settings; use it deliberately.

Start the frontend separately using its README. Django's API is available at `http://localhost:5019/api/v1/`, and the administration site at `/admin/`. Serving the SPA through Django requires an existing `frontend/dist/`.

## Configuration

Settings load `backend/.env`; see [.env.example](.env.example) and [base settings](config/settings/base.py) for all supported values.

| Setting | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY`, `BACKUP_HMAC_KEY` | Session/application security and backup authentication |
| `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` | Debug mode and production hostnames |
| `CORS_ORIGINS` | Allowed browser origins; defaults include port 5173 |
| `DATABASE_ENGINE`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_HOST`, `DATABASE_PORT` | External database configuration |
| `CACHE_BACKEND`, `CACHE_LOCATION` | Shared cache configuration |
| `TIME_ZONE` | Clinic timezone; defaults to `Asia/Damascus` |
| `CLINIC_NAME`, `CLINIC_ADDRESS`, `CLINIC_PHONE` | Clinic identity defaults |
| `MAX_BULK_IMPORT_SIZE`, `MAX_ATTACHMENT_SIZE`, `MAX_CONTENT_LENGTH` | Upload limits in MB |
| `SESSION_COOKIE_AGE`, `MAX_LOGIN_ATTEMPTS`, `LOGIN_LOCKOUT_MINUTES` | Session and login limits |
| `SCHEDULER_INTERVAL_HOURS`, `BACKUP_CHECK_INTERVAL_HOURS`, `BACKUP_*_DAYS` | Scheduling and backup retention |

`manage.py` defaults to `config.settings.development`, which forces debug mode and allows all hosts. Production must explicitly select `config.settings.production` and set `DJANGO_DEBUG=False` in the environment. That module requires allowed hosts, an external database, and a shared cache, enables secure cookies, and disables demo data. Use HTTPS and a production application server; provision its package and database/cache drivers separately.

## API and workflow contracts

- API prefix: `/api/v1/`. JSON responses use a `data` envelope or an `error` object containing `code`, `message`, and optional validation errors; downloads return files.
- Authentication uses session cookies. Fetch `/api/v1/system/config/` to obtain the CSRF cookie before `POST /api/v1/auth/login/`; send `X-CSRFToken` on unsafe requests.
- Access combines the `admin`, `doctor`, and `receptionist` roles, action permissions, and patient/care-team scope.
- Supported updates require the current resource `version` in the body or `If-Match`. Refresh stale records after a conflict.
- Mutations covered by idempotency enforcement use `X-Idempotency-Key`. Retrying one logical operation must reuse its key and payload.
- Finalized visits keep immutable signed revisions. Prescription/referral issuance requires a final or locked visit with a signed revision and preserves the issued document.
- Invoice lines determine totals; payment records include the actor and time. Archival preserves clinical history, and pseudonymization retains identity snapshots in signed history.

## Operations and data recovery

Run management commands from the activated backend environment:

| Command | Effect |
| --- | --- |
| `python manage.py send_appointment_reminders` | Process appointment reminders |
| `python manage.py send_task_reminders` | Process task reminders |
| `python manage.py auto_backup` | Check whether an automatic backup is due |
| `python manage.py cleanup_backups` | Apply backup retention; removes expired backup files |
| `python manage.py run_scheduler` | Run the periodic development loop for reminders, backups, and retention |
| `python manage.py reconcile_media` | Report missing files and old unreferenced uploads without deleting them |

Use cron or systemd timers for the individual scheduled commands in production. Media reconciliation deletes old orphaned uploads only when explicitly given `--delete`.

Full ZIP backups include managed records and media, with authenticated manifests and checksums. Full restore replaces the managed inventory, creates a safety backup, and revokes sessions; it requires a matching preview and confirmation. Catalog-only restore merges catalog data. JSON exports do not include media bytes and cannot recover missing files. Spreadsheet imports also require a preview before applying changes.

Keep `.env`, `data/`, `media/`, `backups/`, and `staticfiles/` out of source control. Serve production media through an access-controlled mechanism appropriate for patient records.

## Layout and development

| Directory | Contents |
| --- | --- |
| `apps/` | Feature models, serializers, services, views, and routes |
| `core/` | Shared permissions, validation, caching, auditing, and management commands |
| `config/` | Django settings and entry points |
| `templates/` | Server-rendered documents and templates |
| `docs/` | Setup, operations, review findings, and implementation notes |

Read [AGENTS.md](AGENTS.md), [workCurrent.md](workCurrent.md), and [doneCurrent.md](doneCurrent.md) before making changes. Migration work, test-suite access, builds/compilation/packaging, and version changes require explicit authorization.

See the [documentation index](docs/README.md), [implemented backend fixes](docs/backend-fixes-implementation.md), and [workflow checklist](docs/critical-workflow-checklist.md). Older guides may describe setup helpers with broader side effects; follow the current project rules. Outstanding validation includes PDF/Arabic rendering, browser workflows, and PostgreSQL concurrency behavior.
