# Getting Started (Quickstart)

Ten-minute dev setup; full walkthrough: `02-development.md`.

## Prerequisites

- Python 3.10+
- Node.js 18+ and `pnpm` (`npm install -g pnpm`)
- `memcached` on `127.0.0.1:11211` (or use LocMemCache per `03-configuration.md#cache`)

Debian/Ubuntu:

```bash
sudo apt update
sudo apt install -y libmagic1 memcached \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    libffi-dev shared-mime-info
sudo systemctl enable --now memcached
```

macOS:

```bash
brew install libmagic memcached pango cairo gdk-pixbuf libffi
brew services start memcached
```

## Backend

```bash
cd "/run/media/mhmmd-ali/MyFiles/IT Projects/Clinic/backend"

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install "Django>=4.2,<6" djangorestframework django-cors-headers \
    python-dotenv whitenoise python-dateutil pandas openpyxl \
    python-magic python-docx olefile Faker weasyprint pymemcache

mkdir -p data backups media
cp .env.example .env 2>/dev/null || nano .env   # see 03-configuration.md for content

python manage.py bootstrap --with-demo-data
python manage.py runserver 0.0.0.0:5019
```

## Frontend

**Second terminal:**

```bash
cd "/run/media/mhmmd-ali/MyFiles/IT Projects/Clinic/frontend"
pnpm install
pnpm dev
```

## Verify

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API health | http://localhost:5019/api/v1/system/health/ |
| Django admin | http://localhost:5019/admin/ |

## Log in

`seed_db`: three users; passwords print once unless `.env` sets `ADMIN_PASSWORD`, `DOCTOR_PASSWORD`, `RECEPTIONIST_PASSWORD` beforehand.

| Role | Username |
|---|---|
| Admin | `admin` |
| Doctor | `doctor1` |
| Receptionist | `receptionist1` |

First login requires password change.

## Lost the admin password?

```bash
python manage.py reset_admin_password --username admin
```

## Next

- Full setup detail → `02-development.md`
- Configuration → `03-configuration.md`
- Something broken → `06-troubleshooting.md`
