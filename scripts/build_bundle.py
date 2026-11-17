"""Build an allowlisted, one-folder executable from two checked-out repositories."""
import argparse
from importlib import metadata
from importlib.util import find_spec
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory


def revision(directory):
    return subprocess.check_output(['git', '-C', str(directory), 'rev-parse', 'HEAD'], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frontend', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    frontend = args.frontend.resolve()
    output = args.output.resolve()
    if not (frontend / 'dist' / 'index.html').is_file():
        parser.error('Build the selected frontend first; dist/index.html is required.')
    if output.exists():
        parser.error('Output must be a new directory; existing files are never replaced.')
    if platform.machine().lower() not in ('amd64', 'x86_64'):
        parser.error('The initial release recipe supports x64 only.')
    for module in ('PyInstaller', 'psycopg', 'psycopg_binary', 'redis', 'tzdata'):
        if find_spec(module) is None:
            parser.error(f'Missing build/runtime dependency: {module}; install the workflow tooling first.')
    with TemporaryDirectory(prefix='clinic-package-') as workspace:
        stage = Path(workspace) / 'source'
        stage.mkdir()
        def ignored(directory, names):
            return [name for name in names if name.startswith('.') or name in ('migrations', 'tests', '__pycache__')
                    or (not (Path(directory) / name).is_dir() and not name.endswith('.py'))]
        for name in ('apps', 'core', 'config'):
            shutil.copytree(root / name, stage / name, ignore=ignored)
        shutil.copy2(root / 'scripts' / 'clinic_entry.py', stage / 'clinic_entry.py')
        resources = stage / 'resources'
        shutil.copytree(root / 'templates', resources / 'templates')
        shutil.copytree(frontend / 'dist', resources / 'frontend')
        # Build outputs are public assets; reject accidentally copied configuration.
        if any(path.name.startswith('.env') or path.suffix in ('.db', '.sqlite', '.sqlite3')
               for path in resources.rglob('*')):
            parser.error('Unexpected private configuration/database file in release resources.')
        shutil.copy2(root / 'docs' / 'bundles.md', resources / 'BUNDLE.md')
        manifest = {
            'backend_commit': revision(root), 'frontend_commit': revision(frontend),
            'platform': platform.system(), 'architecture': platform.machine(),
            'python': platform.python_version(),
            'dependencies': {item.metadata['Name']: item.version for item in metadata.distributions()},
        }
        (resources / 'build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        native = None
        if os.name == 'nt':
            configured = os.environ.get('CLINIC_NATIVE_ROOT')
            if not configured:
                parser.error('CLINIC_NATIVE_ROOT must identify the prepared MSYS2 UCRT64 prefix.')
            native = stage / 'native'
            prefix = Path(configured)
            (native / 'bin').mkdir(parents=True)
            for filename in (prefix / 'bin').glob('*.dll'):
                shutil.copy2(filename, native / 'bin' / filename.name)
            for name in ('share/misc', 'etc/fonts', 'share/fontconfig', 'share/licenses'):
                if (prefix / name).is_dir():
                    shutil.copytree(prefix / name, native / name)
            if not (native / 'share/misc/magic.mgc').is_file() or not (native / 'etc/fonts/fonts.conf').is_file():
                parser.error('MSYS2 MIME/fontconfig resources are incomplete.')
        # Enumerate only the clean staging tree, which contains no local schema,
        # clinic environment, suite files, media, databases or backups.
        modules = []
        for package in ('apps', 'core', 'config'):
            for filename in (stage / package).rglob('*.py'):
                parts = list(filename.relative_to(stage).with_suffix('').parts)
                if parts[-1] == '__init__':
                    parts.pop()
                # Test settings are source-only; no suite is shipped.
                if parts != ['config', 'settings', 'testing']:
                    modules.append('.'.join(parts))
        spec = stage / 'Clinic.spec'
        spec.write_text('''from PyInstaller.utils.hooks import collect_submodules, collect_data_files, copy_metadata
hidden = MODULES
datas = [(RESOURCES, 'resources')]
for package in ('rest_framework', 'corsheaders', 'whitenoise', 'phonenumber_field', 'weasyprint', 'magic', 'psycopg', 'redis', 'tzdata'):
    hidden += collect_submodules(package)
    datas += collect_data_files(package)
for distribution in ('waitress', 'python-magic', 'weasyprint', 'tzdata'):
    datas += copy_metadata(distribution)
if NATIVE:
    datas.append((NATIVE, 'native'))
a = Analysis(['clinic_entry.py'], pathex=[STAGE], datas=datas, hiddenimports=hidden,
             excludes=['tests', 'pytest', 'tkinter', 'config.settings.testing'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Clinic', console=True)
collection = COLLECT(exe, a.binaries, a.datas, name='Clinic')
'''.replace('MODULES', repr(sorted(set(modules))))
            .replace('RESOURCES', repr(str(resources)))
            .replace('NATIVE', repr(str(native)) if native else 'None')
            .replace('STAGE', repr(str(stage))))
        environment = {**os.environ, 'DJANGO_SETTINGS_MODULE': 'config.settings.bundle_check',
                       'PYTHONPATH': os.pathsep.join(filter(None, [str(stage), os.environ.get('PYTHONPATH')]))}
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
                        '--distpath', str(output), '--workpath', str(Path(workspace) / 'work'), str(spec)],
                       cwd=stage, env=environment, check=True)
        shutil.copy2(resources / 'BUNDLE.md', output / 'Clinic' / 'BUNDLE.md')
        shutil.copy2(resources / 'build-manifest.json', output / 'Clinic' / 'build-manifest.json')
    print(f'Bundle written to {output / "Clinic"}')


if __name__ == '__main__':
    main()
