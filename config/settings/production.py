import os
from .base import *

DEBUG = False
ALLOW_DEMO_DATA = False
AUTO_SEED = False

# Parse ALLOWED_HOSTS robustly. The previous
#     os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',')
# yielded [''] when the env var was unset — an empty string host, which is
# not the same as an empty list. Stripping blanks gives [] on unset and
# also tolerates stray commas / whitespace.
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',')
    if host.strip()
]

if not ALLOWED_HOSTS:
    raise RuntimeError(
        'DJANGO_ALLOWED_HOSTS is not set. Production must declare the '
        'hostnames Django will serve, for example:\n'
        '  DJANGO_ALLOWED_HOSTS=clinic.example.com,www.clinic.example.com'
    )

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# ---------------------------------------------------------------------
# Production safety rails
# ---------------------------------------------------------------------
# base.py intentionally defaults to two "development-shaped" backends so the
# local dev setup works out of the box. Both defaults silently break under a
# multi-worker production deployment, so refuse to boot if they were not
# overridden. This turns a confusing "stale data" or "duplicate booking"
# bug report into an immediate, actionable startup error.

# 1. SQLite. It serializes all writers through a single global lock, which
#    masks (rather than fixes) the concurrency issues that the rest of the
#    codebase actively guards against — appointment booking row locks,
#    idempotency-key middleware, invalidate_group() version increments. Under
#    Postgres/MySQL those guards do their job; under SQLite they are no-ops.
if DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
    raise RuntimeError(
        'Production is running on SQLite. Set DATABASE_ENGINE (and the '
        'other DATABASE_* env vars) to a real database, for example:\n'
        '  DATABASE_ENGINE=django.db.backends.postgresql\n'
        '  DATABASE_NAME=clinic\n'
        '  DATABASE_USER=clinic\n'
        '  DATABASE_PASSWORD=<secret>\n'
        '  DATABASE_HOST=127.0.0.1\n'
        '  DATABASE_PORT=5432'
    )

# 2. LocMemCache. It is process-local, so the invalidate_group() version-
#    counter scheme in core/cache_utils.py only works within a single
#    process. With multiple gunicorn/uwsgi workers, each worker keeps its
#    own counter and its own cached values; a write that invalidates a group
#    in one worker leaves the other workers serving stale dashboard, report,
#    and settings data until they restart.
if 'locmem' in CACHES['default']['BACKEND'].lower():
    raise RuntimeError(
        'Production is running on LocMemCache. Set CACHE_BACKEND to a '
        'shared backend, for example:\n'
        '  CACHE_BACKEND=django.core.cache.backends.memcached.PyMemcacheCache\n'
        '  CACHE_LOCATION=127.0.0.1:11211\n'
        'or:\n'
        '  CACHE_BACKEND=django.core.cache.backends.redis.RedisCache\n'
        '  CACHE_LOCATION=redis://127.0.0.1:6379/1'
    )
