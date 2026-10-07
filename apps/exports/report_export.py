from core.spreadsheets import text_cells
# backend/apps/exports/report_export.py
from openpyxl import Workbook
from django.http import HttpResponse
from datetime import datetime
from .base import BaseExportService

class ReportExportService(BaseExportService):
    def export_reports_excel(self, user, filters=None):
        visits = self.filtered_visits(user, filters)
        wb = Workbook()
        ws = wb.active
        ws.title = 'التقارير'
        ws.append(['المريض', 'تاريخ الزيارة', 'التشخيصات', 'الأدوية', 'حالة التوثيق', 'الحالة السريرية', 'ملاحظات الطبيب'])
        for v in visits:
            diagnoses = ', '.join(d.get('arabic_name') or d.get('name', '') for d in v.get_diagnoses())
            medications = ', '.join(m.get('name', '') for m in v.get_medications())
            ws.append([
                v.patient.get_full_name(),
                v.visit_date.isoformat() if v.visit_date else '',
                diagnoses,
                medications,
                v.status or '',
                v.clinical_status or '',
                v.doctor_notes or '',
            ])
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="clinic_reports_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        text_cells(ws)
        wb.save(response)
        return self.stamp_response(response)
