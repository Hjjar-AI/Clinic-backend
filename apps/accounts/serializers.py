# backend/apps/accounts/serializers.py
from rest_framework import serializers
import base64
import binascii
from .models import User


class UserSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()
    # Item #11: align with MinimumLengthValidator (min_length=8 in settings).
    # The previous value of 6 let passwords through serializer validation that
    # then failed inside validate_password(), producing a confusing UX.
    password = serializers.CharField(write_only=True, required=False, allow_blank=True, min_length=8)

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'role', 'is_active', 'force_password_change', 'stamp_data', 'preferences', 'permissions', 'password', 'version']
        read_only_fields = ['id']
        extra_kwargs = {
            'is_active': {'read_only': False},  # allow write but view will strip for non-superuser
            'is_staff': {'read_only': True},    # never writable via API (handled separately if needed)
            'is_superuser': {'read_only': True},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make password required on create
        if self.instance is None:
            self.fields['password'].required = True

    def get_permissions(self, obj):
        perms = set()
        for group in obj.groups.all():
            perms.update(group.permissions.values_list('codename', flat=True))
        perms.update(obj.user_permissions.values_list('codename', flat=True))
        return list(perms)

    def validate_stamp_data(self, value):
        if not value:
            return value
        allowed_prefixes = {
            'data:image/png;base64,': b'\x89PNG\r\n\x1a\n',
            'data:image/jpeg;base64,': b'\xff\xd8\xff',
        }
        prefix = next((item for item in allowed_prefixes if value.startswith(item)), None)
        if not prefix:
            raise serializers.ValidationError('صيغة الختم غير مدعومة')
        try:
            decoded = base64.b64decode(value[len(prefix):], validate=True)
        except (binascii.Error, ValueError):
            raise serializers.ValidationError('بيانات الختم غير صالحة')
        if len(decoded) > 2 * 1024 * 1024:
            raise serializers.ValidationError('حجم الختم يتجاوز 2 ميغابايت')
        if not decoded.startswith(allowed_prefixes[prefix]):
            raise serializers.ValidationError('محتوى الختم لا يطابق صيغته')
        return value


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=80)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    remember = serializers.BooleanField(required=False, default=False)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,  # keep in sync with MinimumLengthValidator in settings
        style={'input_type': 'password'},
    )
