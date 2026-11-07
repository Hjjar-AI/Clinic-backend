"""Subprocess checkpoints for SIGKILL tests; accepts owned test storage only.

Invoked by test_worker_termination, never a production management command.
"""
import json
import os
from pathlib import Path
import sys
import tempfile


def main():
    payload = json.loads(sys.stdin.readline())
    if os.environ.get('DJANGO_SETTINGS_MODULE') != 'tests.postgres_settings':
        raise RuntimeError('Worker termination checks require the owned PostgreSQL test settings')
    if payload['database'] != 'test_clinic_suite':
        raise RuntimeError('Refusing a database outside the disposable test suite')
    workspace = Path(payload['workspace']).resolve()
    if workspace.parent != Path('/tmp') or not workspace.name.startswith('clinic-case-'):
        raise RuntimeError('Refusing storage outside the disposable test case')
    # SIGKILL skips atexit. Keep even settings/import temporary files inside
    # the parent's owned case directory so its cleanup removes them afterward.
    tempfile.tempdir = str(workspace)

    from django.conf import settings
    settings.DATABASES['default']['NAME'] = payload['database']
    import django
    django.setup()
    from django.test import override_settings
    with override_settings(MEDIA_ROOT=workspace / 'media', BACKUP_DIR=workspace / 'backups'):
        run(payload)


def run(payload):
    from unittest.mock import patch
    from django.core.files.storage import default_storage
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.db import connection
    from django.db.models.query import QuerySet
    from rest_framework.test import APIClient
    from apps.backup.backup_restore import BackupRestoreService
    from core.models import IdempotencyOperation, RecoveryOperation

    client = APIClient()
    client.cookies.load(payload['cookies'])

    def checkpoint(**values):
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_backend_pid()')
            pid = cursor.fetchone()[0]
        print(json.dumps({'checkpoint': payload['stage'], 'backend_pid': pid, **values}), flush=True)
        # The parent sends SIGKILL here: no finally/exception/rollback handler runs.
        if not sys.stdin.readline():
            raise RuntimeError('Synthetic parent disconnected before terminating its worker')
        raise RuntimeError('Synthetic worker must be killed at the checkpoint')

    if payload['kind'] == 'invoice':
        original_update = QuerySet.update

        def update(queryset, **values):
            result = original_update(queryset, **values)
            if payload['stage'] == 'before_commit' and queryset.model is IdempotencyOperation and 'response_body' in values:
                checkpoint()
            return result

        with patch.object(QuerySet, 'update', update):
            response = client.post('/api/v1/billing/', payload['data'], format='json', HTTP_X_IDEMPOTENCY_KEY=payload['key'])
        if response.status_code != 201:
            raise RuntimeError(f'Synthetic invoice worker returned {response.status_code}')
        checkpoint(response=response.content.decode(), content_type=response['Content-Type'])
        return

    backup_path = Path(payload['backup']).resolve()
    if backup_path.parent != Path(payload['workspace']).resolve():
        raise RuntimeError('Refusing backup outside the disposable test case')
    backup = backup_path.read_bytes()

    def upload():
        return SimpleUploadedFile('synthetic.zip', backup, 'application/zip')

    preview = client.post('/api/v1/backup/restore/preview/', {'backup_file': upload()},
        HTTP_X_IDEMPOTENCY_KEY='synthetic-killed-worker-preview')
    if preview.status_code != 200:
        raise RuntimeError(f'Synthetic preview returned {preview.status_code}')
    token = preview.json()['data']['preview_token']
    original_save = default_storage.save
    original_update = QuerySet.update
    original_restore = BackupRestoreService.execute_restore

    def save(name, *args, **kwargs):
        result = original_save(name, *args, **kwargs)
        if payload['stage'] == 'after_media' and name == payload['media_path']:
            checkpoint(preview_token=token)
        return result

    def update(queryset, **values):
        result = original_update(queryset, **values)
        if payload['stage'] == 'before_commit' and queryset.model is RecoveryOperation and values.get('state') == 'completed':
            checkpoint(preview_token=token)
        return result

    def restore(service, *args, **kwargs):
        result = original_restore(service, *args, **kwargs)
        if payload['stage'] == 'after_commit':
            checkpoint(preview_token=token)
        return result

    with patch.object(default_storage, 'save', save), patch.object(QuerySet, 'update', update), patch.object(BackupRestoreService, 'execute_restore', restore):
        response = client.post('/api/v1/backup/restore/execute/', {
            'backup_file': upload(), 'confirm_clear': 'true',
            'confirmation_phrase': 'RESTORE CLINIC', 'preview_token': token,
        }, HTTP_X_IDEMPOTENCY_KEY=payload['key'])
    raise RuntimeError(f'Synthetic recovery did not reach its checkpoint ({response.status_code})')


if __name__ == '__main__':
    main()
