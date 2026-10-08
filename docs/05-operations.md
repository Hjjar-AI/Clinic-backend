# Operations

Deployed operations: backups, restore, scheduler, monitoring.

## Backups

### What gets backed up

`python manage.py auto_backup`: signed `clinic_backup_YYYYMMDD_HHMMSS.zip` in `backend/backups/`; historical inventory:

| Entry | Description |
|---|---|
| `backup.json` | Patients, visits, diagnoses, medications, attachments metadata, scale responses |
| `clinic.db` | Full SQLite database (only if using SQLite) |
| `media/*` | Every uploaded file under `MEDIA_ROOT` |
| `signature.txt` | HMAC-SHA256 of `backup.json`, using `BACKUP_HMAC_KEY` |

Restore rejects HMAC-tampered backups.

### Trigger a backup

```bash
cd /srv/myclinic/backend
source /srv/myclinic/venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings.production
python manage.py auto_backup
```

### Backup retention

`apps/backup/retention.py` policy:

- Keep **all** backups for `BACKUP_SAFETY_DAYS` days.
- Then **one/ISO week** for `BACKUP_WEEKLY_DAYS` days.
- Then **one/calendar month** for `BACKUP_MONTHLY_DAYS` days.
- Then **one/year**, forever.

Configure `.env`; sweep:

```bash
python manage.py cleanup_backups
python manage.py cleanup_backups --dry-run    # report only
python manage.py cleanup_backups --dir /custom/path
```

### Off-site sync

Same-filesystem copies do not provide disaster recovery. Off-site options:

```bash
# rsync to a remote host
rsync -a --delete /srv/myclinic/backend/backups/ backup-host:/srv/backups/myclinic/

# rclone to S3 / Backblaze / Google Drive
rclone sync /srv/myclinic/backend/backups/ remote:myclinic-backups
```

Cron scheduling: `04-deployment.md#scheduled-tasks`.

### Restore

Historical API two-step/manual `manage.py` options below; no dedicated CLI restore.

#### Via the API

1. `POST /api/v1/backup/restore/preview/` with `backup_file` — returns counts of patients, visits, diagnoses, medications, and **verifies the signature**.
2. `POST /api/v1/backup/restore/execute/` with `backup_file`, plus:
   - `restore_patients=true`
   - `restore_diagnoses=true`
   - `restore_medications=true`
   - `confirm_clear=true` — **required**. Without it, the endpoint returns 400.

`confirm_clear=true` **deletes existing data** before restore; never run against a live database.

#### Destructive restores from the CLI

API service `apps.backup.backup_restore.BackupRestoreService` has no dedicated CLI command; historical one-off command/shell example:

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

Loops every `SCHEDULER_INTERVAL_HOURS`, indefinitely:

1. `send_appointment_reminders`
2. `send_task_reminders`
3. `auto_backup`
4. `cleanup_backups`

Command failures do not stop others.

### Production

Use separate cron/systemd timers, **not** `run_scheduler`: `04-deployment.md#scheduled-tasks`.

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

UptimeRobot/Pingdom/Nagios: alert for non-200 or `status != "ok"`.

### Logs

- **Gunicorn:** `journalctl -u myclinic -f`
- **Nginx:** `/var/log/nginx/access.log`, `/var/log/nginx/error.log`
- **Django app logs:** same as Gunicorn (stdout) by default, level `INFO`

Separate logs: add `LOGGING` file handler in `config/settings/base.py`.

### Audit log

`core/signals.py::AUDIT_MODELS` changes enter `core.AuditLog` with user/IP/action/entity; query:

```
GET /api/v1/audit-logs/
```

Admins see all; others only their entries.

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

Memcached: `127.0.0.1:11211`; suspected-stale cache clearing:

```bash
python manage.py shell -c "from django.core.cache import cache; cache.clear()"
```

Or via the API (admin only):

```
POST /api/v1/system/cache/clear/
```

Avoid business-hours clears: requests hit DB until cache warms.

## Session management

DB sessions: `django_session`. Force re-login by key rotation or user `session_revoked_at`:

```python
# In shell
from django.utils import timezone
from apps.accounts.models import User
User.objects.all().update(session_revoked_at=timezone.now())
```

`core.middleware.SessionRevocationMiddleware` invalidates in-flight sessions on next request.

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
