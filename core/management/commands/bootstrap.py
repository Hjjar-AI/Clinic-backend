# backend/core/management/commands/bootstrap.py
"""
One-shot first-time setup for the Clinic backend.

Usage:
    python manage.py bootstrap
    python manage.py bootstrap --with-demo-data
    python manage.py bootstrap --with-frontend
    python manage.py bootstrap --clean
    python manage.py bootstrap --clean --yes --with-demo-data

Without --clean, every step is idempotent: re-running on a healthy
project changes nothing. With --clean, the database file and all
migration files for the custom apps are deleted first, then rebuilt
from scratch. --clean requires confirmation unless --yes is passed.

Layout note: in this project `core` lives at `backend/core/`, while
feature apps live at `backend/apps/<name>/`. Path resolution handles
both cases explicitly rather than assuming a single apps/ root.
"""

import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


# Feature apps live under backend/apps/. `core` is handled separately
# because it lives at backend/core/ (see module docstring).
FEATURE_APPS = [
    'accounts',
    'patients',
    'visits',
    'appointments',
    'clinical',
    'billing',
    'tasks',
    'notifications',
    'backup',
    'reports',
    'import_export',
    'prescriptions',
    'referrals',
    'dashboard',
    'settings',
    'exports',
    'system',
]

CORE_APP = 'core'

# Every app that needs a migrations/__init__.py, in a stable order.
CUSTOM_APPS = [CORE_APP] + FEATURE_APPS

# Subset that defines real models. Only these need makemigrations to
# generate 0001_initial.py, and only these are wiped by --clean.
# `backup`, `reports`, `import_export`, `referrals`, `dashboard`,
# `exports`, and `system` are pure service layers.
MODEL_APPS = [
    'core',
    'accounts',
    'patients',
    'visits',
    'appointments',
    'clinical',
    'billing',
    'tasks',
    'notifications',
    'prescriptions',
    'settings',
]


