from rest_framework import serializers
from .models import AuditLog
from django.core.exceptions import ValidationError as DomainValidationError


class StrictFieldsMixin:
    """Read-only echoes remain inert; unknown request keys are never discarded."""
    def to_internal_value(self, data):
        if hasattr(data, 'keys'):
            unknown = set(data.keys()) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({name: ['حقل غير معروف'] for name in sorted(unknown)})
        return super().to_internal_value(data)


class StrictPositiveIntegerField(serializers.IntegerField):
    def to_internal_value(self, data):
        if type(data) is not int or data < 1:
            raise serializers.ValidationError('يلزم عدد صحيح موجب')
        return super().to_internal_value(data)


class StrictBooleanField(serializers.BooleanField):
    def to_internal_value(self, data):
        if type(data) is not bool:
            raise serializers.ValidationError('يلزم نعم أو لا')
        return data


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
