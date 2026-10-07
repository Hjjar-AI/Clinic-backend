from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Visit
from core.cache_utils import invalidate_group

@receiver(post_save, sender=Visit)
def clear_visit_cache(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    invalidate_group('dashboard')
    invalidate_group('reports')

@receiver(post_delete, sender=Visit)
def clear_visit_cache_on_delete(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    invalidate_group('dashboard')
    invalidate_group('reports')