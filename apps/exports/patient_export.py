from core.spreadsheets import csv_cell, text_cells
from django.core.exceptions import ValidationError
# backend/apps/exports/patient_export.py
import csv
import io
from openpyxl import Workbook
from django.http import HttpResponse
from datetime import datetime
from .base import BaseExportService
from apps.patients.services import PatientService

class PatientExportService(BaseExportService):
    def _patients(self, user, filters=None):
        return PatientService().list_patients(user, filters or {})

    def export_patients_csv(self, user, fields=None, filters=None):
        patients = self._patients(user, filters)
        field_map = {
            'full_name': ('الاسم الكامل', lambda p: p.get_full_name()),
            'national_id': ('الرقم الوطني', lambda p: p.national_id or ''),
            'phone': ('الهاتف', lambda p: p.phone or ''),
            'gender': ('الجنس', lambda p: p.gender or ''),
            'dob_year': ('سنة الميلاد', lambda p: str(p.dob_year or '')),
            'address': ('العنوان', lambda p: p.permanent_address or ''),
            'registration_date': ('تاريخ الإضافة', lambda p: p.registration_date.strftime('%d/%m/%Y') if p.registration_date else ''),
            'doctor': ('فريق الرعاية', lambda p: '، '.join(member.user.full_name or member.user.username for member in p.care_team.filter(ended_at__isnull=True).select_related('user'))),
            'patient_number': ('رقم الملف', lambda p: p.patient_number),
            'completeness': ('اكتمال الملف', lambda p: f"{p.get_completeness()['percent']}%"),
        }
        if fields is not None and (not isinstance(fields, list) or not fields or any(f not in field_map for f in fields)):
            raise ValidationError({'fields': ['أعمدة غير صالحة']})
        if fields is None:
            fields = ['full_name', 'national_id', 'phone', 'registration_date']

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([field_map[f][0] for f in fields if f in field_map])
        for p in patients:
            row = [field_map[f][1](p) for f in fields if f in field_map]
            writer.writerow([csv_cell(value) for value in row])
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="patients_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        return self.stamp_response(response)

    def export_patients_excel(self, user, fields=None, filters=None):
        patients = self._patients(user, filters)
        field_map = {
            'full_name': ('الاسم الكامل', lambda p: p.get_full_name()),
            'national_id': ('الرقم الوطني', lambda p: p.national_id or ''),
            'phone': ('الهاتف', lambda p: p.phone or ''),
            'gender': ('الجنس', lambda p: p.gender or ''),
            'dob_year': ('سنة الميلاد', lambda p: p.dob_year or ''),
            'address': ('العنوان', lambda p: p.permanent_address or ''),
            'registration_date': ('تاريخ الإضافة', lambda p: p.registration_date.strftime('%d/%m/%Y') if p.registration_date else ''),
            'doctor': ('فريق الرعاية', lambda p: '، '.join(member.user.full_name or member.user.username for member in p.care_team.filter(ended_at__isnull=True).select_related('user'))),
            'patient_number': ('رقم الملف', lambda p: p.patient_number),
            'completeness': ('اكتمال الملف', lambda p: f"{p.get_completeness()['percent']}%"),
        }
        if fields is not None and (not isinstance(fields, list) or not fields or any(f not in field_map for f in fields)):
            raise ValidationError({'fields': ['أعمدة غير صالحة']})
        fields = fields or []
        if not fields:
            fields = ['full_name', 'national_id', 'phone', 'address', 'registration_date', 'doctor']
        wb = Workbook()
        ws = wb.active
        ws.title = 'المرضى'
        ws.append([field_map[field][0] for field in fields])
        for p in patients:
            ws.append([field_map[field][1](p) for field in fields])
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="patients_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
        text_cells(ws)
        wb.save(response)
        return self.stamp_response(response)

    def export_patient_pdf(self, patient):
        report_data = self.build_patient_report_data(patient)
        clinic_info = self.get_clinic_info()
        html = self.render_to_string('exports/patient_pdf.html', {'report_data': report_data, 'clinic': clinic_info})
        return self.render_pdf(html)

    def export_patient_word(self, patient):
        clinic_info = self.get_clinic_info()
        return self.export_patient_to_word(patient, clinic_info)
