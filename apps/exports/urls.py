from django.urls import path
from .views import (
    ExportPatientsCSV,
    ExportPatientsExcel,
    ExportVisitsCSV,
    ExportVisitsExcel,
    ExportDiagnosesExcel,
    ExportMedicationsExcel,
    ExportReportsExcel,
    ExportPatientPDF,
    ExportPatientWord,
    ExportVisitPDF,
)

urlpatterns = [
    path('patients/csv/', ExportPatientsCSV.as_view(), name='export-patients-csv'),
    path('patients/excel/', ExportPatientsExcel.as_view(), name='export-patients-excel'),
    path('visits/csv/', ExportVisitsCSV.as_view(), name='export-visits-csv'),
    path('visits/excel/', ExportVisitsExcel.as_view(), name='export-visits-excel'),
    path('diagnoses/excel/', ExportDiagnosesExcel.as_view(), name='export-diagnoses-excel'),
    path('medications/excel/', ExportMedicationsExcel.as_view(), name='export-medications-excel'),
    path('reports/excel/', ExportReportsExcel.as_view(), name='export-reports-excel'),
    path('patients/<int:patient_id>/pdf/', ExportPatientPDF.as_view(), name='export-patient-pdf'),
    path('patients/<int:patient_id>/word/', ExportPatientWord.as_view(), name='export-patient-word'),
    path('visits/<int:visit_id>/pdf/', ExportVisitPDF.as_view(), name='export-visit-pdf'),
]