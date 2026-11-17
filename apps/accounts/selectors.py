from django.core.exceptions import ValidationError
from django.db.models import Q
from core.query_utils import apply_ordering
from .models import User


def list_queryset(actor, params):
    qs = User.objects.filter(is_active=True)
    search = params.get('search', '').strip()
    if search:
        qs = qs.filter(Q(username__icontains=search) | Q(full_name__icontains=search))
    role = params.get('role')
    if role:
        if role not in dict(User.ROLE_CHOICES):
            raise ValidationError({'role': ['الدور غير صالح']})
        qs = qs.filter(role=role)
    return apply_ordering(qs, params, {
        'username': 'username',
        'full_name': 'full_name',
        'role': 'role',
        'date_joined': 'date_joined',
    }, default='username')

