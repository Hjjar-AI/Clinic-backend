from django.urls import path
from .views import PrescriptionPreviewView, PrescriptionGenerateView, PrescriptionCalibrationView, PrescriptionHistoryView, PrescriptionDocumentView, ClinicalHandoverView

urlpatterns = [
    path('patient/<int:patient_id>/handover/', ClinicalHandoverView.as_view(), name='latest-clinical-handover'),
    path('visit/<int:visit_id>/handover/', ClinicalHandoverView.as_view(), name='clinical-handover'),
    path('visit/<int:visit_id>/handover/pdf/', ClinicalHandoverView.as_view(), {'pdf': True}, name='clinical-handover-pdf'),
    path('patient/<int:patient_id>/history/', PrescriptionHistoryView.as_view(), name='prescription-history'),
    path('documents/<int:document_id>/pdf/', PrescriptionDocumentView.as_view(), name='prescription-document'),
    path('documents/<int:document_id>/instructions/', PrescriptionDocumentView.as_view(), {'instructions': True}, name='prescription-instructions'),
    path('calibration/', PrescriptionCalibrationView.as_view(), name='prescription-calibration'),
    path('visit/<int:visit_id>/', PrescriptionPreviewView.as_view(), name='prescription-preview'),
    path('generate/', PrescriptionGenerateView.as_view(), name='prescription-generate'),
]
