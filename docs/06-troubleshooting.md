# File 7 of 8: `docs/06-troubleshooting.md`

# Troubleshooting

## Startup

### `RuntimeError: DJANGO_SECRET_KEY is not set`

`config/settings/base.py` raises this when `DJANGO_DEBUG=false` and `DJANGO_SECRET_KEY` is blank. Generate one and put it in `.env`:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Same for `BACKUP_HMAC_KEY`.

### `RuntimeError: BACKUP_HMAC_KEY is not set`

See above.

### `django.core.exceptions.ImproperlyConfigured: settings.DATABASES is improperly configured`

The `data/` directory is missing.

```bash
cd backend
mkdir -p data backups media
```

### `ModuleNotFoundError: No module named 'magic'`

`python-magic` is installed but the system library `libmagic` isn't.

```bash
sudo apt install libmagic1     # Debian/Ubuntu
brew install libmagic          # macOS
pip install python-magic
```

### `OSError: cannot load library 'libgobject-2.0-0'` (WeasyPrint)

Missing GTK/Pango system libraries.

```bash
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libffi-dev
```

### `django.db.utils.OperationalError: no such table: core_auditlog`

You ran `seed_db` before `migrate`. Re-run in order:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py seed_db
```

Or simply use `python manage.py bootstrap`.

## Runtime

### Requests hang for a few seconds then fail

Likely memcached is not running. Check:

```bash
echo stats | nc 127.0.0.1 11211
```

If empty, start it:

```bash
sudo systemctl start memcached
```

Or switch to LocMemCache per `03-configuration.md#cache`.

### 500 with `AttributeError: 'NoneType' object has no attribute ...` in logs

Usually a template trying to access a relation that's null. Check the traceback against the models — most likely a `patient.doctor` or `visit.author` that is `None`.

### Login returns "بيانات الاعتماد غير صحيحة" for a known-good password

The account is probably locked. Check:

```bash
python manage.py shell -c "
from apps.accounts.models import User
u = User.objects.get(username='<username>')
print('locked_until:', u.locked_until)
print('failed_attempts:', u.failed_login_attempts)
"
```

Unlock:

```bash
python manage.py shell -c "
from apps.accounts.models import User
User.objects.filter(username='<username>').update(failed_login_attempts=0, locked_until=None)
"
```

### PDF download returns 503

WeasyPrint failed. Check the Gunicorn log for a Python traceback. Common causes:

- Missing system library (see Startup above)
- Font not installed for Arabic glyphs
- HTML template renders a value that isn't a string

Fallback: `core/pdf_utils.render_pdf_from_html` logs the exception and returns `None`, which the view turns into a 503.

### Frontend can't reach the API

1. Check the backend is up: `curl http://localhost:5019/api/v1/system/health/`
2. Check the Vite proxy target in `frontend/vite.config.js` matches the backend port.
3. Check `CORS_ORIGINS` in `.env` includes the frontend origin **exactly** (no trailing slash, matching scheme/host/port).

### CORS preflight fails

Same as above — CORS origins must be an exact string match. `http://localhost:5173` and `http://127.0.0.1:5173` are different origins even though they point to the same machine.

## Data

### `IntegrityError: UNIQUE constraint failed: patients_patient.national_id`

A patient with that national ID already exists (soft-deleted patients don't count — the constraint is conditional on `deleted_at IS NULL`). Search including deleted:

```bash
python manage.py shell -c "
from apps.patients.models import Patient
Patient.all_objects.filter(national_id='<id>')
"
```

### Restore deleted patients

There's no API for this. In shell:

```bash
python manage.py shell -c "
from apps.patients.models import Patient
p = Patient.all_objects.get(id=<id>)
p.deleted_at = None
p.is_active = True
p.save(update_fields=['deleted_at', 'is_active'])
"
```

Related visits, attachments, and appointments were also soft-deleted during the patient's deletion. Restore them individually.

### Backup fails signature check on restore

The backup was tampered with, truncated, or the `BACKUP_HMAC_KEY` was rotated after the backup was created. If the key was rotated intentionally, the old backups cannot be restored — they are permanently invalid. Restore from the last backup made with the current key.

## Development

### `python manage.py runserver` says port already in use

Something else is on 5019:

```bash
lsof -i :5019
```

Kill it or run on a different port (update the Vite proxy if you do).

### Changes to `base.py` don't take effect

`runserver` reloads on `.py` changes, but not on `.env` changes. `.env` is read at process start. Restart the server.

### Migrations say "No changes detected" but I added a model

- The app is missing from `INSTALLED_APPS`.
- The app's `migrations/` folder is missing or doesn't have `__init__.py`.
- Run `python manage.py bootstrap` — it creates both.

### `--clean` leaves stale migrations behind

`--clean` deletes migration files but not `.pyc` caches. `bootstrap.py` deletes `__pycache__` after removing files. If you did it manually:

```bash
find . -path '*/migrations/__pycache__' -exec rm -rf {} +
```

## No tests

There is currently no test suite. If you add one, look at the highest-risk areas first:

- `apps/backup/backup_restore.py` — destructive; the code's own comments note a past bug here.
- Optimistic locking (`version` fields on Patient, Visit, Appointment, Invoice, UserTask).
- Role-based queryset scoping (each `get_queryset` / `list_*` service).
- Permission cache invalidation in `apps/accounts/signals.py`.

## Still stuck?

1. Check the full traceback in `journalctl -u myclinic -n 200` (prod) or the terminal (dev).
2. `python manage.py check --deploy` for configuration issues.
3. `curl -v http://localhost:5019/api/v1/system/health/` to isolate app vs. proxy problems.
4. Check the `core_auditlog` table for the last actions a user took before the failure.

---