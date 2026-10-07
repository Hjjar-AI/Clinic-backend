# backend/apps/tasks/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import UserTask
from .serializers import TaskSerializer
from .services import TaskService
from core.permissions import (
    PERM_MANAGE_TASKS,
    PERM_VIEW_REPORTS,
    HasManageTasks,
    HasViewReports,
)
from core.exceptions import error_response


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    service = TaskService()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy',
                           'complete', 'cancel', 'activate', 'transition', 'reorder']:
            permission_classes = [permissions.IsAuthenticated, HasManageTasks]
        else:
            permission_classes = [permissions.IsAuthenticated, HasManageTasks]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        assigned_filter = self.request.query_params.get('assigned_to', '')
        status_filter = self.request.query_params.get('status', '')
        return self.service.get_for_user(
            self.request.user, assigned_filter, status_filter, self.request.query_params
        )

    def perform_create(self, serializer):
        instance = self.service.create_task(self.request.user, serializer.validated_data)
        serializer.instance = instance

    def perform_update(self, serializer):
        instance = self.get_object()
        version = self.request.data.get('version')
        if version is not None:
            try:
                version = int(version)
            except (ValueError, TypeError):
                version = None
        data = serializer.validated_data.copy()
        data.pop('version', None)
        # Service owns the optimistic-lock check + field assignment, matching
        # every other mutating resource in this codebase.
        serializer.instance = self.service.update_task(instance, data, version, actor=self.request.user)

    def perform_destroy(self, instance):
        self.service.delete_task(instance)

    @action(detail=True, methods=['put'])
    def complete(self, request, pk=None):
        task = self.get_object()
        version = request.data.get('version')
        if version is not None:
            try:
                version = int(version)
            except (ValueError, TypeError):
                version = None
        updated = self.service.complete_task(task, request.user, version)
        return Response({'data': self.get_serializer(updated).data, 'message': 'تم إكمال المهمة'})

    @action(detail=True, methods=['put'])
    def cancel(self, request, pk=None):
        task = self.get_object()
        version = request.data.get('version')
        if version is not None:
            try:
                version = int(version)
            except (ValueError, TypeError):
                version = None
        updated = self.service.cancel_task(task, request.user, version, request.data.get('reason', ''))
        return Response({'data': self.get_serializer(updated).data, 'message': 'تم إلغاء المهمة'})

    @action(detail=True, methods=['put'])
    def activate(self, request, pk=None):
        task = self.get_object()
        version = request.data.get('version')
        if version is not None:
            try:
                version = int(version)
            except (ValueError, TypeError):
                version = None
        updated = self.service.activate_task(task, request.user, version)
        return Response({'data': self.get_serializer(updated).data, 'message': 'تم تنشيط المهمة'})

    @action(detail=True, methods=['put'])
    def transition(self, request, pk=None):
        task = self.get_object()
        target = request.data.get('status')
        if not target:
            return error_response(400, 'status is required', {'status': ['هذا الحقل مطلوب']})
        version = request.data.get('version')
        try:
            version = int(version) if version is not None else None
        except (ValueError, TypeError):
            version = None
        updated = self.service.transition_task(
            task, target, request.user, version, request.data.get('reason', '')
        )
        return Response({'data': self.get_serializer(updated).data})

    @action(detail=False, methods=['put'])
    def reorder(self, request):
        order_list = request.data.get('order', [])
        if not isinstance(order_list, list):
            return error_response(400, 'order must be list', {})
        # Pass user to service for scope validation
        self.service.reorder_tasks(order_list, request.user)
        return Response({'message': 'تم إعادة الترتيب'})
