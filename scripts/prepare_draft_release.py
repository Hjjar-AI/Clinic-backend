"""Validate two verified bundles and an existing tag; write reviewable release notes."""
import argparse
import json
from pathlib import Path
import re
import subprocess

from verify_archive import verify_checksum


def prepare(directory, backend_sha, tag, run_id, repository, notes):
    if not re.fullmatch(r'[0-9a-f]{40}', backend_sha) or not re.fullmatch(r'[1-9][0-9]*', run_id):
        raise ValueError('Expected an exact backend SHA and positive bundle run ID')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*', tag):
        raise ValueError('Tag must start with a letter or digit and use letters, digits, dots, dashes, slashes or underscores')
    subprocess.run(['git', 'check-ref-format', f'refs/tags/{tag}'], check=True)
    tagged = subprocess.check_output(['git', 'rev-parse', '--verify', f'refs/tags/{tag}^{{commit}}'], text=True).strip()
    if tagged != backend_sha:
        raise ValueError('The existing tag must point to the verified backend commit')
    reports = []
    for system, suffix in (('Linux', '.tar.gz'), ('Windows', '.zip')):
        report = json.loads((directory / f'verification-{system}.json').read_text())
        expected_name = f'Clinic-{system}-x64{suffix}'
        if (report.get('platform') != system or report.get('backend_commit') != backend_sha
                or report.get('archive') != expected_name or report.get('runtime_smoke') != 'passed'):
            raise ValueError('Missing or inconsistent platform verification')
        archive = directory / expected_name
        checksum = verify_checksum(archive)
        if checksum != report.get('sha256'):
            raise ValueError('Archive changed after platform verification')
        reports.append(report)
    frontend = reports[0].get('frontend_commit', '')
    if not re.fullmatch(r'[0-9a-f]{40}', frontend) or reports[1].get('frontend_commit') != frontend:
        raise ValueError('Both platform bundles must contain the same frontend revision')
    notes.write_text(
        f'Clinic Windows/Linux x64 bundles, awaiting release review.\n\n'
        f'- Backend: `{backend_sha}`\n- Frontend: `{frontend}`\n'
        f'- Bundle run: https://github.com/{repository}/actions/runs/{run_id}\n'
        '- Both downloaded archives passed checksum, provenance, native/PDF and HTTP runtime checks.\n'
        '- Full platform regression gates ran in the bundle workflow.\n'
        '- Production configuration/database/cache setup and physical printing remain separately verified.\n\n'
        'Keep the complete extracted folder together. See BUNDLE.md inside each archive for setup and limits.\n',
        encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--backend-sha', required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--notes', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.directory, args.backend_sha, args.tag, args.run_id, args.repository, args.notes)


if __name__ == '__main__':
    main()
