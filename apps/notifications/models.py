from core.constraints import check_constraint
from .choices import NotificationType
from django.db import models
from django.conf import settings
from core.models import TimeStampedModel

class Notification(TimeStampedModel):
    TYPE_CHOICES = NotificationType.choices
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True, default='')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info')
    is_read = models.BooleanField(default=False)
    dedupe_key = models.CharField(max_length=200, blank=True, null=True)
    entity_type = models.CharField(max_length=100, blank=True, default='')
    entity_id = models.PositiveBigIntegerField(null=True, blank=True)
    occurrence = models.UUIDField(null=True, blank=True, editable=False)
    category = models.CharField(max_length=30, blank=True, default='')

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id', 'category', 'is_read']),
            models.Index(fields=['user', 'is_read', '-created_at']),
            models.Index(fields=['created_at']),
        ]
        constraints = [
            check_constraint(condition=models.Q(entity_type='', entity_id__isnull=True) | ~models.Q(entity_type='') & models.Q(entity_id__isnull=False), name='notification_entity_pair_valid'),
            check_constraint(condition=models.Q(type__in=NotificationType.values), name='notifications_notification_type_valid'),
            models.UniqueConstraint(fields=['user', 'dedupe_key'], condition=models.Q(dedupe_key__isnull=False), name='unique_user_notification_dedupe_key'),
        ]

    def __str__(self):
        return self.title
