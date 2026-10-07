# backend/apps/patients/serializers.py
from rest_framework import serializers
from .models import Patient, PatientDocument, PatientCareTeam
from apps.accounts.serializers import UserSerializer
from core.normalization import (
    NATIONAL_ID_MAX_LENGTH,
    NATIONAL_ID_MIN_LENGTH,
    normalize_identifier,
    normalize_name,
    normalize_phone,
)
from django.utils import timezone

class PatientSerializer(serializers.ModelSerializer):
    completeness = serializers.SerializerMethodField()
    doctor = serializers.PrimaryKeyRelatedField(read_only=True)  # explicit read-only doctor
    doctor_name = serializers.CharField(source='doctor.full_name', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    doctor_id = serializers.PrimaryKeyRelatedField(
        source='doctor',
        queryset=Patient._meta.get_field('doctor').remote_field.model.objects.filter(role__in=['doctor', 'admin'], is_active=True),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Patient
        fields = [
            'id', 'first_name', 'father_name', 'surname', 'mother_name',
            'normalised_full_name', 'dob_year', 'gender', 'national_id',
            'marital_status', 'occupation', 'permanent_address', 'phone',
            'emergency_contact_name', 'emergency_contact_relation',
            'emergency_contact_phone', 'family_history', 'important_notes',
            'doctor', 'doctor_name', 'created_by', 'admission_date',
            'is_active', 'version', 'created_at', 'updated_at', 'deleted_at',
            'doctor_id', 'full_name', 'completeness',
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'deleted_at', 'created_by',
            'normalised_full_name', 'is_active', 'doctor', 'doctor_name',
            'full_name', 'completeness',
        ]
        # version is writable for optimistic locking
        extra_kwargs = {
            'version': {'required': False},
        }

    def validate_national_id(self, value):
        value = normalize_identifier(value)
        if value:
            if not (NATIONAL_ID_MIN_LENGTH <= len(value) <= NATIONAL_ID_MAX_LENGTH):
                raise serializers.ValidationError('الرقم الوطني غير صالح')
        return value

    def validate(self, attrs):
        for field in ('first_name', 'father_name', 'surname', 'mother_name'):
            if field in attrs and attrs[field] is not None:
                attrs[field] = normalize_name(attrs[field])
        for field in ('phone', 'emergency_contact_phone'):
            if field in attrs:
                attrs[field] = normalize_phone(attrs[field])
        return attrs

    def validate_dob_year(self, value):
        if value is None:
            return value
        current_year = timezone.localdate().year
        if value < 1900 or value > current_year:
            raise serializers.ValidationError(f'سنة الميلاد يجب أن تكون بين 1900 و{current_year}')
        return value

    def get_completeness(self, obj):
        return obj.get_completeness()


class PatientDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)

    class Meta:
        model = PatientDocument
        fields = [
            'id', 'patient', 'filename', 'original_filename', 'filepath',
            'file_size', 'mime_type', 'category', 'description',
            'uploaded_by', 'uploaded_by_name', 'created_at', 'updated_at',
            'deleted_at'
        ]
        read_only_fields = [
            'id', 'patient', 'filename', 'original_filename', 'filepath',
            'file_size', 'mime_type', 'created_at', 'updated_at', 'deleted_at',
            'uploaded_by', 'uploaded_by_name'
        ]


class CareTeamMemberSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_role = serializers.CharField(source='user.role', read_only=True)

    class Meta:
        model = PatientCareTeam
        fields = ['id', 'user', 'user_name', 'user_role', 'role']
        read_only_fields = ['id', 'user_name', 'user_role']
