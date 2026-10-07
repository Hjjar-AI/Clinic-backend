from django.urls import path
from .views import (
    BulkImportView,
    BulkImportPreviewView,
    BulkImportTemplateView,
    OptionsImportView,
    MedicationUploadView,
    MedicationMapView,
)

urlpatterns = [
    path('', BulkImportView.as_view(), name='bulk-import'),
    path('preview/', BulkImportPreviewView.as_view(), name='bulk-import-preview'),
    path('template/', BulkImportTemplateView.as_view(), name='bulk-import-template'),
    path('options/', OptionsImportView.as_view(), name='options-import'),
    path('medications/upload/', MedicationUploadView.as_view(), name='medication-upload'),
    path('medications/map/', MedicationMapView.as_view(), name='medication-map'),
]
