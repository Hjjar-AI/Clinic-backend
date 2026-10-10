import csv
import io
from datetime import date
from decimal import Decimal
from django.utils import timezone
from apps.appointments.services import AppointmentService
from apps.billing.services import BillingService
from apps.dashboard.services import DashboardService
from apps.patients.services import PatientService
from apps.reports.services import StatisticsService
from .base import ClinicTestCase


class ReportingTests(ClinicTestCase):
    def test_patient_statistics_exclude_unknown_demographics_from_known_groups(self):
        self.patient_for(self.doctor, dob_year=2000, gender='ذكر')
        self.patient_for(self.other_doctor, dob_year=1990, gender='أنثى')
        stats = StatisticsService()
        self.assertEqual(stats.get_total_patients(self.doctor), 2)
        self.assertEqual(stats.get_gender_breakdown(self.doctor), (1, 0, 100))
        self.assertEqual(stats.get_average_age(self.doctor), timezone.localdate().year - 2000)
        self.assertEqual(sum(stats.get_age_distribution(self.doctor)[1]), 1)
        self.assertEqual(stats.get_total_patients(self.other_doctor), 1)

    def test_monthly_visits_fill_empty_periods_and_enforce_scope(self):
        self.visit_for(visit_date=date(2026, 2, 10))
        hidden = self.patient_for(self.other_doctor)
        self.visit_for(hidden, self.other_doctor, visit_date=date(2026, 1, 10))
        labels, counts = StatisticsService().get_monthly_visits(self.doctor, date_from=date(2026, 1, 1), date_to=date(2026, 3, 31))
        self.assertEqual(len(labels), 3)
        self.assertEqual(counts, [0, 1, 0])

    def test_reconciliation_revenue_counts_only_paid_invoices(self):
        service = BillingService()
        for status, amount in [('draft', '90.00'), ('issued', '70.00'), ('paid', '12.50'), ('cancelled', '80.00')]:
            invoice = service.create_invoice({'patient': self.patient, 'total_amount': amount})
            if status in {'issued', 'paid'}:
                invoice = service.transition(invoice, 'issued', self.admin, invoice.version)
            if status == 'paid':
                service.transition(invoice, 'paid', self.admin, invoice.version, payment_method='cash')
            if status == 'cancelled':
                service.transition(invoice, 'cancelled', self.admin, invoice.version, reason='Synthetic cancellation')
        report = StatisticsService().get_reconciliation()['invoices']
        self.assertEqual(report['total'], 4)
        self.assertEqual(report['by_status'], {'cancelled': 1, 'draft': 1, 'issued': 1, 'paid': 1})
        self.assertEqual(Decimal(report['paid_amount']), Decimal('12.50'))

    def test_cancelled_appointments_do_not_inflate_active_counts(self):
        service = AppointmentService()
        for hour in ('10:00', '11:00'):
            row = service.create_appointment({'patient': self.patient, 'doctor': self.doctor,
                'appointment_date': timezone.localdate(), 'appointment_time': hour, 'duration_minutes': 30})
        service.cancel(row, row.version, 'Synthetic cancellation')
        stats = StatisticsService()
        self.assertEqual(stats.get_total_appointments(self.doctor), 1)
        self.assertEqual(stats.get_appointments_today(self.doctor), 1)
        self.assertEqual(stats.get_total_appointments(self.other_doctor), 0)

    def test_dashboard_preserves_patient_scope(self):
        private = self.patient_for(self.other_doctor)
        self.visit_for(private, self.other_doctor)
        dashboard = DashboardService().get_dashboard_data(self.doctor)
        self.assertEqual(dashboard['total_patients'], 1)
        self.assertNotIn(private.pk, [row['id'] for row in dashboard['recent_patients']])
        self.assertEqual(dashboard['total_visits'], 0)

    def test_dashboard_redacts_groups_when_permission_removed(self):
        self.doctor.groups.clear()
        self.doctor.user_permissions.clear()
        self.doctor.clear_permission_cache()
        result = DashboardService().get_dashboard_data(self.doctor)
        self.assertFalse(self.doctor.has_perm('view_patients'))
        self.assertIsNone(result['total_patients'])
        self.assertEqual(result['recent_patients'], [])

    def test_patient_csv_export_is_scoped_filtered_and_formula_safe(self):
        self.patient_for(self.doctor, first_name='=SYNTHETIC()', surname='CsvPublic')
        self.patient_for(self.other_doctor, surname='CsvPrivate')
        self.api.force_login(self.doctor)
        # Explicit export grant while retaining doctor patient scope.
        from django.contrib.auth.models import Permission
        self.doctor.user_permissions.add(Permission.objects.get(codename='export_reports'))
        self.doctor.clear_permission_cache()
        response = self.api.get('/api/v1/exports/patients/csv/', {'search': 'CsvPublic'})
        self.assertEqual(response.status_code, 200)
        body = b''.join(response.streaming_content) if response.streaming else response.content
        rows = list(csv.reader(io.StringIO(body.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 2)
        flattened = ' '.join(rows[1])
        self.assertNotIn('CsvPrivate', flattened)
        self.assertIn("'=SYNTHETIC()", flattened)

    def test_invalid_report_dates_and_months_fail_cleanly(self):
        for path, params in [('/api/v1/reports/statistics/', {'date_from': 'bad'}),
            ('/api/v1/reports/statistics/', {'date_from': '2026-03-01', 'date_to': '2026-01-01'}),
            ('/api/v1/reports/monthly-summary/', {'year': '2026', 'month': '13'})]:
            with self.subTest(path=path, params=params):
                self.assertEqual(self.api.get(path, params).status_code, 400)

    def test_default_patient_excel_has_real_workbook_and_scoped_rows(self):
        from openpyxl import load_workbook
        self.patient_for(self.other_doctor, surname='PrivateWorkbook')
        self.api.force_login(self.doctor)
        response = self.api.get('/api/v1/exports/patients/excel/')
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(io.BytesIO(response.content), read_only=True)
        try:
            rows = list(workbook.active.values)
            self.assertEqual(len(rows), 2)
            self.assertNotIn('PrivateWorkbook', str(rows))
        finally:
            workbook.close()

    def test_explicit_invalid_export_columns_fail_instead_of_using_defaults(self):
        for extension in ('csv', 'excel'):
            with self.subTest(extension=extension):
                response = self.api.get(f'/api/v1/exports/patients/{extension}/', {'fields': 'password'})
                self.assertEqual(response.status_code, 400)
