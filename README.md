# MyClinic backend

Django/DRF API **5019**, `/api/v1/`; [Vue frontend](../frontend/README.md) **5173**. Target: modern Windows x64/Linux, Python 3.10–3.12 (3.12 recommended).

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/sqlite.txt
python manage.py check_runtime --render-pdf
python manage.py serve --host 127.0.0.1 --port 5019
```

Windows: create with `py -3.12 -m venv .venv`; use `.venv\Scripts\python.exe`. Install [native libraries](docs/setup.md#native-libraries-by-os), configure private `.env`, and prepare schema/accounts deliberately before serving. `serve` performs checks, never migrations/seeding.

[Rules](AGENTS.md) · [Remaining](docs/workCurrent.md) · [Evidence](docs/doneCurrent.md) · [Contracts](docs/contracts.md) · [Setup](docs/setup.md) · [Operations](docs/operations.md) · [Verification](docs/verification.md)
