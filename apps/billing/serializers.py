# backend/apps/billing/serializers.py
from rest_framework import serializers
from .models import Invoice
from apps.patients.models import Patient
from apps.visits.models import Visit
from django.utils import timezone

class InvoiceSerializer(serializers.ModelSerializer):
    lines = serializers.ListField(child=serializers.DictField(), required=False, max_length=200, write_only=True)
    line_items = serializers.SerializerMethodField()
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

    def get_line_items(self, obj):
        return list(obj.lines.values('id', 'description', 'quantity', 'unit_price', 'amount'))
