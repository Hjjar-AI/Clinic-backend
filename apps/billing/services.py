from core.mutation import check_mutation
# backend/apps/billing/services.py
import uuid
from django.db import transaction, connection
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from .models import Invoice, InvoiceLine
from apps.patients.models import Patient
from apps.visits.models import Visit
from core.exceptions import ConflictError
from core.lifecycle import enforce_transition

class BillingService:
    INVOICE_PREFIX = 'INV'

    def _lines(self, data, current=None):
        rows = data.get('lines')
        if rows is None:
            if 'total_amount' not in data and current is not None:
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
                quantity, price = (Decimal(str(row.get(k))) for k in ('quantity', 'unit_price'))
                if not all(v.is_finite() for v in (quantity, price)) or quantity <= 0 or price < 0:
                    raise ValueError()
                if any(v != v.quantize(Decimal('.01')) or v > Decimal('99999999.99') for v in (quantity, price)):
                    raise ValueError()
                amount = (quantity * price).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
                total += amount
                if total > Decimal('99999999.99'):
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
            currency=self._currency(data.get('currency', 'SYP')),
        )
        invoice.full_clean()
        invoice.save()
        self._save_lines(invoice, rows)
        return invoice

    @transaction.atomic
    def update_invoice(self, invoice, data, expected_version=None):
        invoice = Invoice.all_objects.select_for_update().get(pk=invoice.pk)
        check_mutation(invoice, expected_version)
        if expected_version is None:
            raise ValidationError(['يجب توفير رقم الإصدار'])
        if invoice.version != expected_version:
            raise ConflictError('تم تعديل الفاتورة بواسطة مستخدم آخر')

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
            if k not in {'version', 'invoice_number'}:
                setattr(invoice, k, v)
        invoice.final_amount = final_amount
        invoice.version += 1
        invoice.full_clean()
        invoice.save()
        self._save_lines(invoice, rows)
        return invoice

    @transaction.atomic
    def delete_invoice(self, invoice, expected_version=None):
        invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
        check_mutation(invoice, expected_version)
        if invoice.status != 'draft':
            raise ValidationError({'status': ['لا يمكن حذف فاتورة صادرة؛ استخدم الإلغاء']})
        invoice.soft_delete()
        return True

    @transaction.atomic
    def transition(self, invoice, target_status, actor, expected_version=None, reason='', payment_method=None):
        invoice = Invoice.all_objects.select_for_update().get(pk=invoice.pk)
        check_mutation(invoice, expected_version)
        if expected_version is None:
            raise ValidationError({'version': ['يجب توفير رقم الإصدار']})
        if invoice.version != expected_version:
            raise ConflictError('تم تعديل الفاتورة بواسطة مستخدم آخر')
        changed = enforce_transition('invoice', invoice.status, target_status)
        if not changed:
            return invoice
        if target_status == 'cancelled' and not str(reason).strip():
            raise ValidationError({'reason': ['سبب الإلغاء مطلوب']})
        if payment_method is not None:
            if target_status != 'paid' or payment_method not in {'cash', 'card', 'bank_transfer', 'insurance', 'other'}:
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
        invoice.status_reason = str(reason).strip() if reason else ''
        invoice.issued_date = issued_date
        invoice.version += 1
        invoice.full_clean()
        invoice.save()
        return invoice
