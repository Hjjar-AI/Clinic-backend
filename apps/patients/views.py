from core.mutation import request_version
from core.access import accessible_patients
# backend/apps/patients/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Patient, PatientDocument
from .serializers import PatientSerializer, PatientDocumentSerializer, CareTeamMemberSerializer
from .services import PatientService, PatientDocumentService
from core.permissions import (
    PERM_DELETE_PATIENT,
    PERM_EDIT_PATIENT,
    PERM_VIEW_PATIENTS,
    PERM_MANAGE_PATIENT_DOCUMENTS,
    PERM_MANAGE_USERS,
    HasViewPatients,
    HasEditPatient,
    HasDeletePatient,
    HasManagePatientDocuments,
    HasManageUsers,
    CanAccessPatient,
)
from core.upload_security import validate_upload
from django.core.exceptions import ValidationError
from core.exceptions import error_response
from django.http import FileResponse
from django.core.files.storage import default_storage
from core.signals import log_action


class PatientViewSet(viewsets.ModelViewSet):
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]
    service = PatientService()

    def get_permissions(self):
        # Item #2: CanAccessPatient is layered on every action that fetches a
        # specific patient via get_object(), as defense-in-depth on top of the
        # queryset scoping in PatientService.list_patients.
        if self.action in ['create', 'duplicates']:
            permission_classes = [permissions.IsAuthenticated, HasEditPatient]
        elif self.action in ['update', 'partial_update']:
            permission_classes = [permissions.IsAuthenticated, HasEditPatient, CanAccessPatient]
        elif self.action in ['destroy', 'archive', 'restore']:
            permission_classes = [permissions.IsAuthenticated, HasDeletePatient, CanAccessPatient]
        elif self.action == 'anonymize':
            permission_classes = [permissions.IsAuthenticated, HasDeletePatient, CanAccessPatient]
        elif self.action in ['list', 'search', 'all_light']:
            permission_classes = [permissions.IsAuthenticated, HasViewPatients]
        elif self.action in ['risk_history', 'timeline']:
            from core.permissions import HasViewVisits
            permission_classes = [permissions.IsAuthenticated, HasViewPatients, HasViewVisits, CanAccessPatient]
        elif self.action in ['retrieve', 'care_team']:
            permission_classes = [permissions.IsAuthenticated, HasViewPatients, CanAccessPatient]
        elif self.action in ['care_team_add', 'care_team_remove']:
            permission_classes = [permissions.IsAuthenticated, HasManageUsers, CanAccessPatient]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user
        if user.has_perm(PERM_VIEW_PATIENTS):
            if self.action == 'restore':
                from core.access import accessible_patients
                return accessible_patients(user, include_archived=True)
            return self.service.list_patients(user, self.request.query_params)
        return Patient.objects.none()

    def _paginate_queryset(self, qs, request):
        # F7: The frontend apiClient rewrites GET `limit` -> `per_page`. Read
        # `per_page` first so caller intent is honored; fall back to `limit`.
        raw_limit = request.query_params.get('per_page') or request.query_params.get('limit', 20)
        try:
            limit = int(raw_limit)
            limit = max(1, min(limit, 200))
        except (ValueError, TypeError):
            limit = 20
        try:
            offset = max(0, int(request.query_params.get('offset', 0)))
        except (ValueError, TypeError):
            offset = 0
        total = qs.count()
        items = list(qs[offset:offset + limit])
        return items, total, limit, offset

    def perform_create(self, serializer):
        instance = self.service.create_patient(serializer.validated_data, self.request.user)
        serializer.instance = instance

    def perform_update(self, serializer):
        instance = self.get_object()
        version = request_version(self.request)
        updated = self.service.update_patient(
            instance,
            serializer.validated_data,
            self.request.user,
            version
        )
        serializer.instance = updated

    def perform_destroy(self, instance):
        self.service.soft_delete_patient(instance, self.request.user, request_version(self.request))

    @action(detail=False, methods=['post'])
    def duplicates(self, request):
        exclude_id = request.data.get('exclude_id')
        try:
            exclude_id = int(exclude_id) if exclude_id else None
        except (ValueError, TypeError):
            return error_response(400, 'exclude_id must be an integer', {})
        matches = self.service.find_duplicates(request.user, request.data, exclude_id)
        return Response({
            'data': {
                'matches': self.get_serializer(matches, many=True).data,
                'has_matches': bool(matches),
            }
        })

    @action(detail=False, methods=['get'])
    def search(self, request):
        qs = self.get_queryset()
        items, total, limit, offset = self._paginate_queryset(qs, request)
        serializer = self.get_serializer(items, many=True)
        return Response({
            'data': {
                'patients': serializer.data,
                'meta': {'total': total, 'limit': limit, 'offset': offset}
            }
        })

    @action(detail=False, methods=['get'], url_path='all_light')
    def all_light(self, request):
        try:
            limit = int(request.query_params.get('limit', 1000))
            limit = max(1, min(limit, 5000))
        except ValueError:
            limit = 1000
        patients = self.service.list_patients(request.user, {})[:limit]
        data = [{'id': p.id, 'first_name': p.first_name, 'surname': p.surname} for p in patients]
        return Response({'data': data})

    @action(detail=True, methods=['post'])
    def anonymize(self, request, pk=None):
        patient = self.get_object()
        self.service.anonymize(patient, request.user, request_version(request))
        return Response({'message': 'تم تقييد الهوية؛ تحتفظ المستندات المعتمدة ببياناتها التاريخية'})

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        patient = self.get_object()
        self.service.soft_delete_patient(patient, request.user, request_version(request))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        patient = self.service.restore_patient(self.get_object(), request.user, request_version(request))
        return Response({'data': self.get_serializer(patient).data})

    @action(detail=True, methods=['get'])
    def risk_history(self, request, pk=None):
        patient = self.get_object()
        visits = patient.visits.filter(deleted_at__isnull=True).order_by('-visit_date')
        items, total, limit, offset = self._paginate_queryset(visits, request)
        history = [{
            'visit_id': v.id,
            'visit_date': v.visit_date,
            'suicide_risk_level': v.suicide_risk_level,
            'violence_risk_level': v.violence_risk_level,
            'firearm_access': v.firearm_access,
        } for v in items]
        return Response({
            'data': {
                'risk_history': history,
                'meta': {'total': total, 'limit': limit, 'offset': offset}
            }
        })

    @action(detail=True, methods=['get'])
    def timeline(self, request, pk=None):
        patient = self.get_object()
        visits = patient.visits.filter(deleted_at__isnull=True).prefetch_related(
            'visit_diagnoses__diagnosis',
            'visit_medications__medication',
        ).order_by('-visit_date')
        items, total, limit, offset = self._paginate_queryset(visits, request)
        timeline = [{
            'id': v.id,
            'visit_date': v.visit_date,
            'main_complaints': v.main_complaints,
            'diagnoses': v.get_diagnoses(),
            'medications': v.get_medications(),
            'follow_up_date': v.follow_up_date,
        } for v in items]
        return Response({
            'data': {
                'timeline': timeline,
                'meta': {'total': total, 'limit': limit, 'offset': offset}
            }
        })

    @action(detail=True, methods=['get'])
    def care_team(self, request, pk=None):
        patient = self.get_object()
        members = self.service.get_care_team(patient)
        serializer = CareTeamMemberSerializer(members, many=True)
        return Response({'data': {'care_team': serializer.data, 'version': patient.version}},
                        headers={'X-Resource-Version': str(patient.version)})

    @action(detail=True, methods=['post'])
    def care_team_add(self, request, pk=None):
        patient = self.get_object()
        user_id = request.data.get('user_id')
        role = request.data.get('role', '')
        member, version = self.service.add_care_team_member(
            patient, user_id, role, request_version(request))
        log_action(request.user.id, 'care_team_add', 'Patient', patient.pk, {'user_id': member.user_id})
        serializer = CareTeamMemberSerializer(member)
        return Response({'data': serializer.data}, status=status.HTTP_201_CREATED,
                        headers={'X-Resource-Version': str(version)})

    @action(detail=True, methods=['delete'], url_path='care-team/(?P<user_id>[^/.]+)')
    def care_team_remove(self, request, pk=None, user_id=None):
        patient = self.get_object()
        version = self.service.remove_care_team_member(patient, user_id, request_version(request))
        log_action(request.user.id, 'care_team_remove', 'Patient', patient.pk, {'user_id': user_id})
        return Response(status=status.HTTP_204_NO_CONTENT, headers={'X-Resource-Version': str(version)})


class PatientDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = PatientDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, HasViewPatients, HasManagePatientDocuments]
    service = PatientDocumentService()

    def get_queryset(self):
        patient = get_object_or_404(accessible_patients(self.request.user, include_archived=True),
                                    pk=self.kwargs.get('patient_pk'))
        return PatientDocument.objects.filter(patient=patient).select_related('uploaded_by')

    def perform_update(self, serializer):
        serializer.instance = self.service.update_document(
            self.get_object(), serializer.validated_data, request_version(self.request))

    def create(self, request, patient_pk=None):
        patient = get_object_or_404(accessible_patients(request.user), pk=patient_pk)
        file = request.FILES.get('file')
        if not file:
            return error_response(400, 'الملف مطلوب', {})
        try:
            validate_upload(file)
        except ValidationError as e:
            return error_response(400, str(e), {})
        category = request.data.get('category', 'other')
        description = request.data.get('description', '')
        doc = self.service.upload_document(patient, file, request.user, category, description)
        serializer = self.get_serializer(doc)
        return Response({'data': serializer.data}, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        self.service.soft_delete_document(instance, request_version(self.request))

    @action(detail=True, methods=['get'])
    def download(self, request, patient_pk=None, pk=None):
        document = self.get_object()
        if not default_storage.exists(document.filepath):
            return error_response(404, 'الملف غير موجود في التخزين', {})
        log_action(request.user.id, 'download_document', 'PatientDocument', document.id, {
            'summary': f'Downloaded patient document {document.original_filename}',
            'patient_id': document.patient_id,
        })
        return FileResponse(
            default_storage.open(document.filepath, 'rb'),
            as_attachment=True,
            filename=document.original_filename,
            content_type=document.mime_type or 'application/octet-stream',
        )
