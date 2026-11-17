from core.permissions import PERM_VIEW_APPOINTMENTS
from django.db.models import Q
from django.core.exceptions import ValidationError
from core.query_utils import apply_ordering
from .models import Appointment
from .services import AppointmentService


def list_queryset(actor, params, kwargs=None):
    kwargs = kwargs or {}
    if actor.has_perm(PERM_VIEW_APPOINTMENTS):
        qs = AppointmentService().get_accessible_appointments(actor)
        patient_id = params.get('patient_id')
        if patient_id:
            qs = qs.filter(patient_id=patient_id)
        status_param = params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(patient__first_name__icontains=search) | Q(patient__surname__icontains=search))
        return apply_ordering(qs, params, {
            'date': 'appointment_date', 'time': 'appointment_time',
            'status': 'status', 'patient': 'patient__surname', 'created_at': 'created_at',
        }, default='-appointment_date')
    return Appointment.objects.none()



def next_appointment(actor, patient_id):
    from django.utils import timezone
    from django.shortcuts import get_object_or_404
    from core.access import accessible_patients
    get_object_or_404(accessible_patients(actor), pk=patient_id)
    now = timezone.localtime()
    row = AppointmentService().get_accessible_appointments(actor).filter(
        patient_id=patient_id, status__in=['scheduled', 'confirmed']).filter(
        Q(appointment_date__gt=now.date()) | Q(appointment_date=now.date(),
        appointment_time__gte=now.time().replace(tzinfo=None))).order_by('appointment_date', 'appointment_time', 'pk').first()
    return {'id': row.pk, 'date': row.appointment_date, 'time': row.appointment_time} if row else {'id': None, 'date': None}


def raw_queryset(actor, params):
    from datetime import datetime
    if not params.get('start_date') or not params.get('end_date'):
        raise ValidationError('start_date and end_date required')
    try:
        start = datetime.strptime(params['start_date'], '%Y-%m-%d').date()
        end = datetime.strptime(params['end_date'], '%Y-%m-%d').date()
        doctor_id = int(params['doctor_id']) if params.get('doctor_id') else None
    except (ValueError, TypeError):
        raise ValidationError('Invalid date or doctor')
    if start >= end or (end - start).days > 366:
        raise ValidationError('Date range must be positive and at most 366 days')
    rows = AppointmentService().get_accessible_appointments(actor).filter(appointment_date__gte=start, appointment_date__lt=end)
    return rows.filter(doctor_id=doctor_id) if doctor_id and actor.role == 'admin' else rows


def calendar_queryset(actor, params):
    from datetime import datetime
    from django.utils import timezone
    view = params.get('view', 'week')
    if view not in {'day', 'week', 'month'}:
        raise ValidationError('view must be day, week, or month')
    try:
        date = datetime.strptime(params['date'], '%Y-%m-%d').date() if params.get('date') else timezone.localdate()
        doctor = int(params['doctor_id']) if params.get('doctor_id') else None
    except (ValueError, TypeError):
        raise ValidationError('Invalid date or doctor')
    rows = AppointmentService().get_calendar(actor, view, date, doctor)
    return rows, {'view': view, 'date': date.isoformat(), 'doctor_id': doctor}


def availability(actor, params):
    from datetime import datetime
    from django.conf import settings
    from django.core.exceptions import PermissionDenied
    try:
        doctor = int(params.get('doctor_id'))
        date = datetime.strptime(params.get('date'), '%Y-%m-%d').date()
        duration = int(params.get('duration', settings.DEFAULT_APPOINTMENT_DURATION))
    except (ValueError, TypeError):
        raise ValidationError('doctor_id, valid date and duration required')
    service = AppointmentService()
    service._validate_duration(duration)
    if actor.role == 'doctor' and doctor != actor.pk:
        raise PermissionDenied('غير مصرح')
    return service.generate_time_slots(doctor, date, duration)
