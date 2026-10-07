from django.db import models
from django.conf import settings
from core.models import TimeStampedModel

class PrescriptionSignature(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='prescription_signatures',
    )
    visit = models.ForeignKey(
        'visits.Visit',
        on_delete=models.CASCADE,
        related_name='prescription_signatures',
    )
    signature_data = models.TextField()
    stamp_data = models.TextField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'visit'],
                name='unique_prescription_signature_per_user_visit',
            ),
        ]
