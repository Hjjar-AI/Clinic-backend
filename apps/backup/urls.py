from django.urls import path
from .views import BackupView, RestorePreviewView, RestoreExecuteView

urlpatterns = [
    path('', BackupView.as_view(), name='backup'),
    path('restore/preview/', RestorePreviewView.as_view(), name='restore-preview'),
    path('restore/execute/', RestoreExecuteView.as_view(), name='restore-execute'),
]