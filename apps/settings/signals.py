from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import ClinicSetting
from core.cache_utils import invalidate_group

@receiver(post_save, sender=ClinicSetting)
@receiver(post_delete, sender=ClinicSetting)
def clear_settings_cache(sender, **kwargs):
    if kwargs.get('raw'):
        return
    invalidate_group('settings')