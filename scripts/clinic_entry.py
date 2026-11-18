"""Frozen Clinic launcher. No schema creation, seeds, installs or upgrades."""
import argparse
import os
from pathlib import Path
import sys


def native_environment():
    if getattr(sys, 'frozen', False) and os.name == 'nt':
        native = Path(sys._MEIPASS) / 'native'
        os.environ['CLINIC_DLL_DIRECTORIES'] = str(native / 'bin')
        os.environ['WEASYPRINT_DLL_DIRECTORIES'] = str(native / 'bin')
        os.environ['LIBMAGIC_DATABASE'] = str(native / 'share' / 'misc' / 'magic.mgc')
        os.environ['FONTCONFIG_PATH'] = str(native / 'etc' / 'fonts')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['check', 'serve', 'smoke-server'], nargs='?', default='serve')
    parser.add_argument('--config', type=Path, help='External production .env file (or CLINIC_CONFIG_FILE)')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5019)
    parser.add_argument('--open-browser', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be 1–65535.')
    native_environment()
    if args.command in ('check', 'smoke-server'):
        os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.bundle_check'
    else:
        from dotenv import load_dotenv
        configured = args.config or os.environ.get('CLINIC_CONFIG_FILE')
        if not configured or not Path(configured).is_file():
            parser.error('Provide an existing external configuration using --config or CLINIC_CONFIG_FILE; see BUNDLE.md.')
        config = Path(configured).resolve()
        application = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
        if config == application or application in config.parents:
            parser.error('Configuration must live outside the application directory.')
        load_dotenv(config, override=False)
        os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.bundle'

    import django
    django.setup()
    from django.core.management import call_command
    if args.command == 'check':
        call_command('check_runtime', render_pdf=True)
        return
    if args.command == 'smoke-server' and args.host != '127.0.0.1':
        parser.error('The disposable smoke server is loopback-only.')
    if args.open_browser and args.host not in ('127.0.0.1', 'localhost'):
        parser.error('--open-browser requires a loopback host.')
    if args.open_browser:
        # Bind first, so an occupied port cannot open an unrelated application.
        from django.conf import settings
        from django.core.wsgi import get_wsgi_application
        from core.runtime_checks import runtime_report
        from waitress import create_server
        if any(not passed for _, passed, _ in runtime_report()):
            parser.error('Runtime checks failed; run Clinic check.')
        call_command('check')
        server = create_server(get_wsgi_application(), host=args.host, port=args.port,
                               max_request_body_size=settings.MAX_REQUEST_BODY_SIZE,
                               expose_tracebacks=False)
        import webbrowser
        webbrowser.open(f'http://{args.host}:{args.port}/')
        try:
            server.run()
        finally:
            server.close()
    else:
        call_command('serve', host=args.host, port=args.port)


if __name__ == '__main__':
    main()
