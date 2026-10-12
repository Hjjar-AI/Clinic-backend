from django.db.models import Q
from django.utils import timezone
from apps.accounts.models import User
from apps.patients.models import PatientCareTeam


class DoctorPerformanceService:
    def get_doctor_performance(self, user):
        patients = self.get_accessible_patients(user)
        visits = self.get_accessible_visits(user)
        teams = PatientCareTeam.objects.filter(patient__in=patients, ended_at__isnull=True,
            started_at__lte=timezone.now(), user__is_active=True, user__role__in=['doctor', 'admin'])
        doctors = User.objects.filter(Q(pk__in=teams.values('user_id')) | Q(pk__in=visits.values('author_id'))).order_by('pk')
        return [{'doctor_id': doctor.pk, 'doctor_name': doctor.full_name or doctor.username,
                 'patient_count': teams.filter(user=doctor).values('patient_id').distinct().count(),
                 'treated_patient_count': visits.filter(author=doctor).values('patient_id').distinct().count(),
                 'visit_count': visits.filter(author=doctor).count()}
                for doctor in doctors]
