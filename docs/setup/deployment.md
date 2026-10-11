# Production hosting by configuration file

Deployment examples, not executed verification. Builds/packaging/schema changes require explicit authorization. Use pinned backend requirements/supported Python, frontend Node engine from `package.json`, HTTPS, external database/shared cache and installed WSGI/database/cache drivers. Production rejects SQLite/LocMemCache. [Configuration](configuration.md), [release checklist](../testing/release-checklist.md).

## Application/environment

Layout: `/srv/myclinic/{backend,frontend,venv}`; deploy user owns writable backend runtime directories. Install system PDF/libmagic libraries from [development](development.md), plus Nginx/shared-cache service. Install the chosen external-DB profile (e.g. `pip install -r requirements/postgresql.txt`) plus shared-cache profile; production WSGI package separately, preserve shared pins. No old Node 18/20 installer or unpinned Django list.

Production `.env` (replace placeholders privately):

```dotenv
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<separate-generated-secret>
BACKUP_HMAC_KEY=<retained-backup-signing-key>
DJANGO_ALLOWED_HOSTS=clinic.example.com
CORS_ORIGINS=https://clinic.example.com
DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=clinic
DATABASE_USER=clinic
DATABASE_PASSWORD=<secret>
DATABASE_HOST=127.0.0.1
DATABASE_PORT=5432
CACHE_BACKEND=django.core.cache.backends.memcached.PyMemcacheCache
CACHE_LOCATION=127.0.0.1:11211
TIME_ZONE=Asia/Damascus
ALLOW_DEMO_DATA=false
AUTO_SEED=false
```

Every process/management command must use `DJANGO_SETTINGS_MODULE=config.settings.production`; secure cookies are forced. Keep passwords/keys/hostnames/clinic defaults in protected configuration. Preserve signing keys for old backups; document rotation/recovery policy.

Authorized asset/schema preparation: apply separately approved schema changes, seed only deliberately, run `pnpm install --frozen-lockfile`/`pnpm build` from frontend, then backend `python manage.py collectstatic --noinput`. Collection before a new build misses new assets. Existing Vite output includes source maps and disables JS/CSS minification. Startup/source checks do not verify bundles.

## `/etc/systemd/system/myclinic.service`

Example uses a private loopback upstream so socket directory permissions are not implicit:

```ini
[Unit]
Description=MyClinic Django backend
After=network.target memcached.service
Requires=memcached.service

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/srv/myclinic/backend
Environment=DJANGO_SETTINGS_MODULE=config.settings.production
EnvironmentFile=/srv/myclinic/backend/.env
ExecStart=/srv/myclinic/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5019 --access-logfile - --error-logfile - config.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
```

Adjust worker count/resources; three is an example, not a measured capacity. `systemctl daemon-reload`, `enable --now myclinic`, `status myclinic`; logs `journalctl -u myclinic -f`. If changing shared-cache backend, update the unit dependency accordingly.

## Nginx site

```nginx
upstream myclinic_backend { server 127.0.0.1:5019; }
server {
    listen 80;
    server_name clinic.example.com;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl;
    server_name clinic.example.com;
    ssl_certificate /etc/letsencrypt/live/clinic.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/clinic.example.com/privkey.pem;
    client_max_body_size 220M;
    location /static/ {
        alias /srv/myclinic/backend/staticfiles/;
        expires 30d;
    }
    location /media/ { return 403; }
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

Deny public raw patient media; authorized API document/attachment downloads remain proxied. Do not add a public media alias. Match upload limit to application limit. TLS files require existing certificates; provision with your certificate workflow (e.g. certbot/Nginx). Enable site, `nginx -t`, reload. Check HTTPS/login/CSRF and document downloads against this actual topology before release.

SPA options: Django's final `config/urls.py` template fallback uses existing `frontend/dist/index.html`; keep API/admin routes before it. Direct Nginx SPA serving instead uses frontend `dist` root and `try_files $uri $uri/ /index.html`, with explicit `/api/` and `/admin/` proxy locations and existing collected `/static/` route. Unknown API errors must not become SPA success pages.

## Scheduled commands/update/rollback

Run individual reminders hourly (task reminder offset five minutes), backup daily 03:00, retention 03:30 through cron/systemd timers. Each uses activated interpreter/production settings; development `run_scheduler` is not production orchestration. [Operations](../operations/guide.md) covers dedupe, retention and off-site copies.

Update: retain last-good code/config and authenticated off-site backup; review requirements/schema changes, install pinned requirements, execute approved schema work, build frontend/collect assets when authorized, restart service, run health/login/API/assets/critical-workflow checks. Rollback: restore last-good code and compatible assets/config; schema changes may need deliberate recovery rather than code checkout alone. Full recovery replaces inventory and revokes sessions.

Protect `.env`, database/media/backups/signing keys, restrict SSH, monitor logs/health, audit dependencies and test staging restore. Rotate leaked keys deliberately; retain backup-key recovery capability. No deploy/build/database action was performed by this documentation update.
