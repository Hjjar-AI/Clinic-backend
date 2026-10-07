from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InvoiceViewSet

router = DefaultRouter()
router.register(r'', InvoiceViewSet, basename='billing')

urlpatterns = [
    path('', include(router.urls)),
]