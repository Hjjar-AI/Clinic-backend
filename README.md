# MyClinic backend

Django REST clinic backend; Arabic [Vue frontend](../frontend/README.md). API **5019**, `/api/v1/`; session-cookie auth with CSRF, action permissions and shared patient/care-team/historical-author scope.

## Local setup

Use Python **3.10–3.12** for pinned Django 5.0.6, [requirements](requirements.txt) and PDF/libmagic system libraries. From `backend/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
mkdir -p data media backups
```

Copy `.env` only if absent; otherwise edit it. Set `DJANGO_DEBUG=True`, separate generated `DJANGO_SECRET_KEY`/`BACKUP_HMAC_KEY`, and `ALLOW_DEMO_DATA=false`/`AUTO_SEED=false` for an empty clinic. Retain signing keys for old-backup recovery. [Defaults/system libraries](docs/setup/configuration.md), [development](docs/setup/development.md).

Fresh schema initialization requires explicit authorization; `bootstrap`/`runserver_auto` perform migration work. Once schema is ready, deliberately seed/start:

```bash
python manage.py seed_db
python manage.py runserver 127.0.0.1:5019
```

Seeding creates users/roles/defaults/catalogs/tasks and updates role/default settings on rerun. New-account passwords print once, including supplied seed-password values; protect output/change at first login. Frontend starts separately on **5173**; `/admin/` is Django admin; SPA serving needs existing `frontend/dist/`.

## Project map

| Location | Responsibility / guide |
| --- | --- |
| `apps/` | Feature models, serializers, canonical services and views; [implemented contracts](docs/contracts/implementation.md), [patient schema/API/retention](docs/contracts/patients.md) |
| `core/` | Permissions/scope, validation, versions/replay, cache/audit, commands; [reference](docs/reference.md) |
| `config/`, `.env.example` | Settings/URLs/entry points; [configuration](docs/setup/configuration.md) |
| `templates/`, `core/pdf_utils.py` | Server documents, bundled Cairo/Inter fonts; [PDF](docs/testing/pdf.md) |
| `data/`, `media/`, `backups/`, `staticfiles/` | Ignored runtime inventory; [operations](docs/operations/guide.md) |
| `tests/` | Synthetic isolated HTTP/service/recovery tests; [testing](docs/testing/guide.md) |

## Contracts and hosting

Fetch `/api/v1/system/config/` before login for CSRF; unsafe requests send `X-CSRFToken`. JSON uses `data`/`error`; downloads return files, no-content statuses return empty bodies. Versioned writes use observed `version`/`If-Match`; refresh conflicts. Covered mutation retries retain `X-Idempotency-Key` and payload. Signed visits/issued documents remain immutable; archive preserves history, pseudonymization retains signed identity. Full authenticated ZIP replaces managed inventory/media after bound preview/confirmation; catalog restore merges.

Production explicitly uses `config.settings.production`, environment `DJANGO_DEBUG=False`, allowed hosts, external database/shared cache and HTTPS/secure cookies; database/cache/WSGI drivers installed separately. SQLite/LocMemCache are rejected in production. [Deployment](docs/setup/deployment.md), [troubleshooting](docs/operations/troubleshooting.md).

Start documentation at [topic index](docs/README.md). Before edits read [AGENTS](AGENTS.md), [remaining work](docs/workCurrent.md), [completed verification](docs/doneCurrent.md). Migration/test-suite work, builds/compilation/packaging and versions require explicit authorization. Never commit secrets/runtime data or expose credentials/patient records.
