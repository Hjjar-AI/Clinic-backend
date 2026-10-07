# backend/apps/reports/base.py
from django.db.models import Q
from apps.patients.models import Patient
from apps.visits.models import Visit

class BaseStatisticsService:
    def get_accessible_patients(self, user):
        if user.role == 'admin':
            return Patient.objects.all()
        if user.role == 'doctor':
            return Patient.objects.filter(doctor=user)
        if user.role == 'receptionist':
            return Patient.objects.filter(Q(doctor=user) | Q(created_by=user))
        return Patient.objects.none()

    def get_accessible_visits(self, user, date_from=None, date_to=None):
        patient_ids = self.get_accessible_patients(user).values_list('id', flat=True)
        qs = Visit.objects.filter(patient_id__in=patient_ids)
        if date_from:
            qs = qs.filter(visit_date__gte=date_from)
        if date_to:
            qs = qs.filter(visit_date__lte=date_to)
        return qs