# Source reference

Ports: frontend **5173**, backend **5019**; browser-test servers **5174/5018**. API `/api/v1/`, admin `/admin/`, health `/api/v1/system/health/`. Production uses configured HTTPS domain. [Setup](setup/development.md), [environment defaults](setup/configuration.md).

## Management commands

Prefix commands with activated `python manage.py`; production requires explicit production settings.

| Command | Purpose/options/limits |
| --- | --- |
| `bootstrap` | Schema+migrations+seed; explicit migration permission. `--with-demo-data`, `--with-frontend` (build permission), `--clean` (destructive SQLite/custom migration removal), `--yes/-y` (skip DELETE confirmation). |
| `runserver_auto` | Prepares schema before runserver; migration authorization. Plain `runserver 127.0.0.1:5019` is local server only. |
| `seed_db` | Permissions/groups/users/default catalogs/settings/tasks; rerun changes role/default settings, use deliberately. |
| `auto_backup` | Creates signed full ZIP every invocation. |
| `cleanup_backups --dry-run --dir PATH` | Retention preview/custom directory; omit dry-run to remove expired matches. |
| `run_scheduler` | Development loop; production timers call individual commands. |
| `send_appointment_reminders`, `send_task_reminders` | Clinic-local windows/occurrence dedupe. |
| `reconcile_media --older-than-hours 24` | Report missing/old orphan files; `--delete` needs explicit removal authorization. |
| `reset_admin_password --username NAME --qr` | Private one-time recovery password/session revocation; QR optional package. |
| Django `check [--deploy]`, `shell`, `createsuperuser` | Configuration check/admin tools; shell/admin writes need intended authorization. |
| `makemigrations`, `migrate`, `collectstatic --noinput` | Schema/asset operations require their explicit scope; not performed by documentation checks. |
| Test commands | Use isolated [test runner/settings](testing/guide.md), not an unspecified development DB. |

## `core/urls.py`: route families

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

## `requirements.txt`: package ownership

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

Use pinned requirements; production DB/cache/WSGI drivers and optional QR/coverage/PDF inspection tools are separate. `wkhtmltopdf`, `pdfkit` and `django-phonenumber-field` are not this renderer/phone contract. [PDF fonts](testing/pdf.md).

## Accounts/permissions

Seed users: admin `admin`, doctor `doctor1`, receptionist `receptionist1`; no fixed documented password. Optional seed-password environment variables or one-time random output; new users must change password. Recovery command generates a private replacement and revokes sessions.

`core/permissions.py` defines codenames; role groups/direct grants determine actions, shared patient/care-team/historical-author scope determines accessible records. Active superusers are authoritative; inactive users denied. Receptionist defaults remain unchanged; do not infer clinical/finance access from role names alone. Effective permissions GET, updates **PUT** `/api/v1/auth/users/permissions/{id}/` (not POST); changes require user-management authorization.

Source layout: `apps/` features, `core/` shared contracts/commands, `config/settings/` runtime modules, `templates/` PDF/email, sibling frontend `src/` and generated `dist/`. Ignored runtime paths: `.env`, `data/clinic.db`, `media/`, `backups/`, `staticfiles/`. [Implementation by source area](contracts/implementation.md), [patient endpoints](contracts/patients.md).
