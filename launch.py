"""Local backend + Vite launcher. Standard library only; no install/schema jobs."""
import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser


ROOT = Path(__file__).resolve().parent
HOST = '127.0.0.1'
ENV_KEYS = {
    'CLINIC_PYTHON', 'CLINIC_NODE', 'CLINIC_BACKEND_PORT',
    'CLINIC_FRONTEND_PORT', 'CLINIC_OPEN_BROWSER', 'DJANGO_SETTINGS_MODULE',
    'DJANGO_ALLOWED_HOSTS', 'CORS_ORIGINS', 'CSRF_TRUSTED_ORIGINS',
}


class LaunchError(Exception):
    pass


def configure(root):
    """Create once, privately; never replace existing configuration/signing keys."""
    target = root / '.env'
    if target.exists():
        print('Existing backend .env retained.')
        return False
    content = (root / '.env.example').read_text(encoding='utf-8')
    for key in ('DJANGO_SECRET_KEY', 'BACKUP_HMAC_KEY'):
        content, count = re.subn(rf'^{key}=.*$', f'{key}={secrets.token_hex(32)}', content, flags=re.M)
        if count != 1:
            raise LaunchError(f'.env.example must contain exactly one {key} assignment.')
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print('Existing backend .env retained.')
        return False
    with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
        stream.write(content)
    print('Created private backend .env with separate generated signing keys.')
    return True


def launcher_values(path, environ):
    """Read only literal launcher/network values; Django loads the full dotenv."""
    if not path.is_file():
        raise LaunchError('Missing backend .env. Run the launcher with configure first.')
    values = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        match = re.match(r'^\s*(?:export\s+)?([A-Z_][A-Z_0-9]*)\s*=\s*(.*)$', line)
        if not match or match[1] not in ENV_KEYS:
            continue
        key, raw = match.groups()
        if key in environ:
            continue
        if raw.startswith(('"', "'")):
            quoted = re.fullmatch(r'''(['"])(.*?)\1\s*(?:#.*)?''', raw)
            if not quoted:
                raise LaunchError(f'Invalid quoted launcher setting: {key}.')
            value = quoted[2]
        else:
            value = re.split(r'\s+#', raw, maxsplit=1)[0].strip()
        if '$' in value:
            raise LaunchError(f'Use a literal value (no variable expansion) for {key}.')
        values[key] = value
    values.update({key: environ[key] for key in ENV_KEYS if key in environ})
    return values


def port_value(values, key, default):
    value = values.get(key, str(default))
    if not re.fullmatch(r'[0-9]{1,5}', value) or not 1 <= int(value) <= 65535:
        raise LaunchError(f'{key} must be an integer from 1 to 65535.')
    return int(value)


@dataclass(frozen=True)
class Configuration:
    root: Path
    frontend: Path
    backend_port: int
    frontend_port: int
    open_browser: bool
    python: str
    node: str
    env: dict


def executable(value, candidates, root, label):
    choices = [value] if value else candidates
    for candidate in choices:
        candidate = str(candidate)
        found = shutil.which(candidate)
        if not found:
            path = Path(candidate).expanduser()
            path = path if path.is_absolute() else root / path
            found = str(path.resolve()) if path.is_file() and os.access(path, os.X_OK) else None
        if found:
            return found
    raise LaunchError(f'{label} not found. Set CLINIC_{label.upper()} in backend .env or install it.')


