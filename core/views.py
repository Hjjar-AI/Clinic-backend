# backend/core/views.py
from rest_framework import viewsets, permissions
from .models import AuditLog
from .serializers import AuditLogSerializer
from core.permissions import PERM_MANAGE_USERS, HasManageUsers
from core.query_utils import parse_date_range

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.has_perm(PERM_MANAGE_USERS):
            qs = AuditLog.objects.all()
        else:
            qs = AuditLog.objects.filter(user=user)
        params = self.request.query_params
        if params.get('entity_type'):
            qs = qs.filter(entity_type=params['entity_type'])
        if params.get('entity_id', '').isdigit():
            qs = qs.filter(entity_id=int(params['entity_id']))
        if params.get('actor_id', '').isdigit() and user.has_perm(PERM_MANAGE_USERS):
            qs = qs.filter(user_id=int(params['actor_id']))
        if params.get('action'):
            qs = qs.filter(action=params['action'])
        date_from, date_to = parse_date_range(params)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs.select_related('user').order_by('-created_at')
