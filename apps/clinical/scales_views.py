from core.mutation import request_version
from .services import update_catalog, restore_catalog, create_catalog
# backend/apps/clinical/scales_views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import ClinicalScale, ScaleField
from .serializers import ClinicalScaleSerializer, ScaleFieldSerializer
from .services import ScaleService
from core.permissions import PERM_MANAGE_OPTIONS, HasManageOptions
from core.exceptions import error_response
from django.db.models import Count, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from apps.visits.models import VisitScaleResponse
from core.query_utils import apply_ordering


class ScaleViewSet(viewsets.ModelViewSet):
    serializer_class = ClinicalScaleSerializer
    permission_classes = [permissions.IsAuthenticated]
    service = ScaleService()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'add_field', 'reactivate']:
            permission_classes = [permissions.IsAuthenticated, HasManageOptions]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        if (
            self.action == 'reactivate'
            or self.request.query_params.get('include_inactive') == 'true'
            and self.request.user.has_perm(PERM_MANAGE_OPTIONS)
        ):
            queryset = ClinicalScale.all_objects.all()
        else:
            queryset = ClinicalScale.objects.all()
        usage = VisitScaleResponse.objects.filter(scale_id=OuterRef('pk')).values(
            'scale_id'
        ).annotate(total=Count('id')).values('total')
        queryset = queryset.annotate(usage_count_value=Coalesce(Subquery(usage), 0))
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )
        activity = self.request.query_params.get('activity')
        if activity == 'active':
            queryset = queryset.filter(is_active=True, deleted_at__isnull=True)
        elif activity == 'inactive':
            queryset = queryset.filter(Q(is_active=False) | Q(deleted_at__isnull=False))
        queryset = apply_ordering(queryset, self.request.query_params, {
            'name': 'name', 'usage_count': 'usage_count_value',
            'created_at': 'created_at', 'updated_at': 'updated_at',
        }, default='name')
        return queryset.prefetch_related('fields')

    def perform_create(self, serializer):
        serializer.instance = create_catalog(ClinicalScale, serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = update_catalog(ClinicalScale, serializer.instance.pk, serializer.validated_data, request_version(self.request))

    def perform_destroy(self, instance):
        self.service.delete_scale(instance.pk, request_version(self.request))

    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        instance = self.get_object()
        instance = restore_catalog(instance, request_version(request))
        return Response({'data': self.get_serializer(instance).data})

    @action(detail=True, methods=['post'], url_path='add-field')
    def add_field(self, request, pk=None):
        scale = self.get_object()
        serializer = ScaleFieldSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        field = self.service.add_field(scale, serializer.validated_data, request_version(request))
        scale.refresh_from_db(fields=['version'])
        return Response(ScaleFieldSerializer(field).data, status=status.HTTP_201_CREATED, headers={'X-Resource-Version': str(scale.version)})
