# Operations

Use the intended interpreter/settings; data-changing commands need authorization. [Setup](setup.md) · [Contracts](contracts.md) · [Evidence](doneCurrent.md).

## Recovery

Full ZIP **format 3** authenticates inventory/media with HMAC, member hashes/sizes and relationship validation; JSON alone has no media. Retain signing keys. Reject earlier formats, unsafe paths, corrupt counts/checksums or invalid relationships.

| POST `/api/v1/backup/` | Contract |
| --- | --- |
| Base | `backup_type=full/json`, manage-backup grant; SHA256/type download headers. |
| `restore/preview/` | Multipart file/scope booleans; 30-minute token binds actor/digest/selection. |
| `restore/execute/` | Authorized admin, same file/token/scope, `confirm_clear=true`, phrase `RESTORE CLINIC`, explicit consent. Patient recovery requires full related scope. |

Full restore replaces app/auth and restores referenced media (unrelated files retained), preserves signed evidence, creates safety ZIP, revokes sessions and requires relogin. Catalog recovery only merges selected catalogs. Installation-local recovery receipts/cache generations stay outside replacement inventory; completed recovery replays only its bounded safety-copy receipt under current restored-admin authorization.

The operation gate drains participating HTTP/jobs before exclusive backup/restore/catalog work; buffer protected streams inside it. Quiesce external writers. PostgreSQL session locks coordinate hosts; other DBs need shared/exclusive-capable common lock storage.

Caught precommit failures compensate files; SIGKILL cannot. PostgreSQL rolls back uncommitted inventory/releases locks, but replaced media can remain. A processing/interrupted receipt blocks further restore. Repair **both DB and media** from the safety archive before acknowledging:

```bash
python manage.py reconcile_recovery --key KEY --reason 'verified reconciliation' --confirm-inventory-and-media
```

Acknowledgment repairs nothing; use a fresh preview/key afterward. Postcommit failure retains committed media/receipt. [Verified checkpoints and limits](verification.md).

## Retention

`cleanup_backups --dry-run [--dir PATH]`: retain all first 30 days, newest ISO-week through 90, newest month through 365, then newest year; settings override. Safety-before-restore copies need separate retention/capacity policy. Automatic backups publish unique ZIPs atomically within size/member/expansion bounds. Keep authenticated, protected off-site copies/keys; same-disk copies cannot survive host loss.

## Jobs and tools

Use systemd/cron or Windows Task Scheduler with explicit interpreter/cwd/production environment, non-overlap and protected output. Suggested cadence: hourly reminders (tasks +5 minutes), daily backup/retention/receipt cleanup. `run_scheduler` is development-only.

| Command / API | Purpose |
| --- | --- |
| `check_runtime [--render-pdf]` / `serve` | DB-free native diagnosis / Waitress with source and DB feature checks. Neither migrates/seeds; startup does not certify schema/login readiness. |
| `send_appointment_reminders` | Scheduled/confirmed local day/hour windows, 60-minute late grace; stable occurrence dedupe. |
| `send_task_reminders` | Open/in-progress due tasks; terminal tasks stop delivery. |
| `run_scheduler` | Poll within half hour-window, minimum 60s; separate backup cadence; failures isolated. |
| `cleanup_operations` | 30-day completed receipts; retain interrupted ones, never reuse expired keys. |
| `reconcile_media --older-than-hours 24` | Missing/orphan report; `--delete` requires removal scope. |
| `reset_admin_password --username NAME [--qr]` | Locked versioned reset, private one-time password, rotation cleared/sessions revoked. |
| `system/health[/full]/` | Inspect `data.status`/`data.database` as well as HTTP status: degraded DB health can still return HTTP 200. `full/` also reports maintenance. |
| `system/cache/clear/` POST | Grant-protected application invalidation; preserves previews/receipts. |
| `audit-logs/` GET | Scoped actor/action history; do not log/export patient values as diagnostics. |

Medication spreadsheet import is content-only: five mapped fields; preserve existing controlled status, new drugs uncontrolled, imported content active. Preview binds file/map/policy/current inventory; intervening edits reject merge/replacement.

## Troubleshooting

Check actual interpreter/port owner/settings first. PDF/MIME failures: native libraries, both fonts, DLL/database paths and `check_runtime --render-pdf`. Auth failures: exact hostname/CORS/CSRF, session revocation/password rotation. Stale writes: retain draft/key/payload, refresh opening version and re-preview changed content. Stale cache/waits: gate/receipt/shared-cache configuration, never raw `cache.clear`. Missing schema/assets: explicit setup scope, never bootstrap clinic storage merely to diagnose. Monitor sanitized logs, health and recoverable backups.
