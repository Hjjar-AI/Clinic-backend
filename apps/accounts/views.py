from core.mutation import request_version
# backend/apps/accounts/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .serializers import UserSerializer, LoginSerializer, ChangePasswordSerializer
from .services import AuthService, UserService
from .models import User
from core.permissions import (
    PERM_MANAGE_USERS,
    HasManageUsers,
    HasViewDoctors,
)
from django.contrib.auth.models import Permission
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

from core.exceptions import ConflictError, error_response
from apps.notifications.services import NotificationService
from core.permissions import ALL_PERMISSIONS, DEFAULT_PERMISSIONS
from core.signals import log_action
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q
from core.query_utils import apply_ordering


@method_decorator(transaction.non_atomic_requests, name='dispatch')
class AuthViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer
    auth_service = AuthService()
    notification_service = NotificationService()

    @action(detail=False, methods=['post'])
    @method_decorator(csrf_protect)
    def login(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self.auth_service.login(
            request,
            serializer.validated_data['username'],
            serializer.validated_data['password'],
            serializer.validated_data.get('remember', False)
        )
        data = UserSerializer(user).data
        data['unread_count'] = self.notification_service.get_for_user(
            user.id, unread_only=True
        ).count()
        return Response({'data': {'user': data}, 'message': 'Login successful'})

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def logout(self, request):
        self.auth_service.logout(request)
        return Response({'message': 'Logout successful'})

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        user = request.user
        data = UserSerializer(user).data
        # Removed: data['all_permissions'] = list(all_perms)
        data['unread_count'] = self.notification_service.get_for_user(
            user.id, unread_only=True
        ).count()
        return Response({'data': {'user': data}})

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def change_password(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.auth_service.change_password(
            request.user,
            serializer.validated_data['current_password'],
            serializer.validated_data['new_password'],
            request=request,
        )
        return Response({'message': 'Password changed'})


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.filter(is_active=True)
    serializer_class = UserSerializer
    service = UserService()

    def get_permissions(self):
        if self.action in ['create', 'list', 'retrieve', 'update', 'partial_update', 'destroy',
                           'permissions', 'update_permissions']:
            permission_classes = [permissions.IsAuthenticated, HasManageUsers]
        elif self.action == 'doctors':
            permission_classes = [permissions.IsAuthenticated, HasViewDoctors]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(username__icontains=search) | Q(full_name__icontains=search))
        role = self.request.query_params.get('role')
        if role:
            if role not in dict(User.ROLE_CHOICES):
                raise ValidationError({'role': ['الدور غير صالح']})
            qs = qs.filter(role=role)
        return apply_ordering(qs, self.request.query_params, {
            'username': 'username',
            'full_name': 'full_name',
            'role': 'role',
            'date_joined': 'date_joined',
        }, default='username')

    def perform_create(self, serializer):
        user = self.service.create_user(
            username=serializer.validated_data['username'],
            password=serializer.validated_data.get('password'),
            full_name=serializer.validated_data.get('full_name', ''),
            role=serializer.validated_data.get('role', 'doctor'),
            stamp_data=serializer.validated_data.get('stamp_data'),
        )
        serializer.instance = user

    def perform_update(self, serializer):
        instance = self.get_object()
        data = serializer.validated_data.copy()
        # No need to pop/reinsert password; service handles it.
        # Remove version from data to avoid accidental overwrite.
        data.pop('version', None)
        version = request_version(self.request)
        updated_user = self.service.update_user(
            instance, request=self.request, expected_version=version, **data
        )
        serializer.instance = updated_user

    def perform_destroy(self, instance):
        self.service.deactivate_user(instance, self.request.user, request_version(self.request))

    @action(detail=False, methods=['get'])
    def doctors(self, request):
        doctors = self.queryset.filter(role__in=['doctor', 'admin'])
        return Response({'data': list(doctors.values('id', 'username', 'full_name', 'role'))})

    @action(detail=True, methods=['get'])
    def permissions(self, request, pk=None):
        user = self.get_object()
        all_perms = ALL_PERMISSIONS
        effective_codenames = sorted(name for name in ALL_PERMISSIONS if user.has_perm(name))
        direct_codenames = sorted(
            set(user.user_permissions.values_list('codename', flat=True)) & set(ALL_PERMISSIONS)
        )
        return Response({
            'data': {
                'all_permissions': [
                    {'codename': codename, 'label': label}
                    for codename, label in all_perms.items()
                ],
                'current_permissions': direct_codenames,
                'inherited_permissions': sorted(set(effective_codenames) - set(direct_codenames)),
                'effective_permissions': effective_codenames,
                'role_matrix': DEFAULT_PERMISSIONS,
                'version': user.version,
            }
        })

    @action(detail=True, methods=['put'])
    @transaction.atomic
    def update_permissions(self, request, pk=None):
        user = self.get_object()
        perm_codenames = request.data.get('permissions', [])
        if not isinstance(perm_codenames, list) or any(not isinstance(item, str) for item in perm_codenames):
            raise ValidationError({'permissions': ['قائمة أسماء صلاحيات مطلوبة']})
        expected_version = request_version(request)
        user = User.objects.select_for_update().get(pk=user.pk)
        if user.version != expected_version:
            raise ConflictError('تم تعديل صلاحيات المستخدم بواسطة مستخدم آخر')
        unknown = sorted(set(perm_codenames) - set(ALL_PERMISSIONS))
        if unknown:
            return error_response(400, 'صلاحيات غير معروفة', {'permissions': unknown})
        before = sorted(user.user_permissions.values_list('codename', flat=True))
        user.user_permissions.clear()
        if perm_codenames:
            perms = Permission.objects.filter(codename__in=perm_codenames)
            user.user_permissions.set(perms)
        user.session_revoked_at = timezone.now()
        user.version += 1
        user.save(update_fields=['session_revoked_at', 'version'])
        log_action(request.user.id, 'permissions_change', 'User', user.id, {
            'summary': f'Permissions changed for {user.username}',
            'before': before,
            'after': sorted(perm_codenames),
        })
        return Response({'message': 'تم تحديث الصلاحيات'})
