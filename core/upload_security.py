from core.native_dependencies import detect_mime
import zipfile
import olefile
from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_MIME_TYPES = {
    'image/png', 'image/jpeg', 'image/gif',
    'application/pdf', 'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
}

SPREADSHEET_MIME_TYPES = {
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/x-ole-storage',
    'text/csv',
    'application/csv',
    'text/plain',
}

def validate_mime(file, allowed_mime_types=None):
    file.seek(0)
    mime = detect_mime(file.read(2048))
    file.seek(0)
    allowed = allowed_mime_types or ALLOWED_MIME_TYPES
    file.verified_mime = mime
    if mime not in allowed:
        raise ValidationError(f'Unsupported file type: {mime}')

def detect_macros(file):
    file.seek(0)
    signature = file.read(4)
    file.seek(0)
    try:
        if signature == b'PK\x03\x04':
            try:
                with zipfile.ZipFile(file) as zf:
                    if any('vbaProject.bin' in name for name in zf.namelist()):
                        raise ValidationError('Macros detected in file')
            except zipfile.BadZipFile:
                pass
        elif olefile.isOleFile(file):
            file.seek(0)
            with olefile.OleFileIO(file) as ole:
                if ole.exists('VBAProject') or ole.exists('_VBA_PROJECT'):
                    raise ValidationError('Macros detected in file')
    finally:
        file.seek(0)


def validate_upload(file):
    if file.size > settings.MAX_ATTACHMENT_SIZE:
        raise ValidationError(
            f'File exceeds the {settings.MAX_ATTACHMENT_SIZE // (1024 * 1024)} MB limit'
        )
    validate_mime(file)
    detect_macros(file)


def validate_spreadsheet_upload(file):
    if file.size > settings.MAX_BULK_IMPORT_SIZE:
        raise ValidationError(
            f'File exceeds the {settings.MAX_BULK_IMPORT_SIZE // (1024 * 1024)} MB import limit'
        )
    filename = (getattr(file, 'name', '') or '').lower()
    if not filename.endswith(('.csv', '.xlsx')):
        raise ValidationError('Unsupported spreadsheet extension')
    validate_mime(file, SPREADSHEET_MIME_TYPES)
    detect_macros(file)
