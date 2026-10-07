# File 8 of 8: `docs/07-reference.md`

# Reference

Look-up tables: commands, URLs, credentials, dependencies.

## Commands

### Django management commands (project-specific)

| Command | Purpose |
|---|---|
| `bootstrap` | First-time setup: migrations + seed. Flags: `--clean`, `--yes`, `--with-demo-data`, `--with-frontend` |
| `seed_db` | Create permissions, groups, users, diagnoses, medications, tasks |
| `auto_backup` | Write a signed backup ZIP to `backups/` |
| `cleanup_backups` | Apply the retention policy. Flags: `--dry-run`, `--dir PATH` |
| `run_scheduler` | Loop through all scheduled commands (dev only) |
| `send_appointment_reminders` | Notify doctors of upcoming appointments |
| `send_task_reminders` | Notify users of tasks due tomorrow |
| `reset_admin_password` | Reset a user's password. Flags: `--username`, `--qr` |
| `runserver_auto` | `makemigrations && migrate && runserver` |

### Standard Django commands

```bash
python manage.py migrate
python manage.py makemigrations
python manage.py collectstatic --noinput
python manage.py shell
python manage.py check --deploy
python manage.py test
python manage.py createsuperuser
```

## Python dependencies

Every package the codebase imports, and where it's used:

| Package | Used by |
|---|---|
| `Django` | framework |
| `djangorestframework` | REST API |
| `django-cors-headers` | CORS middleware |
| `python-dotenv` | `config/settings/base.py` (`load_dotenv`) |
| `whitenoise` | `MIDDLEWARE` / `INSTALLED_APPS` — static files |
| `python-dateutil` | `apps/reports/patient_statistics.py`, `apps/reports/visit_statistics.py` |
| `pandas` | `apps/import_export/services.py` |
| `openpyxl` | Excel import/export (`apps/import_export/*`, `apps/exports/clinical_data_export.py`) |
| `python-magic` | `core/upload_security.py`, `core/file_utils.py` |
| `python-docx` | `apps/exports/word_generator.py` |
| `olefile` | `core/upload_security.py` (macro detection in legacy Office files) |
| `Faker` | `apps/settings/services.py` (demo data) |
| `weasyprint` | `core/pdf_utils.py` — **PDF renderer** |
| `pymemcache` | `CACHES` backend |
| `qrcode` | optional, `reset_admin_password --qr` only |
| `gunicorn` | production WSGI server |

**Not used:** `wkhtmltopdf`, `pdfkit`, `django-phonenumber-field`. If you see them mentioned elsewhere, that documentation is stale.

## URLs

### Development

| Service | URL |
|---|---|
| Frontend (Vite) | `http://localhost:5173` |
| Backend API | `http://localhost:5019/api/v1/` |
| Django admin | `http://localhost:5019/admin/` |
| Health | `http://localhost:5019/api/v1/system/health/` |

### Production

Replace `clinic.example.com` with your domain.

| Service | URL |
|---|---|
| Frontend + API | `https://clinic.example.com` |
| Admin | `https://clinic.example.com/admin/` |
| Health | `https://clinic.example.com/api/v1/system/health/` |

## API routes

All under `/api/v1/`.

| Prefix | App |
|---|---|
| `/auth/` | Login, logout, me, change-password, users, permissions |
| `/patients/` | Patients, documents, care team, risk history, timeline |
| `/visits/` | Visits, attachments, follow-up |
| `/appointments/` | Appointments, calendar, availability |
| `/options/` | Diagnoses, medications, clinical constants |
| `/scales/` | Clinical scales |
| `/templates/` | Clinical note templates |
| `/billing/` | Invoices |
| `/tasks/` | User tasks |
| `/notifications/` | Notifications |
| `/dashboard/` | Dashboard summary and charts |
| `/reports/` | Statistics, monthly summary, doctor performance |
| `/exports/` | CSV, Excel, PDF, Word exports |
| `/backup/` | Backup and restore |
| `/bulk-import/` | Patient and options bulk import |
| `/prescription/` | Prescription PDF |
| `/referrals/` | Referral letter PDF |
| `/settings/` | Clinic settings, theme, demo data |
| `/system/` | Health, version, config, feedback, constants |
| `/audit-logs/` | Audit trail |

## Default credentials

`seed_db` creates three users. Passwords are generated randomly unless `ADMIN_PASSWORD` / `DOCTOR_PASSWORD` / `RECEPTIONIST_PASSWORD` are set in `.env` before seeding.

| Role | Username |
|---|---|
| Admin | `admin` |
| Doctor | `doctor1` |
| Receptionist | `receptionist1` |

All three have `force_password_change = True`: you are required to change the password on first login.

If the initial password is lost:

```bash
python manage.py reset_admin_password --username admin
```

## Roles & permissions

Three roles:

| Role | Typical capabilities |
|---|---|
| `admin` | Everything |
| `doctor` | Own patients, own visits, own appointments, prescriptions, exports, reports |
| `receptionist` | Patients they created, appointments for those patients, view-only billing |

Permission codenames are defined in `core/permissions.py`. They are attached to `Group` records by `seed_db`, and users inherit them via their group. Additionally, users can be granted direct permissions via `POST /api/v1/auth/users/permissions/<id>/`.

To see a user's effective permissions:

```
GET /api/v1/auth/users/permissions/<id>/
```

## Directory cheatsheet

| Path | Purpose |
|---|---|
| `backend/.env` | Environment variables — **gitignored** |
| `backend/data/clinic.db` | SQLite database — **gitignored** |
| `backend/media/` | User uploads — **gitignored** |
| `backend/backups/` | Auto-backup ZIPs — **gitignored** |
| `backend/staticfiles/` | `collectstatic` output — **gitignored** |
| `backend/config/settings/` | `base.py`, `development.py`, `production.py` |
| `backend/core/` | Shared utilities, permissions, pagination, middleware |
| `backend/apps/` | Feature apps |
| `backend/templates/` | PDF and email templates |
| `frontend/src/` | Vue source |
| `frontend/dist/` | Built frontend assets — **gitignored** |

## Environment variables

Full table → `03-configuration.md#env`.

## Next

- Setup → `01-getting-started.md`
- Dev → `02-development.md`
- Ops → `05-operations.md`

---
