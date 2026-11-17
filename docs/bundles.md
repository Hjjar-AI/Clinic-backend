# Executable bundles

[Setup](setup.md) · [Automation](automation.md) · [Verification](verification.md).

The backend's **Windows and Linux bundles** GitHub workflow produces a Windows x64 ZIP and Linux x64 tar.gz. Each contains a `Clinic` executable, its `_internal` resources, the built Vue frontend, templates/fonts, `build-manifest.json` and this guide as `BUNDLE.md`. Keep the entire folder together. These are console bundles, not installers, signed binaries or an automatic update system.

Run `Clinic.exe check` on Windows or `./Clinic check` on Linux. This checks locks, MIME, time zones, fonts and a synthetic Arabic/Latin PDF without reading clinic configuration or accessing a database. CI also starts the frozen executable with disposable settings, checks HTTP configuration, denied anonymous patient access and packaged frontend/assets, then stops it. This does not certify authenticated workflows, physical printing or a deployment.

## Production configuration

The bundle preserves production requirements: a prepared PostgreSQL database, an external shared Redis cache, HTTPS proxy and a supervisor. PostgreSQL/Redis client packages are included; database/cache servers are separate. MySQL/MariaDB drivers are not part of this first bundle recipe. There is no desktop SQLite production mode.

Keep an existing private configuration outside the application folder. It needs the production values described in [setup](setup.md#production), plus `CLINIC_DATA_DIR` pointing to an existing absolute directory outside the application folder. Media/backups/static collection use that directory; existing media and backups need an explicit deployment handoff to those paths. Preserve existing signing keys. Configuration can be selected with `--config` or `CLINIC_CONFIG_FILE`.

```bash
# Linux example; use your own prepared configuration.
./Clinic serve --config /etc/clinic/clinic.env
# Optional local browser launch; the HTTPS proxy remains required in production.
./Clinic serve --config /etc/clinic/clinic.env --open-browser
```

Windows uses `Clinic.exe serve --config C:\ClinicConfig\clinic.env`. Startup never creates schemas/accounts, migrates, seeds, restores data or installs dependencies. Fresh setup and upgrades remain separately managed operations using the matching backend source. Scheduled jobs also remain separately managed; this launcher exposes only serving and runtime checks.

Windows packages include MSYS2 UCRT64 DLLs, MIME/fontconfig resources and supplied native license files. Linux packages target the Ubuntu 24.04 x64 runner ABI and require compatible system libraries: Pango, PangoFT2, Fontconfig, libmagic and shared-mime-info. They are not certified for every Linux distribution. Neither platform bundle requires Node or a separately installed Python.

## Building and downloading

In the backend repository, choose **Actions → Windows and Linux bundles → Run workflow**, select the backend revision and supply the exact 40-character frontend commit SHA. Both repositories are public, so no custom checkout secret is needed. Download the two artifacts after both platform jobs pass; each contains an archive and SHA-256 checksum. The manifest records both source commits and installed build/runtime dependency versions. Artifacts expire after 30 days; the workflow does not publish a GitHub Release or deploy anything.

The workflow runs frontend tests/build and the backend SQLite suite on both platforms, plus the owned PostgreSQL suite on Linux, before packaging. Native checks and frozen smoke checks must pass before upload. CI-only PyInstaller/tzdata tooling is installed on the runner without editing application requirements/lockfiles. Native packages and some existing optional requirements are not fully locked, so manifests provide provenance rather than byte-for-byte reproducibility.

For an authorized local build, install the same workflow tooling in an isolated environment, build the sibling frontend, then run `python -B scripts/build_bundle.py --frontend ../frontend --output /absolute/new/output`. Output must not exist. Only allowlisted source packages, templates and frontend build files are staged; local `.env`, databases, uploads, backups, suites and application migration directories are excluded. Use a clean checkout for distributable artifacts. Packaging intentionally provides no schema installation or upgrade facility.
