# backend/apps/backup/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import HttpResponse
from .backup_creator import BackupCreatorService
from .backup_restore import BackupRestoreService
from core.permissions import HasManageBackup
from core.exceptions import error_response
from core.signals import log_action
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from pathlib import Path
import hashlib
import secrets
from django.db import transaction
from django.utils.decorators import method_decorator


def _upload_digest(file):
    file.seek(0)
    digest = hashlib.sha256()
    for chunk in file.chunks():
        digest.update(chunk)
    file.seek(0)
    return digest.hexdigest()


@method_decorator(transaction.non_atomic_requests, name='dispatch')
class BackupView(APIView):
    # Item #3: use the existing HasManageBackup permission class instead of
    # calling has_perm(PERM_MANAGE_BACKUP) inline, matching every other viewset.
    permission_classes = [IsAuthenticated, HasManageBackup]
    service = BackupCreatorService()

    def post(self, request):
        backup_type = request.data.get('backup_type', 'full')
        if backup_type == 'json':
            data = self.service.create_json_backup()
            response = HttpResponse(data, content_type='application/json')
            response['Content-Disposition'] = 'attachment; filename="backup.json"'
            checksum = hashlib.sha256(data.encode('utf-8')).hexdigest()
        elif backup_type == 'full':
            buffer = self.service.create_full_backup()
            payload = buffer.getvalue()
            response = HttpResponse(payload, content_type='application/zip')
            response['Content-Disposition'] = 'attachment; filename="backup.zip"'
            checksum = hashlib.sha256(payload).hexdigest()
        else:
            return error_response(400, 'نوع النسخة غير صالح', {})
        response['X-Backup-SHA256'] = checksum
        response['X-Backup-Type'] = backup_type
        log_action(request.user.id, 'backup', 'System', 0, {
            'summary': f'Created {backup_type} backup',
            'checksum': checksum,
        })
        return response


class RestorePreviewView(APIView):
    permission_classes = [IsAuthenticated, HasManageBackup]
    parser_classes = [MultiPartParser, FormParser]
    service = BackupRestoreService()

    def post(self, request):
        file = request.FILES.get('backup_file')
        if not file:
            return error_response(400, 'الملف مطلوب', {})
        try:
            selection = {key: request.data.get('restore_' + key, 'true') == 'true' for key in ('patients','diagnoses','medications')}
            preview = self.service.preview_restore(file, **{'restore_' + key: value for key, value in selection.items()})
            token = secrets.token_urlsafe(24)
            cache.set(f'restore-preview:{token}', {
                'user_id': request.user.id,
                'digest': _upload_digest(file),
                'selection': {key: request.data.get('restore_' + key, 'true') == 'true' for key in ('patients', 'diagnoses', 'medications')},
            }, timeout=1800)
            preview['preview_token'] = token
            return Response({'data': preview})
        except ValueError as e:
            return error_response(400, str(e), {})


@method_decorator(transaction.non_atomic_requests, name='dispatch')
class RestoreExecuteView(APIView):
    permission_classes = [IsAuthenticated, HasManageBackup]
    parser_classes = [MultiPartParser, FormParser]
    service = BackupRestoreService()

    def post(self, request):
        file = request.FILES.get('backup_file')
        if not file:
            return error_response(400, 'الملف مطلوب', {})
        restore_patients = request.data.get('restore_patients', 'true') == 'true'
        restore_diagnoses = request.data.get('restore_diagnoses', 'true') == 'true'
        restore_medications = request.data.get('restore_medications', 'true') == 'true'
        confirm_clear = request.data.get('confirm_clear', 'false') == 'true'
        confirmation_phrase = request.data.get('confirmation_phrase', '')
        if not confirm_clear or confirmation_phrase != 'RESTORE CLINIC':
            return error_response(400, 'اكتب RESTORE CLINIC لتأكيد الاستعادة', {
                'confirmation_phrase': ['عبارة التأكيد غير مطابقة'],
            })
        preview_token = request.data.get('preview_token')
        preview = cache.get(f'restore-preview:{preview_token}') if preview_token else None
        if not preview or preview.get('user_id') != request.user.id:
            return error_response(400, 'يجب معاينة ملف الاستعادة أولاً', {})
        selection = {'patients': restore_patients, 'diagnoses': restore_diagnoses, 'medications': restore_medications}
        if preview.get('selection') != selection:
            return error_response(409, 'تغير نطاق الاستعادة؛ أعد المعاينة', {})
        if not any(selection.values()):
            return error_response(400, 'اختر نطاقاً للاستعادة', {})
        if preview.get('digest') != _upload_digest(file):
            return error_response(409, 'ملف الاستعادة تغير بعد المعاينة', {})
        try:
            safety_buffer = BackupCreatorService().create_full_backup()
            backup_dir = Path(settings.BACKUP_DIR)
            backup_dir.mkdir(parents=True, exist_ok=True)
            safety_name = f'safety_before_restore_{timezone.now().strftime("%Y%m%d_%H%M%S_%f")}.zip'
            (backup_dir / safety_name).write_bytes(safety_buffer.getvalue())
            self.service.execute_restore(
                file,
                restore_patients=restore_patients,
                restore_diagnoses=restore_diagnoses,
                restore_medications=restore_medications,
            )
            cache.delete(f'restore-preview:{preview_token}')
            from apps.accounts.models import User
            actor_id = request.user.id if User.objects.filter(pk=request.user.id).exists() else None
            if restore_patients:
                request.session.flush()
            log_action(actor_id, 'restore', 'System', 0, {
                'summary': 'Clinic data restored from validated backup',
                'safety_backup': safety_name,
            })
            return Response({'data': {'safety_backup': safety_name}, 'message': 'تمت الاستعادة بنجاح'})
        except ValueError as e:
            return error_response(400, str(e), {})
