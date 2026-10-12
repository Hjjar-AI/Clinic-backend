"""Run suites against an owned temporary PostgreSQL cluster, with TCP disabled.

python -B tests/run_postgres.py [test labels]
Requires installed PostgreSQL binaries and a psycopg driver. No production
settings, migration files, project storage or existing database is accessed.
"""
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


def main():
    if os.geteuid() == 0:
        raise SystemExit('Disposable PostgreSQL tests must run as an unprivileged user')
    if any(value.startswith('--settings') for value in sys.argv[1:]):
        raise SystemExit('Only the owned PostgreSQL test profile is allowed')
    configured = os.environ.get('CLINIC_TEST_POSTGRES_BIN')
    choices = [Path(configured)] if configured else sorted(Path('/usr/lib/postgresql').glob('*/bin'), reverse=True)
    binary = next((path for path in choices if all((path / name).is_file() for name in ('initdb', 'pg_ctl', 'createdb'))), None)
    if binary is None:
        raise SystemExit('Install PostgreSQL test binaries or set CLINIC_TEST_POSTGRES_BIN')
    root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix='clinic-postgres-') as directory:
        owned = Path(directory); data = owned / 'data'; socket = owned / 'socket'; socket.mkdir()
        (owned / 'owned-by-test-runner').write_text('Synthetic disposable test cluster\n')
        subprocess.run([str(binary / 'initdb'), '-D', str(data), '--username=clinic_suite', '--auth=trust', '--encoding=UTF8', '--no-locale'], check=True, stdout=subprocess.DEVNULL)
        started = False
        try:
            subprocess.run([str(binary / 'pg_ctl'), '-D', str(data), '-l', str(owned / 'postgres.log'), '-o', f"-F -k {socket} -h '' -p 5432", '-w', 'start'], check=True)
            started = True
            subprocess.run([str(binary / 'createdb'), '-h', str(socket), '-U', 'clinic_suite', 'clinic_suite'], check=True)
            env = {**os.environ, 'CLINIC_OWNED_PG_ROOT': str(owned), 'DJANGO_SETTINGS_MODULE': 'tests.postgres_settings'}
            result = subprocess.run([sys.executable, '-B', 'manage.py', 'test', *(sys.argv[1:] or ['tests']), '--noinput', '--settings=tests.postgres_settings'], cwd=root, env=env)
            return result.returncode
        finally:
            if started or (data / 'postmaster.pid').exists():
                subprocess.run([str(binary / 'pg_ctl'), '-D', str(data), '-m', 'immediate', '-w', 'stop'], check=True)


if __name__ == '__main__':
    raise SystemExit(main())
