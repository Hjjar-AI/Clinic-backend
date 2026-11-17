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
        from .selectors import list_queryset
        return list_queryset(self.request.user, self.request.query_params)
