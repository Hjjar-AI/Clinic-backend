from core.mutation import check_mutation
# backend/apps/billing/services.py
import uuid
from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from decimal import Decimal, InvalidOperation
from .models import Invoice, InvoiceLine
from .money import CENT, MAX_AMOUNT, MAX_QUANTITY, bounded_decimal, round_money
from apps.patients.models import Patient
from apps.visits.models import Visit
from core.access import require_actor_permission, accessible_patients, accessible_invoices
from core.exceptions import ConflictError
from core.lifecycle import enforce_transition, transition_reason

class BillingService:
    INVOICE_PREFIX = 'INV'

    @staticmethod
    def _lock_invoice(invoice, actor):
        actor = require_actor_permission(actor, 'manage_billing')
        patient_id = Invoice.all_objects.values_list('patient_id', flat=True).get(pk=invoice.pk)
        Patient.all_objects.select_for_update().get(pk=patient_id)
        invoice = Invoice.all_objects.select_for_update().get(pk=invoice.pk)
        if invoice.patient_id != patient_id:
            raise ConflictError('تغير ملف المريض؛ أعد تحميل الفاتورة')
        if not accessible_invoices(actor).filter(pk=invoice.pk).exists():
            raise PermissionDenied('غير مصرح بالوصول إلى الفاتورة')
        return invoice, actor

    def _lines(self, data, current=None):
        rows = data.get('lines')
        if rows is None:
            if current is not None:
                try:
                    if 'total_amount' in data and bounded_decimal(data['total_amount']) != current.total_amount:
                        raise ValueError()
                except (ValueError, TypeError):
                    raise ValidationError({'lines': ['عدّل البنود صراحة لتغيير المبلغ الإجمالي']})
                return None, current.total_amount
            rows = [{'description': 'خدمات العيادة', 'quantity': 1, 'unit_price': data.get('total_amount', 0)}]
        if not isinstance(rows, list) or not 1 <= len(rows) <= 200:
            raise ValidationError({'lines': ['يلزم بند واحد على الأقل وبحد أقصى 200']})
        normalized = []
        total = Decimal('0')
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ValidationError({'lines': ['بند غير صالح']})
            description = row.get('description')
            if not isinstance(description, str) or not description.strip() or len(description) > 300:
                raise ValidationError({'lines': ['وصف البند مطلوب وبحد أقصى 300 حرف']})
            try:
                quantity = bounded_decimal(row.get('quantity'), minimum=CENT, maximum=MAX_QUANTITY)
                price = bounded_decimal(row.get('unit_price'))
                amount = round_money(quantity * price)
                total += amount
                if total > MAX_AMOUNT:
                    raise ValueError()
            except (ValueError, TypeError, InvalidOperation):
                raise ValidationError({'lines': ['كمية أو سعر غير صالح؛ يلزم استخدام منزلتين عشريتين']})
            normalized.append(dict(description=description.strip(), quantity=quantity, unit_price=price, amount=amount, order=i))
        return normalized, total

    def _save_lines(self, invoice, rows):
        if rows is not None:
            invoice.lines.all().delete()
            InvoiceLine.objects.bulk_create([InvoiceLine(invoice=invoice, **row) for row in rows])

    @staticmethod
    def _currency(value):
        if not isinstance(value, str) or len(value) != 3 or not value.isascii() or not value.isalpha():
            raise ValidationError({'currency': ['يلزم رمز عملة من ثلاثة أحرف']})
        return value.upper()

    def _generate_invoice_number(self):
        unique_part = uuid.uuid4().hex.upper()
        return f"{self.INVOICE_PREFIX}-{unique_part}"

    def _validate_amounts(self, data):
        # Only validate if any amount field is present
        amount_fields = ['total_amount', 'tax', 'discount', 'final_amount']
        if not any(field in data for field in amount_fields):
            return
        try:
            total = bounded_decimal(data.get('total_amount', 0))
            tax = bounded_decimal(data.get('tax', 0))
            discount = bounded_decimal(data.get('discount', 0))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError({'amounts': ['قيمة مالية غير صالحة']})
        try:
            final = total + tax - discount
            if final < 0:
                raise ValidationError({'discount': ['الخصم أكبر من المبلغ المستحق']})
            if final > MAX_AMOUNT:
                raise ValueError()
            return round_money(final)
        except (InvalidOperation, ValueError):
            raise ValidationError({'amounts': ['قيمة مالية غير صالحة؛ يلزم استخدام منزلتين عشريتين ضمن الحد المسموح']})

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
    def create_invoice(self, data, actor):
        actor = require_actor_permission(actor, 'manage_billing')
        data = data.copy()
        rows, total = self._lines(data)
        amounts = {
            'total_amount': total,
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
        if patient:
            patient = Patient.all_objects.select_for_update().get(pk=patient.pk)
        if not patient or patient.deleted_at is not None or not patient.is_active:
            raise ValidationError(['المريض غير موجود'])
        if not accessible_patients(actor).filter(pk=patient.pk).exists():
            raise PermissionDenied('غير مصرح بالوصول إلى الملف')
        if data.get('visit') is not None and not visit:
            raise ValidationError(['الزيارة غير صالحة'])
        if visit:
            visit = Visit.all_objects.select_for_update().get(pk=visit.pk)
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
            currency=self._currency(data.get('currency', 'SYP')),
        )
        invoice.full_clean()
        invoice.save()
        self._save_lines(invoice, rows)
        return invoice

    @transaction.atomic
    def update_invoice(self, invoice, data, expected_version=None, *, actor):
        invoice, actor = self._lock_invoice(invoice, actor)
        check_mutation(invoice, expected_version)

        data = data.copy()
        rows, total = self._lines(data, invoice)
        data.pop('lines', None)
        data['total_amount'] = total
        if 'currency' in data:
            data['currency'] = self._currency(data['currency'])
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
            if k in {'total_amount', 'tax', 'discount', 'payment_method', 'issued_date', 'due_date', 'notes', 'currency'}:
                setattr(invoice, k, v)
        invoice.final_amount = final_amount
        invoice.version += 1
        invoice.full_clean()
        invoice.save()
        self._save_lines(invoice, rows)
        return invoice

    @transaction.atomic
    def delete_invoice(self, invoice, expected_version=None, *, actor):
        invoice, actor = self._lock_invoice(invoice, actor)
        check_mutation(invoice, expected_version)
        if invoice.status != 'draft':
            raise ValidationError({'status': ['لا يمكن حذف فاتورة صادرة؛ استخدم الإلغاء']})
        invoice.soft_delete(actor)
        return True

    @transaction.atomic
    def transition(self, invoice, target_status, actor, expected_version=None, reason='', payment_method=None):
        invoice, actor = self._lock_invoice(invoice, actor)
        check_mutation(invoice, expected_version)
        changed = enforce_transition('invoice', invoice.status, target_status)
        if not changed:
            return invoice
        reason = transition_reason(reason, required=target_status == 'cancelled')
        if payment_method is not None:
            if target_status != 'paid' or not isinstance(payment_method, str) or payment_method not in {'cash', 'card', 'bank_transfer', 'insurance', 'other'}:
                raise ValidationError({'payment_method': ['طريقة الدفع غير صالحة']})
            invoice.payment_method = payment_method
        if target_status == 'paid' and not invoice.payment_method:
            raise ValidationError({'payment_method': ['طريقة الدفع مطلوبة قبل تعليم الفاتورة كمدفوعة']})
        issued_date = invoice.issued_date
        if target_status == 'issued' and not issued_date:
            issued_date = timezone.localdate()
        self._validate_dates(issued_date, invoice.due_date)
        if target_status == 'issued':
            from apps.settings.services import SettingsService
            invoice.issue_snapshot = {'patient_name': invoice.patient.get_full_name(),
                'national_id': invoice.patient.national_id, 'clinic': SettingsService().get_clinic_info()}
        if target_status == 'paid':
            invoice.paid_at = timezone.now()
            invoice.paid_by = actor
        invoice.status = target_status
        invoice.status_reason = reason
        invoice.issued_date = issued_date
        invoice.version += 1
        invoice.full_clean()
        invoice.save()
        return invoice
