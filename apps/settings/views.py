# backend/apps/settings/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .services import SettingsService
from django.conf import settings
from core.permissions import HasManageSettings
from core.exceptions import error_response


class SettingsView(APIView):
    permission_classes = [IsAuthenticated]
    service = SettingsService()

    def get_permissions(self):
        permission_classes = [IsAuthenticated]
        if self.request.method == 'PUT':
            permission_classes.append(HasManageSettings)
        return [permission() for permission in permission_classes]

    def get(self, request):
        return Response({'data': self.service.get_clinic_info()})

    def put(self, request):
        data = request.data
        try:
            updated = self.service.update_clinic_info(data)
        except ValueError as exc:
            return error_response(400, str(exc), {})
        return Response({'data': updated})


class ThemeView(APIView):
    permission_classes = [IsAuthenticated, HasManageSettings]
    service = SettingsService()

    def put(self, request):
        theme = request.data.get('theme', 'default')
        self.service.set_setting('theme', theme)
        return Response({'data': {'status': 'ok'}})


class GenerateDemoDataView(APIView):
    permission_classes = [IsAuthenticated, HasManageSettings]
    service = SettingsService()

    def post(self, request):
        if not settings.ALLOW_DEMO_DATA:
            return error_response(403, 'توليد البيانات التجريبية غير مفعل', {})

        # Parse request-supplied integers first, in their own try block. A
        # non-integer here is genuinely the caller's fault -> 400.
        try:
            num_patients = int(request.data.get('num_patients', settings.DEMO_PATIENTS_COUNT))
            max_visits = int(request.data.get('max_visits', settings.DEMO_VISITS_PER_PATIENT))
        except (ValueError, TypeError):
            return error_response(
                400, 'num_patients و max_visits يجب أن يكونا أعداداً صحيحة', {}
            )

        # generate_demo_data() raises ValueError for exactly two expected
        # pre-condition failures ("no doctor available", "no diagnoses /
        # medications seeded"). Anything else — IntegrityError, DB errors,
        # bugs — is a real 500 and must not be masked as a 400. The previous
        # bare `except Exception` turned every failure, including internal
        # ones, into a 400 "bad request", which is why real bugs here never
        # showed up in logs as errors.
        try:
            count = self.service.generate_demo_data(num_patients, max_visits)
        except ValueError as e:
            return error_response(400, str(e), {})

        return Response({'data': {'created': count}, 'message': f'تم إنشاء {count} مرضى تجريبيين'})

# The dangerous ResetDatabaseView has been removed entirely to prevent
# accidental or malicious data loss.
