from django.db import models
from core.constraints import check_constraint
from django.core.validators import MinValueValidator
from django.utils import timezone

def normalize_optional_text(instance):
    # Missing text has one representation; dates, numbers, booleans and relations keep NULL.
    for field in instance._meta.concrete_fields:
        if isinstance(field, (models.CharField, models.TextField)) and field.blank and not field.null and getattr(instance, field.name) is None:
            setattr(instance, field.name, '')


class OptionalTextModel(models.Model):
    def save(self, *args, **kwargs):
        normalize_optional_text(self)
        return super().save(*args, **kwargs)

    def clean_fields(self, exclude=None):
        normalize_optional_text(self)
        return super().clean_fields(exclude=exclude)

    class Meta:
        abstract = True


class TimeStampedModel(OptionalTextModel):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class StoredFileMetadata(models.Model):
    """Shared columns only; parents and upload permissions remain domain-owned."""
    filename = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    filepath = models.CharField(max_length=500)
    file_size = models.PositiveBigIntegerField(null=True, blank=True)
    checksum = models.CharField(max_length=64, blank=True, editable=False)
    mime_type = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        abstract = True


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True, is_active=True)

class SoftDeleteModel(OptionalTextModel):
    version = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    archived_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_archived')
    archive_reason = models.CharField(max_length=500, blank=True, default='')

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self, actor=None, reason=''):
        from .request_context import get_current_request
        request = get_current_request()
        self.archived_by = actor or (request.user if request and request.user.is_authenticated else None)
        self.archive_reason = reason or 'Archived'
        now = timezone.now()
        self.deleted_at = now
        self.is_active = False
        update_fields = ['deleted_at', 'is_active']
        if hasattr(self, 'version'):
            self.version += 1
            update_fields.append('version')
        if hasattr(self, 'updated_at'):
            self.updated_at = now
            update_fields.append('updated_at')
        self.save(update_fields=update_fields + ['archived_by', 'archive_reason'])

    def restore(self):
        now = timezone.now()
        self.deleted_at = None
        self.is_active = True
        self.archived_by = None
        self.archive_reason = ''
        update_fields = ['deleted_at', 'is_active', 'archived_by', 'archive_reason']
        if hasattr(self, 'version'):
            self.version += 1
            update_fields.append('version')
        if hasattr(self, 'updated_at'):
            self.updated_at = now
            update_fields.append('updated_at')
        self.save(update_fields=update_fields)

class ImmutableQuerySet(models.QuerySet):
    def bulk_create(self, objs, *args, **kwargs):
        from django.core.exceptions import ValidationError
        # Positional arguments include batch_size, ignore_conflicts,
        # update_conflicts. Plain bulk appends remain permitted.
        if kwargs.get('update_conflicts') or (len(args) > 2 and args[2]):
            raise ValidationError('Historical records are immutable')
        return super().bulk_create(objs, *args, **kwargs)

    def update(self, **kwargs):
        from django.core.exceptions import ValidationError
        raise ValidationError('Historical records are immutable')
    def bulk_update(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        raise ValidationError('Historical records are immutable')
    def delete(self):
        from django.core.exceptions import ValidationError
        raise ValidationError('Historical records are immutable')

class ImmutableModel(models.Model):
    objects = ImmutableQuerySet.as_manager()
    class Meta:
        abstract = True
    def save(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        if not self._state.adding or (self.pk and type(self).objects.filter(pk=self.pk).exists()):
            raise ValidationError('Historical records are immutable')
        return super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        raise ValidationError('Historical records are immutable')


class AuditLog(ImmutableModel):
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=50)
    entity_type = models.CharField(max_length=50)
    entity_id = models.PositiveBigIntegerField()
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['entity_type', 'entity_id']),
        ]

    def __str__(self):
        return f"{self.action} {self.entity_type}#{self.entity_id} by {self.user}"

class OperationState(models.TextChoices):
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'


class RecoveryState(models.TextChoices):
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    INTERRUPTED = 'interrupted', 'Interrupted'
    RECONCILED = 'reconciled', 'Reconciled'


class IdempotencyOperation(models.Model):
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    key = models.CharField(max_length=100)
    fingerprint = models.CharField(max_length=64)
    state = models.CharField(max_length=20, choices=OperationState.choices, default=OperationState.PROCESSING)
    response_body = models.BinaryField(null=True)
    response_status = models.PositiveSmallIntegerField(null=True)
    response_headers = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'key'], name='unique_user_operation_key'),
            check_constraint(condition=models.Q(state__in=OperationState.values), name='operation_state_valid'),
            check_constraint(condition=models.Q(state='processing', response_body__isnull=True, response_status__isnull=True) |
                models.Q(state='completed', response_body__isnull=False, response_status__isnull=False, response_status__gte=200, response_status__lt=300),
                name='operation_response_consistent'),
            check_constraint(condition=models.Q(expires_at__gt=models.F('created_at')), name='operation_expiry_valid')]
        indexes = [models.Index(fields=['expires_at'])]


class CacheGeneration(models.Model):
    name = models.CharField(max_length=100, primary_key=True)
    token = models.CharField(max_length=32)


class RecoveryOperation(models.Model):
    """Installation-local receipts; no FK into the restored account inventory."""
    key = models.CharField(max_length=100, unique=True)
    fingerprint = models.CharField(max_length=64)
    initiator = models.JSONField(default=dict)
    state = models.CharField(max_length=20, choices=RecoveryState.choices, default=RecoveryState.PROCESSING)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=['state', 'expires_at'])]
        constraints = [
            check_constraint(condition=models.Q(state__in=RecoveryState.values), name='recovery_state_valid'),
            check_constraint(condition=models.Q(expires_at__gt=models.F('created_at')), name='recovery_expiry_valid'),
        ]
