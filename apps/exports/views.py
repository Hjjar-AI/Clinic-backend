# backend/apps/exports/views.py
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from django.template.loader import render_to_string
from apps.patients.models import Patient
from apps.visits.models import Visit
from .patient_export import PatientExportService
from .visit_export import VisitExportService
from .clinical_data_export import ClinicalDataExportService
from .report_export import ReportExportService
from core.pdf_utils import render_pdf_from_html
from core.permissions import (
    PERM_EXPORT_PDF,
    PERM_EXPORT_WORD,
    PERM_EXPORT_REPORTS,
    PERM_MANAGE_OPTIONS,
    PERM_EXPORT_OPTIONS,
    HasExportPdf,
    HasExportWord,
    HasExportReports,
    HasManageOptions,
    HasExportOptions,
)
from core.exceptions import error_response
from core.signals import log_action


class ExportPatientsCSV(APIView):
    permission_classes = [IsAuthenticated, HasExportReports]
    service = PatientExportService()

    def get(self, request):
        fields = request.query_params.getlist('fields')
        if len(fields) == 1 and ',' in fields[0]:
            fields = fields[0].split(',')
        response = self.service.export_patients_csv(request.user, fields, request.query_params)
        log_action(request.user.id, 'export', 'Patient', None, {
            'summary': 'Patient CSV export', 'filters': request.query_params.dict(),
        })
        return response

class ExportPatientsExcel(APIView):
    permission_classes = [IsAuthenticated, HasExportReports]
    service = PatientExportService()

    def get(self, request):
        fields = request.query_params.getlist('fields')
        if len(fields) == 1 and ',' in fields[0]:
            fields = fields[0].split(',')
        response = self.service.export_patients_excel(request.user, fields, request.query_params)
        log_action(request.user.id, 'export', 'Patient', None, {
            'summary': 'Patient Excel export', 'filters': request.query_params.dict(),
        })
        return response

class ExportVisitsCSV(APIView):
    permission_classes = [IsAuthenticated, HasExportReports]
    service = VisitExportService()

    def get(self, request):
        response = self.service.export_visits_csv(request.user, request.query_params)
        log_action(request.user.id, 'export', 'Visit', None, {
            'summary': 'Visit CSV export', 'filters': request.query_params.dict(),
        })
        return response

class ExportVisitsExcel(APIView):
    permission_classes = [IsAuthenticated, HasExportReports]
    service = VisitExportService()

    def get(self, request):
        response = self.service.export_visits_excel(request.user, request.query_params)
        log_action(request.user.id, 'export', 'Visit', None, {
            'summary': 'Visit Excel export', 'filters': request.query_params.dict(),
        })
        return response

class ExportDiagnosesExcel(APIView):
    permission_classes = [IsAuthenticated, HasExportOptions | HasManageOptions]  # OR condition
    service = ClinicalDataExportService()

    def get(self, request):
        include_inactive = request.user.has_perm(PERM_MANAGE_OPTIONS)
        response = self.service.export_diagnoses_excel(request.query_params, include_inactive)
        log_action(request.user.id, 'export', 'DiagnosisOption', None, {
            'summary': 'Diagnosis options export', 'filters': request.query_params.dict(),
        })
        return response

class ExportMedicationsExcel(APIView):
    permission_classes = [IsAuthenticated, HasExportOptions | HasManageOptions]
    service = ClinicalDataExportService()

    def get(self, request):
        include_inactive = request.user.has_perm(PERM_MANAGE_OPTIONS)
        response = self.service.export_medications_excel(request.query_params, include_inactive)
        log_action(request.user.id, 'export', 'MedicationOption', None, {
            'summary': 'Medication options export', 'filters': request.query_params.dict(),
        })
        return response

class ExportReportsExcel(APIView):
    permission_classes = [IsAuthenticated, HasExportReports]
    service = ReportExportService()

    def get(self, request):
        response = self.service.export_reports_excel(request.user, request.query_params)
        log_action(request.user.id, 'export', 'Report', None, {
            'summary': 'Reports Excel export', 'filters': request.query_params.dict(),
        })
        return response

class ExportPatientPDF(APIView):
    permission_classes = [IsAuthenticated, HasExportPdf]
    service = PatientExportService()

    def get(self, request, patient_id):
        patient = self.service.stats.get_accessible_patients(request.user).filter(id=patient_id).first()
        if not patient:
            return error_response(404, 'المريض غير موجود أو غير مصرح', {})
        pdf = self.service.export_patient_pdf(patient)
        if pdf:
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="patient_{patient_id}.pdf"'
            log_action(request.user.id, 'export', 'Patient', patient_id, {'summary': 'Patient PDF export'})
            return response
        return error_response(503, 'PDF generation failed', {})

class ExportPatientWord(APIView):
    permission_classes = [IsAuthenticated, HasExportWord]
    service = PatientExportService()

    def get(self, request, patient_id):
        patient = self.service.stats.get_accessible_patients(request.user).filter(id=patient_id).first()
        if not patient:
            return error_response(404, 'المريض غير موجود أو غير مصرح', {})
        buffer = self.service.export_patient_word(patient)
        if buffer:
            response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
            response['Content-Disposition'] = f'attachment; filename="patient_{patient_id}.docx"'
            log_action(request.user.id, 'export', 'Patient', patient_id, {'summary': 'Patient Word export'})
            return response
        return error_response(503, 'Word generation failed', {})

class ExportVisitPDF(APIView):
    permission_classes = [IsAuthenticated, HasExportPdf]
    service = VisitExportService()

    def get(self, request, visit_id):
        visit = self.service.stats.get_accessible_visits(request.user).filter(id=visit_id).first()
        if not visit:
            return error_response(404, 'الزيارة غير موجودة أو غير مصرح', {})
        pdf = self.service.export_visit_pdf(visit)
        if pdf:
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="visit_{visit_id}.pdf"'
            log_action(request.user.id, 'export', 'Visit', visit_id, {'summary': 'Visit PDF export'})
            return response
        return error_response(503, 'PDF generation failed', {})
