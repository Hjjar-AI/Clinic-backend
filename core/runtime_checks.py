"""Database-free checks for the native/runtime pieces shared by OS profiles."""
from importlib import metadata
from pathlib import Path
from tempfile import TemporaryDirectory


def probe_file_locks():
    import portalocker
    from contextlib import contextmanager
    from core.operation_gate import file_lock_backend
    locker = file_lock_backend()
    shared = portalocker.LOCK_SH | portalocker.LOCK_NB
    exclusive = portalocker.LOCK_EX | portalocker.LOCK_NB
    with TemporaryDirectory(prefix='clinic-lock-check-') as directory:
        filename = Path(directory) / 'gate.lock'

        @contextmanager
        def held(flags):
            with filename.open('a+b') as handle:
                locker.lock(handle, flags)
                try:
                    yield
                finally:
                    locker.unlock(handle)

        with held(shared), held(shared):
            try:
                with held(exclusive):
                    raise RuntimeError('Exclusive lock entered while readers held the gate')
            except portalocker.exceptions.AlreadyLocked:
                pass
        with held(exclusive):
            pass


def runtime_report(render_pdf=False):
    """No DB queries, schema operations, settings writes or clinical file reads."""
    from django.conf import settings
    from core.native_dependencies import detect_mime, pdf_libraries
    from core.pdf_utils import document_font_css, render_pdf_from_html
    results = []

    def run(name, probe, hint):
        try:
            detail = probe()
            results.append((name, True, str(detail or 'OK')))
        except Exception as exc:
            # Native errors may include local paths; expose only their type and remedy.
            results.append((name, False, f'{type(exc).__name__}: {hint}'))

    run('file locks', probe_file_locks,
        'Install requirements; Windows shared locks need portalocker[win32]. Use a filesystem supporting shared/exclusive locks.')
    def wsgi_server():
        from waitress import serve
        if not callable(serve):
            raise RuntimeError('Waitress WSGI entry point is unavailable')
        return metadata.version('waitress')
    run('WSGI server', wsgi_server, 'Install waitress from requirements.txt.')

    def mime():
        if detect_mime(b'%PDF-1.4\n% runtime probe\n') != 'application/pdf':
            raise RuntimeError('libmagic could not identify a PDF header')
        return metadata.version('python-magic')
    run('MIME detection', mime,
        'Install python-magic and native libmagic; Windows DLLs must match Python architecture. Configure CLINIC_DLL_DIRECTORIES and LIBMAGIC_DATABASE.')

    def fonts():
        _, _, FontConfiguration = pdf_libraries()
        FontConfiguration()
        document_font_css()
        return metadata.version('weasyprint')
    run('PDF libraries/fonts', fonts,
        'Install pinned WeasyPrint, Pango and bundled Cairo/Inter fonts. Check WEASYPRINT_DLL_DIRECTORIES and PDF_FONT_DIR.')

    def timezone_data():
        from zoneinfo import ZoneInfo
        ZoneInfo(settings.TIME_ZONE)
        return settings.TIME_ZONE
    run('time zone', timezone_data, 'Install tzdata and check TIME_ZONE.')
    if render_pdf:
        def render():
            result = render_pdf_from_html('<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><p>فحص الطباعة · Runtime check 123</p></html>')
            if not isinstance(result, bytes) or not result.startswith(b'%PDF-'):
                raise RuntimeError('PDF renderer did not produce a PDF')
            return 'Synthetic Arabic/Latin PDF rendered in memory'
        run('PDF render', render, 'Run the PDF libraries/fonts checks and inspect native renderer installation.')
    return results
