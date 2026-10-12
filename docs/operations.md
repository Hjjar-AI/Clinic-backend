# Operations and troubleshooting

Use the intended activated interpreter/production settings; data-changing commands need intended authorization. Do not use clinic inventory to verify source. [Setup](setup.md), [contracts](contracts.md), [verification](verification.md).

## Recovery

Full ZIP carries managed app/auth/history/archived inventory, complete IDs/timestamps and media, signed manifest/member hashes/sizes plus backup JSON/signature. JSON carries logical records without bytes; full recovery rejects missing/mismatched references, unsafe paths, unsupported schema, malformed counts or authentication. Preserve installation HMAC key; never hand-edit envelopes or bypass previews.

| API `/api/v1/backup/` POST | Contract |
| --- | --- |
| Base | `backup_type=full/json`, manage-backup permission; file with SHA256/type headers. |
| `restore/preview/` | Multipart backup_file and string restore_patients/diagnoses/medications booleans; counts/media/scope and token bound to actor/file digest/selection, 30 minutes. |
| `restore/execute/` | Authorized admin, same preview/file/scope, `confirm_clear=true`, phrase `RESTORE CLINIC` and explicit UI consent. Patient recovery requires all related scope; empty scope rejected. |

Full restore replaces app/auth inventory/media, retains signed revisions/exact documents, writes automatic safety archive, revokes sessions and requires relogin. Catalog-only recovery merges selected catalogs without replacing patients/users/history. Cache generations and installation-local recovery receipts remain outside replacement inventory; restored admin may replay only bounded safety-copy success receipt with the same key/payload, never rerun completed recovery.

Operation gate drains earlier HTTP readers/writers and participating jobs before exclusive snapshot/restore/catalog work. PostgreSQL coordinates worker/host session advisory locks; other profiles require common POSIX OPERATION_LOCK_DIR. Protected streams are buffered within gate; external DB/storage writers must be quiesced. Postcommit failure preserves committed media/receipt; precommit rollback compensates files. Actual external topology/worker termination remains unverified.

Interrupted receipt blocks further restore. Reconcile database **and** media from safety archive, then explicitly acknowledge:

```bash
python manage.py reconcile_recovery --key KEY --reason 'verified reconciliation' --confirm-inventory-and-media
```

This acknowledges operator verification; it does not repair data/files. Use a new preview/key afterward. No dedicated restore CLI; rehearse actual preview/execute/relogin/inventory checks in authorized staging.

## Retention

Automatic backup uses unique `clinic_backup_...zip` and atomic publication, enforcing restore size/member/expansion limits. `cleanup_backups --dry-run [--dir PATH]` previews policy: all first 30 days, newest ISO-week 30–90, newest month 90–365, newest year afterward; settings configure windows. Safety-before-restore archives are outside that pattern and need explicit capacity/retention policy. Keep authenticated encrypted/access-controlled off-site copies/signing keys; same-filesystem safety copy does not survive host loss. Sync deletion can propagate loss; choose remote retention deliberately.

## Jobs and system tools

| Command / endpoint | Current behavior |
| --- | --- |
| send_appointment_reminders | Local scheduled/confirmed day/hour windows, up to 60-minute late-hour grace, actual date/time text; occurrence UUID dedupe, terminal bookings excluded. |
| send_task_reminders | Open/in-progress due-window actions, assignee/owner delivery, stable occurrence retries; terminal actions stop reminders. |
| run_scheduler | Development loop; poll no slower than half hour-reminder window/minimum 60s, independent BACKUP_CHECK_INTERVAL_HOURS backup cadence; one job failure does not stop others. |
| cleanup_operations | Completed ordinary/recovery receipts expire after 30 days; interrupted ones retained. Do not reuse an old key after retry window. |
| reconcile_media --older-than-hours 24 | Report missing references/old orphan uploads; `--delete` only with explicit removal scope. |
| reset_admin_password --username NAME [--qr] | Locked intended-field/version update, one generated private password, rotation cleared and sessions revoked; optional QR. |
| system/health[/full]/ | Database health/full maintenance metadata; verify actual response envelope and alert non-200. |
| system/cache/clear/ POST | Manage-settings application invalidation preserves preview/operation records; avoid global raw cache.clear. |
| audit-logs/ GET | Actor/IP/action/entity scope; avoid exporting patient descriptions in diagnostics. |

Medication spreadsheet import is content-only: five mapped fields, existing controlled classification retained, new drugs uncontrolled, imported content active. Status/controlled columns are not full round-trip recovery. Preview binds file/map/policy/current content/version inventory; intervening edits reject both merge and replacement.

## Troubleshooting

| Symptom | Check / correction |
| --- | --- |
| Startup keys/hosts/DB/cache denial | Separate private keys, production hosts/profile/driver/shared cache and explicit settings; retained backup key is needed for old archives. |
| SQLite missing path/table/schema | Correct parent/ownership and actual selected connection; new schema needs authorization. Do not bootstrap/reseed/delete migrations blindly. |
| CheckConstraint TypeError | Verify source/interpreter; native factory supports Django 5.0 check versus 5.1+ condition. Do not change versions to hide pinned-runtime failure. |
| MIME/PDF import failure or 503 | Distinguish Python magic package/native libmagic; check Pango/Cairo/GObject, both deployed fonts and sanitized renderer logs. |
| Request waits/cache stale | Check exclusive gate/interrupted receipt and DB/shared cache configuration. Generation is DB-backed; use authorized app invalidation. |
| Login/CSRF/CORS | Match hostname/5019/proxy/exact origin, bootstrap CSRF/config/credentials; inspect lockout/revocation/forced password. Recovery uses authorized reset command. |
| Route/static reload 404 | Existing frontend bundle/collected static, history/API/admin routing; dev proxy is not production/preview. |
| Stale write/preview or uncertain transport | Refresh opening resource/parent, retain draft/key/payload, re-preview changed content/scope. Empty 204/205/304 must survive proxy/replay. |
| Duplicate ID/archive/merge | IDs are unchanged/nonblocking; scoped review/optional merge. Preserve retained history; merged source restore blocked; avoid raw lifecycle SQL. |
| Backup validation/interruption | Original key/schema/manifest/count/reference checks and safety receipt; do not remove authentication or assume partial success. |
| Port/runtime disagreement | Identify existing port owner before stopping; compare configured interpreter/DB, not historical passing results. Source/jsdom/SQLite do not prove browser/PDF/concurrency. |

Monitor sanitized service logs/health/fresh backups, audit dependencies and rehearse recovery. Never expose credentials/patient values or open storage merely for source verification.
