# backend/apps/import_export/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.exceptions import ValidationError
from .services import BulkImportService, OptionsImportService
from apps.accounts.models import User
from core.permissions import (
    PERM_IMPORT_DATA,
    PERM_MANAGE_OPTIONS,
    HasImportData,
    HasManageOptions,
)
from core.exceptions import error_response
from core.upload_security import validate_spreadsheet_upload
from django.core.cache import cache
import hashlib
import secrets
import csv
from django.http import HttpResponse
from core.signals import log_action


def _file_digest(file):
    file.seek(0)
    digest = hashlib.sha256()
    for chunk in file.chunks():
        digest.update(chunk)
    file.seek(0)
    return digest.hexdigest()


def _resolve_import_doctor(request):
    raw_doctor_id = request.data.get('doctor_id') or request.user.id
    try:
        doctor_id = int(raw_doctor_id)
    except (TypeError, ValueError):
        return None, error_response(400, 'الطبيب غير صالح', {})

    doctor = User.objects.filter(
        id=doctor_id,
        role__in=['doctor', 'admin'],
        is_active=True,
    ).first()
    if not doctor:
        return None, error_response(400, 'الطبيب غير صالح', {})
    if request.user.role == 'doctor' and doctor_id != request.user.id:
        return None, error_response(403, 'غير مصرح', {})
    if request.user.role not in ['admin', 'doctor']:
        return None, error_response(403, 'غير مصرح', {})
    return doctor_id, None


class BulkImportView(APIView):
    permission_classes = [IsAuthenticated, HasImportData]
    parser_classes = [MultiPartParser, FormParser]
    service = BulkImportService()

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return error_response(400, 'الملف مطلوب', {})
        # Item #6: run the same MIME + macro validation used for patient
        # documents before handing the file to pandas. Previously bulk import
        # bypassed validate_upload() entirely.
        try:
            validate_spreadsheet_upload(file)
        except ValidationError as e:
            return error_response(400, str(e), {})
        doctor_id, doctor_error = _resolve_import_doctor(request)
        if doctor_error:
            return doctor_error
        preview_token = request.data.get('preview_token')
        preview = cache.get(f'import-preview:{preview_token}') if preview_token else None
        if not preview:
            return error_response(400, 'يجب تنفيذ معاينة حديثة قبل الاستيراد', {
                'preview_token': ['المعاينة مطلوبة أو انتهت صلاحيتها'],
            })
        if preview.get('user_id') != request.user.id or preview.get('doctor_id') != doctor_id:
            return error_response(403, 'المعاينة لا تخص هذا المستخدم أو الطبيب', {})
        if preview.get('digest') != _file_digest(file):
            return error_response(409, 'الملف تغير بعد المعاينة. أعد المعاينة.', {})
        try:
            results = self.service.import_patients(file, doctor_id, request.user.id)
        except (ValueError, UnicodeError):
            return error_response(400, 'تعذر قراءة الملف أو أن صيغته غير صالحة', {})
        cache.delete(f'import-preview:{preview_token}')
        log_action(request.user.id, 'import', 'Patient', 0, {
            'summary': f'Patient import: {results.get("added", 0)} created, {results.get("skipped", 0)} skipped',
            'counts': {key: results.get(key, 0) for key in ('added', 'skipped', 'failed')},
        })
        return Response({'data': results})


class BulkImportPreviewView(APIView):
    permission_classes = [IsAuthenticated, HasImportData]
    parser_classes = [MultiPartParser, FormParser]
    service = BulkImportService()

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return error_response(400, 'الملف مطلوب', {})
        try:
            validate_spreadsheet_upload(file)
        except ValidationError as e:
            return error_response(400, str(e), {})

        doctor_id, doctor_error = _resolve_import_doctor(request)
        if doctor_error:
            return doctor_error
        try:
            results = self.service.preview_patients(file, doctor_id, request.user.id)
        except (ValueError, UnicodeError):
            return error_response(400, 'تعذر قراءة الملف أو أن صيغته غير صالحة', {})
        token = secrets.token_urlsafe(24)
        cache.set(f'import-preview:{token}', {
            'user_id': request.user.id,
            'doctor_id': doctor_id,
            'digest': _file_digest(file),
        }, timeout=1800)
        results['preview_token'] = token
        return Response({'data': results})


class BulkImportTemplateView(APIView):
    permission_classes = [IsAuthenticated, HasImportData]
    VERSION = '1'
    HEADERS = [
        'الاسم الأول', 'اسم الأب', 'اللقب', 'اسم الأم', 'سنة الميلاد', 'الجنس',
        'الرقم الوطني', 'الحالة الاجتماعية', 'المهنة', 'الهاتف', 'العنوان',
        'جهة اتصال للطوارئ (الاسم)', 'صلة القرابة', 'هاتف جهة الاتصال', 'التاريخ العائلي',
        'ملاحظات هامة', 'تاريخ الإضافة',
    ]

    def get(self, request):
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response.write('\ufeff')
        writer = csv.writer(response)
        writer.writerow(self.HEADERS)
        response['Content-Disposition'] = f'attachment; filename="patients_import_template_v{self.VERSION}.csv"'
        response['X-Import-Template-Version'] = self.VERSION
        log_action(request.user.id, 'export', 'ImportTemplate', 0, {
            'summary': f'Patient import template v{self.VERSION} download',
        })
        return response


