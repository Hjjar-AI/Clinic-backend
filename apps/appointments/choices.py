"""Canonical stored values and labels for this feature."""
from django.db.models import TextChoices


class AppointmentStatus(TextChoices):
    SCHEDULED = 'scheduled', 'Scheduled'
    CONFIRMED = 'confirmed', 'Confirmed'
    ARRIVED = 'arrived', 'Arrived'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'
    NO_SHOW = 'no-show', 'No-show'
