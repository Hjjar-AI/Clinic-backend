# backend/apps/dashboard/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .services import DashboardService
from core.permissions import PERM_VIEW_REPORTS, HasViewReports
from core.query_utils import parse_date_range

class DashboardView(APIView):
    permission_classes = [IsAuthenticated]
    service = DashboardService()

    def get(self, request):
        date_from, date_to = parse_date_range(request.query_params)

        data = self.service.get_dashboard_data(request.user, date_from, date_to)
        return Response({'data': data})


class ChartsView(APIView):
    permission_classes = [IsAuthenticated, HasViewReports]
    service = DashboardService()

    def get(self, request):
        date_from, date_to = parse_date_range(request.query_params)

        data = self.service.get_chart_data(request.user, date_from, date_to)
        return Response({'data': data})


class SummaryView(APIView):
    permission_classes = [IsAuthenticated]
    service = DashboardService()

    def get(self, request):
        data = self.service.get_summary(request.user)
        return Response({'data': data})
