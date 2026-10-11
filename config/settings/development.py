from .base import *

# base.py reads DJANGO_DEBUG and DJANGO_ALLOWED_HOSTS from the environment.
# Keep those choices rather than silently overriding the local .env.

# Development deliberately inherits the SQLite + LocMemCache defaults from
# base.py. Those defaults are correct here — the dev server runs as a single
# process on a single machine — but they are NOT safe in production. The
# enforcement that production cannot silently run on them lives in
# config/settings/production.py.
#
# No overrides needed; if you want to test against Postgres or a shared
# cache locally, set DATABASE_ENGINE / CACHE_BACKEND in your environment
# and they will be picked up by base.py.