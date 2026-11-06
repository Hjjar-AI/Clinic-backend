from core.serializers import StrictFieldsMixin
# backend/apps/billing/serializers.py
from rest_framework import serializers
from .models import Invoice
from apps.patients.models import Patient
from apps.visits.models import Visit
from django.utils import timezone
from decimal import Decimal
from .models import InvoiceLine
from .money import MAX_QUANTITY


class InvoiceLineInputSerializer(StrictFieldsMixin, serializers.Serializer):
    description = serializers.CharField(max_length=300)
    quantity = serializers.DecimalField(max_digits=8, decimal_places=2, min_value=Decimal('0.01'), max_value=MAX_QUANTITY, coerce_to_string=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'), coerce_to_string=True)


class InvoiceLineSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=True)

    class Meta:
        model = InvoiceLine
        fields = ['id', 'description', 'quantity', 'unit_price', 'amount', 'order']
        read_only_fields = fields

class InvoiceSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'), required=False, coerce_to_string=True)
    tax = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'), required=False, coerce_to_string=True)
    discount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'), required=False, coerce_to_string=True)
    final_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, coerce_to_string=True)
    lines = InvoiceLineInputSerializer(many=True, required=False, write_only=True, allow_empty=False, max_length=200)
    line_items = InvoiceLineSerializer(source='lines', many=True, read_only=True)
    is_overdue = serializers.SerializerMethodField()
    patient_name = serializers.CharField(source='patient.get_full_name', read_only=True)
    patient = serializers.PrimaryKeyRelatedField(read_only=True)
    visit = serializers.PrimaryKeyRelatedField(read_only=True)
    patient_id = serializers.PrimaryKeyRelatedField(
        source='patient',
        queryset=Patient.objects.filter(deleted_at__isnull=True),
        write_only=True,
        required=True,
    )
    visit_id = serializers.PrimaryKeyRelatedField(
        source='visit',
        queryset=Visit.objects.filter(deleted_at__isnull=True),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Invoice
        fields = ['id', 'invoice_number', 'patient', 'patient_name', 'visit',
                  'total_amount', 'tax', 'discount', 'final_amount', 'status', 'status_reason',
                  'payment_method', 'issued_date', 'due_date', 'notes', 'version',
                  'created_at', 'updated_at', 'patient_id', 'visit_id', 'is_overdue', 'lines', 'line_items', 'currency', 'paid_at', 'paid_by', 'issue_snapshot']
        read_only_fields = ['id', 'invoice_number', 'patient_name', 'final_amount', 'created_at', 'updated_at', 'status', 'status_reason', 'paid_at', 'paid_by', 'issue_snapshot']

    def get_is_overdue(self, obj):
        return bool(obj.status == 'issued' and obj.due_date and obj.due_date < timezone.localdate())