def configuration(root, environ=None, no_browser=False):
    environ = dict(os.environ if environ is None else environ)
    values = launcher_values(root / '.env', environ)
    mode = values.get('DJANGO_SETTINGS_MODULE') or 'config.settings.development'
    if mode != 'config.settings.development':
        raise LaunchError('This launcher is for local development. Use docs/setup.md for production settings.')
    backend_port = port_value(values, 'CLINIC_BACKEND_PORT', 5019)
    frontend_port = port_value(values, 'CLINIC_FRONTEND_PORT', 5173)
    if backend_port == frontend_port:
        raise LaunchError('Backend and frontend ports must be different.')
    browser = values.get('CLINIC_OPEN_BROWSER', 'true').lower()
    if browser not in {'true', 'false'}:
        raise LaunchError('CLINIC_OPEN_BROWSER must be true or false.')
    python = executable(values.get('CLINIC_PYTHON'), [
        root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python'),
        root / 'venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python'),
        sys.executable,
    ], root, 'Python')
    node = executable(values.get('CLINIC_NODE'), ['node'], root, 'Node')
    env = {**environ, 'DJANGO_SETTINGS_MODULE': mode, 'PYTHONUNBUFFERED': '1',
        'VITE_BACKEND_URL': f'http://{HOST}:{backend_port}', 'VITE_API_BASE_URL': '/api/v1'}
    for key, required in (
        ('DJANGO_ALLOWED_HOSTS', [HOST, 'localhost']),
        ('CORS_ORIGINS', [f'http://{HOST}:{frontend_port}', f'http://localhost:{frontend_port}']),
        ('CSRF_TRUSTED_ORIGINS', [f'http://{HOST}:{frontend_port}', f'http://localhost:{frontend_port}']),
    ):
        existing = [part.strip() for part in values.get(key, '').split(',') if part.strip()]
        env[key] = ','.join(dict.fromkeys([*existing, *required]))
    return Configuration(root, root.parent / 'frontend', backend_port, frontend_port,
        browser == 'true' and not no_browser, python, node, env)


def checked_output(command, *, cwd, env):
    try:
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
            text=True, check=True, timeout=15)
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        # Do not echo child output: configuration/errors could contain private values.
        raise LaunchError('Runtime check failed. Check the configured Python/Node executable and dependencies.') from None


def require_free_port(port):
    try:
        with socket.socket() as listener:
            listener.bind((HOST, port))
    except OSError:
        raise LaunchError(f'Port {port} is unavailable. Stop its existing owner or change the port in .env.') from None


def preflight(config):
    version = checked_output([config.python, '-B', '-c',
        'import json,sys; print(json.dumps(list(sys.version_info[:2])))'], cwd=config.root, env=config.env)
    try:
        supported = (3, 10) <= tuple(json.loads(version)) <= (3, 12)
    except (TypeError, ValueError):
        supported = False
    if not supported:
        raise LaunchError('Use Python 3.10–3.12 (3.12 recommended); set CLINIC_PYTHON to the app environment.')
    modules = checked_output([config.python, '-B', '-c',
        "import importlib.util,json; print(json.dumps([name for name in "
        "('django','dotenv','rest_framework','waitress','portalocker') if importlib.util.find_spec(name) is None]))"],
        cwd=config.root, env=config.env)
    try:
        missing = json.loads(modules)
    except (TypeError, ValueError):
        raise LaunchError('Python dependency inspection returned an invalid result; check CLINIC_PYTHON.') from None
    if not isinstance(missing, list) or missing:
        raise LaunchError('Python dependencies are missing. Install requirements for your database in the selected environment; see docs/setup.md.')
    keys = checked_output([config.python, '-B', '-c',
        "import json,os; from dotenv import load_dotenv; load_dotenv('.env', override=False); "
        "keys=('DJANGO_SECRET_KEY','BACKUP_HMAC_KEY'); "
        "print(json.dumps(bool(all(os.getenv(k) for k in keys)) and os.getenv(keys[0]) != os.getenv(keys[1])))"],
        cwd=config.root, env=config.env)
    if keys != 'true':
        raise LaunchError('Set separate nonempty DJANGO_SECRET_KEY and BACKUP_HMAC_KEY in the existing .env; existing keys are never regenerated.')
    node_version = checked_output([config.node, '--version'], cwd=config.root, env=config.env)
    match = re.fullmatch(r'v(\d+)\.(\d+)\.(\d+)', node_version)
    version = tuple(map(int, match.groups())) if match else (0, 0, 0)
    if not ((22, 18, 0) <= version < (23, 0, 0) or version >= (24, 12, 0)):
        raise LaunchError('Use Node ^22.18.0 or >=24.12.0, as declared in frontend/package.json.')
    if not (config.frontend / 'node_modules/vite/bin/vite.js').is_file():
        raise LaunchError('Frontend dependencies are missing. Run pnpm install --frozen-lockfile in frontend once.')
    require_free_port(config.backend_port)
    require_free_port(config.frontend_port)
    result = subprocess.run([config.python, '-B', 'manage.py', 'check_runtime', '--render-pdf'],
        cwd=config.root, env=config.env, timeout=60)
    if result.returncode:
        raise LaunchError('Native/runtime dependencies are incomplete; follow the reported remedies.')


