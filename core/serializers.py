from rest_framework import serializers
from .models import AuditLog
from django.core.exceptions import ValidationError as DomainValidationError


def domain_validation(validator, *args, error_field=None, **kwargs):
    try:
        return validator(*args, **kwargs)
    except DomainValidationError as exc:
        detail = exc.message_dict if hasattr(exc, 'message_dict') else exc.messages
        if error_field is not None and isinstance(detail, dict):
            detail = detail.get(error_field, detail)
        raise serializers.ValidationError(detail) from exc


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'user', 'user_name', 'action', 'entity_type', 'entity_id', 'details', 'ip_address', 'created_at']
        read_only_fields = fields