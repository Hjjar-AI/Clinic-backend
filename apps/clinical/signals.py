from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import DiagnosisOption, MedicationOption, ClinicalScale, ClinicalNoteTemplate
from core.cache_utils import invalidate_group

@receiver(post_save, sender=DiagnosisOption)
@receiver(post_delete, sender=DiagnosisOption)
def clear_diagnosis_cache(sender, **kwargs):
    invalidate_group('reports')
    invalidate_group('context')

@receiver(post_save, sender=MedicationOption)
@receiver(post_delete, sender=MedicationOption)
def clear_medication_cache(sender, **kwargs):
    invalidate_group('reports')
    invalidate_group('context')

@receiver(post_save, sender=ClinicalScale)
@receiver(post_delete, sender=ClinicalScale)
def clear_scale_cache(sender, **kwargs):
    invalidate_group('context')

@receiver(post_save, sender=ClinicalNoteTemplate)
@receiver(post_delete, sender=ClinicalNoteTemplate)
def clear_template_cache(sender, **kwargs):
    invalidate_group('context')