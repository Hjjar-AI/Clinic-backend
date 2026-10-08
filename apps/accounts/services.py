from core.mutation import parse_version
# backend/apps/accounts/services.py
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.password_validation import validate_password
from rest_framework.exceptions import AuthenticationFailed
from .models import User
from django.db import transaction
from core.exceptions import ConflictError
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from core.permissions import ALL_PERMISSIONS, DEFAULT_PERMISSIONS
from core.signals import log_action


class AuthService:

    def login(self, request, username, password, remember=False):
        username = User.normalize_username(username).strip()
        user = User.objects.filter(username=username).first()
        if user is None:
            User().set_password(password)
        if not user or not user.check_password(password):
            if user:
                user.increment_failed_attempts()
            # 401, not 400 — DRF's AuthenticationFailed carries the right
            # WWW-Authenticate semantics and is handled by the default
            # exception handler, which our custom handler then re-envelopes.
            raise AuthenticationFailed('بيانات الاعتماد غير صحيحة')

        if user.is_locked():
            raise AuthenticationFailed('الحساب مقفل')

        if not user.is_active:
            raise AuthenticationFailed('الحساب معطل')

        # Reset failed attempts and set last_login in one save
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = timezone.now()
        user.save(update_fields=['failed_login_attempts', 'locked_until', 'last_login'])

        login(request, user)

        # Store login time for session invalidation checks
        request.session['login_time'] = timezone.now().isoformat()

        if not remember:
            request.session.set_expiry(0)
        else:
            request.session.set_expiry(86400 * 30)

        return user

    def logout(self, request):
        logout(request)
        request.session.flush()

    @transaction.atomic
    def change_password(self, user, current_password, new_password, request=None):
        user = User.objects.select_for_update().get(pk=user.pk)
        if not user.check_password(current_password):
            raise ValidationError(['كلمة المرور الحالية غير صحيحة'])
        try:
            validate_password(new_password, user)
        except ValidationError as e:
            raise ValidationError(e.messages)

        user.set_password(new_password)
        user.version += 1
        user.force_password_change = False
        user.session_revoked_at = timezone.now()
        user.save()

        if request:
            # Flush current session to force re-login
            request.session.flush()


class UserService:

    @staticmethod
    def _apply_role_group(user, role):
        content_type, _ = ContentType.objects.get_or_create(app_label='auth', model='permission')
        for codename, label in ALL_PERMISSIONS.items():
            Permission.objects.get_or_create(
                content_type=content_type,
                codename=codename,
                defaults={'name': label},
            )
        group, created = Group.objects.get_or_create(name=role)
        if created:
            codenames = DEFAULT_PERMISSIONS.get(role, [])
            group.permissions.set(Permission.objects.filter(content_type=content_type, codename__in=codenames))
        user.groups.set([group])

    @transaction.atomic
    def create_user(self, username, password, full_name, role, stamp_data=None):
        if User.objects.filter(username=username).exists():
            raise ValidationError(['اسم المستخدم موجود بالفعل'])
        try:
            validate_password(password)
        except ValidationError as e:
            raise ValidationError(e.messages)
        user = User.objects.create_user(
            username=username,
            password=password,
            full_name=full_name,
            role=role,
            force_password_change=True,
            stamp_data=stamp_data,
        )
        self._apply_role_group(user, role)
        return user

    @transaction.atomic
    def update_user(self, user, request, expected_version=None, **data):
        # Evaluate rows in a stable order; count() alone does not acquire row locks.
        active_admin_ids = list(User.objects.select_for_update().filter(
            role='admin', is_active=True
        ).order_by('pk').values_list('pk', flat=True))
        user = User.objects.select_for_update().get(pk=user.pk)
        expected_version = parse_version(expected_version)
        if user.version != expected_version:
            raise ConflictError('تم تعديل المستخدم بواسطة مستخدم آخر')
        # Enforce privilege escalation prevention: only superusers can modify these fields.
        if not request.user.is_superuser:
            data.pop('is_staff', None)
            data.pop('is_superuser', None)
            data.pop('is_active', None)

        if user.role == 'admin' and user.is_active:
            losing_admin = data.get('role', user.role) != 'admin' or not data.get('is_active', user.is_active)
            if losing_admin and len(active_admin_ids) <= 1:
                raise ValidationError({'user': ['لا يمكن تعطيل أو تغيير دور آخر حساب مدير نشط']})

        if 'password' in data:
            new_password = data.pop('password')
            try:
                validate_password(new_password, user)
            except ValidationError as e:
                raise ValidationError(e.messages)
            user.set_password(new_password)
            user.force_password_change = True
            user.session_revoked_at = timezone.now()

        data.pop('force_password_change', None)
        old_role = user.role
        for k, v in data.items():
            if k != 'version':  # Exclude version from direct assignment
                setattr(user, k, v)
        user.version += 1
        user.save()
        if user.role != old_role:
            previous_direct = sorted(user.user_permissions.values_list('codename', flat=True))
            user.user_permissions.clear()
            self._apply_role_group(user, user.role)
            user.session_revoked_at = timezone.now()
            user.save(update_fields=['session_revoked_at'])
            log_action(request.user.id, 'role_change', 'User', user.id, {
                'summary': f'Role changed from {old_role} to {user.role}; direct grants reset',
                'before_role': old_role,
                'after_role': user.role,
                'removed_direct_permissions': previous_direct,
            })
        return user

    @transaction.atomic
    def deactivate_user(self, user, actor, expected_version=None):
        active_admin_ids = list(User.objects.select_for_update().filter(
            role='admin', is_active=True
        ).order_by('pk').values_list('pk', flat=True))
        user = User.objects.select_for_update().get(pk=user.pk)
        from core.mutation import check_mutation
        check_mutation(user, expected_version)
        if user.pk == actor.pk:
            raise ValidationError({'user': ['لا يمكنك تعطيل حسابك الحالي']})
        if user.role == 'admin':
            if user.is_active and len(active_admin_ids) <= 1:
                raise ValidationError({'user': ['لا يمكن تعطيل آخر حساب مدير نشط']})
        user.is_active = False
        user.session_revoked_at = timezone.now()
        user.version += 1
        user.save(update_fields=['is_active', 'session_revoked_at', 'version'])
        return user
