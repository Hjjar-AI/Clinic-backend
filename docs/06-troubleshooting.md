# Troubleshooting

## Startup

### `RuntimeError: DJANGO_SECRET_KEY is not set`

`config/settings/base.py`: blank `DJANGO_SECRET_KEY` with `DJANGO_DEBUG=false`; generate into `.env`:

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

Installed `python-magic` lacks system `libmagic`:

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

`seed_db` preceded `migrate`; authorized repair order:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py seed_db
```

Alternative: authorized `python manage.py bootstrap`.

## Runtime

### Requests hang for a few seconds then fail

Check likely stopped memcached:

```bash
echo stats | nc 127.0.0.1 11211
```

If empty, start:

```bash
sudo systemctl start memcached
```

Or switch to LocMemCache per `03-configuration.md#cache`.

### 500 with `AttributeError: 'NoneType' object has no attribute ...` in logs

Trace template null relations against models, especially `patient.doctor`/`visit.author` = `None`.

### Login returns "بيانات الاعتماد غير صحيحة" for a known-good password

Check likely account lock:

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

WeasyPrint failure: inspect Gunicorn traceback. Causes:

- Missing system library (see Startup above)
- Font not installed for Arabic glyphs
- HTML template renders a value that isn't a string

`core/pdf_utils.render_pdf_from_html` logs exceptions/returns `None`; view emits 503.

### Frontend can't reach the API

1. Check the backend is up: `curl http://localhost:5019/api/v1/system/health/`
2. Match `frontend/vite.config.js` proxy/backend port.
3. `.env` `CORS_ORIGINS`: exact frontend scheme/host/port, no trailing slash.

### CORS preflight fails

Exact CORS match required: `http://localhost:5173` ≠ `http://127.0.0.1:5173`, despite same machine.

## Data

### `IntegrityError: UNIQUE constraint failed: patients_patient.national_id`

Existing national ID; conditional `deleted_at IS NULL` excludes soft-deleted patients. Search including deleted:

```bash
python manage.py shell -c "
from apps.patients.models import Patient
Patient.all_objects.filter(national_id='<id>')
"
```

### Restore deleted patients

Historical guide had no restore API; shell example:

```bash
python manage.py shell -c "
from apps.patients.models import Patient
p = Patient.all_objects.get(id=<id>)
p.deleted_at = None
p.is_active = True
p.save(update_fields=['deleted_at', 'is_active'])
"
```

Related visits/attachments/appointments were also soft-deleted; restore individually.

### Backup fails signature check on restore

Possible tampering/truncation or post-backup `BACKUP_HMAC_KEY` rotation. Historical guide treats old-key backups as permanently invalid; use latest current-key backup.

## Development

### `python manage.py runserver` says port already in use

Something else is on 5019:

```bash
lsof -i :5019
```

Stop it or change port/update Vite proxy.

### Changes to `base.py` don't take effect

`runserver` reloads `.py`, not startup-read `.env`; restart for env changes.

### Migrations say "No changes detected" but I added a model

- The app is missing from `INSTALLED_APPS`.
- The app's `migrations/` folder is missing or doesn't have `__init__.py`.
- Run `python manage.py bootstrap` — it creates both.

### `--clean` leaves stale migrations behind

`--clean` removes migrations, not `.pyc`; `bootstrap.py` also deletes `__pycache__`. Historical manual cleanup:

```bash
find . -path '*/migrations/__pycache__' -exec rm -rf {} +
```

## No tests

Historical guide recorded no suite; authorized test work should prioritize:

- `apps/backup/backup_restore.py` — destructive, comments note past bug.
- Optimistic `version` locking: Patient/Visit/Appointment/Invoice/UserTask.
- Role-based queryset scoping (each `get_queryset` / `list_*` service).
- Permission cache invalidation in `apps/accounts/signals.py`.

## Still stuck?

1. Full traceback: `journalctl -u myclinic -n 200` (prod), terminal (dev).
2. `python manage.py check --deploy` for configuration issues.
3. `curl -v http://localhost:5019/api/v1/system/health/` to isolate app vs. proxy problems.
4. Check pre-failure user actions in `core_auditlog`.
