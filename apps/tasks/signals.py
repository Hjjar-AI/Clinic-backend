from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from core.cache_utils import invalidate_group
from .models import UserTask

@receiver(post_save, sender=UserTask)
def clear_task_cache(sender, instance, **kwargs):
    invalidate_group('dashboard')

@receiver(post_delete, sender=UserTask)
def clear_task_cache_on_delete(sender, instance, **kwargs):
    invalidate_group('dashboard')