"""Server-owned verification stamps; callers decide which fact changes invalidate them."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone


def stamp_verification(row, actor, previous=None, *, prefix='', denial='تأكيد المستندات مخصص للطبيب أو المدير'):
    state = getattr(row, prefix + 'verification', None)
    if state is None:
        return
    if state == 'verified' and previous != 'verified':
        if actor is None:
            raise ValidationError('المستخدم المنفذ مطلوب للتحقق')
        if actor.role not in {'admin', 'doctor'}:
            raise PermissionDenied(denial)
        setattr(row, prefix + 'verified_at', timezone.now())
        setattr(row, prefix + 'verified_by', actor)
    elif state != 'verified':
        setattr(row, prefix + 'verified_at', None)
        setattr(row, prefix + 'verified_by', None)
