# MyClinic backend

Django/DRF clinic API at **5019**, `/api/v1/`; Arabic [Vue frontend](../frontend/README.md) at **5173**.

Use Python **3.10–3.12** with pinned requirements. From `backend/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/sqlite.txt
```

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
