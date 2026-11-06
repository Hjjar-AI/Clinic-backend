"""Canonical stored values and labels for this feature."""
from django.db.models import TextChoices


class UserRole(TextChoices):
    ADMIN = 'admin', 'Admin'
    DOCTOR = 'doctor', 'Doctor'
    RECEPTIONIST = 'receptionist', 'Receptionist'
