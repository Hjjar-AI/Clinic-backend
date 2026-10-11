# Operations by service/command

Use activated backend interpreter and explicit production settings for deployed commands. Recovery/cleanup/password operations change data; never use clinic inventory just to verify source. [Reference](../reference.md), [configuration](../setup/configuration.md).

## `apps/backup/`: backup and recovery

`auto_backup` writes `clinic_backup_YYYYMMDD_HHMMSS.zip` to `BACKUP_DIR` on each invocation. Current portable ZIP contains complete managed logical inventory (including archived rows/auth/history), referenced media, canonical signed `manifest.json` with member hashes/sizes, `signature.txt` and `backup.json`. JSON envelopes sign canonical inner data; JSON carries no media bytes. Do not treat a raw SQLite file copy or signature of `backup.json` alone as current full-archive verification.

| API under `/api/v1/backup/` | Required contract |
| --- | --- |
| POST base | `backup_type=full` or `json`; returns file, `X-Backup-SHA256`, `X-Backup-Type`; authenticated manage-backup permission. |
| POST `restore/preview/` | Multipart `backup_file`, string booleans `restore_patients`, `restore_diagnoses`, `restore_medications`; authenticates/validates inventory/media, returns counts/impact/scope and `preview_token`. Token binds user/file digest/selection, expires after 30 minutes. |
| POST `restore/execute/` | Same file/selection/token, `confirm_clear=true`, `confirmation_phrase=RESTORE CLINIC`; UI requires execution consent. Rejected stale/wrong-actor/digest/scope token does not authorize mutation. |

Full patient recovery replaces managed app/auth inventory and media, preserves IDs/complete timestamps/signed revisions/exact issued bytes, creates `safety_before_restore_*.zip`, revokes old sessions and requires relogin. Catalog-only scope merges selected catalogs while preserving clinical records/current users; empty scope rejected. JSON recovery fails if referenced bytes are absent or mismatch. Unsupported/incomplete legacy formats, tampered manifest/media, unsafe paths/expanded sizes/counts/references fail before writes. Preserve installation HMAC key; do not hand-edit archive envelopes or bypass preview via a shell one-liner. No dedicated restore CLI.

Validate/rehearse full recovery in authorized staging using actual preview and release workflow; inspect checksums/counts/signed artifacts/media and reconcile after restore. [Automated synthetic recovery](../testing/guide.md), [clinical/PDF checks](../testing/pdf.md), [patient retention](../contracts/patients.md).

## `apps/backup/retention.py`: retention/off-site

`cleanup_backups [--dry-run] [--dir PATH]`: keeps all within **30 days**, newest per ISO week from 30–90 days, newest per calendar month 90–365 days, then newest per year forever; boundaries use configurable safety/weekly/monthly windows. Only matching `clinic_backup_*.zip` names are selected; safety-before-restore files are not covered by that pattern. Dry-run reports without removal.

Store authenticated copies off-site with appropriate access/encryption; same-filesystem copies cannot survive host loss. `rsync -a`/rclone are possible transport tools; sync deletion flags can propagate removals, so apply a deliberate remote retention policy. Preserve signing keys separately and test restores/counts/media. [Hosting](../setup/deployment.md).

## `core/management/commands/`: reminders and maintenance

| Command | Current behavior |
| --- | --- |
| `send_appointment_reminders` | Clinic-local day/hour windows from clinic reminder settings, catches eligible future scheduled/confirmed occurrences across midnight, occurrence-specific dedupe and updated bookkeeping; terminal/cancelled rows excluded. |
| `send_task_reminders` | Open/in-progress tasks through local due window, recipient assignee or owner; dedupe per due occurrence; completion/cancellation stops reminders. |
| `run_scheduler` | Development loop: appointment reminders, tasks, backup, cleanup; configured interval (minimum 60s), one failure does not stop others. Production uses individually monitored timers. |
| `reconcile_media [--older-than-hours 24]` | Reports missing references and old orphan uploads; deletes only with explicit `--delete` authorization, does not replace patient retention policy. |
| `reset_admin_password --username admin [--qr]` | Generates/prints one private password, clears forced rotation and revokes existing sessions; optional qrcode tooling. |

## System endpoints and monitoring

| Check / action | Source/meaning |
| --- | --- |
| GET `/api/v1/system/health/`, `health/full/` | Health/database (full includes maintenance); alert on failure/non-200, verify actual envelope. |
| GET `/api/v1/audit-logs/` | `core/signals.py`/AuditLog actor/IP/action/entity; admin sees all, others scoped entries. Avoid exporting patient descriptions in diagnostics. |
| POST `/api/v1/system/cache/clear/` | Manage-settings application cache clear preserves protected preview/idempotency records; avoid raw global `cache.clear()` as routine recovery. |
| Logs | App/Gunicorn stdout via `journalctl -u myclinic`; Nginx access/error logs; default INFO console handler. |

Monitor health hourly, errors/fresh backups daily, dependency advisories weekly, staged restore/reconciliation monthly. Review secret rotation/recovery quarterly; retaining original backup keys is essential. User password/security flows and `SessionRevocationMiddleware` revoke affected sessions; avoid blanket ORM edits bypassing canonical validation/version/audit. [Troubleshooting](troubleshooting.md), [release sign-off](../testing/release-checklist.md).
