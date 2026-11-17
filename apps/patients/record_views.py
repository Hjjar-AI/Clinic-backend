from core.serializers import StrictFieldsMixin
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import get_object_or_404
from .record_services import RECORDS, CLINICAL_KINDS, PatientRecordService, require_access, history_patient_ids
from .models import PatientCorrection, PatientMerge
from django.db.models import Q
from .merge_services import PatientMergeService
from core.mutation import request_version


def record_serializer(kind):
    model, fields = RECORDS[kind]
    metadata = ['id', 'created_at', 'updated_at', 'created_by', 'updated_by', 'is_active', 'retired_at', 'retirement_reason']
    if kind == 'identifiers':
        metadata.append('is_primary')
    metadata += [name for name in ['verified_at', 'verified_by', 'outcome_at', 'outcome_by', 'completed_revision']
                 if any(field.name == name for field in model._meta.fields)]
    meta = type('Meta', (), {'model': model, 'fields': metadata + fields, 'read_only_fields': metadata})
    return type('PatientRecordSerializer', (StrictFieldsMixin, serializers.ModelSerializer), {'Meta': meta})


class PatientRecordsMixin:
    @action(detail=True, methods=['get', 'post'])
    def records(self, request, pk=None):
        patient = self.get_object()
        if request.method == 'POST' and set(request.data) - {'kind', 'record_id', 'operation', 'fields', 'reason', 'version'}:
            raise ValidationError('حقول طلب غير معروفة')
        kind = request.query_params.get('kind') if request.method == 'GET' else request.data.get('kind')
        if kind not in RECORDS:
            raise ValidationError({'kind': ['نوع سجل غير صالح']})
        service = PatientRecordService()
        serializer = record_serializer(kind)
        if request.method == 'GET':
            rows = service.list(patient, kind, request.user)
            # Bound response size; use explicit offset for older records.
            try:
                offset = max(0, int(request.query_params.get('offset', 0)))
                limit = max(1, min(int(request.query_params.get('per_page', 100)), 200))
            except (TypeError, ValueError):
                raise ValidationError('إزاحة غير صالحة')
            return Response({'data': {'items': serializer(rows[offset:offset + limit], many=True).data,
                'total': rows.count(), 'version': patient.version, 'offset': offset, 'limit': limit}})
        data = request.data.get('fields', {})
        if not isinstance(data, dict):
            raise ValidationError({'fields': ['يلزم كائن حقول']})
        operation = request.data.get('operation', 'save')
        if any(key not in RECORDS[kind][1] for key in data) or operation not in {'save', 'retire', 'select_primary'}:
            raise ValidationError('حقول أو عملية غير صالحة')
        if operation == 'select_primary':
            if kind != 'identifiers' or data or not request.data.get('record_id'):
                raise ValidationError('عملية اختيار الهوية الأساسية غير صالحة')
            row, version = service.select_primary(patient, request.data['record_id'], request.user,
                request_version(request), request.data.get('reason', ''))
            return Response({'data': {'record': serializer(row).data, 'version': version}}, headers={'X-Resource-Version': str(version)})
        if request.data.get('operation') == 'retire' and not request.data.get('record_id'):
            raise ValidationError('يلزم تحديد السجل')
        validated = serializer(data=data, partial=bool(request.data.get('record_id')))
        validated.is_valid(raise_exception=True)
        row, version = service.save(patient, kind, validated.validated_data, request.user, request_version(request),
            record_id=request.data.get('record_id'), retire=request.data.get('operation') == 'retire', reason=request.data.get('reason', ''))
        return Response({'data': {'record': serializer(row).data, 'version': version}}, headers={'X-Resource-Version': str(version)})

    @action(detail=True, methods=['get'])
    def corrections(self, request, pk=None):
        from .history import correction_history
        return Response({'data': correction_history(self.get_object(), request.user, request.query_params)})

    @action(detail=True, methods=['post'])
    def duplicate_review(self, request, pk=None):
        version = PatientMergeService().dismiss(self.get_object(), request.data.get('other_id'),
            request.data.get('status', 'dismissed'), request.data.get('reason', ''), request.user, request_version(request))
        return Response({'data': {'version': version}}, headers={'X-Resource-Version': str(version)})

    @action(detail=True, methods=['post'])
    def merge_preview(self, request, pk=None):
        preview = PatientMergeService().preview(self.get_object(), request.data.get('target_id'), request.user)
        return Response({'data': preview})

    @action(detail=True, methods=['post'])
    def merge(self, request, pk=None):
        patient = PatientMergeService().merge(self.get_object(), request.data.get('token'), request.data.get('reason'),
            request.user, request_version(request), request.data.get('target_version'))
        return Response({'data': self.get_serializer(patient).data})
