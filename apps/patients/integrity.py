"""Cross-record invariants for ordinary services and authenticated inventories."""
from django.core.exceptions import ValidationError


def validate_links(row, inventory=None):
    def related(name):
        field = row._meta.get_field(name)
        identifier = getattr(row, field.attname)
        if identifier is None:
            return None
        model = field.remote_field.model
        result = (inventory.get((model._meta.label_lower, identifier)) if inventory is not None
                  else model._base_manager.filter(pk=identifier).first())
        if result is None:
            raise ValidationError({name: ['مرجع غير موجود']})
        return result

    label = row._meta.label_lower
    if label == 'patients.patient':
        identifier = related('primary_identifier')
        if identifier and (identifier.patient_id != row.pk or not identifier.is_active or identifier.identifier_type != 'national_id'):
            raise ValidationError({'primary_identifier': ['اختر هوية وطنية نشطة من هذا الملف']})
        if row.merged_into_id:
            seen = {row.pk}
            current = row
            while current.merged_into_id:
                identifier = current.merged_into_id
                if identifier in seen:
                    raise ValidationError({'merged_into': ['حلقة دمج غير صالحة']})
                seen.add(identifier)
                current = (inventory.get(('patients.patient', identifier)) if inventory is not None
                           else type(row).all_objects.filter(pk=identifier).first())
                if current is None:
                    raise ValidationError({'merged_into': ['مرجع دمج غير موجود']})
            if row.is_active or row.deleted_at is None:
                raise ValidationError({'merged_into': ['الملف المدمج مؤرشف']})
    patient_id = getattr(row, 'patient_id', None)
    if patient_id is not None:
        for name in ('source_visit', 'completed_visit', 'appointment', 'visit'):
            if name in {field.name for field in row._meta.fields}:
                target = related(name)
                if target and target.patient_id != patient_id:
                    raise ValidationError({name: ['المرجع لا يخص هذا المريض']})
    if label == 'visits.visit' and row.follow_up_id:
        occurrence = related('follow_up')
        if (not occurrence.is_active or occurrence.patient_id != row.patient_id
                or occurrence.source_visit_id != row.pk or occurrence.due_date < row.visit_date):
            raise ValidationError({'follow_up': ['متابعة زيارة غير صالحة']})
    if label == 'patients.patientfollowup':
        source = related('source_visit')
        if source and row.due_date < source.visit_date:
            raise ValidationError({'due_date': ['المتابعة لا تسبق الزيارة']})
        revision = related('completed_revision')
        if row.completed_visit_id:
            if row.status != 'completed' or not revision or revision.visit_id != row.completed_visit_id:
                raise ValidationError({'completed_revision': ['دليل الإنجاز لا يطابق الزيارة']})
            if row.outcome_at and revision.signed_at > row.outcome_at:
                raise ValidationError({'completed_revision': ['اعتماد الزيارة يجب أن يسبق نتيجة المتابعة']})
        elif revision:
            raise ValidationError({'completed_revision': ['يلزم تحديد زيارة الإنجاز']})
    if label == 'billing.invoiceline':
        from apps.billing.money import round_money
        if row.amount != round_money(row.quantity * row.unit_price):
            raise ValidationError({'amount': ['مبلغ البند لا يطابق الكمية والسعر']})
    if label == 'prescriptions.issueddocument':
        import hashlib
        from core.json_schemas import validate_issued_snapshot
        validate_issued_snapshot(row.snapshot)
        revision = related('revision')
        if (row.snapshot['revision_id'] != row.revision_id or row.snapshot['visit_id'] != revision.visit_id
                or hashlib.sha256(bytes(row.pdf_data)).hexdigest() != row.checksum or not row.pdf_data):
            raise ValidationError({'snapshot': ['بيانات المستند أو بصمته لا تطابق الدليل المحفوظ']})
    if label == 'visits.visitrevision':
        from core.json_schemas import validate_revision_snapshot
        validate_revision_snapshot(row.snapshot)
        if row.snapshot['fields'].get('id') != row.visit_id or row.snapshot['fields'].get('signed_by') != row.signer_id:
            raise ValidationError({'snapshot': ['النسخة لا تطابق الزيارة أو الموقّع']})


def validate_inventory(inventory):
    """Use only the supplied inventory, never IDs from the live database."""
    invoice_totals = {}
    for row in inventory.values():
        validate_links(row, inventory)
        if row._meta.label_lower == 'billing.invoiceline':
            invoice_totals[row.invoice_id] = invoice_totals.get(row.invoice_id, 0) + row.amount
    for row in inventory.values():
        if row._meta.label_lower == 'billing.invoice' and invoice_totals.get(row.pk, 0) != row.total_amount:
            raise ValidationError({'lines': ['مجموع البنود لا يطابق الفاتورة']})
