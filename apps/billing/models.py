from decimal import Decimal

from django.db import models
from django.db.models.functions import Round
from django.core.validators import MinValueValidator
from core.models import TimeStampedModel, SoftDeleteModel

class Invoice(SoftDeleteModel, TimeStampedModel):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]
    invoice_number = models.CharField(max_length=50, unique=True)
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.PROTECT,
        related_name='invoices',
    )
    visit = models.ForeignKey(
        'visits.Visit',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='invoices',
    )
    total_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal('0'))],
    )
    tax = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal('0'))],
    )
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal('0'))],
    )
    final_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal('0'))],
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    status_reason = models.CharField(max_length=500, blank=True, default='')
    payment_method = models.CharField(max_length=30, blank=True, null=True, choices=[
        ('cash', 'Cash'), ('card', 'Card'), ('bank_transfer', 'Bank transfer'),
        ('insurance', 'Insurance'), ('other', 'Other'),
    ])
    issued_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    currency = models.CharField(max_length=3, default='SYP')
    issue_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    paid_at = models.DateTimeField(null=True, blank=True, editable=False)
    paid_by = models.ForeignKey('accounts.User', on_delete=models.PROTECT, null=True, blank=True, related_name='paid_invoices')
    version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        indexes = [
            models.Index(fields=['patient']),
            models.Index(fields=['visit']),
            models.Index(fields=['status']),
            models.Index(fields=['issued_date']),
        ]
        constraints = [
            models.CheckConstraint(
                check=~models.Q(status='paid') | models.Q(paid_at__isnull=False, paid_by__isnull=False),
                name='paid_invoice_has_payment_metadata',
            ),
            models.CheckConstraint(check=models.Q(version__gte=1, status__in=['draft', 'issued', 'paid', 'cancelled']), name='invoice_version_status_valid'),
            models.CheckConstraint(
                check=(
                    models.Q(total_amount__gte=0)
                    & models.Q(tax__gte=0)
                    & models.Q(discount__gte=0)
                    & models.Q(final_amount__gte=0)
                ),
                name='invoice_amounts_nonnegative',
            ),
            models.CheckConstraint(
                check=models.Q(discount__lte=Round(models.F('total_amount') + models.F('tax'), precision=2)),
                name='invoice_discount_not_excessive',
            ),
            models.CheckConstraint(
                check=models.Q(
                    final_amount=Round(models.F('total_amount') + models.F('tax') - models.F('discount'), precision=2)
                ),
                name='invoice_final_amount_matches',
            ),
            models.CheckConstraint(
                check=(
                    models.Q(issued_date__isnull=True)
                    | models.Q(due_date__isnull=True)
                    | models.Q(due_date__gte=models.F('issued_date'))
                ),
                name='invoice_due_date_not_before_issue',
            ),
        ]

    def __str__(self):
        return self.invoice_number


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    description = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'pk']
        constraints = [models.CheckConstraint(check=models.Q(quantity__gt=0, unit_price__gte=0, amount__gte=0), name='invoice_line_amounts_valid')]
