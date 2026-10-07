from decimal import Decimal

from django.db import models
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
        on_delete=models.CASCADE,
        related_name='invoices',
    )
    visit = models.ForeignKey(
        'visits.Visit',
        on_delete=models.SET_NULL,
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
    payment_method = models.CharField(max_length=30, blank=True, null=True)
    issued_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
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
                check=(
                    models.Q(total_amount__gte=0)
                    & models.Q(tax__gte=0)
                    & models.Q(discount__gte=0)
                    & models.Q(final_amount__gte=0)
                ),
                name='invoice_amounts_nonnegative',
            ),
            models.CheckConstraint(
                check=models.Q(discount__lte=models.F('total_amount') + models.F('tax')),
                name='invoice_discount_not_excessive',
            ),
            models.CheckConstraint(
                check=models.Q(
                    final_amount=models.F('total_amount') + models.F('tax') - models.F('discount')
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
