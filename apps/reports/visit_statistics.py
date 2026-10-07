# backend/apps/reports/visit_statistics.py
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth, ExtractWeekDay
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from .base import BaseStatisticsService
from apps.visits.models import Visit, VisitDiagnosis, VisitMedication

class VisitStatisticsService(BaseStatisticsService):
    def get_total_visits(self, user, date_from=None, date_to=None):
        qs = self.get_accessible_visits(user)
        if date_from:
            qs = qs.filter(visit_date__gte=date_from)
        if date_to:
            qs = qs.filter(visit_date__lte=date_to)
        return qs.count()

    def get_monthly_visits(self, user, months=12, date_from=None, date_to=None):
        visits = self.get_accessible_visits(user)
        if date_from:
            visits = visits.filter(visit_date__gte=date_from)
        if date_to:
            visits = visits.filter(visit_date__lte=date_to)
        today = timezone.now().date()
        start_date = today - relativedelta(months=months)
        visits = visits.filter(visit_date__gte=start_date)

        monthly = visits.annotate(month=TruncMonth('visit_date')).values('month').annotate(count=Count('id')).order_by('month')
        labels = []
        counts = []
        month_names = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']
        for entry in monthly:
            month_date = entry['month']
            labels.append(f"{month_names[month_date.month-1]} {month_date.year}")
            counts.append(entry['count'])
        return labels, counts

    def get_top_diagnoses(self, user, limit=5, date_from=None, date_to=None):
        visits = self.get_accessible_visits(user, date_from, date_to)
        diagnoses = VisitDiagnosis.objects.filter(visit__in=visits)
        top = diagnoses.values('diagnosis__arabic_name', 'diagnosis__english_name', 'custom_arabic', 'custom_name') \
            .annotate(count=Count('id')).order_by('-count')[:limit]
        result = []
        for entry in top:
            name = entry['diagnosis__arabic_name'] or entry['diagnosis__english_name'] or entry['custom_arabic'] or entry['custom_name'] or 'غير محدد'
            result.append((name, entry['count']))
        return result

    def get_top_medications(self, user, limit=5, date_from=None, date_to=None):
        visits = self.get_accessible_visits(user, date_from, date_to)
        meds = VisitMedication.objects.filter(visit__in=visits)
        top = meds.values('medication__generic_arabic', 'medication__generic_english', 'custom_name') \
            .annotate(count=Count('id')).order_by('-count')[:limit]
        result = []
        for entry in top:
            name = entry['medication__generic_arabic'] or entry['medication__generic_english'] or entry['custom_name'] or 'غير محدد'
            result.append((name, entry['count']))
        return result

    def get_followup_stats(self, user, date_from=None, date_to=None):
        visits = self.get_accessible_visits(user, date_from, date_to)
        today = timezone.now().date()
        completed = visits.filter(follow_up_date__isnull=False, follow_up_completed=True).count()
        overdue = visits.filter(follow_up_date__lt=today, follow_up_completed=False).count()
        total = overdue + completed
        adherence = (completed / total * 100) if total > 0 else 0
        return completed, overdue, adherence

    def get_visit_status_distribution(self, user, date_from=None, date_to=None):
        visits = self.get_accessible_visits(user, date_from, date_to)
        results = visits.values('status').annotate(count=Count('id'))
        return [(r['status'] or 'غير محدد', r['count']) for r in results]

    def get_weekday_distribution(self, user, date_from=None, date_to=None):
        visits = self.get_accessible_visits(user, date_from, date_to)
        results = visits.annotate(dow=ExtractWeekDay('visit_date')).values('dow').annotate(count=Count('id')).order_by('dow')
        weekday_names = {1: 'الأحد', 2: 'الاثنين', 3: 'الثلاثاء', 4: 'الأربعاء', 5: 'الخميس', 6: 'الجمعة', 7: 'السبت'}
        labels = []
        counts = []
        for r in results:
            dow = r['dow']
            if dow in weekday_names:
                labels.append(weekday_names[dow])
                counts.append(r['count'])
        return labels, counts

    def get_avg_visits_per_patient(self, user):
        total_patients = self.get_total_patients(user)
        if total_patients == 0:
            return 0
        return self.get_total_visits(user) / total_patients

    def get_high_risk_patients(self, user, limit=20):
        patients = self.get_accessible_patients(user)
        high_risk_visit_ids = Visit.objects.filter(
            patient__in=patients,
        ).filter(Q(suicide_risk_level='High') | Q(violence_risk_level='High')).values('patient_id').distinct()
        return patients.filter(id__in=high_risk_visit_ids)[:limit]

    def get_level_of_care_distribution(self, user, date_from=None, date_to=None):
        visits = self.get_accessible_visits(user, date_from, date_to)
        results = visits.values('level_of_care').annotate(count=Count('id'))
        return [(r['level_of_care'] or 'غير محدد', r['count']) for r in results]

    def get_suicide_risk_distribution(self, user, date_from=None, date_to=None):
        visits = self.get_accessible_visits(user, date_from, date_to)
        results = visits.values('suicide_risk_level').annotate(count=Count('id'))
        risk_map = {'High': 'مرتفع', 'Moderate': 'متوسط', 'Low': 'منخفض', None: 'غير محدد'}
        return [(risk_map.get(r['suicide_risk_level'], 'غير محدد'), r['count']) for r in results]

    def get_monthly_summary(self, user, year, month):
        visits = self.get_accessible_visits(user).filter(visit_date__year=year, visit_date__month=month)
        total_visits = visits.count()

        diagnoses = VisitDiagnosis.objects.filter(visit__in=visits)
        diag_counts = diagnoses.values('diagnosis__arabic_name', 'diagnosis__english_name', 'custom_arabic', 'custom_name') \
            .annotate(count=Count('id')).order_by('-count')
        diag_list = [{
            'name': (d['diagnosis__arabic_name'] or d['diagnosis__english_name'] or d['custom_arabic'] or d['custom_name'] or 'غير محدد'),
            'count': d['count']
        } for d in diag_counts]

        medications = VisitMedication.objects.filter(visit__in=visits)
        med_counts = medications.values('medication__generic_arabic', 'medication__generic_english', 'custom_name') \
            .annotate(count=Count('id')).order_by('-count')
        med_list = [{
            'name': (m['medication__generic_arabic'] or m['medication__generic_english'] or m['custom_name'] or 'غير محدد'),
            'count': m['count']
        } for m in med_counts]

        return {
            'year': year,
            'month': month,
            'total_visits': total_visits,
            'diagnoses': diag_list,
            'medications': med_list,
        }
