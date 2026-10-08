# MyClinic backend

Django REST clinic backend: patients, visits, appointments, billing, tasks, notifications, prescriptions, referrals, reports, imports, backups; Arabic UI: [Vue frontend](../frontend/README.md).

## Requirements

- Python 3.10–3.12 for pinned Django 5.0.6.
- Virtual environment with [requirements.txt](requirements.txt).
- `python-magic`/WeasyPrint system libraries and Arabic PDF fonts.
- Local: SQLite. Production: external database/shared cache; install matching Python drivers separately.

## Local setup

From `backend/`, POSIX shell:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
mkdir -p data media backups
```

Edit an existing `.env` rather than overwrite it. Set `DJANGO_DEBUG=True`; generate separate `DJANGO_SECRET_KEY`/`BACKUP_HMAC_KEY` values:

```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
python -c 'import secrets; print(secrets.token_hex(32))'
```

For an empty clinic, change example `ALLOW_DEMO_DATA`/`AUTO_SEED` to `false`. Retain the backup signing key for recovery.

**Database prerequisite:** prepare a fresh schema matching current models before seeding/workflows. Schema initialization requires separate explicit authorization; this guide generates/applies no migrations. Exclude migration-running `bootstrap`/`runserver_auto` from this sequence.

Once the schema is ready, initialize/start Django:

```bash
python manage.py seed_db
python manage.py runserver 127.0.0.1:5019
```

`seed_db` creates permissions, role groups, users, clinic settings, catalogs, tasks. Passwords print once unless environment `ADMIN_PASSWORD`/`DOCTOR_PASSWORD`/`RECEPTIONIST_PASSWORD` are supplied; new users must change them. Re-running updates role permissions/default clinic settings; use deliberately.

Start frontend separately per its README. API: `http://localhost:5019/api/v1/`; admin: `/admin/`. Django SPA serving requires existing `frontend/dist/`.

## Configuration

Settings load `backend/.env`; supported values: [.env.example](.env.example), [base settings](config/settings/base.py).

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

`manage.py` defaults to `config.settings.development` (debug/all hosts). Production: explicitly select `config.settings.production`, set environment `DJANGO_DEBUG=False`; allowed hosts, external database/shared cache required, secure cookies enabled, demo data disabled. Use HTTPS/production server; install server package and database/cache drivers separately.

## API and workflow contracts

- API: `/api/v1/`; JSON: `data` or `error` (`code`, `message`, optional validation errors); downloads: files.
- Session-cookie auth: fetch `/api/v1/system/config/` for CSRF before `POST /api/v1/auth/login/`; unsafe requests send `X-CSRFToken`.
- Access: `admin`/`doctor`/`receptionist` roles + action permissions + patient/care-team scope.
- Supported updates require current `version` or `If-Match`; refresh stale records after conflicts.
- Covered mutations use `X-Idempotency-Key`; retries reuse the operation's key/payload.
- Finalized visits retain immutable signed revisions; prescription/referral issuance requires final/locked signed visits and preserves issued documents.
- Invoice lines determine totals; payments record actor/time. Archive preserves clinical history; pseudonymization retains signed identity snapshots.

## Operations and data recovery

From the activated backend environment:

| Command | Effect |
| --- | --- |
| `python manage.py send_appointment_reminders` | Process appointment reminders |
| `python manage.py send_task_reminders` | Process task reminders |
| `python manage.py auto_backup` | Check whether an automatic backup is due |
| `python manage.py cleanup_backups` | Apply backup retention; removes expired backup files |
| `python manage.py run_scheduler` | Run the periodic development loop for reminders, backups, and retention |
| `python manage.py reconcile_media` | Report missing files and old unreferenced uploads without deleting them |

Production: cron/systemd timers for individual commands. Media reconciliation deletes old orphans only with explicit `--delete`.

Full ZIP: managed records/media, authenticated manifests/checksums. Full restore requires matching preview/confirmation, replaces managed inventory, creates safety backup, revokes sessions. Catalog restore merges. JSON exports contain no media bytes and cannot recover missing files; spreadsheet imports also require previews.

Never commit `.env`, `data/`, `media/`, `backups/`, `staticfiles/`; protect production patient media with access control.

## Layout and development

| Directory | Contents |
| --- | --- |
| `apps/` | Feature models, serializers, services, views, and routes |
| `core/` | Shared permissions, validation, caching, auditing, and management commands |
| `config/` | Django settings and entry points |
| `templates/` | Server-rendered documents and templates |
| `docs/` | Setup, operations, review findings, and implementation notes |

Before changes: [AGENTS.md](AGENTS.md), [workCurrent.md](docs/workCurrent.md), [doneCurrent.md](docs/doneCurrent.md). Migrations, test-suite access, builds/compilation/packaging, version changes require explicit authorization.

References: [documentation index](docs/README.md), [implemented backend fixes](docs/backend-fixes-implementation.md), [workflow checklist](docs/critical-workflow-checklist.md). Current rules override older setup helpers' broader side effects. Unverified: PDF/Arabic rendering, browser workflows, PostgreSQL concurrency.
