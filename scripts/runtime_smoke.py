"""Start/check/stop a synthetic HTTP process; never prepares a database."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    command = [str(args.executable.resolve())] if args.executable else [sys.executable, '-B', str(root / 'scripts' / 'clinic_entry.py')]
    env = {**os.environ, 'PYTHONPATH': str(root)}
    if args.executable:
        # Do not accidentally pass runner-installed native paths to the bundle.
        for name in ('CLINIC_DLL_DIRECTORIES', 'WEASYPRINT_DLL_DIRECTORIES', 'LIBMAGIC_DATABASE', 'FONTCONFIG_PATH'):
            env.pop(name, None)
        if os.name == 'nt':
            env['PATH'] = os.pathsep.join([str(Path(os.environ['SystemRoot']) / 'System32'), os.environ['SystemRoot']])
    subprocess.run([*command, 'check'], env=env, cwd=tempfile.gettempdir(), check=True, timeout=90)
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    with tempfile.TemporaryFile(mode='w+b') as output:
        process = subprocess.Popen([*command, 'smoke-server', '--port', str(port)], env=env,
                                   cwd=tempfile.gettempdir(), stdout=output, stderr=output)
        try:
            address = f'http://127.0.0.1:{port}'
            deadline = time.monotonic() + 60
            while True:
                if process.poll() is not None:
                    raise RuntimeError('Synthetic server exited before readiness')
                try:
                    with urlopen(address + '/api/v1/system/config/', timeout=2) as response:
                        assert response.status == 200
                    break
                except (URLError, TimeoutError):
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Synthetic server readiness timed out')
                    time.sleep(0.2)
            try:
                urlopen(address + '/api/v1/patients/', timeout=5)
            except HTTPError as error:
                assert error.code in (401, 403), error.code
            else:
                raise AssertionError('Unauthenticated patient access was allowed')
            if args.executable:
                with urlopen(address + '/', timeout=5) as response:
                    assert b'<html' in response.read().lower(), 'Missing packaged frontend'
                with urlopen(address + '/static/static/fonts/Cairo-VariableFont_slnt,wght.ttf', timeout=5) as response:
                    assert len(response.read()) > 1000, 'Missing packaged font'
            print('PASS: native runtime/PDF, HTTP configuration, access denial and process shutdown' +
                  ('; packaged frontend/assets' if args.executable else ''))
        except BaseException:
            output.seek(0)
            print(output.read().decode('utf-8', errors='replace'), file=sys.stderr)
            raise
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        with socket.socket() as probe:
            probe.settimeout(2)
            assert probe.connect_ex(('127.0.0.1', port)) != 0, 'Server port remained open'


if __name__ == '__main__':
    main()
