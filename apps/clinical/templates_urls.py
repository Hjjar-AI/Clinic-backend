from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .templates_views import TemplateViewSet

router = DefaultRouter()
router.register(r'', TemplateViewSet, basename='templates')

urlpatterns = [
    path('', include(router.urls)),
]