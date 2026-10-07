from core.mutation import request_version
from .services import update_catalog, restore_catalog, create_catalog
# backend/apps/clinical/views.py
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import DiagnosisOption, MedicationOption
from .serializers import DiagnosisOptionSerializer, MedicationOptionSerializer
from .services import DiagnosisService, MedicationService
from core.permissions import (
    PERM_MANAGE_OPTIONS,
    HasManageOptions,
)
from django.db.models import Count, Q
from core.query_utils import apply_ordering


class DiagnosisViewSet(viewsets.ModelViewSet):
    serializer_class = DiagnosisOptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    service = DiagnosisService()

    def get_queryset(self):
        manager = DiagnosisOption.all_objects if (
            self.action == 'reactivate'
            or self.request.query_params.get('include_inactive') == 'true'
            and self.request.user.has_perm(PERM_MANAGE_OPTIONS)
        ) else DiagnosisOption.objects
        queryset = manager.all().annotate(usage_count=Count('visitdiagnosis'))
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(code__icontains=search)
                | Q(english_name__icontains=search)
                | Q(arabic_name__icontains=search)
            )
        activity = self.request.query_params.get('activity')
        if activity == 'active':
            queryset = queryset.filter(is_active=True, deleted_at__isnull=True)
        elif activity == 'inactive':
            queryset = queryset.filter(Q(is_active=False) | Q(deleted_at__isnull=False))
        return apply_ordering(queryset, self.request.query_params, {
            'order': 'order', 'code': 'code',
            'english_name': 'english_name', 'arabic_name': 'arabic_name',
            'usage_count': 'usage_count',
        }, default='order')

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'reactivate']:
            permission_classes = [permissions.IsAuthenticated, HasManageOptions]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        instance = self.service.create_diagnosis(**serializer.validated_data)
        serializer.instance = instance

    def perform_update(self, serializer):
        instance = self.get_object()
        serializer.instance = self.service.update_diagnosis(instance.id, expected_version=request_version(self.request), **serializer.validated_data)

    def perform_destroy(self, instance):
        self.service.soft_delete(instance.id, request_version(self.request))

    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        instance = self.get_object()
        instance = restore_catalog(instance, request_version(request))
        return Response({'data': self.get_serializer(instance).data})


class MedicationViewSet(viewsets.ModelViewSet):
    serializer_class = MedicationOptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    service = MedicationService()

    def get_queryset(self):
        manager = MedicationOption.all_objects if (
            self.action == 'reactivate'
            or self.request.query_params.get('include_inactive') == 'true'
            and self.request.user.has_perm(PERM_MANAGE_OPTIONS)
        ) else MedicationOption.objects
        queryset = manager.all().annotate(usage_count=Count('visitmedication'))
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(generic_english__icontains=search)
                | Q(generic_arabic__icontains=search)
                | Q(brand_english__icontains=search)
                | Q(brand_arabic__icontains=search)
                | Q(dosage__icontains=search)
            )
        activity = self.request.query_params.get('activity')
        if activity == 'active':
            queryset = queryset.filter(is_active=True, deleted_at__isnull=True)
        elif activity == 'inactive':
            queryset = queryset.filter(Q(is_active=False) | Q(deleted_at__isnull=False))
        return apply_ordering(queryset, self.request.query_params, {
            'order': 'order', 'generic_english': 'generic_english',
            'generic_arabic': 'generic_arabic', 'dosage': 'dosage',
            'brand_english': 'brand_english', 'brand_arabic': 'brand_arabic',
            'usage_count': 'usage_count',
        }, default='order')

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'reactivate']:
            permission_classes = [permissions.IsAuthenticated, HasManageOptions]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        instance = self.service.create_medication(**serializer.validated_data)
        serializer.instance = instance

    def perform_update(self, serializer):
        instance = self.get_object()
        serializer.instance = self.service.update_medication(instance.id, expected_version=request_version(self.request), **serializer.validated_data)

    def perform_destroy(self, instance):
        self.service.soft_delete(instance.id, request_version(self.request))

    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        instance = self.get_object()
        instance = restore_catalog(instance, request_version(request))
        return Response({'data': self.get_serializer(instance).data})


class ClinicalConstantsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from django.conf import settings
        return Response({
            'data': {
                'suicide_risk_levels': ['Low', 'Moderate', 'High'],
                'violence_risk_levels': ['Low', 'Moderate', 'High'],
                'level_of_care': [
                    'Outpatient', 'IOP', 'PHP', 'Inpatient', 'Residential',
                    'Voluntary', 'Involuntary'
                ],
                'follow_up_type': ['In-person', 'Telehealth', 'Phone'],
                'marital_status_male': ['أعزب', 'متزوج', 'مطلق', 'أرمل'],
                'marital_status_female': ['عزباء', 'متزوجة', 'مطلقة', 'أرملة'],
            }
        })
