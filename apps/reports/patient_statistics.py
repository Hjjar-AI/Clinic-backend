# backend/apps/reports/patient_statistics.py
from django.db.models import Count, Avg
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.db.models.functions import TruncMonth
from .base import BaseStatisticsService

class PatientStatisticsService(BaseStatisticsService):
    def get_total_patients(self, user):
        return self.get_accessible_patients(user).count()

    def get_gender_breakdown(self, user):
        patients = self.get_accessible_patients(user)
        male_count = patients.filter(gender='ذكر').count()
        female_count = patients.filter(gender='أنثى').count()
        total = male_count + female_count
        ratio = (male_count / total * 100) if total > 0 else 0
        return male_count, female_count, ratio

    def get_average_age(self, user):
        patients = self.get_accessible_patients(user)
        avg_year = patients.aggregate(avg_year=Avg('dob_year'))['avg_year']
        if avg_year:
            return timezone.now().year - avg_year
        return 0

    def get_monthly_patients_acquired(self, user, months=12, date_from=None, date_to=None):
        patients = self.get_accessible_patients(user)
        if date_from:
            patients = patients.filter(created_at__date__gte=date_from)
        if date_to:
            patients = patients.filter(created_at__date__lte=date_to)
        today = timezone.now().date()
        start_date = today - relativedelta(months=months)
        patients = patients.filter(created_at__gte=start_date)
        monthly = patients.annotate(month=TruncMonth('created_at')).values('month').annotate(count=Count('id')).order_by('month')
        month_names = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
                       'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
        labels = [f"{month_names[entry['month'].month - 1]} {entry['month'].year}" for entry in monthly]
        return labels, [entry['count'] for entry in monthly]

    def get_age_distribution(self, user):
        patients = self.get_accessible_patients(user)
        current_year = timezone.now().year
        age_groups = {
            '0-18': patients.filter(dob_year__gte=current_year-18).count(),
            '19-30': patients.filter(dob_year__lt=current_year-18, dob_year__gte=current_year-30).count(),
            '31-45': patients.filter(dob_year__lt=current_year-30, dob_year__gte=current_year-45).count(),
            '46-60': patients.filter(dob_year__lt=current_year-45, dob_year__gte=current_year-60).count(),
            '61-80': patients.filter(dob_year__lt=current_year-60, dob_year__gte=current_year-80).count(),
            '80+': patients.filter(dob_year__lt=current_year-80).count(),
        }
        return list(age_groups.keys()), list(age_groups.values())

    def get_marital_status_distribution(self, user):
        patients = self.get_accessible_patients(user)
        results = patients.values('marital_status').annotate(count=Count('id'))
        return [(r['marital_status'] or 'غير محدد', r['count']) for r in results]

    def get_patients_by_doctor(self, user):
        rows = (
            self.get_accessible_patients(user)
            .filter(doctor__isnull=False)
            .values('doctor__full_name', 'doctor__username')
            .annotate(count=Count('id'))
            .order_by('doctor__full_name', 'doctor__username')
        )
        return [
            (row['doctor__full_name'] or row['doctor__username'], row['count'])
            for row in rows
        ]
