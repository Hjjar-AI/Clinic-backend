# backend/apps/reports/appointment_statistics.py
from django.utils import timezone
from datetime import timedelta
from .base import BaseStatisticsService
from apps.appointments.models import Appointment

class AppointmentStatisticsService(BaseStatisticsService):
    def get_total_appointments(self, user, date_from=None, date_to=None):
        qs = Appointment.objects.exclude(status='cancelled')
        if user.role == 'doctor':
            qs = qs.filter(doctor=user)
        elif user.role == 'receptionist':
            patient_ids = self.get_accessible_patients(user).values_list('id', flat=True)
            qs = qs.filter(patient_id__in=patient_ids)
        if date_from:
            qs = qs.filter(appointment_date__gte=date_from)
        if date_to:
            qs = qs.filter(appointment_date__lte=date_to)
        return qs.count()

    def get_no_show_rate(self, user, date_from=None, date_to=None):
        qs = Appointment.objects.all()
        if user.role == 'doctor':
            qs = qs.filter(doctor=user)
        elif user.role == 'receptionist':
            patient_ids = self.get_accessible_patients(user).values_list('id', flat=True)
            qs = qs.filter(patient_id__in=patient_ids)
        if date_from:
            qs = qs.filter(appointment_date__gte=date_from)
        if date_to:
            qs = qs.filter(appointment_date__lte=date_to)
        total = qs.count()
        if total == 0:
            return 0
        no_show = qs.filter(status='no-show').count()
        return no_show / total * 100

    def get_appointments_today(self, user):
        today = timezone.now().date()
        qs = Appointment.objects.filter(
            appointment_date=today,
            status__in=['scheduled', 'confirmed', 'arrived', 'completed'],
        )
        if user.role == 'doctor':
            qs = qs.filter(doctor=user)
        elif user.role == 'receptionist':
            patient_ids = self.get_accessible_patients(user).values_list('id', flat=True)
            qs = qs.filter(patient_id__in=patient_ids)
        return qs.count()

    def get_appointments_week(self, user):
        today = timezone.now().date()
        end_date = today + timedelta(days=7)
        qs = Appointment.objects.filter(
            appointment_date__gte=today,
            appointment_date__lte=end_date,
            status__in=['scheduled', 'confirmed', 'arrived', 'completed'],
        )
        if user.role == 'doctor':
            qs = qs.filter(doctor=user)
        elif user.role == 'receptionist':
            patient_ids = self.get_accessible_patients(user).values_list('id', flat=True)
            qs = qs.filter(patient_id__in=patient_ids)
        return qs.count()
