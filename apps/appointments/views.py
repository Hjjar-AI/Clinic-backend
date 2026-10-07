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
        if self.request.user.has_perm(PERM_VIEW_APPOINTMENTS):
            qs = self.service.get_accessible_appointments(self.request.user)
            patient_id = self.request.query_params.get('patient_id')
            if patient_id:
                qs = qs.filter(patient_id=patient_id)
            status_param = self.request.query_params.get('status')
            if status_param:
                qs = qs.filter(status=status_param)
            search = self.request.query_params.get('search', '').strip()
            if search:
                qs = qs.filter(Q(patient__first_name__icontains=search) | Q(patient__surname__icontains=search))
            return apply_ordering(qs, self.request.query_params, {
                'date': 'appointment_date', 'time': 'appointment_time',
                'status': 'status', 'patient': 'patient__surname', 'created_at': 'created_at',
            }, default='-appointment_date')
        return Appointment.objects.none()

    def perform_create(self, serializer):
        patient = serializer.validated_data['patient']
        doctor = serializer.validated_data['doctor']
        user = self.request.user
        if not self.patient_service.list_patients(user, {}).filter(pk=patient.pk).exists():
            self.permission_denied(self.request)
        if user.role == 'doctor' and doctor.pk != user.pk:
            self.permission_denied(self.request)
        instance = self.service.create_appointment(serializer.validated_data)
        serializer.instance = instance

    def perform_update(self, serializer):
        instance = self.get_object()
        version = self.request.data.get('version')
        if version is not None:
            try:
                version = int(version)
            except (ValueError, TypeError):
                version = None
        data = serializer.validated_data.copy()
        data.pop('version', None)
        serializer.instance = self.service.update_appointment(instance, data, version)

    def perform_destroy(self, instance):
        self.service.archive(instance)

    def _paginate_queryset(self, qs, request):
        """
        Offset/limit pagination helper.

        F7: The frontend apiClient interceptor rewrites GET `params.limit` into
        `params.per_page`, so the canonical key on the wire is `per_page`.
        Read it first; fall back to `limit` for direct API clients.
        """
        raw_limit = request.query_params.get('per_page') or request.query_params.get('limit', 20)
        try:
            limit = int(raw_limit)
            limit = max(1, min(limit, 200))
        except (ValueError, TypeError):
            limit = 20
        try:
            offset = max(0, int(request.query_params.get('offset', 0)))
        except (ValueError, TypeError):
            offset = 0
        total = qs.count()
        items = list(qs[offset:offset + limit])
        return items, total, limit, offset

    @action(detail=False, methods=['get'])
    def raw(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        doctor_id = request.query_params.get('doctor_id')
        if not start_date or not end_date:
            return error_response(400, 'start_date and end_date required', {})
        # Item #5: guard parsing so malformed query params return 400, not 500.
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return error_response(400, 'Invalid date format; expected YYYY-MM-DD', {})
        if start >= end:
            return error_response(400, 'end_date must be after start_date', {})
        if (end - start).days > 366:
            return error_response(400, 'Date range cannot exceed 366 days', {})
        if doctor_id:
            try:
                doctor_id = int(doctor_id)
            except (ValueError, TypeError):
                return error_response(400, 'doctor_id must be an integer', {})
        qs = self.service.get_accessible_appointments(request.user)
        qs = qs.filter(appointment_date__gte=start, appointment_date__lt=end)
        if doctor_id and request.user.role == 'admin':
            qs = qs.filter(doctor_id=doctor_id)

        items, total, limit, offset = self._paginate_queryset(qs, request)
        serializer = self.get_serializer(items, many=True)
        return Response({
            'data': {
                'appointments': serializer.data,
                'meta': {
                    'total': total,
                    'limit': limit,
                    'offset': offset,
                }
            }
        })

    @action(detail=False, methods=['get'])
    def calendar(self, request):
        view = request.query_params.get('view', 'week')
        if view not in {'day', 'week', 'month'}:
            return error_response(400, 'view must be day, week, or month', {})
        date_str = request.query_params.get('date')
        doctor_id = request.query_params.get('doctor_id')
        # Item #5: guard date parsing so malformed `date=` returns 400, not 500.
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                return error_response(400, 'Invalid date format; expected YYYY-MM-DD', {})
        else:
            date_obj = timezone.now().date()
        # Validate doctor_id is numeric up-front, but pass the original string
        # through so the response shape is unchanged.
        if doctor_id:
            try:
                int(doctor_id)
            except (ValueError, TypeError):
                return error_response(400, 'doctor_id must be an integer', {})
        appointments = self.service.get_calendar(request.user, view, date_obj, doctor_id)

        items, total, limit, offset = self._paginate_queryset(appointments, request)
        serializer = self.get_serializer(items, many=True)
        return Response({
            'data': {
                'view': view,
                'date': date_obj.isoformat(),
                'doctor_id': doctor_id,
                'appointments': serializer.data,
                'meta': {
                    'total': total,
                    'limit': limit,
                    'offset': offset,
                }
            }
        })

    @action(detail=False, methods=['get'])
    def availability(self, request):
        doctor_id = request.query_params.get('doctor_id')
        date_str = request.query_params.get('date')
        duration_raw = request.query_params.get('duration', 30)
        if not doctor_id or not date_str:
            return error_response(400, 'doctor_id and date required', {})
        # Item #5: guard parsing of doctor_id, duration, and date.
        try:
            doctor_id_int = int(doctor_id)
        except (ValueError, TypeError):
            return error_response(400, 'doctor_id must be an integer', {})
        try:
            duration = int(duration_raw)
        except (ValueError, TypeError):
            return error_response(400, 'duration must be an integer', {})
        if duration < 5 or duration > 480:
            return error_response(400, 'duration must be between 5 and 480 minutes', {})
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return error_response(400, 'Invalid date format; expected YYYY-MM-DD', {})
        if request.user.role == 'doctor' and doctor_id_int != request.user.id:
            return error_response(403, 'غير مصرح', {})
        slots = self.service.generate_time_slots(doctor_id_int, date_obj, duration)
        return Response({'data': {'slots': slots}})

    @action(detail=True, methods=['put'])
    def cancel(self, request, pk=None):
        apt = self.get_object()
        version = self._required_version(request)
        updated = self.service.cancel(apt, version, request.data.get('reason', ''))
        return Response({'data': self.get_serializer(updated).data, 'message': 'تم إلغاء الموعد'})

    @action(detail=True, methods=['put'])
    def complete(self, request, pk=None):
        apt = self.get_object()
        version = self._required_version(request)
        updated = self.service.complete(apt, version)
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
        )
        return Response({'data': self.get_serializer(updated).data})

    @staticmethod
    def _required_version(request):
        version = request.data.get('version')
        if version is None:
            raise ValidationError({'version': ['يجب توفير رقم الإصدار']})
        try:
            return int(version)
        except (ValueError, TypeError):
            raise ValidationError({'version': ['رقم الإصدار غير صالح']})

    @action(detail=True, methods=['put'])
    def reschedule(self, request, pk=None):
        apt = self.get_object()
        new_date = request.data.get('date')
        new_time = request.data.get('time')
        if not new_date or not new_time:
            return error_response(400, 'date and time required', {})
        # Item #5: validate date and time formats before hitting the service.
        try:
            datetime.strptime(new_date, '%Y-%m-%d')
        except (ValueError, TypeError):
            return error_response(400, 'Invalid date format; expected YYYY-MM-DD', {})
        try:
            datetime.strptime(new_time, '%H:%M')
        except (ValueError, TypeError):
            try:
                datetime.strptime(new_time, '%H:%M:%S')
            except (ValueError, TypeError):
                return error_response(400, 'Invalid time format; expected HH:MM', {})
        version = request.data.get('version')
        if version is None:
            return error_response(400, 'version is required', {})
        try:
            version = int(version)
        except (ValueError, TypeError):
            return error_response(400, 'version must be an integer', {})
        updated = self.service.reschedule(apt, new_date, new_time, version)
        return Response({'data': self.get_serializer(updated).data, 'message': 'تم نقل الموعد'})

    @action(detail=False, methods=['get'], url_path='next/(?P<patient_id>[^/.]+)')
    def next(self, request, patient_id=None):
        if not request.user.has_perm(PERM_VIEW_APPOINTMENTS):
            return error_response(403, 'غير مصرح', {})
        try:
            patient_id_int = int(patient_id)
        except (ValueError, TypeError):
            return error_response(400, 'patient_id must be an integer', {})

        accessible_patients = self.patient_service.list_patients(request.user, {})
        patient_obj = accessible_patients.filter(id=patient_id_int).first()
        if not patient_obj:
            return error_response(404, 'المريض غير موجود أو غير مصرح', {})

        next_apt = Appointment.objects.filter(
            patient_id=patient_id_int,
            status__in=['scheduled', 'confirmed'],
            appointment_date__gte=timezone.now().date(),
        ).order_by('appointment_date', 'appointment_time').first()
        if next_apt:
            return Response({'data': {'date': next_apt.appointment_date, 'time': next_apt.appointment_time}})
        return Response({'data': {'date': None}})
