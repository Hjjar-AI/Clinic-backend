# backend/apps/notifications/views.py
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer
from .services import NotificationService


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    service = NotificationService()

    def get_queryset(self):
        unread_only = self.request.query_params.get('unread_only') == 'true'
        return self.service.get_for_user(self.request.user.id, unread_only)

    def perform_destroy(self, instance):
        self.service.delete(instance.pk, self.request.user.id)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        unread_count = self.service.get_for_user(
            self.request.user.id,
            unread_only=True
        ).count()

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)

            if isinstance(response.data, dict):
                inner = response.data.get('data')
                if isinstance(inner, dict) and isinstance(inner.get('meta'), dict):
                    inner['meta']['unread_count'] = unread_count

            return response

        serializer = self.get_serializer(queryset, many=True)

        return Response(
            {
                'data': {
                    'items': serializer.data,
                    'meta': {
                        'unread_count': unread_count,
                    },
                }
            }
        )

    @action(detail=False, methods=['put'])
    def mark_all_read(self, request):
        self.service.mark_all_read(request.user.id)
        return Response({'message': 'تم قراءة جميع الإشعارات'})

    @action(detail=True, methods=['put'])
    def mark_read(self, request, pk=None):
        self.service.mark_read(pk, request.user.id)
        return Response({'message': 'تم قراءة الإشعار'})

    @action(detail=False, methods=['delete'])
    def delete_all_read(self, request):
        self.service.delete_all_read(request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)
