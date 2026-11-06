"""Renew occurrence identity only when the owning workflow schedules a new occurrence."""
import uuid


def renew_reminder(instance, *delivery_fields):
    instance.reminder_generation = uuid.uuid4()
    for field in delivery_fields:
        setattr(instance, field, False)
