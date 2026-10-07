from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DiagnosisViewSet, MedicationViewSet, ClinicalConstantsView

router = DefaultRouter()
router.register(r'diagnoses', DiagnosisViewSet, basename='diagnoses')
router.register(r'medications', MedicationViewSet, basename='medications')

urlpatterns = [
    path('', include(router.urls)),
    path('clinical-constants/', ClinicalConstantsView.as_view(), name='clinical-constants'),
]