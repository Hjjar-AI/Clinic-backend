# backend/apps/settings/urls.py
from django.urls import path
from .views import SettingsView, ThemeView, GenerateDemoDataView

urlpatterns = [
    path('', SettingsView.as_view(), name='settings'),
    path('theme/', ThemeView.as_view(), name='theme'),
    path('generate-demo-data/', GenerateDemoDataView.as_view(), name='generate-demo-data'),
]