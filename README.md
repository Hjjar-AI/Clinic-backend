# MyClinic backend

Django/DRF API **5019**, [Vue UI](../frontend/README.md) **5173**. Local Windows/Linux launcher starts both servers, opens the browser and stops both with Ctrl+C. Run from either folder:

```bash
./start.sh                 # Linux
./start.sh --no-browser    # optional
./start.sh check           # prerequisites; no DB/schema check
```

Windows: double-click `start.cmd`, or run `start.cmd check`. Launcher settings live in **backend/.env**: ports, browser, optional Python/Node paths; the frontend proxy follows automatically.

First use: Python 3.12–3.14 (3.14 recommended), Node `^22.18.0 || >=24.12.0`, pnpm and [native libraries](docs/setup.md#native-libraries-by-os). `./start.sh configure` (`start.cmd configure`) creates private `.env`/separate signing keys only when absent. Install backend requirements/frontend dependencies and prepare the intended schema/accounts once: [setup](docs/setup.md#local-launcher). Daily startup performs no installation, migrations or seeding.

[Rules](AGENTS.md) · [Remaining](docs/workCurrent.md) · [Evidence](docs/doneCurrent.md) · [Contracts](docs/contracts.md) · [Setup](docs/setup.md) · [Operations](docs/operations.md) · [Verification](docs/verification.md)
