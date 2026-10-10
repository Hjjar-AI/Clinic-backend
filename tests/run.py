"""Safe default entry point: python -B tests/run.py [Django test options]."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.testing'
from django.core.management import execute_from_command_line

if __name__ == '__main__':
    if any(arg.startswith('--settings') for arg in sys.argv[1:]):
        raise SystemExit('This runner only accepts isolated test settings.')
    execute_from_command_line(['manage.py', 'test', 'tests', '--noinput', *sys.argv[1:]])
