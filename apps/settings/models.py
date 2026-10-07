from django.db import models
from core.models import TimeStampedModel

class ClinicSetting(TimeStampedModel):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True)

    def __str__(self):
        return self.key

    class Meta:
        ordering = ['key']
