from core.mutation import request_version
# backend/apps/visits/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Visit, VisitAttachment
from .serializers import VisitSerializer, VisitAttachmentSerializer
from .services import VisitService, VisitAttachmentService
from core.permissions import (
    PERM_ADD_VISIT,
    PERM_EDIT_VISIT,
    PERM_DELETE_VISIT,
    PERM_VIEW_VISITS,
    PERM_MANAGE_PATIENT_DOCUMENTS,
    HasAddVisit,
    HasEditVisit,
    HasDeleteVisit,
    HasViewVisits,
    HasManagePatientDocuments,
    CanAccessVisit,
)
from core.upload_security import validate_upload
from apps.patients.models import Patient
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime
from core.exceptions import error_response
from core.query_utils import apply_ordering
from django.db.models import Q
from django.core.files.storage import default_storage
from django.http import FileResponse
from core.signals import log_action


class VisitViewSet(viewsets.ModelViewSet):
    serializer_class = VisitSerializer
    permission_classes = [permissions.IsAuthenticated]
    service = VisitService()

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [permissions.IsAuthenticated, HasAddVisit]
        elif self.action in ['update', 'partial_update', 'transition']:
            permission_classes = [permissions.IsAuthenticated, HasEditVisit, CanAccessVisit]
        elif self.action == 'destroy':
            permission_classes = [permissions.IsAuthenticated, HasDeleteVisit, CanAccessVisit]
        elif self.action in ['retrieve', 'list_attachments', 'revisions', 'issued_documents']:
            permission_classes = [permissions.IsAuthenticated, HasViewVisits, CanAccessVisit]
        elif self.action in ['attachments', 'attachment_detail']:
            permission_classes = [permissions.IsAuthenticated, HasManagePatientDocuments, CanAccessVisit]
        elif self.action == 'mark_all_overdue':
            permission_classes = [permissions.IsAuthenticated, HasEditVisit]
        elif self.action == 'list':
            permission_classes = [permissions.IsAuthenticated, HasViewVisits]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        from .selectors import list_queryset
        return list_queryset(self.request.user, self.request.query_params, self.kwargs)

    def _paginate_queryset(self, qs, request):
        from core.collections import offset_page
        return offset_page(qs, request.query_params)

    def _check_patient_access(self, patient):
        from core.access import accessible_patients
        if not accessible_patients(self.request.user).filter(pk=patient.pk).exists():
            self.permission_denied(self.request)

    def perform_create(self, serializer):
        patient_pk = self.kwargs.get('patient_pk')
        if patient_pk:
            patient = get_object_or_404(Patient, pk=patient_pk)
            self._check_patient_access(patient)
            instance = self.service.create_visit(patient, serializer.validated_data, self.request.user)
            serializer.instance = instance
        else:
            patient = serializer.validated_data.pop('patient', None)
            if not patient:
                # F8: previously returned an error_response here, but DRF ignores
                # the return value of perform_create, producing a bogus 201 with
                # no instance. Raise so DRF returns a proper 400.
                raise ValidationError({'patient_id': ['يجب تحديد المريض']})
            self._check_patient_access(patient)
            instance = self.service.create_visit(patient, serializer.validated_data, self.request.user)
            serializer.instance = instance

    def perform_update(self, serializer):
        instance = self.get_object()
        version = request_version(self.request)
        data = serializer.validated_data
        data.pop('version', None)
        updated = self.service.update_visit(instance, data, self.request.user, version)
        serializer.instance = updated

    def perform_destroy(self, instance):
        self.service.soft_delete_visit(instance, self._required_version(self.request))

    @action(detail=True, methods=['put'])
    def transition(self, request, pk=None):
        visit = self.get_object()
        target = request.data.get('status')
        if not target:
            return error_response(400, 'status is required', {'status': ['هذا الحقل مطلوب']})
        updated = self.service.transition(
            visit,
            target,
            request.user,
            self._required_version(request),
            request.data.get('reason', ''),
        )
        return Response({'data': self.get_serializer(updated).data})

    @staticmethod
    def _required_version(request):
        from core.mutation import request_version
        return request_version(request)

    @action(detail=False, methods=['post'], url_path='mark-all-overdue')
    def mark_all_overdue(self, request):
        count = self.service.mark_all_overdue(request.user)
        return Response({'data': {'updated': count}})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, HasManagePatientDocuments])
    def attachments(self, request, pk=None):
        visit = self.get_object()
        file = request.FILES.get('file')
        if not file:
            return error_response(400, 'الملف مطلوب', {})
        try:
            validate_upload(file)
        except ValidationError as e:
            return error_response(400, str(e), {})
        attachment = VisitAttachmentService().upload_attachment(visit, file, request.user, self._required_version(request))
        serializer = VisitAttachmentSerializer(attachment)
        visit.refresh_from_db(fields=['version'])
        return Response({'data': serializer.data}, status=201, headers={'X-Resource-Version': str(visit.version)})

    @action(detail=True, methods=['get'])
    def list_attachments(self, request, pk=None):
        visit = self.get_object()
        attachments = visit.attachments.filter(deleted_at__isnull=True)
        items, total, limit, offset = self._paginate_queryset(attachments, request)
        serializer = VisitAttachmentSerializer(items, many=True)
        return Response({
            'data': {
                'attachments': serializer.data,
                'meta': {'total': total, 'limit': limit, 'offset': offset}
            }
        })

    @action(
        detail=True,
        methods=['get', 'delete'],
        url_path=r'attachments/(?P<attachment_id>\d+)',
    )
    def attachment_detail(self, request, pk=None, attachment_id=None):
        visit = self.get_object()
        attachment = get_object_or_404(
            visit.attachments,
            pk=attachment_id,
            deleted_at__isnull=True,
        )
        if request.method == 'DELETE':
            VisitAttachmentService().soft_delete_attachment(attachment, self._required_version(request), actor=request.user)
            log_action(request.user.id, 'archive', 'VisitAttachment', attachment.id, {
                'summary': f'Archived visit attachment {attachment.original_filename}',
                'visit_id': visit.id,
            })
            visit.refresh_from_db(fields=['version'])
            return Response(status=status.HTTP_204_NO_CONTENT, headers={'X-Resource-Version': str(visit.version)})
        if not default_storage.exists(attachment.filepath):
            return error_response(404, 'الملف غير موجود في التخزين', {})
        log_action(request.user.id, 'download_attachment', 'VisitAttachment', attachment.id, {
            'summary': f'Downloaded visit attachment {attachment.original_filename}',
            'visit_id': visit.id,
        })
        return FileResponse(
            default_storage.open(attachment.filepath, 'rb'),
            as_attachment=True,
            filename=attachment.original_filename,
            content_type=attachment.mime_type or 'application/octet-stream',
        )

    @action(detail=True, methods=['get'])
    def revisions(self, request, pk=None):
        visit = self.get_object()
        from .selectors import revision_history
        return Response({'data': revision_history(visit, request.query_params)}, headers={'Cache-Control': 'no-store'})

    @action(detail=True, methods=['get'], url_path='issued-documents')
    def issued_documents(self, request, pk=None):
        visit = self.get_object()
        from .selectors import issued_documents
        return Response({'data': issued_documents(visit, request.user, request.query_params)}, headers={'Cache-Control': 'no-store'})
