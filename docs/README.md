# File 1 of 8: `docs/README.md`

# MyClinic — Documentation

Full-stack clinic management system. Django REST backend, Vue + Vite frontend.

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

- **Dev port:** backend `5019`, frontend `5173`
- **API base:** `/api/v1/`
- **Response envelope:** every JSON response is `{ "data": … }` or `{ "error": { "code", "message", "errors" } }`
- **Auth:** session cookie; login at `POST /api/v1/auth/login/`
- **Permissions:** role-based (`admin`, `doctor`, `receptionist`) plus codename permissions on the user model

## Contributing

1. Create a branch.
2. Make changes; run `python manage.py test` if any exist (currently none — see `06-troubleshooting.md#no-tests`).
3. Open a PR.

Never commit `.env`, `data/`, `media/`, `backups/`, or `staticfiles/`.

---
