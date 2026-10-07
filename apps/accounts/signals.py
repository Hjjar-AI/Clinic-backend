# backend/apps/accounts/signals.py
from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.core.cache import cache
from .models import User
from core.signals import log_action
from django.contrib.auth.signals import user_logged_in, user_logged_out
from core.cache_utils import invalidate_group
from django.contrib.auth.models import Group

@receiver(post_save, sender=User)
@receiver(post_delete, sender=User)
def clear_user_cache(sender, **kwargs):
    if kwargs.get('raw'):
        return
    invalidate_group('context_doctors')
    invalidate_group('context_users')
    invalidate_group('dashboard')

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    if kwargs.get('raw'):
        return
    log_action(
        user.id,
        'login',
        'User',
        user.id,
        {'ip': request.META.get('REMOTE_ADDR')}
    )

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if kwargs.get('raw'):
        return
    if user:
        log_action(
            user.id,
            'logout',
            'User',
            user.id,
            {'ip': request.META.get('REMOTE_ADDR')}
        )

# Invalidate permission cache when group membership changes
@receiver(m2m_changed, sender=User.groups.through)
def user_groups_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    if kwargs.get('raw'):
        return
    """
    Clear the permission cache for affected users when group membership changes.
    """
    if action in ['post_add', 'post_remove', 'post_clear']:
        # instance is the User if reverse=False, otherwise it's the Group
        if reverse:
            # model is User
            users = model.objects.filter(pk__in=pk_set) if pk_set else model.objects.all()
        else:
            users = [instance]
        for user in users:
            user.clear_permission_cache()

# Invalidate permission cache when direct user permissions change
@receiver(m2m_changed, sender=User.user_permissions.through)
def user_permissions_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    if kwargs.get('raw'):
        return
    if action in ['post_add', 'post_remove', 'post_clear']:
        if reverse:
            users = model.objects.filter(pk__in=pk_set) if pk_set else model.objects.all()
        else:
            users = [instance]
        for user in users:
            user.clear_permission_cache()

# NEW: Invalidate permission cache when group permissions change
@receiver(m2m_changed, sender=Group.permissions.through)
def group_permissions_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
    if kwargs.get('raw'):
        return
    """
    Clear permission cache for all users belonging to the group(s) whose permissions changed.
    """
    if action in ['post_add', 'post_remove', 'post_clear']:
        # If reverse=True, instance is a Permission and model is Group
        # If reverse=False, instance is a Group and model is Permission
        if reverse:
            # pk_set contains group IDs
            groups = Group.objects.filter(pk__in=pk_set) if pk_set else Group.objects.all()
        else:
            groups = [instance]
        for group in groups:
            for user in group.user_set.all():
                user.clear_permission_cache()