from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PatientViewSet, PatientDocumentViewSet
from apps.visits.views import VisitViewSet

router = DefaultRouter()
router.register(r'', PatientViewSet, basename='patients')

# Nested documents
patient_document_router = DefaultRouter()
patient_document_router.register(r'documents', PatientDocumentViewSet, basename='patient-documents')

urlpatterns = [
    path('', include(router.urls)),
    # Nested visits endpoint: /api/v1/patients/<patient_pk>/visits/
    path('<int:patient_pk>/visits/', VisitViewSet.as_view({'post': 'create', 'get': 'list'}), name='patient-visits'),
    # Nested documents endpoint: /api/v1/patients/<patient_pk>/documents/
    path('<int:patient_pk>/', include(patient_document_router.urls)),
]