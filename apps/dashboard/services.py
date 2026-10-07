# backend/apps/dashboard/services.py
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from apps.patients.models import Patient
from apps.visits.models import Visit, VisitDiagnosis, VisitMedication
from apps.appointments.models import Appointment
from apps.tasks.models import UserTask
from apps.reports.services import StatisticsService


class DashboardService:
    def __init__(self):
        self.stats = StatisticsService()

    def _get_accessible_patients(self, user):
        return self.stats.get_accessible_patients(user)

    def _get_accessible_visits(self, user, date_from=None, date_to=None):
        visits = self.stats.get_accessible_visits(user)
        if date_from:
            visits = visits.filter(visit_date__gte=date_from)
        if date_to:
            visits = visits.filter(visit_date__lte=date_to)
        return visits

    def get_summary(self, user):
        return self._permitted(user, {
            'total_patients': self.stats.get_total_patients(user),
            'total_visits': self.stats.get_total_visits(user),
            'appointments_today': self.stats.get_appointments_today(user),
            'pending_tasks': self.stats.get_pending_tasks_count(user),
            '_meta': self._meta(),
        })

    def _meta(self, date_from=None, date_to=None):
        return {
            'generated_at': timezone.now().isoformat(),
            'timezone': timezone.get_current_timezone_name(),
            'date_from': date_from.isoformat() if date_from else None,
            'date_to': date_to.isoformat() if date_to else None,
            'definitions': {
                'total_patients': 'كل المرضى غير المؤرشفين ضمن نطاق المستخدم',
                'total_visits': 'كل الزيارات غير المؤرشفة، بما فيها المسودات، ضمن الفترة',
                'appointments_today': 'مواعيد اليوم المجدولة أو المؤكدة أو الواصلة أو المكتملة',
                'pending_tasks': 'المهام المفتوحة أو قيد التنفيذ ضمن نطاق المستخدم',
            },
        }

    def get_dashboard_data(self, user, date_from=None, date_to=None):
        today = timezone.localdate()
        next_week = today + timedelta(days=7)

        visits_for_period = self._get_accessible_visits(user, date_from, date_to)

        recent_patients = self._get_accessible_patients(user).order_by('-created_at')[:5]
        high_risk = self.stats.get_high_risk_patients(user, limit=20)

        overdue_followups = visits_for_period.filter(
            follow_up_date__lt=today,
            follow_up_outcome='pending'
        ).order_by('follow_up_date')[:50]

        upcoming_followups = visits_for_period.filter(
            follow_up_date__gte=today,
            follow_up_date__lte=next_week,
            follow_up_outcome='pending'
        ).order_by('follow_up_date')[:50]

        pending_tasks = UserTask.objects.filter(
            Q(assigned_to=user) | Q(assigned_to__isnull=True),
            status__in=['open', 'in_progress']
        ).order_by('due_date', 'created_at')[:5]
        if user.role == 'admin':
            pending_tasks = UserTask.objects.filter(
                status__in=['open', 'in_progress']
            ).order_by('due_date', 'created_at')[:5]

        from core.access import accessible_appointments
        upcoming_appointments = accessible_appointments(user).filter(
            status__in=['scheduled', 'confirmed'],
            appointment_date__gte=today,
            appointment_date__lte=next_week,
        )
        if date_from:
            upcoming_appointments = upcoming_appointments.filter(appointment_date__gte=date_from)
        if date_to:
            upcoming_appointments = upcoming_appointments.filter(appointment_date__lte=date_to)

        upcoming_appointments = upcoming_appointments.order_by('appointment_date', 'appointment_time')[:10]

        # Today's appointments: apply date filters if provided; otherwise show all today's appointments
        today_appointments = accessible_appointments(user).filter(
            status__in=['scheduled', 'confirmed', 'arrived'],
            appointment_date=today,
        )
        if date_from:
            today_appointments = today_appointments.filter(appointment_date__gte=date_from)
        if date_to:
            today_appointments = today_appointments.filter(appointment_date__lte=date_to)

        today_appointments = today_appointments.order_by('appointment_time')[:50]

        return self._permitted(user, {
            'total_patients': self.stats.get_total_patients(user),
            'total_visits': self.stats.get_total_visits(user, date_from, date_to),
            'recent_patients': self._serialize_patients(recent_patients),
            'overdue_followups': self._serialize_visits(overdue_followups),
            'upcoming_followups': self._serialize_visits(upcoming_followups),
            'pending_tasks': self._serialize_tasks(pending_tasks),
            'high_risk_patients': self._serialize_patients(high_risk),
            'upcoming_appointments': self._serialize_appointments(upcoming_appointments),
            'today_appointments': self._serialize_appointments(today_appointments),
            'appointments_today': self.stats.get_appointments_today(user),
            'pending_tasks_count': self.stats.get_pending_tasks_count(user),
            '_meta': self._meta(date_from, date_to),
        })

    @staticmethod
    def _permitted(user, data):
        groups = {
            'view_patients': ('total_patients', 'recent_patients'),
            'view_visits': ('total_visits', 'overdue_followups', 'upcoming_followups', 'high_risk_patients'),
            'view_appointments': ('appointments_today', 'today_appointments', 'upcoming_appointments'),
            'manage_tasks': ('pending_tasks', 'pending_tasks_count'),
        }
        for permission, keys in groups.items():
            if not user.has_perm(permission):
                for key in keys:
                    if key in data:
                        data[key] = [] if isinstance(data[key], list) else None
        return data

    def get_chart_data(self, user, date_from=None, date_to=None):
        months_labels, visits_counts = self.stats.get_monthly_visits(user, months=12, date_from=date_from, date_to=date_to)
        top_diag = self.stats.get_top_diagnoses(user, limit=10, date_from=date_from, date_to=date_to)
        weekday_labels, weekday_data = self.stats.get_weekday_distribution(user, date_from=date_from, date_to=date_to)
        return {
            'months_labels': months_labels,
            'visits_counts': visits_counts,
            'top_diagnoses_labels': [d[0] for d in top_diag],
            'top_diagnoses_counts': [d[1] for d in top_diag],
            'weekday_labels': weekday_labels,
            'weekday_data': weekday_data,
            '_meta': self._meta(date_from, date_to),
        }

    def _serialize_patients(self, qs):
        return [{
            'id': p.id,
            'first_name': p.first_name,
            'father_name': p.father_name,
            'surname': p.surname,
            'mother_name': p.mother_name,
            'dob_year': p.dob_year,
            'gender': p.gender,
            'national_id': p.national_id,
            'phone': p.phone,
            'admission_date': p.admission_date.isoformat() if p.admission_date else None,
            'doctor_name': p.doctor.full_name if p.doctor else None,
            'created_at': p.created_at.isoformat() if p.created_at else None,
        } for p in qs]

    def _serialize_visits(self, qs):
        return [{
            'id': v.id,
            'version': v.version,
            'patient_id': v.patient_id,
            'patient_name': v.patient.get_full_name(),
            'visit_date': v.visit_date.isoformat() if v.visit_date else None,
            'main_complaints': v.main_complaints,
            'status': v.status,
            'follow_up_date': v.follow_up_date.isoformat() if v.follow_up_date else None,
            'follow_up_completed': v.follow_up_completed,
        } for v in qs]

    def _serialize_tasks(self, qs):
        return [{
            'id': t.id,
            'title': t.title,
            'description': t.description,
            'priority': t.priority,
            'due_date': t.due_date.isoformat() if t.due_date else None,
            'status': t.status_display(),
            'assigned_to': t.assigned_to.full_name if t.assigned_to else None,
        } for t in qs]

    def _serialize_appointments(self, qs):
        return [{
            'id': a.id,
            'version': a.version,
            'patient_id': a.patient_id,
            'patient_name': a.patient.get_full_name(),
            'appointment_date': a.appointment_date.isoformat() if a.appointment_date else None,
            'appointment_time': a.appointment_time,
            'duration_minutes': a.duration_minutes,
            'status': a.status,
            'notes': a.notes,
        } for a in qs]
