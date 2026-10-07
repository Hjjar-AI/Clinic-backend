# backend/apps/accounts/models.py
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from django.core.validators import MinValueValidator


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('The Username field must be set')
        username = self.model.normalize_username(username).strip()
        if not username:
            raise ValueError('The Username field must be set')
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)  # Explicitly set active
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('doctor', 'Doctor'),
        ('receptionist', 'Receptionist'),
    ]
    username = models.CharField(max_length=80, unique=True)
    full_name = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='doctor')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    force_password_change = models.BooleanField(default=False)
    stamp_data = models.TextField(blank=True, null=True)
    preferences = models.JSONField(default=dict, blank=True)
    session_revoked_at = models.DateTimeField(null=True, blank=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    class Meta:
        constraints = [models.CheckConstraint(check=models.Q(version__gte=1), name='user_version_positive')]
        indexes = [
            models.Index(fields=['role', 'is_active']),
        ]

    def __str__(self):
        return self.username

    # F2: Use a distinct attribute name. Django's PermissionsMixin / ModelBackend
    # also caches on `_perm_cache`, but stores dotted strings ('app.codename').
    # Reusing that name caused `_get_perm_cache()` to return the dotted set, so
    # codename-only lookups like `has_perm('view_patients')` silently returned
    # False once any dotted check had primed the cache on the same instance.
    def _get_perm_cache(self):
        if not hasattr(self, '_codename_perm_cache'):
            all_perms = self.get_all_permissions()
            self._codename_perm_cache = {p.split('.')[-1] for p in all_perms}
        return self._codename_perm_cache

    def clear_permission_cache(self):
        """
        Reset cached permissions. Called by signals when groups or permissions change.
        Clears both our codename cache and Django's dotted-name cache so future
        has_perm() calls re-read from the database.
        """
        for attribute in ('_codename_perm_cache', '_perm_cache',
                          '_user_perm_cache', '_group_perm_cache'):
            self.__dict__.pop(attribute, None)

    def has_perm(self, perm, obj=None):
        """
        Support permission checks by codename only.
        Dotted names are delegated to Django's standard machinery.
        """
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        if '.' in perm:
            return super().has_perm(perm, obj)
        return perm in self._get_perm_cache()

    def has_module_perms(self, app_label):
        return super().has_module_perms(app_label)

    @transaction.atomic
    def increment_failed_attempts(self):
        # Item #8: read lockout policy from settings so the values declared in
        # .env (MAX_LOGIN_ATTEMPTS, LOGIN_LOCKOUT_MINUTES) actually apply.
        # Lock the row so simultaneous failed requests cannot overwrite each
        # other with the same incremented value.
        current = type(self).objects.select_for_update().get(pk=self.pk)
        current.failed_login_attempts += 1
        max_attempts = getattr(settings, 'MAX_LOGIN_ATTEMPTS', 10)
        lockout_minutes = getattr(settings, 'LOGIN_LOCKOUT_MINUTES', 15)
        if current.failed_login_attempts >= max_attempts:
            current.locked_until = timezone.now() + timezone.timedelta(minutes=lockout_minutes)
        current.save(update_fields=['failed_login_attempts', 'locked_until'])
        self.failed_login_attempts = current.failed_login_attempts
        self.locked_until = current.locked_until

    def reset_failed_attempts(self):
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(update_fields=['failed_login_attempts', 'locked_until'])

    def is_locked(self):
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False
