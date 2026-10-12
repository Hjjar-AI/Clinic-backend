# Backend documentation

| Need | Read | Source ownership |
| --- | --- | --- |
| Start locally | [Root README](../README.md), [development](setup/development.md) | Requirements, settings, management commands |
| Working rules | [AGENTS](../AGENTS.md) | Scope, authorization, privacy |
| Remaining work / latest verification | [Current](workCurrent.md) / [completed](doneCurrent.md) | Open checks / recorded outcomes |
| Environment defaults | [Configuration](setup/configuration.md) | `config/settings/`, `.env.example`, storage/fonts |
| Production hosting | [Deployment](setup/deployment.md) | WSGI, Nginx, HTTPS, assets, scheduled commands |
| Backups/recovery/reminders | [Operations](operations/guide.md) | `apps/backup/`, `core/management/commands/` |
| Diagnose a failure | [Troubleshooting](operations/troubleshooting.md) | Startup, session, proxy, media, restore |
| Routes/commands/dependencies | [Reference](reference.md) | `core/urls.py`, permissions, command options |
| Implemented logic by source area | [Implementation](contracts/implementation.md) | Models/services, auth/scope, versions, recovery, reports |
| Models and deep logic review | [Consolidated review](reviews/models-and-logic-2026-10-12.md) | Model inventory, all related areas, findings, design suggestions and verification limits |
| Patient schema/API/retention | [Patients](contracts/patients.md) | `apps/patients/`, related visit/team/document flows |
| Test commands and coverage | [Testing](testing/guide.md) | Isolated HTTP/service/recovery tests |
| Arabic PDF/print verification | [PDF](testing/pdf.md) | `core/pdf_utils.py`, templates, browser documents |
| Release validation | [Checklist](testing/release-checklist.md) | Role/failure/full workflow checks |
| UI coordination | [Frontend index](../../frontend/docs/README.md) | Vue, CSS/RTL, browser interactions |

One guide per topic; source-file tables retain corrections, contracts and limits. Put only unresolved work in `workCurrent.md` and current outcomes in `doneCurrent.md`.
