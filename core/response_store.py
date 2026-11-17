"""Receipts reference exact file bytes; authoritative issued documents stay in DB."""
import hashlib
import os
import re
import tempfile
from pathlib import Path
from django.conf import settings
from django.http import HttpResponse

REFERENCE = '_clinic_body_reference_v1'
HEADERS = {'content-type', 'content-disposition', 'location', 'cache-control',
    'x-backup-sha256', 'x-backup-type', 'x-resource-version', 'x-document-checksum'}


class ResultUnavailable(Exception):
    pass


def artifact_directory():
    return Path(getattr(settings, 'OPERATION_RESPONSE_DIR', None) or Path(settings.BACKUP_DIR) / 'operation-responses')


def store_response(response):
    headers = {name: value for name, value in response.items() if name.lower() in HEADERS}
    reference = getattr(response, '_receipt_reference', None)
    binary = 'attachment' in response.get('Content-Disposition', '') or not response.get('Content-Type', '').startswith('application/json')
    if reference:
        headers[REFERENCE] = reference
        return b'', headers
    if binary and response.content:
        digest = hashlib.sha256(response.content).hexdigest()
        directory = artifact_directory()
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = directory / digest
        if target.is_symlink():
            raise RuntimeError('Response artifact must not be a symlink')
        # Publish atomically. Concurrent writers of identical bytes share one name.
        fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=directory)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(response.content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
        headers[REFERENCE] = {'kind': 'artifact', 'checksum': digest}
        return b'', headers
    return response.content, headers


def replay_response(operation):
    headers = dict(operation.response_headers)
    reference = headers.pop(REFERENCE, None)
    if reference:
        digest = reference.get('checksum', '')
        if not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ResultUnavailable()
        if reference.get('kind') == 'issued_document':
            from apps.prescriptions.models import IssuedDocument
            document = IssuedDocument.objects.filter(pk=reference.get('id'), checksum=digest).first()
            if document is None:
                raise ResultUnavailable()
            body = bytes(document.pdf_data)
        elif reference.get('kind') == 'artifact':
            path = artifact_directory() / digest
            try:
                if path.is_symlink():
                    raise ResultUnavailable()
                body = path.read_bytes()
            except OSError as exc:
                raise ResultUnavailable() from exc
        else:
            raise ResultUnavailable()
        if hashlib.sha256(body).hexdigest() != digest:
            raise ResultUnavailable()
    else:
        # Existing buffered receipts remain readable without converting stored data.
        body = bytes(operation.response_body)
    return HttpResponse(body, status=operation.response_status, headers=headers)


def cleanup_artifacts(now):
    """Caller holds the exclusive operation gate, including across file removal."""
    from .models import IdempotencyOperation
    live = set()
    for headers in IdempotencyOperation.objects.values_list('response_headers', flat=True).iterator():
        ref = headers.get(REFERENCE, {})
        if ref.get('kind') == 'artifact':
            live.add(ref.get('checksum'))
    directory = artifact_directory()
    if not directory.exists():
        return
    cutoff = now.timestamp() - 30 * 86400
    for path in directory.iterdir():
        if (re.fullmatch(r'[0-9a-f]{64}', path.name) or path.name.startswith('.pending-')) and path.name not in live:
            if not path.is_symlink() and path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
