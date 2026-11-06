"""Native PDF/MIME loading without importing optional DLLs during Django setup."""
import importlib
import os
import threading
from pathlib import Path

_dll_handles = {}
_dll_lock = threading.Lock()
_magic_local = threading.local()


def configure_native_libraries():
    """Keep Windows DLL-directory handles alive for the process lifetime."""
    if os.name != 'nt':
        return
    directories = []
    for variable in ('CLINIC_DLL_DIRECTORIES', 'WEASYPRINT_DLL_DIRECTORIES'):
        directories.extend(value.strip() for value in os.environ.get(variable, '').split(os.pathsep) if value.strip())
    with _dll_lock:
        for value in directories:
            directory = str(Path(value).expanduser().resolve())
            key = os.path.normcase(directory)
            if key not in _dll_handles:
                if not Path(directory).is_dir():
                    raise RuntimeError('A configured native DLL directory does not exist; check CLINIC_DLL_DIRECTORIES / WEASYPRINT_DLL_DIRECTORIES.')
                _dll_handles[key] = os.add_dll_directory(directory)
                # python-magic locates DLLs through ctypes.find_library/PATH.
                # add_dll_directory alone only handles loading their dependencies.
                current_path = os.environ.get('PATH', '')
                os.environ['PATH'] = directory + (os.pathsep + current_path if current_path else '')


def detect_mime(content):
    configure_native_libraries()
    magic = importlib.import_module('magic')
    database = os.environ.get('LIBMAGIC_DATABASE', '').strip()
    if not database:
        return magic.from_buffer(content, mime=True)
    if not Path(database).is_file():
        raise RuntimeError('LIBMAGIC_DATABASE must name an existing magic.mgc database.')
    # libmagic handles are not thread-safe; Waitress threads need separate instances.
    if getattr(_magic_local, 'database', None) != database:
        _magic_local.detector = magic.Magic(mime=True, magic_file=database)
        _magic_local.database = database
    return _magic_local.detector.from_buffer(content)


def pdf_libraries():
    configure_native_libraries()
    weasyprint = importlib.import_module('weasyprint')
    fonts = importlib.import_module('weasyprint.text.fonts')
    return weasyprint.HTML, weasyprint.CSS, fonts.FontConfiguration
