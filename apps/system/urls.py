from django.urls import path
from .views import HealthView, HealthFullView, VersionView, ConfigView, FeedbackView, StatusConstantsView, ClearCacheView

urlpatterns = [
    path('health/', HealthView.as_view(), name='health'),
    path('health/full/', HealthFullView.as_view(), name='health-full'),
    path('version/', VersionView.as_view(), name='version'),
    path('config/', ConfigView.as_view(), name='config'),
    path('feedback/', FeedbackView.as_view(), name='feedback'),
    path('status-constants/', StatusConstantsView.as_view(), name='status-constants'),
    path('cache/clear/', ClearCacheView.as_view(), name='cache-clear'),
]