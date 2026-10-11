"""Database configuration from the environment; never opens a connection."""
import json
from pathlib import Path


ENGINE_ALIASES = {
    'sqlite': 'django.db.backends.sqlite3',
    'sqlite3': 'django.db.backends.sqlite3',
    'postgres': 'django.db.backends.postgresql',
    'postgresql': 'django.db.backends.postgresql',
    'mysql': 'django.db.backends.mysql',
    'maria': 'django.db.backends.mysql',
    'mariadb': 'django.db.backends.mysql',
}


def database_config(base_dir, environ, django_version):
    """Accept friendly engine names or an installed Django backend path."""
    selected = environ.get('DATABASE_ENGINE', '').strip() or 'sqlite'
    engine = ENGINE_ALIASES.get(selected.lower(), selected)
    config = {'ENGINE': engine, 'ATOMIC_REQUESTS': True}
    if engine == 'django.db.backends.sqlite3':
        name = environ.get('DATABASE_NAME', '').strip() or 'data/clinic.db'
        if name != ':memory:' and not name.startswith('file:'):
            path = Path(name).expanduser()
            name = path if path.is_absolute() else Path(base_dir) / path
        options = {'timeout': float(environ.get('DATABASE_TIMEOUT', '20'))}
        # SQLite init_command was added in Django 5.1; retain pinned 5.0 support.
        if django_version >= (5, 1):
            options['init_command'] = 'PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL;'
        if isinstance(name, str) and name.startswith('file:'):
            options['uri'] = True
        config.update(NAME=name, OPTIONS=options)
    else:
        config.update(
            NAME=environ.get('DATABASE_NAME', '').strip() or 'clinic',
            USER=environ.get('DATABASE_USER', ''),
            PASSWORD=environ.get('DATABASE_PASSWORD', ''),
            HOST=environ.get('DATABASE_HOST', ''),
            PORT=environ.get('DATABASE_PORT', ''),
            CONN_MAX_AGE=int(environ.get('DATABASE_CONN_MAX_AGE', '600')),
        )
        options = {}
        if engine == 'django.db.backends.postgresql':
            if environ.get('DATABASE_SSLMODE', '').strip():
                options['sslmode'] = environ['DATABASE_SSLMODE'].strip()
            if environ.get('DATABASE_SSL_CA', '').strip():
                options['sslrootcert'] = environ['DATABASE_SSL_CA'].strip()
        elif engine == 'django.db.backends.mysql':
            options.update(charset='utf8mb4', init_command="SET sql_mode='STRICT_TRANS_TABLES'")
            if environ.get('DATABASE_SSL_CA', '').strip():
                options['ssl'] = {'ca': environ['DATABASE_SSL_CA'].strip()}
        config['OPTIONS'] = options
    try:
        overrides = json.loads(environ.get('DATABASE_OPTIONS', '').strip() or '{}')
    except json.JSONDecodeError as exc:
        raise ValueError('DATABASE_OPTIONS must be a JSON object.') from exc
    if not isinstance(overrides, dict):
        raise ValueError('DATABASE_OPTIONS must be a JSON object.')
    config['OPTIONS'].update(overrides)
    return config
