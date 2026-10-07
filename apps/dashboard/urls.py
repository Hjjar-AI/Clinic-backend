from django.urls import path
from .views import DashboardView, ChartsView, SummaryView

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('charts/', ChartsView.as_view(), name='dashboard-charts'),
    path('summary/', SummaryView.as_view(), name='dashboard-summary'),
]