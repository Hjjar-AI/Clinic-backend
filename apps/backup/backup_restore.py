import io
import json
import hashlib
import zipfile
from pathlib import PurePosixPath
from django.conf import settings
from django.core import serializers
from django.core.serializers.base import DeserializationError
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.management.color import no_style
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Value
from django.db.models.functions import Lower, Trim
from django.contrib.sessions.models import Session
from django.utils import timezone
from .backup_validation import BackupValidationService
from .backup_creator import backup_models


class BackupRestoreService:
    def _read(self, stream, require_media=True):
        try:
            return self._parse_backup(stream, require_media)
        except zipfile.BadZipFile as exc:
            raise ValueError('Corrupt backup archive') from exc

    def _parse_backup(self, stream, require_media=True):
        stream.seek(0)
        maximum = getattr(settings, 'MAX_BULK_IMPORT_SIZE', 200 * 1024 * 1024)
        raw = stream.read(maximum + 1)
        if len(raw) > maximum:
            raise ValueError('Backup exceeds upload limit')
        media = {}
        if zipfile.is_zipfile(io.BytesIO(raw)):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                infos = archive.infolist()
                if len(infos) > 100_000 or sum(info.file_size for info in infos) > maximum * 5:
                    raise ValueError('Expanded backup exceeds limit')
                names = [info.filename for info in infos]
                if len(names) != len(set(names)):
                    raise ValueError('Duplicate backup members')
                for name in names:
                    path = PurePosixPath(name)
                    if path.is_absolute() or '..' in path.parts or '\\' in name or not name:
                        raise ValueError('Unsafe backup member')
                try:
                    manifest_raw = archive.read('manifest.json')
                    signature = archive.read('signature.txt').decode().strip()
                    if not BackupValidationService().verify_signature(manifest_raw, signature):
                        raise ValueError('Backup manifest signature verification failed')
                    manifest = json.loads(manifest_raw)
                    if not isinstance(manifest, dict) or not isinstance(manifest.get('members'), dict):
                        raise ValueError('Invalid backup manifest')
                    expected = manifest['members']
                    if set(expected) != set(names) - {'manifest.json', 'signature.txt'}:
                        raise ValueError('Backup inventory mismatch')
                    for name, info in expected.items():
                        content = archive.read(name)
                        if len(content) != info['size'] or hashlib.sha256(content).hexdigest() != info['sha256']:
                            raise ValueError('Backup member checksum mismatch')
                        if name.startswith('media/'):
                            media[name[6:]] = content
                        elif name != 'backup.json':
                            raise ValueError('Unsupported backup member')
                    envelope = json.loads(archive.read('backup.json'))
                except (KeyError, UnicodeError, TypeError) as exc:
                    raise ValueError('Incomplete or invalid full backup') from exc
        else:
            try:
                envelope = json.loads(raw)
            except (ValueError, UnicodeError) as exc:
                raise ValueError('Invalid backup JSON') from exc
        data = BackupValidationService().verify_envelope(envelope)
        metadata = data.get('metadata', {})
        if not isinstance(metadata, dict):
            raise ValueError('Invalid backup metadata')
        if metadata.get('format_version') != 2 or metadata.get('schema') != 'complete-records':
            raise ValueError('Backup uses an incomplete legacy schema; full recovery is unsupported')
        models = {model._meta.label_lower: model for model in backup_models()}
        records = data.get('records')
        declared_counts = metadata.get('counts')
        if (not isinstance(records, list) or not isinstance(declared_counts, dict)
                or set(declared_counts) != set(models)
                or any(type(count) is not int or count < 0 for count in declared_counts.values())):
            raise ValueError('Backup schema does not match this installation')
        identifiers = set()
        objects = []
        try:
            for obj in serializers.deserialize('python', records):
                model = obj.object.__class__
                label = model._meta.label_lower
                key = (label, obj.object.pk)
                if label not in models or key in identifiers or type(obj.object.pk) is not int or obj.object.pk <= 0:
                    raise ValueError('Invalid or duplicate record identifier')
                identifiers.add(key)
                obj.object.clean_fields(exclude=[field.name for field in model._meta.fields if field.is_relation])
                obj.object.clean()
                if label == 'visits.visit':
                    from apps.visits.input_validation import clinical_object
                    from apps.visits.lab_validation import normalize_lab_values
                    clinical_object(obj.object.clinical_data)
                    normalize_lab_values(obj.object.lab_values)
                objects.append(obj)
        except (ValidationError, DeserializationError, TypeError, KeyError) as exc:
            raise ValueError('Backup record validation failed') from exc
        counts = {label: sum(obj.object._meta.label_lower == label for obj in objects) for label in models}
        if counts != metadata['counts']:
            raise ValueError('Backup record counts do not match inventory')
        for obj in objects:
            for field in obj.object._meta.fields:
                if field.is_relation and field.many_to_one:
                    value = getattr(obj.object, field.attname)
                    if value is not None and (field.remote_field.model._meta.label_lower, value) not in identifiers:
                        raise ValueError('Backup contains a dangling reference')
            for name, values in (obj.m2m_data or {}).items():
                related = obj.object._meta.get_field(name).remote_field.model._meta.label_lower
                if any((related, value) not in identifiers for value in values):
                    raise ValueError('Backup contains a dangling membership')
        for obj in objects:
            if obj.object._meta.label_lower in {'patients.patientdocument', 'visits.visitattachment'}:
                path = obj.object.filepath
                if not path or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts or '\\' in path:
                    raise ValueError('Invalid attachment path')
                if require_media:
                    if path in media:
                        content = media[path]
                        size, checksum = len(content), hashlib.sha256(content).hexdigest()
                    elif default_storage.exists(path):
                        size, digest = 0, hashlib.sha256()
                        with default_storage.open(path, 'rb') as stored:
                            for chunk in stored.chunks():
                                size += len(chunk)
                                digest.update(chunk)
                        checksum = digest.hexdigest()
                    else:
                        raise ValueError('Backup references missing files; use a complete ZIP backup with media')
                    if size != obj.object.file_size or checksum != obj.object.checksum:
                        raise ValueError('Attachment metadata does not match file content')
        return data, objects, media

    def _verify_backup(self, stream):
        self._read(stream)
        stream.seek(0)

    def preview_restore(self, stream, restore_patients=True, restore_diagnoses=True, restore_medications=True):
        if restore_patients and not (restore_diagnoses and restore_medications):
            raise ValueError('Patient recovery requires the complete related dataset')
        if not any((restore_patients, restore_diagnoses, restore_medications)):
            raise ValueError('Select a restore scope')
        data, objects, media = self._read(stream, require_media=restore_patients)
        counts = data['metadata']['counts']
        return {'patients_count': counts.get('patients.patient', 0),
                'visits_count': counts.get('visits.visit', 0),
                'diagnoses_count': counts.get('clinical.diagnosisoption', 0),
                'medications_count': counts.get('clinical.medicationoption', 0),
                'media_files_count': len(media), 'created_at': data['metadata']['created_at'],
                'format_version': 2, 'compatible': True, 'counts': counts,
                'will_replace': sorted(counts) if restore_patients else [],
                'will_merge': ([] if restore_patients else
                    (['clinical.diagnosisoption'] if restore_diagnoses else []) +
                    (['clinical.medicationoption'] if restore_medications else [])),
                'restores_media': restore_patients and bool(media),
                'sessions_will_be_revoked': restore_patients}

    def execute_restore(self, stream, restore_patients=True, restore_diagnoses=True, restore_medications=True):
        if not any((restore_patients, restore_diagnoses, restore_medications)):
            raise ValueError('Select a restore scope')
        data, objects, media = self._read(stream, require_media=restore_patients)
        full = restore_patients and restore_diagnoses and restore_medications
        if restore_patients and not full:
            raise ValueError('Patient recovery requires the complete related dataset')
        if not full:
            # Catalog-only recovery preserves IDs and existing historical references.
            selected = set()
            if restore_diagnoses:
                selected.add('clinical.diagnosisoption')
            if restore_medications:
                selected.add('clinical.medicationoption')
            with transaction.atomic():
                for obj in objects:
                    if obj.object._meta.label_lower not in selected:
                        continue
                    model = obj.object.__class__
                    values = {f.name: getattr(obj.object, f.attname) for f in model._meta.fields if not f.primary_key}
                    if model._meta.model_name == 'diagnosisoption':
                        lookup = {'code': values.pop('code')}
                    else:
                        lookup = {key: values.pop(key) for key in ('generic_english', 'dosage', 'brand_english')}
                    values.pop('version', None)
                    values['archived_by'] = None
                    queryset = model._base_manager.select_for_update()
                    if model._meta.model_name == 'medicationoption':
                        # Match the same database Lower/Trim identity as the unique constraint.
                        for index, (key, value) in enumerate(lookup.items()):
                            alias = f'identity_{index}'
                            queryset = queryset.alias(**{alias: Lower(Trim(key))}).filter(
                                **{alias: Lower(Trim(Value(value)))})
                    else:
                        queryset = queryset.filter(**lookup)
                    existing = queryset.first()
                    if existing:
                        for key, value in values.items(): setattr(existing, key, value)
                        existing.version += 1
                        existing.full_clean()
                        existing.save()
                    else:
                        restored = model(**lookup, **values)
                        restored.full_clean()
                        restored.save()
            return True
        # Restore media with compensation if database loading fails. Existing unrelated
        # files are retained; no whole-directory deletion is needed for recovery.
        previous, written = {}, []
        try:
            for path, content in media.items():
                if default_storage.exists(path):
                    with default_storage.open(path, 'rb') as old:
                        previous[path] = old.read()
                    default_storage.delete(path)
                saved = default_storage.save(path, ContentFile(content))
                written.append(saved)
                if saved != path:
                    raise ValueError('Storage changed a restored file path')
            with connection.constraint_checks_disabled(), transaction.atomic():
                from core.models import IdempotencyOperation
                IdempotencyOperation.objects.all()._raw_delete('default')
                models = backup_models()
                for model in models:
                    for field in model._meta.local_many_to_many:
                        field.remote_field.through._base_manager.all()._raw_delete('default')
                # Only this validated full-recovery path bypasses PROTECT/immutable guards.
                for model in reversed(models):
                    model._base_manager.all()._raw_delete('default')
                memberships = [(obj, obj.m2m_data) for obj in objects]
                for obj in objects:
                    obj.save(save_m2m=False)
                for obj, memberships_data in memberships:
                    if memberships_data:
                        for name, values in memberships_data.items():
                            getattr(obj.object, name).set(values)
                connection.check_constraints()
                with connection.cursor() as cursor:
                    for sql in connection.ops.sequence_reset_sql(no_style(), models):
                        cursor.execute(sql)
                Session.objects.all().delete()
                from core.cache_utils import invalidate_group
                for group in ('settings', 'dashboard', 'reports', 'context', 'context_users', 'context_doctors', 'context_appointments', 'context_patients', 'tasks', 'patients', 'visits'):
                    invalidate_group(group)
        except Exception:
            for path in written:
                default_storage.delete(path)
            for path, content in previous.items():
                default_storage.save(path, ContentFile(content))
            raise
        return True
