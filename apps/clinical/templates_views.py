from core.mutation import request_version
from .services import update_catalog, restore_catalog, create_catalog
# backend/apps/clinical/templates_views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import ClinicalNoteTemplate
from .serializers import ClinicalNoteTemplateSerializer
from .services import TemplateService
from core.permissions import PERM_MANAGE_TEMPLATES, HasManageTemplates
from django.db.models import Q
from core.query_utils import apply_ordering


class TemplateViewSet(viewsets.ModelViewSet):
    serializer_class = ClinicalNoteTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]
    service = TemplateService()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'reactivate']:
            permission_classes = [permissions.IsAuthenticated, HasManageTemplates]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        if (
            self.action == 'reactivate'
            or self.request.query_params.get('include_inactive') == 'true'
            and self.request.user.has_perm(PERM_MANAGE_TEMPLATES)
        ):
            queryset = ClinicalNoteTemplate.all_objects.all()
        else:
            queryset = ClinicalNoteTemplate.objects.all()
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        activity = self.request.query_params.get('activity')
        if activity == 'active':
            queryset = queryset.filter(is_active=True, deleted_at__isnull=True)
        elif activity == 'inactive':
            queryset = queryset.filter(Q(is_active=False) | Q(deleted_at__isnull=False))
        return apply_ordering(queryset, self.request.query_params, {
            'name': 'name', 'category': 'category',
            'created_at': 'created_at', 'updated_at': 'updated_at',
        }, default='name')

    def perform_create(self, serializer):
        instance = self.service.create_template(serializer.validated_data)
        serializer.instance = instance

    def perform_update(self, serializer):
        instance = self.get_object()
        serializer.instance = self.service.update_template(instance.id, serializer.validated_data, request_version(self.request))

    def perform_destroy(self, instance):
        self.service.delete_template(instance.id, request_version(self.request))

    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        instance = self.get_object()
        instance = restore_catalog(instance, request_version(request))
        return Response({'data': self.get_serializer(instance).data})
