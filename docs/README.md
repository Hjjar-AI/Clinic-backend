# MyClinic — Documentation

Clinic management: Django REST + Vue/Vite. Guides 01–07 retain historical examples; [current setup](../README.md) and [agent rules](../AGENTS.md) take precedence, including authorization for migration/build/test work.

## Where to start

| If you want to… | Read |
|---|---|
| Get the app running locally in 10 minutes | `01-getting-started.md` |
| Understand the full dev setup and directory layout | `02-development.md` |
| Configure `.env`, cache, or file storage | `03-configuration.md` |
| Deploy to a production server | `04-deployment.md` |
| Run backups, the scheduler, or monitor the app | `05-operations.md` |
| Fix a startup error or bug | `06-troubleshooting.md` |
| Look up a command, URL, or default credential | `07-reference.md` |

## Project layout

```
Clinic/
├── backend/      Django project
│   ├── config/       settings + urls
│   ├── core/         shared utilities
│   ├── apps/         feature apps
│   ├── data/         SQLite DB (gitignored)
│   ├── media/        uploads (gitignored)
│   └── backups/      auto-backup ZIPs (gitignored)
└── frontend/     Vue 3 + Vite
    ├── src/
    └── vite.config.js
```

## Conventions

- **Ports/API:** backend `5019`, frontend `5173`; `/api/v1/`
- **JSON:** `{ "data": … }` or `{ "error": { "code", "message", "errors" } }`
- **Auth:** session cookie; `POST /api/v1/auth/login/`
- **Permissions:** roles (`admin`, `doctor`, `receptionist`) + user permission codenames

## Contributing

1. Create a branch.
2. Make changes; when authorized, run `python manage.py test` if present (historically none: `06-troubleshooting.md#no-tests`).
3. Open a PR.

Never commit `.env`, `data/`, `media/`, `backups/`, or `staticfiles/`.

Patient record design: [schema, API, duplicates and retention](patient-record-schema.md).
