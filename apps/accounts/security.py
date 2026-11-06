"""Security changes share revocation mechanics; callers own locking and version increments."""
from django.utils import timezone
from core.mutation import parse_version
from core.exceptions import ConflictError


def check_user_version(user, expected_version):
    if user.version != parse_version(expected_version):
        raise ConflictError('تم تعديل المستخدم بواسطة مستخدم آخر')


def revoke_sessions(user):
    user.session_revoked_at = timezone.now()
    user.clear_permission_cache()
