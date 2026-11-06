"""Canonical stored values and labels for this feature."""
from django.db.models import TextChoices


class ScaleFieldType(TextChoices):
    SLIDER = 'slider', 'Slider'
    TEXT = 'text', 'Text'
