from django.urls import path
from .views import StatisticsView, MonthlySummaryView, DoctorPerformanceView, ReconciliationView

urlpatterns = [
    path('statistics/', StatisticsView.as_view(), name='statistics'),
    path('monthly-summary/', MonthlySummaryView.as_view(), name='monthly-summary'),
    path('doctor-performance/', DoctorPerformanceView.as_view(), name='doctor-performance'),
    path('reconciliation/', ReconciliationView.as_view(), name='reconciliation'),
]
