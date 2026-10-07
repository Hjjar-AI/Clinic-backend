from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .scales_views import ScaleViewSet

router = DefaultRouter()
router.register(r'', ScaleViewSet, basename='scales')

urlpatterns = [
    path('', include(router.urls)),
]