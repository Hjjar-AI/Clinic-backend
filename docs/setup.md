# Setup and hosting

[Entry commands](../README.md) · [Operations](operations.md) · [Verification](verification.md). Use Python 3.10–3.12 (3.12 recommended); Windows 10/11 x64/Linux. Windows 7/Python 3.8 unsupported; macOS unverified.

## Local launcher

From backend or frontend: **`./start.sh`** (Linux), **`start.cmd`** (Windows/double-click). One terminal owns both servers; Ctrl+C stops their processes. `--no-browser` suppresses opening the UI; `check` verifies prerequisites/ports/native PDF without DB access. This is local development only; production remains below.

First-time environment/dependencies, from backend:

```bash
./start.sh configure
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/sqlite.txt
```

Windows: `start.cmd configure`, `py -3.12 -m venv .venv`, then `.venv\Scripts\python.exe -m pip install -r requirements/sqlite.txt`. Choose the requirements file matching your DB. In frontend, run `pnpm install --frozen-lockfile` once. Install native libraries below; prepare the intended fresh schema/accounts explicitly if needed. The launcher never initializes/upgrades a database.

Only backend `.env` is needed for launcher configuration:

```dotenv
CLINIC_BACKEND_PORT=5019
CLINIC_FRONTEND_PORT=5173
CLINIC_OPEN_BROWSER=true
# CLINIC_PYTHON="/path/to/app/environment/bin/python"
# CLINIC_NODE="/path/to/node"
```

Default Python: backend `.venv`, `venv`, then wrapper interpreter. Paths may contain spaces; launcher/network values are literal (no variable expansion). Shell overrides `.env`. Both proxy target and loopback hosts/CORS/CSRF origins follow selected ports; token checks remain required. Other `.env` values keep Django/python-dotenv behavior. Use `CSRF_TRUSTED_ORIGINS` for explicit additional origins.

A missing `.env` is created with separate random keys; existing files/keys remain byte-for-byte unchanged. Missing tools/native libraries or occupied ports yield a remedy. Startup uses Waitress plus Vite directly with strict ports, never pnpm installation/builds. `check`/TCP readiness do not certify database/schema readiness. [Verification limits](doneCurrent.md).

## Configuration

Copy [.env.example](../.env.example) only if `.env` is absent. Defaults: [base](../config/settings/base.py), [database](../config/settings/database.py). `manage.py` loads `.env`; shell/`--settings` override selection; WSGI defaults production. Restart after environment changes. DB selection never initializes/moves data.

- Separate private `DJANGO_SECRET_KEY`/`BACKUP_HMAC_KEY`; retain backup signing keys.
- `requirements/{sqlite,postgresql,mysql,mariadb}.txt` includes shared pins/driver; `cache-{redis,memcached}.txt` adds clients. Install servers separately; mysqlclient may need native headers.
- Set DB engine/name/credentials/SSL/options and cache backend/location explicitly. SQLite defaults `data/clinic.db`; production requires external DB/shared cache. MySQL/MariaDB needs InnoDB, utf8mb4 and strict mode.
- `TIME_ZONE=Asia/Damascus`; business dates are clinic-local. Match credentialed CORS/session/CSRF origins to frontend hostname/port.
- Ignored runtime paths: `.env`, `data/`, `media/`, `backups/`, `staticfiles/`. Clinical media is API-protected even in DEBUG.
- Both Cairo/Inter fonts must resolve together from frontend public/dist fonts or `PDF_FONT_DIR`.

## Native libraries by OS

Portalocker/Waitress/python-magic/WeasyPrint support the same service source. PostgreSQL uses session advisory gates; other DBs require a common shared/exclusive-capable `OPERATION_LOCK_DIR` across all workers/jobs. Windows installs Portalocker's `win32` extra. Local locks do not certify network filesystems.

Debian/Ubuntu native examples: `libpango-1.0-0`, `libpangoft2-1.0-0`, `libfontconfig1`, `libmagic1`, `shared-mime-info`; names vary by release. Wheels do not replace native libraries.

Windows: install matching x64 [MSYS2 UCRT64 libraries](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows):

```bash
pacman -S mingw-w64-ucrt-x86_64-pango mingw-w64-ucrt-x86_64-file
```

Private environment/`.env`, adjusted to installation:

```dotenv
CLINIC_DLL_DIRECTORIES=C:/msys64/ucrt64/bin
WEASYPRINT_DLL_DIRECTORIES=C:/msys64/ucrt64/bin
LIBMAGIC_DATABASE=C:/msys64/ucrt64/share/misc/magic.mgc
```

Use forward slashes; directory lists use `;` on Windows. DLL handles remain alive; explicit MIME databases are thread-local. Optional `PDF_FONT_DIR` must contain both fonts. `python manage.py check_runtime --render-pdf` checks locks/MIME/fonts/PDF/timezones without DB access, migrations or retained PDF files.

## Schema and startup

Application migrations were deleted by request; package markers remain. Fresh-schema preparation needs explicit scope; old DB/full-backup compatibility is absent. For an intended new empty database, `python manage.py bootstrap` generates schema/default accounts; the launcher never runs it. Never initialize clinic storage for verification.

`bootstrap`/`runserver_auto` perform migrations. Bootstrap `--with-demo-data` seeds, `--with-frontend` installs/builds, `--clean` deletes SQLite/custom migrations. `seed_db` changes defaults/accounts/catalogs/tasks; generated passwords print once and require rotation. These are deliberate operations, not diagnostics.

## Production

Use `DJANGO_SETTINGS_MODULE=config.settings.production`, debug/demo/auto-seed off, explicit hosts, external DB/shared cache, HTTPS/secure cookies and protected secrets. Non-PostgreSQL requires explicit shared lock storage. Production rejects SQLite/LocMemCache. Shared cache carries cross-worker previews/state; DB-backed generations alone do not replace it.

```bash
python manage.py serve --settings=config.settings.production --host 127.0.0.1 --port 5019 --threads 8
```

Configure systemd or a Windows service supervisor with the intended interpreter, backend working directory/environment, restart policy and dependencies. Waitress checks runtime/source, never migrates/seeds or terminates HTTPS; eight threads is an example, not capacity evidence.

Proxy HTTPS to 5019 with Host/real-IP/forwarded headers; allow uploads at least 210 MB (e.g. 220M), serve collected `/static/`, deny direct `/media/`. Django serves existing frontend index after API/admin routes; direct SPA hosting needs explicit API/admin proxy and history fallback. Never turn unknown API errors into SPA success.

Authorized asset order: frontend frozen install/build, then collectstatic. Existing Vite output includes sourcemaps and disables JS/CSS minification. Use individual scheduled jobs, not the development scheduler. Keep last-good code/config and authenticated off-site backups; schema/assets/deploy/rollback require their own scope. [Release procedure](verification.md#release-checks).
