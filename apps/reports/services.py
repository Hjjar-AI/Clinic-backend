# backend/apps/reports/services.py
from .patient_statistics import PatientStatisticsService
from .visit_statistics import VisitStatisticsService
from .appointment_statistics import AppointmentStatisticsService
from .doctor_performance import DoctorPerformanceService
from .tasks_statistics import TaskStatisticsService
from django.db.models import Count, Sum
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.billing.models import Invoice
from apps.patients.models import Patient
from apps.tasks.models import UserTask
from apps.visits.models import Visit

class StatisticsService(
    PatientStatisticsService,
    VisitStatisticsService,
    AppointmentStatisticsService,
    DoctorPerformanceService,
    TaskStatisticsService
):
    @staticmethod
    def _status_counts(queryset):
        return {
            row['status']: row['count']
            for row in queryset.values('status').annotate(count=Count('id')).order_by('status')
        }

    def get_reconciliation(self):
        invoices = Invoice.objects.all()
        paid_amount = (
            invoices.filter(status='paid').aggregate(total=Sum('final_amount'))['total'] or 0
        )
        return {
            'patients': {'total': Patient.objects.count()},
            'visits': {
                'total': Visit.objects.count(),
                'by_status': self._status_counts(Visit.objects.all()),
            },
            'appointments': {
                'total': Appointment.objects.count(),
                'by_status': self._status_counts(Appointment.objects.all()),
            },
            'tasks': {
                'total': UserTask.objects.count(),
                'by_status': self._status_counts(UserTask.objects.all()),
            },
            'invoices': {
                'total': invoices.count(),
                'by_status': self._status_counts(invoices),
                'paid_amount': str(paid_amount),
                'revenue_definition': 'إجمالي الفواتير المدفوعة فقط؛ المسودات والملغاة مستثناة',
            },
            '_meta': {
                'generated_at': timezone.now().isoformat(),
                'timezone': timezone.get_current_timezone_name(),
                'scope': 'السجلات غير المؤرشفة الظاهرة في قوائم النظام',
            },
        }
