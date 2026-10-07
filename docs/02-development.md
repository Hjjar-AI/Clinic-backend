# File 3 of 8: `docs/02-development.md`

# Development Setup (Full)

Detailed walkthrough for local development. If you only want the fast path, see `01-getting-started.md`.

## 1. Directory layout

The project root is:

```
/run/media/mhmmd-ali/MyFiles/IT Projects/Clinic/
├── backend/
└── frontend/
```

Commands in this document assume you are inside `backend/` unless stated otherwise.

## 2. Python environment

```bash
cd "/run/media/mhmmd-ali/MyFiles/IT Projects/Clinic/backend"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

Every new shell must re-run `source .venv/bin/activate` before `python manage.py …`.

## 3. Python dependencies

There is no `requirements.txt`. Install explicitly:

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

Each package is imported by the codebase — see `07-reference.md#python-dependencies` for the mapping.

Optional:

```bash
pip install qrcode      # for `reset_admin_password --qr`
```

### 3.1 System libraries for WeasyPrint

PDFs (prescriptions, patient reports, referral letters) are rendered by **WeasyPrint**, not wkhtmltopdf. Install its system libraries per the Prerequisites block in `01-getting-started.md#prerequisites`.

Verify:

```bash
python -c "from weasyprint import HTML; print('ok')"
```

If this errors, WeasyPrint is missing a system library. Re-run the apt/brew install.

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

Contents and every variable's meaning → `03-configuration.md#env`.

## 6. Database

Two options.

### 6.1 Bootstrap (recommended)

```bash
python manage.py bootstrap
```

This will:

1. Ensure every custom app has a `migrations/__init__.py`.
2. Generate initial migrations if any app is missing them.
3. Run `migrate`.
4. Run `seed_db`.

Flags:

| Flag | Effect |
|---|---|
| `--with-demo-data` | Also call `SettingsService.generate_demo_data()` |
| `--with-frontend` | Also run `pnpm install && pnpm build` |
| `--clean` | Delete `clinic.db` and every custom-app migration file first |
| `--yes` / `-y` | Skip the interactive `--clean` confirmation |

`--clean` is destructive and requires you to type `DELETE` unless `--yes` is passed.

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

Alternative (regenerates migrations first, then runs):

```bash
python manage.py runserver_auto 0.0.0.0:5019
```

## 8. Frontend

In a **second terminal**:

```bash
cd "/run/media/mhmmd-ali/MyFiles/IT Projects/Clinic/frontend"
pnpm install       # first time only
pnpm dev
```

Frontend: `http://localhost:5173`.

The Vite proxy (in `frontend/vite.config.js`) forwards `/api/*` to the backend. **The proxy target must match the backend port.** If you move the backend to a different port, update both `vite.config.js` and `CORS_ORIGINS` in `.env`.

## 9. Development workflow

### 9.1 Editing backend code

Django's autoreloader restarts the server on file save. No manual restart needed for `.py` changes. Template changes are also picked up.

### 9.2 Model changes

```bash
python manage.py makemigrations
python manage.py migrate
```

Or just restart via `runserver_auto`, which runs both first.

### 9.3 Adding a permission or role

1. Add the codename to `core/permissions.py` (`ALL_PERMISSIONS` and, if applicable, `DEFAULT_PERMISSIONS`).
2. Add the DRF class if needed.
3. Re-run `python manage.py seed_db` — it uses `get_or_create`, so it is idempotent.

### 9.4 Adding a new Django app

Add it to `INSTALLED_APPS` in `config/settings/base.py` and re-run `bootstrap`.

## 10. Tests

There are currently **no automated tests**. New tests should live alongside each app:

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

---