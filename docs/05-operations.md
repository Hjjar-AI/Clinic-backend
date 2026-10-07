# File 6 of 8: `docs/05-operations.md`

# Operations

Day-to-day running of a deployed MyClinic instance: backups, restore, scheduler, monitoring.

## Backups

### What gets backed up

`python manage.py auto_backup` produces a signed ZIP in `backend/backups/` named `clinic_backup_YYYYMMDD_HHMMSS.zip`. Contents:

| Entry | Description |
|---|---|
| `backup.json` | Patients, visits, diagnoses, medications, attachments metadata, scale responses |
| `clinic.db` | Full SQLite database (only if using SQLite) |
| `media/*` | Every uploaded file under `MEDIA_ROOT` |
| `signature.txt` | HMAC-SHA256 of `backup.json`, using `BACKUP_HMAC_KEY` |

The HMAC means tampered backups fail signature verification on restore.

### Trigger a backup

```bash
cd /srv/myclinic/backend
source /srv/myclinic/venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings.production
python manage.py auto_backup
```

### Backup retention

The retention policy in `apps/backup/retention.py`:

- Keep **every** backup from the last `BACKUP_SAFETY_DAYS` days.
- Keep **one per ISO week** for the next `BACKUP_WEEKLY_DAYS` days.
- Keep **one per calendar month** for the next `BACKUP_MONTHLY_DAYS` days.
- Keep **one per year** beyond that, forever.

Adjust via `.env`. Sweep:

```bash
python manage.py cleanup_backups
python manage.py cleanup_backups --dry-run    # report only
python manage.py cleanup_backups --dir /custom/path
```

### Off-site sync

Backups on the same filesystem as the database are not backups. Options:

```bash
# rsync to a remote host
rsync -a --delete /srv/myclinic/backend/backups/ backup-host:/srv/backups/myclinic/

# rclone to S3 / Backblaze / Google Drive
rclone sync /srv/myclinic/backend/backups/ remote:myclinic-backups
```

Schedule via cron. See `04-deployment.md#scheduled-tasks`.

### Restore

Two-step via the API, or one-shot via `manage.py`.

#### Via the API

1. `POST /api/v1/backup/restore/preview/` with `backup_file` — returns counts of patients, visits, diagnoses, medications, and **verifies the signature**.
2. `POST /api/v1/backup/restore/execute/` with `backup_file`, plus:
   - `restore_patients=true`
   - `restore_diagnoses=true`
   - `restore_medications=true`
   - `confirm_clear=true` — **required**. Without it, the endpoint returns 400.

`confirm_clear=true` **deletes all existing data** before restoring. Do not run this against a live database.

#### Destructive restores from the CLI

There is no CLI restore command today. The service (`apps.backup.backup_restore.BackupRestoreService`) is designed for the API. For CLI use, write a one-off management command or shell:

```bash
python manage.py shell
>>> from apps.backup.backup_restore import BackupRestoreService
>>> with open('/path/to/backup.zip', 'rb') as f:
...     BackupRestoreService().execute_restore(f, confirm_clear=True)
```

### Verify a backup without restoring

```bash
python -c "
from apps.backup.backup_validation import BackupValidationService
import zipfile
with zipfile.ZipFile('/path/to/backup.zip') as zf:
    raw = zf.read('backup.json')
    sig = zf.read('signature.txt').decode()
print('valid' if BackupValidationService().verify_signature(raw, sig) else 'INVALID')
"
```

## Scheduler

### Development

```bash
python manage.py run_scheduler
```

Loops forever, calling every `SCHEDULER_INTERVAL_HOURS`:

1. `send_appointment_reminders`
2. `send_task_reminders`
3. `auto_backup`
4. `cleanup_backups`

Failures in one command don't stop the others.

### Production

Do **not** run `run_scheduler`. Use cron or systemd timers, one entry per command. See `04-deployment.md#scheduled-tasks`.

### What each command does

| Command | Purpose | Frequency |
|---|---|---|
| `send_appointment_reminders` | Notifies doctors of appointments tomorrow and within the next hour | hourly |
| `send_task_reminders` | Notifies users of tasks due tomorrow | hourly |
| `auto_backup` | Writes a signed backup ZIP | daily |
| `cleanup_backups` | Applies the retention policy | daily |

## Monitoring

### Health endpoint

```
GET /api/v1/system/health/
→ {"data": {"status": "ok", "database": "ok"}}
```

Fuller version:

```
GET /api/v1/system/health/full/
→ {"data": {"status": "ok", "database": "ok", "maintenance": false}}
```

Point UptimeRobot, Pingdom, or a Nagios check at this URL. Alert if the response is not 200 or if `status != "ok"`.

### Logs

- **Gunicorn:** `journalctl -u myclinic -f`
- **Nginx:** `/var/log/nginx/access.log`, `/var/log/nginx/error.log`
- **Django app logs:** same as Gunicorn (stdout) by default, level `INFO`

To persist Django logs separately, add a file handler to `LOGGING` in `config/settings/base.py`.

### Audit log

Every model change listed in `core/signals.py::AUDIT_MODELS` is recorded in `core.AuditLog` with user, IP, action, and entity. Query via:

```
GET /api/v1/audit-logs/
```

Admins see everything; other users see only their own entries.

### Periodic checks

| Cadence | Check |
|---|---|
| Hourly | `/system/health/` returns `ok` |
| Daily | Gunicorn log has no new tracebacks |
| Daily | Backups directory has a fresh `clinic_backup_*.zip` |
| Weekly | `pip-audit` reports no criticals |
| Monthly | Restore a backup to a staging DB and verify patient counts |
| Quarterly | Rotate `.env` secrets; test key rotation end-to-end |

## Cache

Memcached on `127.0.0.1:11211`. Clear the cache if you suspect stale data:

```bash
python manage.py shell -c "from django.core.cache import cache; cache.clear()"
```

Or via the API (admin only):

```
POST /api/v1/system/cache/clear/
```

Do **not** clear cache during business hours — every request will hit the database until the cache warms.

## Session management

Sessions live in `django_session` (DB). To force every user to re-login, rotate a key or set `session_revoked_at` on the user:

```python
# In shell
from django.utils import timezone
from apps.accounts.models import User
User.objects.all().update(session_revoked_at=timezone.now())
```

Every in-flight session becomes invalid on the next request (enforced by `core.middleware.SessionRevocationMiddleware`).

## Useful one-liners

```bash
# Count active patients
python manage.py shell -c "from apps.patients.models import Patient; print(Patient.objects.count())"

# Force a full cache clear
python manage.py shell -c "from django.core.cache import cache; cache.clear()"

# Trigger a backup manually
python manage.py auto_backup

# Reset a user's password
python manage.py reset_admin_password --username admin
```

## Next

- Troubleshooting → `06-troubleshooting.md`
- Reference → `07-reference.md`

---