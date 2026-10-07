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
from apps.patients.services import PatientService
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
        user = self.request.user
        qs = Invoice.objects.select_related('patient', 'visit')
        if user.role == 'admin':
            pass
        elif user.role == 'doctor':
            qs = qs.filter(patient__doctor=user)
        elif user.role == 'receptionist':
            qs = qs.filter(patient__created_by=user)
        else:
            qs = qs.none()

        status_param = self.request.query_params.get('status')
        if status_param == 'overdue':
            qs = qs.filter(status='issued', due_date__lt=timezone.localdate())
        elif status_param:
            qs = qs.filter(status=status_param)

        date_from = self.request.query_params.get('date_from')
        if date_from:
            try:
                date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
                qs = qs.filter(issued_date__gte=date_from_parsed)
            except ValueError:
                raise ValidationError({'date_from': ['صيغة التاريخ يجب أن تكون YYYY-MM-DD']})

        date_to = self.request.query_params.get('date_to')
        if date_to:
            try:
                date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
                qs = qs.filter(issued_date__lte=date_to_parsed)
            except ValueError:
                raise ValidationError({'date_to': ['صيغة التاريخ يجب أن تكون YYYY-MM-DD']})

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(invoice_number__icontains=search)
                | Q(patient__first_name__icontains=search)
                | Q(patient__surname__icontains=search)
            )
        return apply_ordering(qs, self.request.query_params, {
            'invoice_number': 'invoice_number', 'patient': 'patient__surname',
            'amount': 'final_amount', 'status': 'status', 'issued_date': 'issued_date',
        })

    def perform_create(self, serializer):
        patient = serializer.validated_data['patient']
        if not PatientService().list_patients(self.request.user, {}).filter(pk=patient.pk).exists():
            self.permission_denied(self.request)
        instance = self.service.create_invoice(serializer.validated_data)
        serializer.instance = instance

    def perform_update(self, serializer):
        instance = self.get_object()
        version = self.request.data.get('version')
        if version is not None:
            try:
                version = int(version)
            except (ValueError, TypeError):
                version = None
        data = serializer.validated_data.copy()
        data.pop('version', None)
        serializer.instance = self.service.update_invoice(instance, data, version)

    def perform_destroy(self, instance):
        self.service.delete_invoice(instance)

    @action(detail=True, methods=['put'])
    def transition(self, request, pk=None):
        invoice = self.get_object()
        target = request.data.get('status')
        if not target:
            return error_response(400, 'status is required', {'status': ['هذا الحقل مطلوب']})
        version = request.data.get('version')
        if version is None:
            raise ValidationError({'version': ['يجب توفير رقم الإصدار']})
        try:
            version = int(version)
        except (ValueError, TypeError):
            raise ValidationError({'version': ['رقم الإصدار غير صالح']})
        updated = self.service.transition(
            invoice, target, request.user, version, request.data.get('reason', '')
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
        patient = Patient.objects.filter(id=patient_id).first()
        if not patient:
            return error_response(404, 'المريض غير موجود', {})
        user = self.request.user
        if user.role == 'doctor' and patient.doctor_id != user.id:
            return error_response(403, 'غير مصرح', {})
        if user.role == 'receptionist' and patient.created_by_id != user.id:
            return error_response(403, 'غير مصرح', {})
        qs = Visit.objects.filter(patient_id=patient_id)
        if user.role == 'doctor':
            qs = qs.filter(patient__doctor=user)
        elif user.role == 'receptionist':
            qs = qs.filter(patient__created_by=user)
        # Billing only needs a small visit selector. Do not expose the full
        # clinical visit serializer (notes, diagnoses, risk data) here.
        visits = list(qs.order_by('-visit_date').values(
            'id', 'visit_date', 'status', 'main_complaints'
        ))
        return Response({'data': {'visits': visits}})

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        invoice = self.get_object()
        clinic_info = SettingsService().get_clinic_info()
        clinic = {
            'name': clinic_info.get('clinic_name', ''),
            'address': clinic_info.get('clinic_address', ''),
            'phone': clinic_info.get('clinic_phone', ''),
        }
        html = render_to_string('billing/invoice_pdf.html', {
            'invoice': invoice,
            'clinic': clinic,
            'generated_at': timezone.localtime().strftime('%d/%m/%Y %H:%M'),
            'timezone': timezone.get_current_timezone_name(),
            'status_label': STATUS_PRESENTATION['invoice'][invoice.status]['label'],
        })
        pdf = render_pdf_from_html(html)
        if not pdf:
            return error_response(503, 'تعذر إنشاء ملف الفاتورة', {})
        log_action(request.user.id, 'export', 'Invoice', invoice.id, {
            'summary': f'Invoice PDF export {invoice.invoice_number}',
            'version': invoice.version,
        })
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
        return response
