#!/usr/bin/env python
import os
import sys

def main():
    # Load the local environment before selecting settings. Shell/CLI overrides
    # retain precedence; this does not initialize, seed or migrate a database.
    from pathlib import Path
    from dotenv import load_dotenv

    settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', '')
    for index, argument in enumerate(sys.argv[1:], start=1):
        if argument.startswith('--settings='):
            settings_module = argument.split('=', 1)[1]
        elif argument == '--settings' and index + 1 < len(sys.argv):
            settings_module = sys.argv[index + 1]
    # Isolated test settings intentionally exclude clinic environment/secrets.
    if settings_module != 'config.settings.testing':
        load_dotenv(Path(__file__).resolve().parent / '.env', override=False)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()