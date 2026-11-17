from core.mutation import request_version
# backend/apps/billing/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Invoice
from .serializers import InvoiceSerializer
from .services import BillingService
from core.permissions import (
    PERM_VIEW_BILLING,
    PERM_MANAGE_BILLING,
    HasViewBilling,
    HasManageBilling,
    CanAccessInvoice,
)
from apps.patients.models import Patient
from apps.visits.models import Visit
from datetime import datetime
from core.exceptions import error_response
from django.core.exceptions import ValidationError
from core.query_utils import apply_ordering
from django.db.models import Q
from django.http import HttpResponse
from core.pdf_utils import render_pdf_from_html
from django.template.loader import render_to_string
from apps.settings.services import SettingsService
from core.signals import log_action
from django.utils import timezone
from core.lifecycle import STATUS_PRESENTATION


class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    service = BillingService()

    def get_permissions(self):
        if self.action in ['create']:
            permission_classes = [permissions.IsAuthenticated, HasManageBilling]
        elif self.action in ['update', 'partial_update', 'destroy', 'transition', 'visits_for_patient']:
            permission_classes = [permissions.IsAuthenticated, HasManageBilling, CanAccessInvoice]
        elif self.action in ['retrieve', 'pdf']:
            permission_classes = [permissions.IsAuthenticated, HasViewBilling, CanAccessInvoice]
        else:
            permission_classes = [permissions.IsAuthenticated, HasViewBilling]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        from .selectors import list_queryset
        return list_queryset(self.request.user, self.request.query_params, self.kwargs)

    def perform_create(self, serializer):
        instance = self.service.create_invoice(serializer.validated_data, self.request.user)
        serializer.instance = instance

    def perform_update(self, serializer):
        instance = self.get_object()
        version = request_version(self.request)
        data = serializer.validated_data.copy()
        data.pop('version', None)
        serializer.instance = self.service.update_invoice(instance, data, version, actor=self.request.user)

    def perform_destroy(self, instance):
        self.service.delete_invoice(instance, request_version(self.request), actor=self.request.user)

    @action(detail=True, methods=['put'])
    def transition(self, request, pk=None):
        invoice = self.get_object()
        target = request.data.get('status')
        if not target:
            return error_response(400, 'status is required', {'status': ['هذا الحقل مطلوب']})
        version = request_version(request)
        updated = self.service.transition(
            invoice, target, request.user, version, request.data.get('reason', ''), payment_method=request.data.get('payment_method')
        )
        return Response({'data': self.get_serializer(updated).data})

    @action(detail=False, methods=['get'], url_path='visits_for_patient')
    def visits_for_patient(self, request):
        patient_id = request.query_params.get('patient_id')
        if not patient_id:
            return error_response(400, 'patient_id required', {})
        try:
            patient_id = int(patient_id)
        except (TypeError, ValueError):
            return error_response(400, 'patient_id must be an integer', {})
        from .selectors import visits_for_patient
        return Response({'data': visits_for_patient(request.user, patient_id)})

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        invoice = self.get_object()
        from .documents import invoice_pdf
        pdf = invoice_pdf(invoice, request.user)
        if not pdf:
            return error_response(503, 'تعذر إنشاء ملف الفاتورة', {})
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
        return response
