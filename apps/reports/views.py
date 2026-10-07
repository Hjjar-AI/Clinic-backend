# backend/apps/reports/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .services import StatisticsService
from datetime import datetime
from django.utils import timezone
from core.permissions import (
    HasViewReports,
    HasExportReports,
    IsAdminRole,
)
from core.query_utils import parse_date_range

class StatisticsView(APIView):
    permission_classes = [IsAuthenticated, HasViewReports]
    service = StatisticsService()

    def get(self, request):
        date_from, date_to = parse_date_range(request.query_params)

        stats = self.service

        risk_data = stats.get_suicide_risk_distribution(request.user, date_from, date_to)
        risk_labels = [item[0] for item in risk_data] if risk_data else []
        risk_counts = [item[1] for item in risk_data] if risk_data else []

        status_data = stats.get_visit_status_distribution(request.user, date_from, date_to)
        status_labels = [item[0] for item in status_data] if status_data else []
        status_counts = [item[1] for item in status_data] if status_data else []

        marital_data = stats.get_marital_status_distribution(request.user)
        marital_labels = [item[0] for item in marital_data] if marital_data else []
        marital_counts = [item[1] for item in marital_data] if marital_data else []

        level_data = stats.get_level_of_care_distribution(request.user, date_from, date_to)
        level_labels = [item[0] for item in level_data] if level_data else []
        level_counts = [item[1] for item in level_data] if level_data else []

        age_labels, age_counts = stats.get_age_distribution(request.user)
        weekday_labels, weekday_data = stats.get_weekday_distribution(request.user, date_from, date_to)
        months_labels, visits_counts = stats.get_monthly_visits(request.user, date_from=date_from, date_to=date_to)
        patient_month_labels, patients_acquisition = stats.get_monthly_patients_acquired(
            request.user, date_from=date_from, date_to=date_to
        )

        top_diag = stats.get_top_diagnoses(request.user, 1, date_from, date_to)
        top_diag_label = top_diag[0][0] if top_diag else None
        top_diag_count = top_diag[0][1] if top_diag else None

        top_med = stats.get_top_medications(request.user, 1, date_from, date_to)
        top_med_label = top_med[0][0] if top_med else None
        top_med_count = top_med[0][1] if top_med else None

        top_meds = stats.get_top_medications(request.user, 10, date_from, date_to)
        med_labels = [m[0] for m in top_meds] if top_meds else []
        med_counts = [m[1] for m in top_meds] if top_meds else []
        male_count, female_count, gender_ratio = stats.get_gender_breakdown(request.user)
        followup_completed, followup_overdue, followup_adherence = stats.get_followup_stats(
            request.user, date_from, date_to
        )
        doctor_distribution = stats.get_patients_by_doctor(request.user)

        data = {
            'total_patients': stats.get_total_patients(request.user),
            'total_visits': stats.get_total_visits(request.user, date_from, date_to),
            'total_appointments': stats.get_total_appointments(request.user, date_from, date_to),
            'male_count': male_count,
            'female_count': female_count,
            'gender_ratio': round(gender_ratio, 1),
            'avg_age': round(stats.get_average_age(request.user), 1),
            'avg_visits_per_patient': round(stats.get_avg_visits_per_patient(request.user), 1),
            'top_diagnosis': [top_diag_label, top_diag_count] if top_diag else None,
            'top_medication': [top_med_label, top_med_count] if top_med else None,
            'no_show_rate': round(stats.get_no_show_rate(request.user, date_from, date_to), 1),
            'followup_stats': {
                'completed': followup_completed,
                'overdue': followup_overdue,
                'adherence': round(followup_adherence, 1),
            },
            'completed_tasks': stats.get_completed_tasks_count(request.user),
            'pending_tasks': stats.get_pending_tasks_count(request.user),
            'appointments_today': stats.get_appointments_today(request.user),
            'appointments_week': stats.get_appointments_week(request.user),
            'months_labels': months_labels,
            'visits_counts': visits_counts,
            'patients_acquisition': patients_acquisition,
            'patients_acquisition_labels': patient_month_labels,
            'status_labels': status_labels,
            'status_data': status_counts,
            'weekday_labels': weekday_labels,
            'weekday_data': weekday_data,
            'med_labels': med_labels,
            'med_counts': med_counts,
            'risk_labels': risk_labels,
            'risk_counts': risk_counts,
            'age_labels': age_labels,
            'age_counts': age_counts,
            'marital_labels': marital_labels,
            'marital_counts': marital_counts,
            'level_labels': level_labels,
            'level_counts': level_counts,
            'doctor_labels': [d[0] for d in doctor_distribution],
            'doctor_counts': [d[1] for d in doctor_distribution],
            '_meta': {
                'generated_at': timezone.now().isoformat(),
                'timezone': timezone.get_current_timezone_name(),
                'date_from': date_from.isoformat() if date_from else None,
                'date_to': date_to.isoformat() if date_to else None,
                'definitions': {
                    'visit_metrics': 'زيارات غير مؤرشفة بما فيها المسودات، ضمن نطاق المستخدم والفترة',
                    'appointment_metrics': 'المواعيد ضمن نطاق المستخدم والفترة؛ الملغاة مستثناة من الإجمالي',
                    'patient_metrics': 'كل المرضى غير المؤرشفين ضمن نطاق المستخدم؛ لا يطبق عليهم نطاق تاريخ الزيارات',
                },
            },
        }
        return Response({'data': data})


class MonthlySummaryView(APIView):
    permission_classes = [IsAuthenticated, HasExportReports]
    service = StatisticsService()

    def get(self, request):
        year = int(request.query_params.get('year', datetime.now().year))
        month = int(request.query_params.get('month', datetime.now().month))
        data = self.service.get_monthly_summary(request.user, year, month)
        return Response({'data': data})


class DoctorPerformanceView(APIView):
    permission_classes = [IsAuthenticated, HasExportReports]
    service = StatisticsService()

    def get(self, request):
        data = self.service.get_doctor_performance(request.user)
        return Response({'data': data})


class ReconciliationView(APIView):
    permission_classes = [IsAuthenticated, HasViewReports, IsAdminRole]
    service = StatisticsService()

    def get(self, request):
        data = self.service.get_reconciliation()
        return Response({'data': data})
