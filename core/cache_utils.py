import logging
import secrets
from django.core.cache import cache
from .models import CacheGeneration

logger = logging.getLogger(__name__)


def invalidate_group(group_name):
    # The generation and mutation commit together. No fallible cache callback
    # can change the outcome of a durable write or its idempotency receipt.
    row, _ = CacheGeneration.objects.get_or_create(name=group_name, defaults={'token': secrets.token_hex(16)})
    CacheGeneration.objects.filter(pk=row.pk).update(token=secrets.token_hex(16))


def get_group_version(group_name):
    row, _ = CacheGeneration.objects.get_or_create(name=group_name, defaults={'token': secrets.token_hex(16)})
    return row.token


def set_grouped_key(group_name, key, value, timeout=300, *, version=None):
    if version is None or version != get_group_version(group_name):
        return False
    try:
        cache.set(f'{group_name}:v{version}:{key}', value, timeout)
        return True
    except Exception:
        logger.warning('Grouped cache write failed for %s', group_name)
        return False


def get_grouped_key(group_name, key, default=None, *, version=None):
    version = version or get_group_version(group_name)
    try:
        return cache.get(f'{group_name}:v{version}:{key}', default)
    except Exception:
        logger.warning('Grouped cache read failed for %s', group_name)
        return default
