# backend/apps/exports/visit_export.py
import csv
import io
from openpyxl import Workbook
from core.spreadsheets import csv_cell, text_cells
from django.http import HttpResponse
from datetime import datetime
from .base import BaseExportService

VISIT_COLUMNS = ['المريض', 'تاريخ الزيارة', 'الشكوى', 'حالة التوثيق', 'الحالة السريرية']


def visit_export_row(visit):
    return [visit.patient.get_full_name(), visit.visit_date.isoformat() if visit.visit_date else '',
            visit.main_complaints or '', visit.status or '', visit.clinical_status or '']


class VisitExportService(BaseExportService):
    def export_visits_csv(self, user, filters=None):
        visits = self.filtered_visits(user, filters)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(VISIT_COLUMNS)
        for v in visits:
            writer.writerow([csv_cell(value) for value in visit_export_row(v)])
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="visits_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        return self.stamp_response(response)

    def export_visits_excel(self, user, filters=None):
        visits = self.filtered_visits(user, filters)
        wb = Workbook()
        ws = wb.active
        ws.title = 'الزيارات'
        ws.append(VISIT_COLUMNS)
        for v in visits:
            ws.append(visit_export_row(v))
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="visits_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        for sheet in wb.worksheets:
            text_cells(sheet)
        wb.save(response)
        return self.stamp_response(response)

    def export_visit_pdf(self, visit):
        data = self.build_visit_pdf_data(visit)
        html = self.render_to_string('visit_pdf.html', {'data': data, 'clinic': self.get_clinic_info()})
        return self.render_pdf(html)
