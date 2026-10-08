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
    admission_date = serializers.DateField(source='registration_date', read_only=True)
    correction_reason = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=500)
    care_team_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), write_only=True, required=False, max_length=100)
    care_team_names = serializers.SerializerMethodField()

    def get_care_team_names(self, obj):
        return [member.user.full_name or member.user.username for member in obj.care_team.filter(ended_at__isnull=True).select_related('user')]

    doctor = serializers.PrimaryKeyRelatedField(read_only=True)  # explicit read-only doctor
    doctor_name = serializers.CharField(source='doctor.full_name', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    doctor_id = serializers.PrimaryKeyRelatedField(
        source='doctor',
        queryset=Patient._meta.get_field('doctor').remote_field.model.objects.filter(role='doctor', is_active=True),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Patient
        fields = [
            'patient_number', 'registration_date', 'identity_verification', 'identity_verified_at', 'identity_verified_by',
            'preferred_language', 'preferred_contact_channel', 'communication_restrictions', 'allergy_status', 'medication_status',
            'merged_into', 'care_team_ids', 'care_team_names', 'correction_reason', 'id', 'first_name', 'father_name', 'surname', 'mother_name',
            'normalised_full_name', 'dob_year', 'gender', 'national_id',
            'marital_status', 'occupation', 'permanent_address', 'phone',
            'emergency_contact_name', 'emergency_contact_relation',
            'emergency_contact_phone', 'family_history', 'important_notes',
            'doctor', 'doctor_name', 'created_by', 'admission_date',
            'is_active', 'version', 'created_at', 'updated_at', 'deleted_at',
            'doctor_id', 'full_name', 'completeness',
        ]
        read_only_fields = [
            'patient_number', 'identity_verified_at', 'identity_verified_by', 'merged_into', 'care_team_names', 'admission_date',
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
        if self.instance and ('care_team_ids' in attrs or 'doctor' in attrs):
            raise serializers.ValidationError('تُعدل عضويات الفريق من إجراءات فريق الرعاية')
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
            'uploaded_by', 'uploaded_by_name', 'created_at', 'updated_at', 'document_date', 'source', 'provider', 'verification', 'verified_at', 'verified_by',
            'deleted_at', 'version'
        ]
        read_only_fields = [
            'id', 'patient', 'filename', 'original_filename', 'filepath',
            'file_size', 'mime_type', 'created_at', 'updated_at', 'deleted_at',
            'uploaded_by', 'uploaded_by_name', 'verified_at', 'verified_by'
        ]


class CareTeamMemberSerializer(serializers.ModelSerializer):
    assigned_by_name = serializers.SerializerMethodField()
    ended_by_name = serializers.SerializerMethodField()

    def get_assigned_by_name(self, obj):
        return (obj.assigned_by.full_name or obj.assigned_by.username) if obj.assigned_by else ''

    def get_ended_by_name(self, obj):
        return (obj.ended_by.full_name or obj.ended_by.username) if obj.ended_by else ''

    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_role = serializers.CharField(source='user.role', read_only=True)

    class Meta:
        model = PatientCareTeam
        fields = ['id', 'user', 'user_name', 'user_role', 'role', 'started_at', 'ended_at', 'assigned_by', 'ended_by', 'removal_reason', 'assigned_by_name', 'ended_by_name']
        read_only_fields = ['id', 'user_name', 'user_role']
