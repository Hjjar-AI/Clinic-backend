import io
import json
import zipfile
import hashlib
from django.apps import apps
from django.core import serializers
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone
from .backup_validation import BackupValidationService, payload_bytes


def backup_models():
    labels = {'core', 'auth', 'contenttypes', 'admin'} | {
        config.label for config in apps.get_app_configs() if config.name.startswith('apps.')
    }
    return sorted([model for model in apps.get_models() if model._meta.app_label in labels
                   and model._meta.managed and model.__name__ != 'IdempotencyOperation'],
                  key=lambda model: model._meta.label_lower)


def media_paths(directory=''):
    if directory and ('..' in directory.split('/') or directory.startswith('/')):
        raise ValueError('Invalid media path')
    try:
        directories, files = default_storage.listdir(directory)
    except FileNotFoundError:
        return
    for filename in sorted(files):
        yield '/'.join(filter(None, [directory, filename]))
    for name in sorted(directories):
        yield from media_paths('/'.join(filter(None, [directory, name])))


class BackupCreatorService:
    def _data(self):
        models = backup_models()
        # PostgreSQL uses one repeatable-read snapshot for the entire inventory.
        # Set isolation before this transaction's first query.
        from django.db import connection
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        records, counts = [], {}
        for model in models:
            rows = list(model._base_manager.order_by('pk'))
            records.extend(json.loads(serializers.serialize('json', rows)))
            counts[model._meta.label_lower] = len(rows)
        return {'metadata': {'created_at': timezone.now().isoformat(), 'format_version': 2,
                             'schema': 'complete-records', 'counts': counts,
                             'includes': sorted(counts)}, 'records': records}

    def _json_backup(self):
        data = self._data()
        signature = BackupValidationService()._sign_data(payload_bytes(data))
        return json.dumps({'signature': signature, 'data': data}, ensure_ascii=False, allow_nan=False)

    @transaction.atomic
    def create_json_backup(self):
        return self._json_backup()

    @transaction.atomic
    def create_full_backup(self):
        buffer = io.BytesIO()
        members = {'backup.json': self._json_backup().encode()}
        for path in media_paths():
            with default_storage.open(path, 'rb') as file:
                members['media/' + path] = file.read()
        manifest = {'format_version': 2, 'members': {
            name: {'sha256': hashlib.sha256(value).hexdigest(), 'size': len(value)}
            for name, value in members.items()}}
        raw_manifest = payload_bytes(manifest)
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, value in members.items():
                archive.writestr(name, value)
            archive.writestr('manifest.json', raw_manifest)
            archive.writestr('signature.txt', BackupValidationService()._sign_data(raw_manifest))
        buffer.seek(0)
        return buffer
