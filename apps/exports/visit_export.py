# backend/apps/exports/visit_export.py
import csv
import io
from openpyxl import Workbook
from django.http import HttpResponse
from datetime import datetime
from .base import BaseExportService

class VisitExportService(BaseExportService):
    def export_visits_csv(self, user, filters=None):
        visits = self.filtered_visits(user, filters)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['المريض', 'تاريخ الزيارة', 'الشكوى', 'حالة التوثيق', 'الحالة السريرية'])
        for v in visits:
            writer.writerow([
                v.patient.get_full_name(),
                v.visit_date.isoformat() if v.visit_date else '',
                v.main_complaints or '',
                v.status or '',
                v.clinical_status or '',
            ])
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="visits_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        return self.stamp_response(response)

    def export_visits_excel(self, user, filters=None):
        visits = self.filtered_visits(user, filters)
        wb = Workbook()
        ws = wb.active
        ws.title = 'الزيارات'
        ws.append(['المريض', 'تاريخ الزيارة', 'الشكوى', 'حالة التوثيق', 'الحالة السريرية'])
        for v in visits:
            ws.append([
                v.patient.get_full_name(),
                v.visit_date.isoformat() if v.visit_date else '',
                v.main_complaints or '',
                v.status or '',
                v.clinical_status or '',
            ])
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="visits_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        wb.save(response)
        return self.stamp_response(response)

    def export_visit_pdf(self, visit):
        data = self.build_visit_pdf_data(visit)
        html = self.render_to_string('visit_pdf.html', {'data': data, 'clinic': self.get_clinic_info()})
        return self.render_pdf(html)
