from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Patient
from core.cache_utils import invalidate_group
from core.normalization import normalized_search_text

@receiver(pre_save, sender=Patient)
def update_normalised_full_name(sender, instance, **kwargs):
    parts = [instance.first_name]
    if instance.father_name:
        parts.append(instance.father_name)
    if instance.surname:
        parts.append(instance.surname)
    instance.normalised_full_name = normalized_search_text(" ".join(parts))

@receiver(post_save, sender=Patient)
def clear_patient_cache(sender, instance, **kwargs):
    invalidate_group('dashboard')
    invalidate_group('reports')
    invalidate_group('context_patients')

@receiver(post_delete, sender=Patient)
def clear_patient_cache_on_delete(sender, instance, **kwargs):
    invalidate_group('dashboard')
    invalidate_group('reports')
    invalidate_group('context_patients')