class OptionsImportView(APIView):
    permission_classes = [IsAuthenticated, HasManageOptions]
    parser_classes = [MultiPartParser, FormParser]
    service = OptionsImportService()

    def post(self, request):
        category = request.data.get('category')
        file = request.FILES.get('file')
        if not file or not category:
            return error_response(400, 'ملف أو فئة مفقودة', {})
        # Item #6: validate the uploaded file before parsing.
        try:
            validate_spreadsheet_upload(file)
        except ValidationError as e:
            return error_response(400, str(e), {})
        if category == 'diagnosis':
            merge_mode = request.data.get('merge_mode', 'merge')
            if merge_mode not in {'merge', 'replace'}:
                return error_response(400, 'طريقة الدمج غير صالحة', {})
            digest = _file_digest(file)
            if request.data.get('preview') == 'true':
                result = self.service.preview_diagnoses(file, merge_mode)
                token = secrets.token_urlsafe(24)
                cache.set(f'options-import-preview:{token}', {
                    'user_id': request.user.id,
                    'category': category,
                    'merge_mode': merge_mode,
                    'digest': digest,
                }, timeout=1800)
                result['preview_token'] = token
                return Response({'data': result})
            token = request.data.get('preview_token')
            preview = cache.get(f'options-import-preview:{token}') if token else None
            expected = {
                'user_id': request.user.id,
                'category': category,
                'merge_mode': merge_mode,
                'digest': digest,
            }
            if not preview or any(preview.get(key) != value for key, value in expected.items()):
                return error_response(409, 'الملف أو خياراته تغيرت بعد المعاينة', {
                    'preview_token': ['نفّذ معاينة جديدة أولاً'],
                })
            result = self.service.import_diagnoses(file, merge_mode)
            cache.delete(f'options-import-preview:{token}')
            log_action(request.user.id, 'import', 'DiagnosisOption', 0, {
                'summary': 'Diagnosis options import',
                'merge_mode': merge_mode,
                'counts': {key: result.get(key, 0) for key in ('added', 'updated', 'reactivated')},
            })
            return Response({'data': result})
        return error_response(400, 'فئة غير مدعومة', {})


class MedicationUploadView(APIView):
    permission_classes = [IsAuthenticated, HasManageOptions]
    parser_classes = [MultiPartParser, FormParser]
    service = OptionsImportService()

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return error_response(400, 'الرجاء اختيار ملف', {})
        # Item #6: validate the uploaded file before parsing.
        try:
            validate_spreadsheet_upload(file)
        except ValidationError as e:
            return error_response(400, str(e), {})
        table = self.service._read_file(file)
        columns = [f"عمود {i+1} (مثال: {table.rows[0][i][:30]})" for i in range(len(table.columns))]
        preview_rows = table.rows[:5]
        token = secrets.token_urlsafe(24)
        cache.set(f'options-import-preview:{token}', {
            'user_id': request.user.id,
            'category': 'medication',
            'digest': _file_digest(file),
        }, timeout=1800)
        return Response({
            'data': {
                'columns': columns,
                'preview_rows': preview_rows,
                'preview_token': token,
            }
        })


class MedicationMapView(APIView):
    permission_classes = [IsAuthenticated, HasManageOptions]
    parser_classes = [MultiPartParser, FormParser]
    service = OptionsImportService()

    def post(self, request):
        file = request.FILES.get('file')
        column_map = request.data.get('column_map')
        merge_mode = request.data.get('merge_mode', 'merge')
        preview_token = request.data.get('preview_token')
        if not file or not column_map:
            return error_response(400, 'ملف أو خريطة الأعمدة مفقودة', {})
        # Item #6: validate the uploaded file before parsing.
        try:
            validate_spreadsheet_upload(file)
        except ValidationError as e:
            return error_response(400, str(e), {})
        import json
        try:
            column_map = json.loads(column_map)
        except Exception:
            return error_response(400, 'خريطة الأعمدة غير صالحة', {})
        preview = cache.get(f'options-import-preview:{preview_token}') if preview_token else None
        if (
            not preview
            or preview.get('user_id') != request.user.id
            or preview.get('category') != 'medication'
            or preview.get('digest') != _file_digest(file)
        ):
            return error_response(409, 'الملف تغير أو انتهت صلاحية المعاينة', {
                'preview_token': ['ارفع الملف وراجع معاينته مرة أخرى'],
            })
        if merge_mode not in {'merge', 'overwrite'}:
            return error_response(400, 'طريقة الدمج غير صالحة', {})
        if request.data.get('preview') == 'true':
            result = self.service.preview_medications(file, column_map, merge_mode)
            token = secrets.token_urlsafe(24)
            cache.set(f'options-import-preview:{token}', {**preview, 'column_map':column_map, 'merge_mode':merge_mode}, timeout=1800)
            result['preview_token'] = token
            return Response({'data':result})
        if preview.get('column_map') != column_map or preview.get('merge_mode') != merge_mode:
            return error_response(409, 'أعد معاينة خريطة الأعمدة وخيارات الدمج', {})
        result = self.service.import_medications(file, column_map, merge_mode)
        cache.delete(f'options-import-preview:{preview_token}')
        log_action(request.user.id, 'import', 'MedicationOption', 0, {
            'summary': 'Medication options import',
            'merge_mode': merge_mode,
            'counts': {key: result.get(key, 0) for key in ('added', 'updated', 'reactivated')},
        })
        return Response({'data': result})