def spawn(command, cwd, env):
    options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
    return subprocess.Popen(command, cwd=cwd, env=env, **options)


def stop(process):
    if os.name == 'nt':
        if process.poll() is None:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        # A server may exit before its descendants; clean the owned group too.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=10)


def ready(port):
    try:
        with socket.create_connection((HOST, port), timeout=0.2):
            return True
    except OSError:
        return False


def run_servers(config, commands=None, timeout=90):
    commands = commands or [
        ([config.python, '-B', 'manage.py', 'serve', '--host', HOST, '--port', str(config.backend_port)], config.root),
        ([config.node, str(config.frontend / 'node_modules/vite/bin/vite.js'), '--host', HOST,
          '--port', str(config.frontend_port), '--strictPort'], config.frontend),
    ]
    processes = []
    try:
        for command, cwd in commands:
            processes.append(spawn(command, cwd, config.env))
        deadline = time.monotonic() + timeout
        announced = False
        while True:
            for label, process in zip(('Backend', 'Frontend'), processes):
                if process.poll() is not None:
                    raise LaunchError(f'{label} stopped (exit {process.returncode}); both servers are being stopped.')
            if not announced:
                if all(ready(port) for port in (config.backend_port, config.frontend_port)):
                    url = f'http://{HOST}:{config.frontend_port}'
                    print(f'Clinic ready: {url} — Ctrl+C stops both servers.', flush=True)
                    announced = True
                    if config.open_browser:
                        try:
                            webbrowser.open(url)
                        except (webbrowser.Error, OSError):
                            print('Open the displayed URL in your browser.')
                elif time.monotonic() >= deadline:
                    raise LaunchError('Startup timed out; both servers are being stopped. Check the server output above.')
            time.sleep(0.2)
    except KeyboardInterrupt:
        print('\nStopping Clinic…', flush=True)
    finally:
        for process in reversed(processes):
            try:
                stop(process)
            except (OSError, subprocess.SubprocessError):
                print('A server could not be stopped; check its terminal/process before restarting.', file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Local Clinic launcher: one .env, backend + frontend, Ctrl+C to stop.')
    parser.add_argument('command', nargs='?', default='start', choices=('start', 'configure', 'check'))
    parser.add_argument('--no-browser', action='store_true', help='Start without opening a browser.')
    args = parser.parse_args(argv)
    try:
        if args.command == 'configure':
            configure(ROOT)
            return 0
        if args.command == 'start' and not (ROOT / '.env').exists():
            configure(ROOT)
        config = configuration(ROOT, no_browser=args.no_browser)
        print(f'Backend {HOST}:{config.backend_port} · Frontend {HOST}:{config.frontend_port}', flush=True)
        preflight(config)
        if args.command == 'check':
            print('Startup prerequisites passed. Database/schema readiness is not checked.')
            return 0
        def interrupted(*_):
            raise KeyboardInterrupt
        previous = signal.signal(signal.SIGTERM, interrupted)
        try:
            run_servers(config)
        finally:
            signal.signal(signal.SIGTERM, previous)
        return 0
    except KeyboardInterrupt:
        print('\nStartup cancelled.', flush=True)
        return 130
    except (LaunchError, OSError, subprocess.SubprocessError) as error:
        message = str(error) if isinstance(error, LaunchError) else 'A runtime/process operation failed; check the installed tools and local permissions.'
        print(f'Clinic: {message}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