class Command(BaseCommand):
    help = (
        'First-time setup: create migrations packages for custom apps, '
        'migrate, and seed default data (admin, groups, permissions, '
        'diagnoses, medications, tasks). Pass --clean to wipe the database '
        'and migration files first.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            action='store_true',
            help=(
                'DESTRUCTIVE: delete the SQLite database file and every '
                'migration file under the custom apps before rebuilding. '
                'The entire database is lost. Requires confirmation.'
            ),
        )
        parser.add_argument(
            '--yes', '-y',
            action='store_true',
            help='Skip the interactive confirmation for --clean (for scripts/CI).',
        )
        parser.add_argument(
            '--with-demo-data',
            action='store_true',
            help='Also generate demo patients/visits via the settings service.',
        )
        parser.add_argument(
            '--with-frontend',
            action='store_true',
            help='Also run `pnpm install && pnpm build` in the frontend directory.',
        )

    def handle(self, *args, **options):
        # backend/  (bootstrap.py lives at backend/core/management/commands/)
        # parents: [commands, management, core, backend]
        backend_dir = Path(__file__).resolve().parents[3]
        project_root = backend_dir.parent

        if options['clean']:
            self._confirm_clean(assume_yes=options['yes'])
            self._clean(backend_dir)

        self._bootstrap(backend_dir, options)

        if options['with_frontend']:
            self._build_frontend(project_root)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✓ Bootstrap complete.'))
        self.stdout.write('  Start the dev server:  python manage.py runserver 0.0.0.0:8000')

    # ── path helpers ────────────────────────────────────────────────

    def _app_dir(self, app_label, backend_dir):
        """Resolve an app's directory. core -> backend/core/, others -> backend/apps/<name>/."""
        if app_label == CORE_APP:
            return backend_dir / 'core'
        return backend_dir / 'apps' / app_label

    # ── --clean helpers ─────────────────────────────────────────────

    def _confirm_clean(self, assume_yes):
        if assume_yes:
            return

        db_path = Path(settings.DATABASES['default']['NAME'])
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('⚠  --clean will destroy:'))
        self.stdout.write(self.style.WARNING(f'   • {db_path}'))
        for app in MODEL_APPS:
            self.stdout.write(self.style.WARNING(
                f'   • {app}/migrations/*.py  (except __init__.py)'
            ))
        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            '   This cannot be undone. Any patients, visits, appointments, '
            'invoices, tasks, notifications, and settings will be lost.'
        ))
        self.stdout.write('')

        try:
            answer = input("Type DELETE (all caps) to proceed: ").strip()
        except (EOFError, KeyboardInterrupt):
            self.stdout.write('')
            raise CommandError('Aborted.')

        if answer != 'DELETE':
            raise CommandError('Aborted.')

    def _clean(self, backend_dir):
        engine = settings.DATABASES['default']['ENGINE']
        if engine != 'django.db.backends.sqlite3':
            raise CommandError(
                f'--clean only supports SQLite. Current engine: {engine}'
            )

        # CRITICAL: close every open DB connection before unlinking the
        # SQLite file. Clinic's settings enable WAL mode
        # (PRAGMA journal_mode=WAL), so -wal and -shm sidecars are
        # actively in use. Unlinking the main file while a connection
        # is still open drops the directory entry but leaves the inode
        # (and every byte of data) alive; the next command in this same
        # process would reuse the cached connection and read from the
        # deleted inode, producing InconsistentMigrationHistory against
        # a database file that "doesn't exist".
        #
        # Do NOT remove this call. It is load-bearing.
        from django.db import connections
        connections.close_all()

        # 1. Delete the DB file plus every SQLite sidecar. WAL mode is
        #    on in this project, so -wal and -shm are the primary
        #    sidecars; -journal appears only if WAL is ever disabled.
        db_path = Path(settings.DATABASES['default']['NAME'])
        deleted_any = False
        for suffix in ('', '-journal', '-wal', '-shm'):
            candidate = Path(str(db_path) + suffix)
            if candidate.exists():
                candidate.unlink()
                self.stdout.write(f'[clean] deleted {candidate}')
                deleted_any = True
        if not deleted_any:
            self.stdout.write(f'[clean] no database file at {db_path} (already clean)')

        # 2. Delete migration files, keeping __init__.py so the folder
        #    remains a Python package.
        for app in MODEL_APPS:
            app_dir = self._app_dir(app, backend_dir)
            migrations_dir = app_dir / 'migrations'
            if not migrations_dir.is_dir():
                continue
            for f in sorted(migrations_dir.glob('*.py')):
                if f.name == '__init__.py':
                    continue
                f.unlink()
                self.stdout.write(
                    f'[clean] deleted {app}/migrations/{f.name}'
                )
            # Drop the .pyc cache so Django doesn't pick up stale
            # compiled migrations on the next import.
            pycache = migrations_dir / '__pycache__'
            if pycache.is_dir():
                shutil.rmtree(pycache)

    # ── main bootstrap pipeline ─────────────────────────────────────

    def _bootstrap(self, backend_dir, options):
        # ── 1. Ensure every custom app has a migrations package ─────
        ensured = []
        for app in CUSTOM_APPS:
            app_dir = self._app_dir(app, backend_dir)
            if not app_dir.is_dir():
                continue
            migrations_dir = app_dir / 'migrations'
            migrations_dir.mkdir(exist_ok=True)
            init_file = migrations_dir / '__init__.py'
            if not init_file.exists():
                init_file.touch()
            ensured.append(app)

        self.stdout.write(self.style.SUCCESS(
            f'[1/5] migrations packages ensured: {", ".join(ensured) or "(none found)"}'
        ))

        # ── 2. makemigrations only if any model app lacks migration files ─
        needs_makemigrations = False
        for app in MODEL_APPS:
            app_dir = self._app_dir(app, backend_dir)
            migrations_dir = app_dir / 'migrations'
            if not migrations_dir.is_dir():
                needs_makemigrations = True
                break
            has_file = any(
                f.name != '__init__.py' for f in migrations_dir.glob('*.py')
            )
            if not has_file:
                needs_makemigrations = True
                break

        if needs_makemigrations:
            self.stdout.write('[2/5] creating initial migrations for custom apps...')
            call_command('makemigrations', *MODEL_APPS)
        else:
            self.stdout.write(
                '[2/5] custom apps already have migrations — skipping makemigrations'
            )

        # ── 3. migrate (Django makes this a no-op if nothing new) ───
        self.stdout.write('[3/5] applying migrations...')
        call_command('migrate')

        # ── 4. seed (idempotent: exists() / get_or_create) ──────────
        self.stdout.write('[4/5] seeding default data...')
        call_command('seed_db')

        # ── 5. optionally generate demo data ────────────────────────
        if options['with_demo_data']:
            self.stdout.write('[5/5] generating demo data...')
            if not getattr(settings, 'ALLOW_DEMO_DATA', False):
                self.stdout.write(self.style.WARNING(
                    '     skipped: ALLOW_DEMO_DATA is disabled in settings.'
                ))
            else:
                from apps.settings.services import SettingsService
                try:
                    created = SettingsService().generate_demo_data()
                    self.stdout.write(self.style.SUCCESS(
                        f'     created {created} demo patients.'
                    ))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'     failed: {e}'))
        else:
            self.stdout.write(
                '[5/5] skipping demo data (pass --with-demo-data to generate)'
            )

    # ── optional frontend build ─────────────────────────────────────

    def _build_frontend(self, project_root):
        frontend_dir = project_root / 'frontend'
        if not frontend_dir.is_dir():
            self.stdout.write(self.style.WARNING(
                f'[frontend] no frontend directory at {frontend_dir}, skipping'
            ))
            return
        if not (frontend_dir / 'package.json').exists():
            self.stdout.write(self.style.WARNING(
                f'[frontend] no package.json in {frontend_dir}, skipping'
            ))
            return

        self.stdout.write('[frontend] running pnpm install...')
        try:
            subprocess.run(['pnpm', 'install'], cwd=str(frontend_dir), check=True)
            self.stdout.write('[frontend] running pnpm build...')
            subprocess.run(['pnpm', 'build'], cwd=str(frontend_dir), check=True)
            self.stdout.write(self.style.SUCCESS('[frontend] build complete.'))
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING(
                '[frontend] pnpm not found on PATH, skipping.'
            ))
        except subprocess.CalledProcessError as e:
            raise CommandError(f'Frontend build failed: {e}')