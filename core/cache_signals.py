"""Model-to-cache ownership, with generations updated in the mutation transaction."""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .cache_utils import invalidate_group

CACHE_GROUPS = {
    'accounts.user': ('context_doctors', 'context_users', 'dashboard'),
    'patients.patient': ('dashboard', 'reports', 'context_patients'),
    'visits.visit': ('dashboard', 'reports'),
    'appointments.appointment': ('dashboard', 'context_appointments'),
    'billing.invoice': ('dashboard', 'reports'),
    'tasks.usertask': ('dashboard',),
    'clinical.diagnosisoption': ('reports', 'context'),
    'clinical.medicationoption': ('reports', 'context'),
    'clinical.clinicalscale': ('context',),
    'clinical.clinicalnotetemplate': ('context',),
    'settings.clinicsetting': ('settings',),
}


@receiver(post_save, dispatch_uid='clinic.model_cache.save')
@receiver(post_delete, dispatch_uid='clinic.model_cache.delete')
def invalidate_model_cache(sender, **kwargs):
    if kwargs.get('raw'):
        return
    for group in CACHE_GROUPS.get(sender._meta.label_lower, ()):
        invalidate_group(group)
