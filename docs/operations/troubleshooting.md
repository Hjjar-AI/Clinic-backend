# Troubleshooting by source/failure

Start with sanitized traceback (`journalctl -u myclinic -n 200` or development terminal), health/proxy response and recent audit events. Inspect configuration before altering data; commands changing schema/data need authorization. [Configuration](../setup/configuration.md), [contracts](../contracts/implementation.md).

| Symptom | Owning files / correction |
| --- | --- |
| Missing `DJANGO_SECRET_KEY`/`BACKUP_HMAC_KEY` | `config/settings/base.py` requires nonempty separate keys when environment debug false; generate/store privately. Existing backups need their original signing key. |
| Production refuses hosts/SQLite/LocMemCache | `config/settings/production.py`; declare allowed hosts, external DB/driver and shared cache/driver, production module and environment debug false. |
| SQLite cannot open database | Check configured path/parent ownership; create `data/` if missing. Bootstrap now creates filesystem parent before checks but also performs migrations, so do not invoke it only as a folder fix. |
| Missing table / model/schema mismatch | Check actual installed app/schema. Fresh-schema preparation requires explicit authorization; don't delete migration caches/database or reseed blindly. |
| `CheckConstraint(check=...)` TypeError | Current native factory in `core/constraints.py` supports Django 5.0 `check` and 5.1+ `condition`; verify checkout/interpreter before changing versions. Pinned Django still needs supported Python. |
| Python `magic` import / libmagic load error | Install pinned Python requirements and system libmagic (Debian `libmagic1`, macOS `libmagic`); module absence and native-library absence are different. |
| WeasyPrint/GObject/Pango error or PDF 503 | Check Pango/Cairo/GObject libraries, `core/pdf_utils.py` sanitized logs, both bundled Cairo/Inter fonts and deployed font path; render failure returns 503. [PDF inspection](../testing/pdf.md). |
| Requests hang/cache stale | Verify configured shared cache service/location (`echo stats \| nc 127.0.0.1 11211` for memcached), process configuration and after-commit generation handling; use admin application clear, not raw global clear. |
| Login rejects known credentials | Check lockout state/expiry, session revocation/forced-password gate and CSRF bootstrap. Authorized `reset_admin_password --username NAME` is recovery; no direct SQL counter/password edits as normal workflow. |
| API/CORS/CSRF failure | Health at 5019; match Vite target/exact origin and consistent localhost/127.0.0.1; send session credentials, bootstrap config and CSRF header. Restart for `.env` changes. |
| Frontend route reload/static 404 | Existing `frontend/dist`/collected assets and history fallback, `/api/`/`admin/` routing, `/static/` base; dev proxy is not preview/production routing. |
| Archive committed but browser reports transport failure | Current renderer returns empty 204/205/304/replayed bodies; verify server checkout/proxy response, refresh resource before uncertain retry. Retain operation key to prevent duplicate mutation. |
| Stale write/preview conflict | Refresh observed opening resource/parent version, compare retained draft, re-preview changed import/recovery/merge file/scope; never silently overwrite or recycle different-operation keys. |
| Duplicate national ID | Cross-person duplicates are allowed/nonblocking and IDs stay unchanged; use permanent patient numbers/scoped duplicate review and optional preview-bound merge. Older uniqueness diagnosis is obsolete. |
| Archived/merged patient | Use authorized patient archive/restore service/API, preserve dependencies/history/version; merged source restoration is blocked. Don't clear `deleted_at` manually. [Retention](../contracts/patients.md). |
| Backup signature/media validation fails | Check original HMAC key, archive integrity/format/manifest/reference hashes/counts/scope; never remove authentication or partially restore as full success. [Recovery](guide.md). |
| Port in use | `lsof -i :5019`; identify existing process before stopping it, or change backend port/Vite proxy/CORS deliberately. |
| Test/runtime disagreement | Actual suite/isolated settings: [testing](../testing/guide.md). Python 3.14/pinned Django template errors are not passing compatibility; jsdom/source checks are not rendered/PDF/concurrency evidence. |

Use `python manage.py check --deploy` only with the intended settings/environment; it does not replace runtime release checks. Never log patient values/credentials or open clinic storage merely to validate source.
