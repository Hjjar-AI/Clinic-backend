from django.conf import settings
from core.mutation import request_version
# backend/apps/appointments/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from datetime import datetime
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Appointment
from .serializers import AppointmentSerializer
from .services import AppointmentService
from core.permissions import (
    PERM_VIEW_APPOINTMENTS,
    PERM_MANAGE_APPOINTMENTS,
    HasViewAppointments,
    HasManageAppointments,
    CanAccessAppointment,
)
from core.exceptions import error_response
from apps.patients.services import PatientService
from django.db.models import Q
from core.query_utils import apply_ordering


class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    service = AppointmentService()
    patient_service = PatientService()

    def get_permissions(self):
        # Item #2: CanAccessAppointment is layered on every action that fetches
        # a specific appointment via get_object(), as defense-in-depth on top of
        # the queryset scoping in AppointmentService.get_accessible_appointments.
        if self.action in ['create']:
            permission_classes = [permissions.IsAuthenticated, HasManageAppointments]
        elif self.action in ['update', 'partial_update', 'destroy',
                             'cancel', 'complete', 'reschedule', 'transition']:
            permission_classes = [
                permissions.IsAuthenticated, HasManageAppointments, CanAccessAppointment,
            ]
        elif self.action in ['retrieve']:
            permission_classes = [
                permissions.IsAuthenticated, HasViewAppointments, CanAccessAppointment,
            ]
        else:
            permission_classes = [permissions.IsAuthenticated, HasViewAppointments]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        from .selectors import list_queryset
        return list_queryset(self.request.user, self.request.query_params, self.kwargs)

    def perform_create(self, serializer):
        patient = serializer.validated_data['patient']
        doctor = serializer.validated_data['doctor']
        user = self.request.user
        if not self.patient_service.list_patients(user, {}).filter(pk=patient.pk).exists():
            self.permission_denied(self.request)
        if user.role == 'doctor' and doctor.pk != user.pk:
            self.permission_denied(self.request)
        instance = self.service.create_appointment(serializer.validated_data, actor=user)
        serializer.instance = instance

    def perform_update(self, serializer):
        instance = self.get_object()
        version = request_version(self.request)
        data = serializer.validated_data.copy()
        data.pop('version', None)
        serializer.instance = self.service.update_appointment(instance, data, version, actor=self.request.user)

    def perform_destroy(self, instance):
        self.service.archive(instance, self._required_version(self.request), actor=self.request.user)

    def _paginate_queryset(self, qs, request):
        from core.collections import offset_page
        return offset_page(qs, request.query_params)

    @action(detail=False, methods=['get'])
    def raw(self, request):
        from .selectors import raw_queryset
        items, total, limit, offset = self._paginate_queryset(raw_queryset(request.user, request.query_params), request)
        return Response({'data': {'items': self.get_serializer(items, many=True).data,
            'meta': {'pagination': 'offset', 'total': total, 'per_page': limit, 'offset': offset}}})

    @action(detail=False, methods=['get'])
    def calendar(self, request):
        from .selectors import calendar_queryset
        rows, context = calendar_queryset(request.user, request.query_params)
        items, total, limit, offset = self._paginate_queryset(rows, request)
        return Response({'data': {'items': self.get_serializer(items, many=True).data,
            'meta': {**context, 'pagination': 'offset', 'total': total, 'per_page': limit, 'offset': offset}}})

    @action(detail=False, methods=['get'])
    def availability(self, request):
        from .selectors import availability
        return Response({'data': {'items': availability(request.user, request.query_params), 'meta': {'pagination': 'none'}}})

    @action(detail=True, methods=['put'])
    def cancel(self, request, pk=None):
        apt = self.get_object()
        version = self._required_version(request)
        updated = self.service.cancel(apt, version, request.data.get('reason', ''), actor=request.user)
        return Response({'data': self.get_serializer(updated).data, 'message': 'تم إلغاء الموعد'})

    @action(detail=True, methods=['put'])
    def complete(self, request, pk=None):
        apt = self.get_object()
        version = self._required_version(request)
        updated = self.service.complete(apt, version, actor=request.user)
        return Response({'data': self.get_serializer(updated).data, 'message': 'تم إكمال الموعد'})

    @action(detail=True, methods=['put'])
    def transition(self, request, pk=None):
        apt = self.get_object()
        target = request.data.get('status')
        if not target:
            return error_response(400, 'status is required', {'status': ['هذا الحقل مطلوب']})
        updated = self.service.transition(
            apt,
            target,
            self._required_version(request),
            request.data.get('reason', ''),
            actor=request.user,
        )
        return Response({'data': self.get_serializer(updated).data})

    @staticmethod
    def _required_version(request):
        from core.mutation import request_version
        return request_version(request)

    @action(detail=True, methods=['put'])
    def reschedule(self, request, pk=None):
        apt = self.get_object()
        new_date = request.data.get('date')
        new_time = request.data.get('time')
        if not new_date or not new_time:
            return error_response(400, 'date and time required', {})
        version = request_version(request)
        updated = self.service.reschedule(apt, new_date, new_time, version, actor=request.user)
        return Response({'data': self.get_serializer(updated).data, 'message': 'تم نقل الموعد'})

    @action(detail=False, methods=['get'], url_path='next/(?P<patient_id>[^/.]+)')
    def next(self, request, patient_id=None):
        if not request.user.has_perm(PERM_VIEW_APPOINTMENTS):
            return error_response(403, 'غير مصرح', {})
        try:
            patient_id_int = int(patient_id)
        except (ValueError, TypeError):
            return error_response(400, 'patient_id must be an integer', {})

        from .selectors import next_appointment
        return Response({'data': next_appointment(request.user, patient_id_int)})
