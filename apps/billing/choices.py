"""Canonical stored values and labels for this feature."""
from django.db.models import TextChoices


class InvoiceStatus(TextChoices):
    DRAFT = 'draft', 'Draft'
    ISSUED = 'issued', 'Issued'
    PAID = 'paid', 'Paid'
    CANCELLED = 'cancelled', 'Cancelled'

class PaymentMethod(TextChoices):
    CASH = 'cash', 'Cash'
    CARD = 'card', 'Card'
    BANK_TRANSFER = 'bank_transfer', 'Bank transfer'
    INSURANCE = 'insurance', 'Insurance'
    OTHER = 'other', 'Other'
