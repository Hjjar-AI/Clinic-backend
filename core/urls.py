from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AuditLogViewSet

router = DefaultRouter()
router.register(r'audit-logs', AuditLogViewSet, basename='audit-logs')

urlpatterns = [
    path('auth/', include('apps.accounts.urls')),
    path('patients/', include('apps.patients.urls')),
    path('visits/', include('apps.visits.urls')),
    path('appointments/', include('apps.appointments.urls')),
    path('options/', include('apps.clinical.urls')),
    path('billing/', include('apps.billing.urls')),
    path('tasks/', include('apps.tasks.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('backup/', include('apps.backup.urls')),
    path('reports/', include('apps.reports.urls')),
    path('bulk-import/', include('apps.import_export.urls')),
    path('prescription/', include('apps.prescriptions.urls')),
    path('referrals/', include('apps.referrals.urls')),
    path('scales/', include('apps.clinical.scales_urls')),
    path('templates/', include('apps.clinical.templates_urls')),
    path('dashboard/', include('apps.dashboard.urls')),
    path('exports/', include('apps.exports.urls')),
    path('settings/', include('apps.settings.urls')),
    path('system/', include('apps.system.urls')),
    path('', include(router.urls)),
]