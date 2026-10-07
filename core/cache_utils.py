# backend/core/cache_utils.py
from django.core.cache import cache


def invalidate_group(group_name: str):
    """
    Invalidate all keys belonging to a group by incrementing the group's
    version counter. Works with any cache backend that supports
    get/set/incr (every built-in backend does).

    The previous implementation did cache.get(version_key) then
    cache.set(version_key, current + 1) as two separate operations. Two
    concurrent callers could both read version N and both write N+1, so
    one invalidation was silently lost — a real lost-update race that
    only shows up under concurrent writes.

    get_or_set seeds the counter exactly once (atomic on every backend);
    incr is atomic on Redis, memcached, and LocMemCache. Together they
    remove the read-modify-write window.
    """
    version_key = f"group_version_{group_name}"
    # Seed the counter on first use. get_or_set is a no-op after the first
    # call, so on subsequent invalidations the existing integer is returned
    # and immediately incremented by the next line.
    cache.get_or_set(version_key, 1, timeout=None)
    # incr raises ValueError only if the key is missing or non-integer.
    # Both are impossible here: we just guaranteed existence and the value
    # is always an int (the seed is 1, subsequent writes are incr results).
    cache.incr(version_key)


def get_group_version(group_name: str) -> int:
    """Return the current version of a group."""
    version_key = f"group_version_{group_name}"
    return cache.get(version_key, 1)


def set_grouped_key(group_name: str, key: str, value, timeout=300):
    """
    Set a cache key that belongs to a group, automatically including the current group version.
    The default timeout is set to 300 seconds (5 minutes) to ensure automatic cleanup.
    """
    version = get_group_version(group_name)
    full_key = f"{group_name}:v{version}:{key}"
    cache.set(full_key, value, timeout)


def get_grouped_key(group_name: str, key: str, default=None):
    """
    Get a cache key that belongs to a group, using the current group version.
    """
    version = get_group_version(group_name)
    full_key = f"{group_name}:v{version}:{key}"
    return cache.get(full_key, default)