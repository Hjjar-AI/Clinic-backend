"""Check a downloaded bundle's checksum, provenance and extracted executable."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
import zipfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_checksum(archive):
    fields = Path(str(archive) + '.sha256').read_text().strip().split(maxsplit=1)
    if len(fields) != 2 or not re.fullmatch(r'[0-9a-f]{64}', fields[0]) or fields[1] != archive.name:
        raise ValueError('Malformed checksum or mismatched archive filename')
    if digest(archive) != fields[0]:
        raise ValueError('Archive checksum mismatch')
    return fields[0]


def extract(archive, destination):
    if archive.name.endswith('.tar.gz'):
        with tarfile.open(archive, 'r:gz') as bundle:
            bundle.extractall(destination, filter='data')
    elif archive.suffix == '.zip':
        with zipfile.ZipFile(archive) as bundle:
            for item in bundle.infolist():
                path = PurePosixPath(item.filename.replace('\\', '/'))
                if path.is_absolute() or '..' in path.parts or ':' in item.filename or stat.S_ISLNK(item.external_attr >> 16):
                    raise ValueError('Unsafe ZIP member')
            bundle.extractall(destination)
    else:
        raise ValueError('Expected a ZIP or tar.gz bundle')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--backend-sha', required=True)
    parser.add_argument('--frontend-sha', default='')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    for value in (args.backend_sha, args.frontend_sha):
        if value and not re.fullmatch(r'[0-9a-fA-F]{40}', value):
            parser.error('Source revisions must be full commit SHAs')
    args.backend_sha = args.backend_sha.lower()
    args.frontend_sha = args.frontend_sha.lower()
    archive = args.archive.resolve()
    checksum = verify_checksum(archive)
    with TemporaryDirectory(prefix='clinic archive check ') as workspace:
        root = Path(workspace)
        extract(archive, root)
        application = root / 'Clinic'
        manifest = json.loads((application / 'build-manifest.json').read_text())
        if manifest.get('backend_commit') != args.backend_sha:
            raise ValueError('Backend revision does not match the selected build')
        frontend = manifest.get('frontend_commit', '')
        if not re.fullmatch(r'[0-9a-f]{40}', frontend) or (args.frontend_sha and frontend != args.frontend_sha):
            raise ValueError('Frontend revision does not match the selected build')
        system = platform.system()
        if manifest.get('platform') != system or manifest.get('architecture', '').lower() not in ('amd64', 'x86_64'):
            raise ValueError('Bundle targets a different platform or architecture')
        executable = application / ('Clinic.exe' if system == 'Windows' else 'Clinic')
        if not executable.is_file() or (system != 'Windows' and not executable.stat().st_mode & stat.S_IXUSR):
            raise ValueError('Missing executable or lost executable permission')
        subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('runtime_smoke.py')),
                        '--executable', str(executable)], check=True, timeout=180)
        report = {'platform': system, 'backend_commit': args.backend_sha, 'frontend_commit': frontend,
                  'archive': archive.name, 'sha256': checksum, 'runtime_smoke': 'passed'}
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: downloaded {archive.name}, checksum, source revisions and extracted runtime')


if __name__ == '__main__':
    main()
