# backend/apps/billing/services.py
import uuid
from django.db import transaction, connection
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from .models import Invoice
from apps.patients.models import Patient
from apps.visits.models import Visit
from core.exceptions import ConflictError
from core.lifecycle import enforce_transition

class BillingService:
    INVOICE_PREFIX = 'INV'

    def _generate_invoice_number(self):
        unique_part = uuid.uuid4().hex[:8].upper()
        return f"{self.INVOICE_PREFIX}-{unique_part}"

    def _validate_amounts(self, data):
        # Only validate if any amount field is present
        amount_fields = ['total_amount', 'tax', 'discount', 'final_amount']
        if not any(field in data for field in amount_fields):
            return
        try:
            total = Decimal(str(data.get('total_amount', 0)))
            tax = Decimal(str(data.get('tax', 0)))
            discount = Decimal(str(data.get('discount', 0)))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError({'amounts': ['قيمة مالية غير صالحة']})
        if not all(amount.is_finite() for amount in (total, tax, discount)):
            raise ValidationError({'amounts': ['قيمة مالية غير صالحة']})
        if total < 0 or tax < 0 or discount < 0:
            raise ValidationError(['المبالغ لا يمكن أن تكون سالبة'])
        if discount > total + tax:
            raise ValidationError({'discount': ['الخصم أكبر من المبلغ المستحق']})
        return (total + tax - discount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def _validate_dates(self, issued_date, due_date):
        if issued_date and due_date:
            try:
                due_before_issue = due_date < issued_date
            except TypeError:
                raise ValidationError({'due_date': ['تاريخ الاستحقاق غير صالح']})
            if due_before_issue:
                raise ValidationError({
                    'due_date': ['تاريخ الاستحقاق لا يمكن أن يسبق تاريخ الإصدار'],
                })

    @transaction.atomic
    def create_invoice(self, data):
        amounts = {
            'total_amount': data.get('total_amount', 0),
            'tax': data.get('tax', 0),
            'discount': data.get('discount', 0),
        }
        final_amount = self._validate_amounts(amounts)
        self._validate_dates(data.get('issued_date'), data.get('due_date'))
        patient = data.get('patient')
        visit = data.get('visit')
        if isinstance(patient, int):
            patient = Patient.objects.filter(id=patient).first()
        if isinstance(visit, int):
            visit = Visit.objects.filter(id=visit).first()
        if not patient or patient.deleted_at is not None or not patient.is_active:
            raise ValidationError(['المريض غير موجود'])
        if data.get('visit') is not None and not visit:
            raise ValidationError(['الزيارة غير صالحة'])
        if visit and (visit.deleted_at is not None or not visit.is_active):
            raise ValidationError(['الزيارة غير صالحة'])
        if visit and visit.patient_id != patient.id:
            raise ValidationError(['الزيارة غير صالحة'])
        number = self._generate_invoice_number()
        invoice = Invoice(
            invoice_number=number,
            patient=patient,
            visit=visit,
            total_amount=amounts['total_amount'],
            tax=amounts['tax'],
            discount=amounts['discount'],
            final_amount=final_amount,
            status='draft',
            payment_method=data.get('payment_method'),
            issued_date=data.get('issued_date'),
            due_date=data.get('due_date'),
            notes=data.get('notes', ''),
        )
        invoice.save()
        return invoice

    @transaction.atomic
    def update_invoice(self, invoice, data, expected_version=None):
        invoice = Invoice.all_objects.select_for_update().get(pk=invoice.pk)
        if expected_version is None:
            raise ValidationError(['يجب توفير رقم الإصدار'])
        if invoice.version != expected_version:
            raise ConflictError('تم تعديل الفاتورة بواسطة مستخدم آخر')

        # Prevent changing patient or visit
        if 'patient' in data and data['patient'] != invoice.patient:
            raise ValidationError(['لا يمكن تغيير المريض المرتبط بالفاتورة'])
        if 'visit' in data and data['visit'] != invoice.visit:
            raise ValidationError(['لا يمكن تغيير الزيارة المرتبطة بالفاتورة'])
        # Remove these fields from data to avoid accidental assignment
        data.pop('patient', None)
        data.pop('visit', None)

        if invoice.status != 'draft':
            raise ValidationError({'status': ['لا يمكن تعديل فاتورة بعد إصدارها؛ قم بإلغائها عند الحاجة']})
        data.pop('status', None)
        data.pop('final_amount', None)
        amounts = {
            'total_amount': data.get('total_amount', invoice.total_amount),
            'tax': data.get('tax', invoice.tax),
            'discount': data.get('discount', invoice.discount),
        }
        final_amount = self._validate_amounts(amounts)
        self._validate_dates(
            data.get('issued_date', invoice.issued_date),
            data.get('due_date', invoice.due_date),
        )
        for k, v in data.items():
            if k not in {'version', 'invoice_number'}:
                setattr(invoice, k, v)
        invoice.final_amount = final_amount
        invoice.version += 1
        invoice.save()
        return invoice

    @transaction.atomic
    def delete_invoice(self, invoice):
        invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if invoice.status != 'draft':
            raise ValidationError({'status': ['لا يمكن حذف فاتورة صادرة؛ استخدم الإلغاء']})
        invoice.soft_delete()
        return True

    @transaction.atomic
    def transition(self, invoice, target_status, actor, expected_version=None, reason=''):
        invoice = Invoice.all_objects.select_for_update().get(pk=invoice.pk)
        if expected_version is None:
            raise ValidationError({'version': ['يجب توفير رقم الإصدار']})
        if invoice.version != expected_version:
            raise ConflictError('تم تعديل الفاتورة بواسطة مستخدم آخر')
        changed = enforce_transition('invoice', invoice.status, target_status)
        if not changed:
            return invoice
        if target_status == 'cancelled' and not str(reason).strip():
            raise ValidationError({'reason': ['سبب الإلغاء مطلوب']})
        if target_status == 'paid' and not invoice.payment_method:
            raise ValidationError({'payment_method': ['طريقة الدفع مطلوبة قبل تعليم الفاتورة كمدفوعة']})
        issued_date = invoice.issued_date
        if target_status == 'issued' and not issued_date:
            issued_date = timezone.localdate()
        self._validate_dates(issued_date, invoice.due_date)
        invoice.status = target_status
        invoice.status_reason = str(reason).strip() if reason else ''
        invoice.issued_date = issued_date
        invoice.version += 1
        invoice.save(update_fields=['status', 'status_reason', 'issued_date', 'version', 'updated_at'])
        return invoice
