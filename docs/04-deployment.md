# File 5 of 8: `docs/04-deployment.md`

# Deployment (Production)

Production checklist and reference configs. Assumes Debian/Ubuntu with `systemd` and `nginx`.

## 1. Checklist

Before you start:

- [ ] Server with Python 3.10+, Node.js 18+, `pnpm`, `memcached`, `nginx`
- [ ] Database chosen: SQLite works for small clinics; PostgreSQL for anything larger
- [ ] `DJANGO_SECRET_KEY` and `BACKUP_HMAC_KEY` generated and stored in a secret manager
- [ ] `.env` created on the server (not in git)
- [ ] DNS pointing at the server
- [ ] TLS certificate (Let's Encrypt via `certbot` works)

## 2. System packages

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx memcached \
    libmagic1 libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    libffi-dev shared-mime-info
sudo systemctl enable --now memcached
```

Node (for the build step):

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g pnpm
```

## 3. Deploy the code

Recommended layout:

```
/srv/myclinic/
├── backend/      (git clone of the repo's backend/)
├── frontend/     (built assets)
└── venv/         (python environment)
```

```bash
sudo mkdir -p /srv/myclinic
sudo chown -R deploy:deploy /srv/myclinic
cd /srv/myclinic
git clone <repo-url> .
```

## 4. Backend environment

```bash
cd /srv/myclinic/backend
python3 -m venv /srv/myclinic/venv
source /srv/myclinic/venv/bin/activate
pip install --upgrade pip
pip install \
    "Django>=4.2,<6" djangorestframework django-cors-headers \
    python-dotenv whitenoise python-dateutil pandas openpyxl \
    python-magic python-docx olefile Faker weasyprint pymemcache \
    gunicorn
```

## 5. Production `.env`

Create `/srv/myclinic/backend/.env`:

```dotenv
DJANGO_SECRET_KEY=<generated>
BACKUP_HMAC_KEY=<generated>

DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=clinic.example.com
CORS_ORIGINS=https://clinic.example.com

SESSION_COOKIE_SECURE=true
SESSION_COOKIE_AGE=10800
MAX_LOGIN_ATTEMPTS=10
LOGIN_LOCKOUT_MINUTES=15

CLINIC_NAME=عيادة الإتزان
CLINIC_ADDRESS=...
CLINIC_PHONE=...

CACHE_LOCATION=127.0.0.1:11211
```

Note: `production.py` sets `SESSION_COOKIE_SECURE = True` and `CSRF_COOKIE_SECURE = True` unconditionally. TLS is required.

## 6. Database migrations

```bash
cd /srv/myclinic/backend
source /srv/myclinic/venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings.production

mkdir -p data backups media
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py seed_db
```

`seed_db` prints admin credentials once. Save them, then immediately log in and rotate.

## 7. Frontend build

```bash
cd /srv/myclinic/frontend
pnpm install --frozen-lockfile
pnpm build
```

Output lands in `frontend/dist/`, which is already in `STATICFILES_DIRS`.

Re-run `python manage.py collectstatic --noinput` afterwards.

## 8. Gunicorn systemd unit

`/etc/systemd/system/myclinic.service`:

```ini
[Unit]
Description=MyClinic Django backend
After=network.target memcached.service
Requires=memcached.service

[Service]
Type=notify
User=deploy
Group=deploy
WorkingDirectory=/srv/myclinic/backend
Environment="DJANGO_SETTINGS_MODULE=config.settings.production"
EnvironmentFile=/srv/myclinic/backend/.env
ExecStart=/srv/myclinic/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/run/myclinic.sock \
    --access-logfile - \
    --error-logfile - \
    config.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RuntimeDirectory=myclinic

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now myclinic
sudo systemctl status myclinic
```

Worker count: `2 × CPU cores + 1` is the classic heuristic; 3 is fine for a small clinic.

## 9. Nginx

`/etc/nginx/sites-available/myclinic`:

```nginx
upstream myclinic_backend {
    server unix:/run/myclinic.sock;
}

server {
    listen 80;
    server_name clinic.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name clinic.example.com;

    ssl_certificate     /etc/letsencrypt/live/clinic.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/clinic.example.com/privkey.pem;

    client_max_body_size 220M;

    # Static assets collected by Django
    location /static/ {
        alias /srv/myclinic/backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # User uploads
    location /media/ {
        alias /srv/myclinic/backend/media/;
        expires 7d;
    }

    # Everything else → Django
    location / {
        proxy_pass http://myclinic_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
```

Enable:

```bash
sudo ln -s /etc/nginx/sites-available/myclinic /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

TLS via `certbot`:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d clinic.example.com
```

## 10. Serving the frontend

Two options.

**Option A — Django serves `index.html` (already wired).**  
`config/urls.py` ends with a catch-all `re_path(r'^.*$', TemplateView.as_view(template_name='index.html'))`. As long as `frontend/dist/` is in `STATICFILES_DIRS` and `collectstatic` has run, Nginx's `location /` proxies to Django, which returns the SPA shell for any unknown path.

**Option B — Nginx serves `dist/` directly.**  
Replace `location /` with:

```nginx
location / {
    root /srv/myclinic/frontend/dist;
    try_files $uri $uri/ /index.html;
}
location /api/ {
    proxy_pass http://myclinic_backend;
    # ... headers as above
}
```

Option B is faster. Option A is simpler. Pick one.

## 11. Media files

`MEDIA_ROOT = /srv/myclinic/backend/media`. Nginx serves it directly (above). Ensure:

- The `deploy` user owns `media/`.
- `client_max_body_size` in Nginx matches `MAX_CONTENT_LENGTH` in `.env` (default 210 MB) — otherwise large uploads fail with a 413 before reaching Django.

## 12. Scheduled tasks

Do **not** use `python manage.py run_scheduler` in production. Configure `systemd` timers or cron instead:

`/etc/cron.d/myclinic`:

```cron
# Appointment reminders — every hour
0 * * * *  deploy  cd /srv/myclinic/backend && /srv/myclinic/venv/bin/python manage.py send_appointment_reminders

# Task reminders — every hour, offset by 5 min
5 * * * *  deploy  cd /srv/myclinic/backend && /srv/myclinic/venv/bin/python manage.py send_task_reminders

# Daily backup at 03:00
0 3 * * *  deploy  cd /srv/myclinic/backend && /srv/myclinic/venv/bin/python manage.py auto_backup

# Retention sweep at 03:30
30 3 * * * deploy  cd /srv/myclinic/backend && /srv/myclinic/venv/bin/python manage.py cleanup_backups
```

Set `DJANGO_SETTINGS_MODULE=config.settings.production` in each environment. See `05-operations.md` for details.

## 13. Backups

`auto_backup` writes signed ZIP archives to `backend/backups/`. **Backups on the same server as the database are not real backups.** Add an off-site sync:

```bash
# Example: rsync to a remote host nightly at 04:00
0 4 * * * deploy rsync -a --delete /srv/myclinic/backend/backups/ backup-host:/srv/backups/myclinic/
```

Or use `rclone` to push to S3/B2/Drive. See `05-operations.md#off-site-sync`.

## 14. Health checks

External monitoring should poll:

```
GET https://clinic.example.com/api/v1/system/health/
```

Returns `{"data":{"status":"ok","database":"ok"}}` when healthy. Anything else means the app or DB is down.

## 15. Updating a deployment

```bash
cd /srv/myclinic
git pull
source venv/bin/activate

cd backend
pip install -r requirements.txt   # or the explicit list above
export DJANGO_SETTINGS_MODULE=config.settings.production
python manage.py migrate
python manage.py collectstatic --noinput

cd ../frontend
pnpm install --frozen-lockfile
pnpm build
cd ../backend
python manage.py collectstatic --noinput

sudo systemctl restart myclinic
```

## 16. Rollback

Keep the last known-good commit hash. To roll back:

```bash
git checkout <previous-commit>
# rerun §15 steps 5–10
sudo systemctl restart myclinic
```

Database migrations are the hard part. If the schema changed, you may need to restore from a backup — see `05-operations.md#restore`.

## 17. Security notes

- Never run with `DEBUG=true` in production. `base.py` raises if secrets are missing; `production.py` forces secure cookies.
- Store `.env` outside of git. Use a secret manager (Vault, AWS Secrets Manager, systemd credentials) if available.
- Restrict SSH. Use key auth only.
- Rotate `DJANGO_SECRET_KEY` and `BACKUP_HMAC_KEY` immediately if either leaks.
- `ALLOWED_HOSTS` must not contain `*` in production.
- Run `pip-audit` periodically to catch vulnerable dependencies.

## Next

- Operations → `05-operations.md`
- Troubleshooting → `06-troubleshooting.md`

---