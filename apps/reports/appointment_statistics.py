# backend/apps/reports/appointment_statistics.py
from django.utils import timezone
from datetime import timedelta
from .base import BaseStatisticsService
from apps.appointments.models import Appointment
from core.access import accessible_appointments

class AppointmentStatisticsService(BaseStatisticsService):
    def get_total_appointments(self, user, date_from=None, date_to=None):
        qs = accessible_appointments(user).exclude(status='cancelled')
        if date_from:
            qs = qs.filter(appointment_date__gte=date_from)
        if date_to:
            qs = qs.filter(appointment_date__lte=date_to)
        return qs.count()

    def get_no_show_rate(self, user, date_from=None, date_to=None):
        qs = accessible_appointments(user)
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
        today = timezone.localdate()
        qs = accessible_appointments(user).filter(
            appointment_date=today,
            status__in=['scheduled', 'confirmed', 'arrived', 'completed'],
        )
        return qs.count()

    def get_appointments_week(self, user):
        today = timezone.localdate()
        end_date = today + timedelta(days=7)
        qs = accessible_appointments(user).filter(
            appointment_date__gte=today,
            appointment_date__lte=end_date,
            status__in=['scheduled', 'confirmed', 'arrived', 'completed'],
        )
        return qs.count()
