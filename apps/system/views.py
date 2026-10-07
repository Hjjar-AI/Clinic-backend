# backend/apps/system/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.db import connection
from django.conf import settings
from django.core.cache import cache
from core.permissions import PERM_MANAGE_SETTINGS, HasManageSettings
from core.exceptions import error_response
from core.normalization import NATIONAL_ID_MAX_LENGTH, NATIONAL_ID_MIN_LENGTH


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            db_status = 'ok'
        except Exception:
            db_status = 'error'
        return Response({
            'data': {
                'status': 'ok' if db_status == 'ok' else 'degraded',
                'database': db_status,
            }
        })


class HealthFullView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        db_status = 'ok'
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
        except Exception:
            db_status = 'error'

        maintenance = getattr(settings, 'MAINTENANCE_MODE', False)
        return Response({
            'data': {
                'status': 'ok' if db_status == 'ok' else 'degraded',
                'database': db_status,
                'maintenance': maintenance,
            }
        })


class VersionView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'data': {
                'version': getattr(settings, 'VERSION', '2.0.0'),
                'build_date': getattr(settings, 'BUILD_DATE', '2026-07-10'),
            }
        })


class ConfigView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'data': {
                'working_hours': {
                    'start': f"{settings.WORK_START_HOUR:02d}:{settings.WORK_START_MINUTE:02d}",
                    'end': f"{settings.WORK_END_HOUR:02d}:{settings.WORK_END_MINUTE:02d}",
                },
                'max_attachment_size': settings.MAX_ATTACHMENT_SIZE,
                'max_import_size': settings.MAX_BULK_IMPORT_SIZE,
                'accepted_attachment_types': [
                    'image/png', 'image/jpeg', 'image/gif', 'application/pdf',
                    'application/msword',
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'application/vnd.ms-excel',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                ],
                'appointment_duration_default': settings.DEFAULT_APPOINTMENT_DURATION,
                'phone_min_length': 9,
                'phone_max_length': 13,
                'national_id_min_length': NATIONAL_ID_MIN_LENGTH,
                'national_id_max_length': NATIONAL_ID_MAX_LENGTH,
                'session_lifetime': settings.SESSION_COOKIE_AGE,
                'allow_demo_data': settings.ALLOW_DEMO_DATA,
            }
        })


class FeedbackView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = request.data.get('message')
        if not message:
            return error_response(400, 'الرسالة مطلوبة', {})
        return Response({'data': {'success': True, 'message': 'شكراً على ملاحظاتك'}})


class StatusConstantsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from core.lifecycle import lifecycle_payload
        return Response({
            'data': {
                **lifecycle_payload(),
                'risk_levels': {
                    'High': {'label': 'مرتفع', 'color': 'danger', 'icon': 'exclamation-triangle'},
                    'Moderate': {'label': 'متوسط', 'color': 'warning', 'icon': 'exclamation-circle'},
                    'Low': {'label': 'منخفض', 'color': 'success', 'icon': 'check-circle'},
                    'None': {'label': 'غير محدد', 'color': 'grey', 'icon': 'minus-circle'},
                },
                'user_roles': {
                    'admin': {'label': 'مدير', 'color': 'purple', 'icon': 'crown'},
                    'doctor': {'label': 'طبيب', 'color': 'primary', 'icon': 'user-md'},
                    'receptionist': {'label': 'موظف استقبال', 'color': 'info', 'icon': 'user-tie'},
                },
            }
        })


class ClearCacheView(APIView):
    permission_classes = [IsAuthenticated, HasManageSettings]

    def post(self, request):
        cache.clear()
        return Response({'data': {'success': True}})
