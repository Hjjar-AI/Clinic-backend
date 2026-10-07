import secrets
from django.core.cache import cache
from django.db import transaction


def invalidate_group(group_name):
    # A fresh token also prevents generation reuse after counter-key eviction.
    transaction.on_commit(lambda: cache.set(f'group_version_{group_name}', secrets.token_hex(16), timeout=None))


def get_group_version(group_name):
    key = f'group_version_{group_name}'
    return cache.get_or_set(key, secrets.token_hex(16), timeout=None)


def set_grouped_key(group_name, key, value, timeout=300, *, version=None):
    # Callers must capture the generation before reading the database.
    if version is None or version != get_group_version(group_name):
        return False
    cache.set(f'{group_name}:v{version}:{key}', value, timeout)
    return True


def get_grouped_key(group_name, key, default=None, *, version=None):
    version = version or get_group_version(group_name)
    return cache.get(f'{group_name}:v{version}:{key}', default)
