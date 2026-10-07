from django.urls import path
from .views import PrescriptionPreviewView, PrescriptionGenerateView

urlpatterns = [
    path('visit/<int:visit_id>/', PrescriptionPreviewView.as_view(), name='prescription-preview'),
    path('generate/', PrescriptionGenerateView.as_view(), name='prescription-generate'),
]