from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VisitViewSet

router = DefaultRouter()
router.register(r'', VisitViewSet, basename='visits')

urlpatterns = [
    path('', include(router.urls)),
    # Nested patient visits route has been moved to patients/urls.py
    # to keep the URL prefix consistent: /api/v1/patients/<pk>/visits/
]