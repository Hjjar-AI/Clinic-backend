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
    metadata += [name for name in ['verified_at', 'verified_by', 'completed_at', 'completed_by', 'legacy_visit_follow_up']
                 if any(field.name == name for field in model._meta.fields)]
    meta = type('Meta', (), {'model': model, 'fields': metadata + fields, 'read_only_fields': metadata})
    return type('PatientRecordSerializer', (serializers.ModelSerializer,), {'Meta': meta})


class PatientRecordsMixin:
    @action(detail=True, methods=['get', 'post'])
    def records(self, request, pk=None):
        patient = self.get_object()
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
            except (TypeError, ValueError):
                raise ValidationError('إزاحة غير صالحة')
            return Response({'data': {'items': serializer(rows[offset:offset + 100], many=True).data,
                'total': rows.count(), 'version': patient.version}})
        data = request.data.get('fields', {})
        if not isinstance(data, dict):
            raise ValidationError({'fields': ['يلزم كائن حقول']})
        if any(key not in RECORDS[kind][1] for key in data) or request.data.get('operation', 'save') not in {'save', 'retire'}:
            raise ValidationError('حقول أو عملية غير صالحة')
        if request.data.get('operation') == 'retire' and not request.data.get('record_id'):
            raise ValidationError('يلزم تحديد السجل')
        validated = serializer(data=data, partial=bool(request.data.get('record_id')))
        validated.is_valid(raise_exception=True)
        row, version = service.save(patient, kind, validated.validated_data, request.user, request_version(request),
            record_id=request.data.get('record_id'), retire=request.data.get('operation') == 'retire', reason=request.data.get('reason', ''))
        return Response({'data': {'record': serializer(row).data, 'version': version}}, headers={'X-Resource-Version': str(version)})

    @action(detail=True, methods=['get'])
    def corrections(self, request, pk=None):
        patient = self.get_object()
        require_access(patient, request.user)
        history_ids = history_patient_ids(patient)
        rows = PatientCorrection.objects.filter(patient_id__in=history_ids).select_related('actor', 'patient').order_by('-created_at', '-pk')
        merges = PatientMerge.objects.filter(Q(source_id__in=history_ids) | Q(survivor_id__in=history_ids)).select_related('actor', 'source', 'survivor').order_by('-created_at', '-pk')
        if not request.user.has_perm('view_visits'):
            rows = rows.exclude(record_type__in=CLINICAL_KINDS)
        try:
            offset = max(0, int(request.query_params.get('offset', 0)))
        except (TypeError, ValueError):
            raise ValidationError('إزاحة غير صالحة')
        return Response({'data': {'items': [{'id': row.pk, 'actor': row.actor.full_name or row.actor.username,
            'reason': row.reason, 'record_type': row.record_type, 'record_id': row.record_id, 'patient_number': row.patient.patient_number,
            'changes': row.changes, 'created_at': row.created_at} for row in rows[offset:offset + 100]],
            'total': rows.count(), 'merges': [{'id': event.pk, 'source': event.source.patient_number,
                'survivor': event.survivor.patient_number, 'actor': event.actor.full_name or event.actor.username,
                'reason': event.reason, 'created_at': event.created_at} for event in merges[:100]]}})

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
