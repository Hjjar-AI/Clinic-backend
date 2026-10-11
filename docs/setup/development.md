# Development by source/configuration area

Canonical install/start sequence: [root README](../../README.md); frontend Node/setup: [frontend README](../../../frontend/README.md). Commands run from activated `backend/` environment. Use the matching database profile (SQLite/PostgreSQL/MySQL/MariaDB) including pinned `requirements.txt`; optional cache clients are separate. No hard-coded workstation paths.

| Files / task | Behavior and options |
| --- | --- |
| `manage.py`, `config/settings/base.py`, `database.py`, `.env.example` | `.env` selects settings/DB/cache before command dispatch; SQLite defaults `data/clinic.db` with configurable path, process-local cache for development; [configuration](configuration.md). `.env` startup reads require restart after changes. |
| System dependencies | Debian/Ubuntu: `libmagic1`, Pango/Cairo/GObject dependencies, `libffi-dev`, `shared-mime-info`; macOS: `libmagic pango cairo gdk-pixbuf libffi`. `python -c "from weasyprint import HTML; print('ok')"` checks renderer import only. Memcached optional locally. |
| Runtime directories | `data/`, `media/`, `backups/`, generated `staticfiles/` remain ignored; creating folders does not initialize schema. |
| `bootstrap` command | Requires explicit migration authorization: prepares migrations/schema and seeds. `--with-demo-data` populates samples; `--with-frontend` installs/builds (separate build authorization). `--clean` deletes SQLite/custom migrations and needs explicit destructive authorization; `--yes` skips its DELETE prompt. |
| `runserver_auto` | Also prepares migrations before serving; explicit migration authorization required. Plain `runserver 127.0.0.1:5019` avoids that helper. |
| `seed_db` | Creates/updates permission groups/defaults/users/catalogs/tasks; deliberately authorized data operation. Seed passwords and role behavior: [reference](../reference.md). |
| Models / `INSTALLED_APPS` | Trace service/serializer/API/import/export/recovery/UI consumers, keep contracts consistent. Schema generation/application is separately authorized, not a documentation/source check. |
| `core/permissions.py` | Add codenames to `ALL_PERMISSIONS`/appropriate defaults and DRF permission class, then deliberately reseed role defaults. User creation must not rewrite existing grants. |
| New feature app | Register in `INSTALLED_APPS`; canonical services own lifecycle/validation, serializers adapt representation. [Contracts](../contracts/implementation.md). |
| Frontend `vite.config.js` | `/api` dev proxy defaults 5019; use `VITE_BACKEND_URL` for alternative backend port and match CORS exact origin. |
| Tests | Actual suite is `tests/` with isolated settings/runner, not historical app-local skeletons. [Commands](../testing/guide.md), [frontend tests](../../../frontend/docs/testing/guide.md). |

Development health: `http://localhost:5019/api/v1/system/health/`; UI `http://localhost:5173`; admin `/admin/`. Django autoreloads Python/template changes; frontend Vite handles source updates. Development source checks are not production-bundle/browser/PostgreSQL verification. [Rules](../../AGENTS.md), [troubleshooting](../operations/troubleshooting.md).
