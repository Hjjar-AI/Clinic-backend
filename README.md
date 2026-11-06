# MyClinic backend

Django/DRF clinic API at **5019**, `/api/v1/`; Arabic [Vue frontend](../frontend/README.md) at **5173**.

Target modern **Windows 10/11 x64 and Linux**, using Python **3.10–3.12** (3.12 recommended) with pinned requirements. Windows 7/Python 3.8 are not supported. From `backend/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/sqlite.txt
```

On Windows, activation is optional; use the virtual environment's Python directly:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements/sqlite.txt
```

The current model redesign requires a fresh schema. Application migration scripts were removed as requested and have not been regenerated; [remaining schema/integration work](docs/workCurrent.md) must be handled before starting the application.

Install native PDF/MIME libraries using the [OS setup instructions](docs/setup.md#native-libraries-by-os). Once configuration and schema are ready:

```bash
python manage.py check_runtime --render-pdf
python manage.py serve --host 127.0.0.1 --port 5019
```

On Windows use `.\.venv\Scripts\python.exe` instead of `python` in those commands. `serve` uses Waitress on either OS, checks runtime dependencies and performs no migrations or seeding. `check_runtime` reads no clinic records and renders only synthetic data in memory.

Copy `.env.example` to `.env` only when absent; configure separate signing keys and the intended DB/cache. Once schema/accounts are initialized, start `python manage.py runserver 127.0.0.1:5019`. Schema preparation and seeding are deliberate authorized operations; `bootstrap`/`runserver_auto` perform migration work.

| Need | Document |
| --- | --- |
| Working rules | [AGENTS](AGENTS.md) |
| Remaining work / completed evidence | [Current](docs/workCurrent.md) / [completed](docs/doneCurrent.md) |
| Models, API, identity and retention | [Contracts](docs/contracts.md) |
| Environment, dependencies and hosting | [Setup](docs/setup.md) |
| Backups, jobs and troubleshooting | [Operations](docs/operations.md) |
| Test commands, PDF inspection and release checks | [Verification](docs/verification.md) |

Production uses explicit production settings, HTTPS, external DB/shared cache and authorized assets/schema preparation. Runtime secrets/data stay ignored. No migration/test-suite work, builds or version changes without explicit authorization.
