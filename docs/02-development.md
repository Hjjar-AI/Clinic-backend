# Development Setup (Full)

Full dev walkthrough; quickstart: `01-getting-started.md`.

## 1. Directory layout

Project root:

```
/run/media/mhmmd-ali/MyFiles/IT Projects/Clinic/
├── backend/
└── frontend/
```

Commands assume `backend/` unless stated otherwise.

## 2. Python environment

```bash
cd "/run/media/mhmmd-ali/MyFiles/IT Projects/Clinic/backend"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

Each shell: `source .venv/bin/activate` before `python manage.py …`.

## 3. Python dependencies

Historical setup assumed no `requirements.txt`; explicit list:

```bash
pip install \
    "Django>=4.2,<6" \
    djangorestframework \
    django-cors-headers \
    python-dotenv \
    whitenoise \
    python-dateutil \
    pandas \
    openpyxl \
    python-magic \
    python-docx \
    olefile \
    Faker \
    weasyprint \
    pymemcache
```

Import mapping: `07-reference.md#python-dependencies`.

Optional:

```bash
pip install qrcode      # for `reset_admin_password --qr`
```

### 3.1 System libraries for WeasyPrint

Prescription/patient-report/referral PDFs use **WeasyPrint**, not wkhtmltopdf; system libraries: `01-getting-started.md#prerequisites`.

Verify:

```bash
python -c "from weasyprint import HTML; print('ok')"
```

Errors imply missing system libraries; repeat apt/brew installation.

## 4. Directories

```bash
mkdir -p data backups media
```

| Directory | Purpose | Gitignored |
|---|---|---|
| `data/` | SQLite database (`clinic.db`) | yes |
| `media/` | Uploaded files (patient docs, attachments) | yes |
| `backups/` | Auto-backup ZIPs | yes |

## 5. Environment file

```bash
cp .env.example .env 2>/dev/null || nano .env
```

Values/meanings: `03-configuration.md#env`.

## 6. Database

Two historical options (require migration authorization).

### 6.1 Bootstrap (recommended)

```bash
python manage.py bootstrap
```

Creates missing `migrations/__init__.py`/initial migrations, runs `migrate`, then `seed_db`.

Flags:

| Flag | Effect |
|---|---|
| `--with-demo-data` | Also call `SettingsService.generate_demo_data()` |
| `--with-frontend` | Also run `pnpm install && pnpm build` |
| `--clean` | Delete `clinic.db` and every custom-app migration file first |
| `--yes` / `-y` | Skip the interactive `--clean` confirmation |

Destructive `--clean` requires `DELETE` unless `--yes`.

### 6.2 Manual

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py seed_db
```

## 7. Run the backend

```bash
python manage.py runserver 0.0.0.0:5019
```

Alternative (regenerates migrations before running):

```bash
python manage.py runserver_auto 0.0.0.0:5019
```

## 8. Frontend

**Second terminal:**

```bash
cd "/run/media/mhmmd-ali/MyFiles/IT Projects/Clinic/frontend"
pnpm install       # first time only
pnpm dev
```

Frontend: `http://localhost:5173`.

`frontend/vite.config.js` proxies `/api/*`; target must match backend port. Port changes require updating `vite.config.js` and `.env` `CORS_ORIGINS`.

## 9. Development workflow

### 9.1 Editing backend code

Django autoreloads saved `.py`/template changes; no manual restart needed.

### 9.2 Model changes

```bash
python manage.py makemigrations
python manage.py migrate
```

`runserver_auto` runs both before restart.

### 9.3 Adding a permission or role

1. Add codename to `core/permissions.py`: `ALL_PERMISSIONS` and applicable `DEFAULT_PERMISSIONS`.
2. Add the DRF class if needed.
3. Re-run `python manage.py seed_db` (idempotent `get_or_create`).

### 9.4 Adding a new Django app

Add to `config/settings/base.py` `INSTALLED_APPS`; re-run authorized `bootstrap`.

## 10. Tests

Historical guide recorded **no automated tests**; authorized new tests belong beside each app:

```
apps/<app>/tests/
├── __init__.py
├── test_services.py
└── test_views.py
```

Run:

```bash
python manage.py test
```

## 11. Next

- Configuration details → `03-configuration.md`
- Production → `04-deployment.md`
- Commands cheat sheet → `07-reference.md#commands`
