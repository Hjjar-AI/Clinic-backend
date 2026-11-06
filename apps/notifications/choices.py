"""Canonical stored values and labels for this feature."""
from django.db.models import TextChoices


class NotificationType(TextChoices):
    INFO = 'info', 'Info'
    SUCCESS = 'success', 'Success'
    WARNING = 'warning', 'Warning'
    DANGER = 'danger', 'Danger'
