"""Canonical stored values and labels for this feature."""
from django.db.models import TextChoices


class DocumentType(TextChoices):
    PRESCRIPTION = 'prescription', 'Prescription'
    REFERRAL = 'referral', 'Referral'
