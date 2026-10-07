import magic
import zipfile
import olefile
import io
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
    mime = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)
    allowed = allowed_mime_types or ALLOWED_MIME_TYPES
    if mime not in allowed:
        raise ValidationError(f'Unsupported file type: {mime}')

def detect_macros(file):
    file.seek(0)
    data = file.read()
    file.seek(0)
    if data[:4] == b'PK\x03\x04':  # ZIP-based (xlsx, docx)
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for name in zf.namelist():
                    if 'vbaProject.bin' in name:
                        raise ValidationError('Macros detected in file')
        except zipfile.BadZipFile:
            pass
    elif olefile.isOleFile(io.BytesIO(data)):
        ole = olefile.OleFileIO(io.BytesIO(data))
        if ole.exists('VBAProject') or ole.exists('_VBA_PROJECT'):
            ole.close()
            raise ValidationError('Macros detected in file')
        ole.close()

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
    if not filename.endswith(('.csv', '.xls', '.xlsx')):
        raise ValidationError('Unsupported spreadsheet extension')
    validate_mime(file, SPREADSHEET_MIME_TYPES)
    detect_macros(file)
