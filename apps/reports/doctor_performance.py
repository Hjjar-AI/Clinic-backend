# backend/apps/reports/doctor_performance.py
from apps.accounts.models import User
from apps.visits.models import Visit

class DoctorPerformanceService:
    def get_doctor_performance(self, user):
        accessible_patient_ids = self.get_accessible_patients(user).values_list('id', flat=True)
        doctors = User.objects.filter(
            role__in=['doctor', 'admin'],
            is_active=True,
            patients__id__in=accessible_patient_ids,
        ).distinct()
        result = []
        for doctor in doctors:
            patients_count = doctor.patients.filter(id__in=accessible_patient_ids).count()
            visits_count = Visit.objects.filter(patient_id__in=accessible_patient_ids, patient__doctor=doctor).count()
            result.append({
                'doctor_name': doctor.full_name or doctor.username,
                'patient_count': patients_count,
                'visit_count': visits_count,
            })
        return result
