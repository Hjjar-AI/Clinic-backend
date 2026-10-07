# backend/apps/appointments/models.py
from django.db import models
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from core.models import TimeStampedModel, SoftDeleteModel

class Appointment(SoftDeleteModel, TimeStampedModel):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('arrived', 'Arrived'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no-show', 'No-show'),
    ]
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='appointments',
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='appointments',
    )
    appointment_date = models.DateField()
    appointment_time = models.TimeField()  # changed from CharField to TimeField
    duration_minutes = models.PositiveSmallIntegerField(
        default=30,
        validators=[MinValueValidator(1), MaxValueValidator(1440)],
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    status_reason = models.CharField(max_length=500, blank=True, default='')
    notes = models.TextField(blank=True, null=True)
    reminder_sent = models.BooleanField(default=False)
    reminder_sent_hour = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        indexes = [
            models.Index(fields=['doctor', 'appointment_date', 'status']),
            models.Index(fields=['doctor', 'appointment_date', 'appointment_time']),
            models.Index(fields=['patient']),
            models.Index(fields=['deleted_at']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(duration_minutes__gte=1, duration_minutes__lte=1440),
                name='appointment_duration_valid',
            ),
        ]

    def __str__(self):
        return f"{self.patient} with {self.doctor} on {self.appointment_date} at {self.appointment_time}"
