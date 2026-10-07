from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
from core.models import TimeStampedModel

class UserTask(TimeStampedModel):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_tasks',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='low')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    status_reason = models.CharField(max_length=500, blank=True, default='')
    due_date = models.DateField(null=True, blank=True)
    reminder_sent = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_tasks',
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        indexes = [
            models.Index(fields=['assigned_to', 'completed_at', 'cancelled_at']),
            models.Index(fields=['assigned_to', 'status', 'due_date']),
            models.Index(fields=['due_date']),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(
                        status='completed',
                        completed_at__isnull=False,
                        cancelled_at__isnull=True,
                    )
                    | models.Q(
                        status='cancelled',
                        completed_at__isnull=True,
                        completed_by__isnull=True,
                        cancelled_at__isnull=False,
                    )
                    | models.Q(
                        status__in=['open', 'in_progress'],
                        completed_at__isnull=True,
                        completed_by__isnull=True,
                        cancelled_at__isnull=True,
                    )
                ),
                name='task_terminal_timestamps_consistent',
            ),
        ]

    def __str__(self):
        return self.title

    def is_done(self):
        return self.status in {'completed', 'cancelled'}

    def status_display(self):
        return self.status

    def reactivate(self):
        now = timezone.now()
        self.status = 'open'
        self.completed_at = None
        self.completed_by = None
        self.cancelled_at = None
        self.reminder_sent = False
        self.updated_at = now
        self.save(update_fields=[
            'status', 'completed_at', 'completed_by', 'cancelled_at',
            'reminder_sent', 'updated_at',
        ])
