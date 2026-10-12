from django.urls import path
from .views import PrescriptionPreviewView, PrescriptionGenerateView, PrescriptionCalibrationView

urlpatterns = [
    path('calibration/', PrescriptionCalibrationView.as_view(), name='prescription-calibration'),
    path('visit/<int:visit_id>/', PrescriptionPreviewView.as_view(), name='prescription-preview'),
    path('generate/', PrescriptionGenerateView.as_view(), name='prescription-generate'),
]