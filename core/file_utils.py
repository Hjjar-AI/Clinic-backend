# backend/core/file_utils.py
import os
import re
import uuid
import hashlib

import magic
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


# Item #7: derive the stored extension from the validated MIME type, not the
# client-supplied filename. The previous code took whatever extension the
# uploader put in file.name, which allowed a file whose content is a PNG but
# whose name is "evil.html" to be stored and served with a .html extension.
MIME_TO_EXT = {
    'image/png': '.png',
    'image/jpeg': '.jpg',
    'image/gif': '.gif',
    'application/pdf': '.pdf',
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    'application/vnd.ms-excel': '.xls',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
}

# Fallback: only accept short, alphanumeric extensions if MIME detection fails
# (e.g., unknown but not rejected by validate_upload). This path should be rare
# because validate_upload already rejects unknown MIME types at the view layer.
_SAFE_EXT_RE = re.compile(r'^\.[A-Za-z0-9]{1,10}$')


def _resolve_extension(file):
    file.seek(0)
    mime = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)

    ext = MIME_TO_EXT.get(mime)
    if ext:
        return ext

    original_ext = os.path.splitext(file.name or '')[1].lower()
    if original_ext and _SAFE_EXT_RE.match(original_ext):
        return original_ext

    return ''


def save_uploaded_file(file, directory, prefix_id):
    """
    Save an uploaded file to the default storage under the given directory.
    The stored extension is derived from the detected MIME type, with a
    sanitized fallback to the client filename extension.
    Returns the stored file path.
    """
    ext = _resolve_extension(file)
    unique_name = f'{prefix_id}_{uuid.uuid4().hex}{ext}'
    content = file.read()
    file.verified_size = len(content)
    file.verified_checksum = hashlib.sha256(content).hexdigest()
    file.seek(0)
    path = default_storage.save(f'{directory}/{unique_name}', ContentFile(content))
    return path