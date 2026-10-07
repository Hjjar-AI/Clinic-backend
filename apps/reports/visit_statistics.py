# backend/apps/reports/visit_statistics.py
from django.db.models import Count, Q, OuterRef, Subquery
from collections import Counter
from .periods import monthly_period, fill_months
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
        start, end = monthly_period(months, date_from, date_to)
        visits = self.get_accessible_visits(user, start, end)
        rows = visits.annotate(month=TruncMonth('visit_date')).values('month').annotate(count=Count('id')).order_by('month')
        return fill_months(rows, start, end)

    @staticmethod
    def _top(rows, kind, limit):
        counts, names = Counter(), {}
        for row in rows.order_by('visit__visit_date', 'visit_id', 'order', 'pk'):
            if kind == 'diagnosis':
                name = row.custom_arabic or row.custom_name or row.custom_code or 'غير محدد'
                key = ('catalog', row.diagnosis_id) if row.diagnosis_id else ('custom', row.custom_code.casefold(), name.casefold())
            else:
                name = row.custom_name or 'غير محدد'
                key = ('catalog', row.medication_id) if row.medication_id else ('custom', name.casefold(), (row.custom_dosage or '').casefold())
            counts[key] += 1
            names[key] = name
        return [(names[key], count) for key, count in counts.most_common(limit)]

    def get_top_diagnoses(self, user, limit=5, date_from=None, date_to=None):
        visits = self.get_accessible_visits(user, date_from, date_to)
        return self._top(VisitDiagnosis.objects.filter(visit__in=visits), 'diagnosis', limit)

    def get_top_medications(self, user, limit=5, date_from=None, date_to=None):
        visits = self.get_accessible_visits(user, date_from, date_to)
        return self._top(VisitMedication.objects.filter(visit__in=visits), 'medication', limit)

    def get_followup_stats(self, user, date_from=None, date_to=None):
        visits = self.get_accessible_visits(user, date_from, date_to)
        today = timezone.localdate()
        completed = visits.filter(follow_up_date__isnull=False, follow_up_outcome='completed').count()
        overdue = visits.filter(follow_up_date__lt=today, follow_up_outcome__in=['pending', 'missed']).count()
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

    def get_avg_visits_per_patient(self, user, date_from=None, date_to=None):
        total_patients = self.get_total_patients(user)
        if total_patients == 0:
            return 0
        return self.get_total_visits(user, date_from, date_to) / total_patients

    def get_high_risk_patients(self, user, limit=20):
        patients = self.get_accessible_patients(user)
        latest = self.get_accessible_visits(user).filter(patient_id=OuterRef('pk')).exclude(status='draft').order_by('-visit_date', '-pk')
        return patients.annotate(latest_suicide=Subquery(latest.values('suicide_risk_level')[:1]),
            latest_violence=Subquery(latest.values('violence_risk_level')[:1])).filter(
            Q(latest_suicide='High') | Q(latest_violence='High')).order_by('pk')[:limit]

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

        from datetime import date
        from dateutil.relativedelta import relativedelta
        start = date(year, month, 1)
        end = start + relativedelta(months=1, days=-1)
        diag_list = [dict(name=name, count=count) for name, count in self.get_top_diagnoses(user, 1000, start, end)]
        med_list = [dict(name=name, count=count) for name, count in self.get_top_medications(user, 1000, start, end)]

        return {
            'year': year,
            'month': month,
            'total_visits': total_visits,
            'diagnoses': diag_list,
            'medications': med_list,
        }
