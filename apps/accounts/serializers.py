# backend/apps/accounts/serializers.py
from rest_framework import serializers
from core.image_data import validate_embedded_image
from core.serializers import domain_validation
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
        read_only_fields = ['id', 'force_password_change']
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
        from core.permissions import ALL_PERMISSIONS
        return sorted(codename for codename in ALL_PERMISSIONS if obj.has_perm(codename))

    def validate_stamp_data(self, value):
        return domain_validation(validate_embedded_image, value, 'stamp_data', error_field='stamp_data')

    def validate_username(self, value):
        value = User.normalize_username(value).strip()
        matches = User.objects.filter(username=value)
        if self.instance:
            matches = matches.exclude(pk=self.instance.pk)
        if not value or matches.exists():
            raise serializers.ValidationError('اسم المستخدم غير صالح أو موجود بالفعل')
        return value

    def validate_preferences(self, value):
        from core.json_schemas import validate_preferences
        return domain_validation(validate_preferences, value)


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
