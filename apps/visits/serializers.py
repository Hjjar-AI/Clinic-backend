from core.serializers import StrictFieldsMixin, StrictPositiveIntegerField, StrictBooleanField
# backend/apps/visits/serializers.py
from rest_framework import serializers
from .models import Visit, VisitDiagnosis, VisitMedication, VisitAttachment, VisitScaleResponse
from apps.patients.models import Patient
from apps.accounts.models import User
from .scale_validation import normalize_scale_response
from apps.patients.choices import FollowUpMethod


class FollowUpInputSerializer(StrictFieldsMixin, serializers.Serializer):
    due_date = serializers.DateField(required=False, allow_null=True)
    method = serializers.ChoiceField(choices=FollowUpMethod.choices, required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class DiagnosisInputSerializer(StrictFieldsMixin, serializers.Serializer):
    id = StrictPositiveIntegerField(required=False, allow_null=True, min_value=1)
    code = serializers.CharField(required=False, allow_blank=True, max_length=50)
    name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    arabic_name = serializers.CharField(required=False, allow_blank=True, max_length=200)


class MedicationInputSerializer(StrictFieldsMixin, serializers.Serializer):
    id = StrictPositiveIntegerField(required=False, allow_null=True, min_value=1)
    name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    dosage = serializers.CharField(required=False, allow_blank=True, max_length=100)
    brand = serializers.CharField(required=False, allow_blank=True, max_length=200)
    schedule = serializers.CharField(required=False, allow_blank=True, max_length=200)
    is_custom = StrictBooleanField(required=False)
    controlled = serializers.BooleanField(read_only=True)


class LabInputSerializer(StrictFieldsMixin, serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    value = serializers.CharField(required=False, allow_blank=True, max_length=200)
    unit = serializers.CharField(required=False, allow_blank=True, max_length=50)
    reference_range = serializers.CharField(required=False, allow_blank=True, max_length=100)
    date = serializers.CharField(required=False, allow_blank=True, max_length=10)
    status = serializers.CharField(required=False, allow_blank=True, max_length=20)


class ScaleResponseInputSerializer(StrictFieldsMixin, serializers.Serializer):
    scale_id = StrictPositiveIntegerField(min_value=1)
    scale_name = serializers.CharField(read_only=True)
    responses = serializers.JSONField()

class VisitDiagnosisSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = VisitDiagnosis
        fields = ['id', 'diagnosis', 'custom_code', 'custom_name', 'custom_arabic', 'order']

class VisitMedicationSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = VisitMedication
        fields = ['id', 'medication', 'custom_name', 'custom_dosage', 'custom_brand', 'is_custom', 'schedule', 'order']

class VisitAttachmentSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = VisitAttachment
        fields = ['id', 'original_filename', 'file_size', 'mime_type', 'created_at']

class VisitScaleResponseSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = VisitScaleResponse
        fields = ['scale_id', 'scale_name_snapshot', 'responses_json']

class PatientSummarySerializer(StrictFieldsMixin, serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = ['id', 'first_name', 'father_name', 'surname', 'mother_name',
                  'dob_year', 'gender', 'national_id', 'phone', 'permanent_address',
                  'registration_date', 'patient_number', 'doctor_id', 'created_by_id', 'full_name']

    def get_full_name(self, obj):
        return obj.get_full_name()

class VisitSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    follow_up = serializers.SerializerMethodField()
    follow_up_input = FollowUpInputSerializer(write_only=True, required=False, allow_null=True)

    def get_follow_up(self, obj):
        from apps.patients.follow_up_services import follow_up_data
        return follow_up_data(obj.follow_up)

    # Write-only fields for accepting nested data from the frontend
    diagnoses_input = DiagnosisInputSerializer(many=True, max_length=200, write_only=True, required=False)
    medications_input = MedicationInputSerializer(many=True, max_length=200, write_only=True, required=False)
    lab_values_input = LabInputSerializer(many=True, max_length=200, write_only=True, required=False)
    scale_responses_input = ScaleResponseInputSerializer(many=True, max_length=100, write_only=True, required=False)

    patient = PatientSummarySerializer(read_only=True)
    patient_id = serializers.PrimaryKeyRelatedField(
        source='patient',
        queryset=Patient.objects.filter(deleted_at__isnull=True),
        write_only=True,
        required=False,
    )

    supervisor_id = serializers.PrimaryKeyRelatedField(
        source='supervisor',
        queryset=User.objects.filter(is_active=True),
        write_only=True,
        required=False,
        allow_null=True,
    )
    signed_by_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Visit
        fields = [
            'id', 'patient', 'patient_id', 'follow_up', 'follow_up_input', 'visit_date', 'main_complaints',
            'history_presenting_complaint', 'treatment_text', 'doctor_notes',
            'status', 'status_reason', 'clinical_status', 'accompanied_by', 'companion_relation', 'pain_level', 'anxiety_level',
            'suicide_risk_level', 'violence_risk_level', 'firearm_access',
            'level_of_care', 'care_basis', 'date_signed', 'signed_by',
            'supervisor', 'diagnosis_discussed', 'plan_discussed',
            'clinical_data', 'version', 'author',
            'created_at', 'updated_at', 'deleted_at',
            'diagnoses_input', 'medications_input', 'lab_values_input', 'scale_responses_input',
            'supervisor_id', 'signed_by_id', 'signed_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'deleted_at', 'author',
                            'signed_by', 'signed_by_id', 'date_signed', 'supervisor', 'signed_at']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['diagnoses'] = instance.get_diagnoses()
        rep['medications'] = instance.get_medications()
        rep['lab_values'] = instance.get_lab_values()
        rep['scale_responses'] = VisitScaleResponseSerializer(instance.scale_responses.all(), many=True).data
        return rep

    def validate_clinical_data(self, value):
        from .input_validation import clinical_object
        return clinical_object(value)

    def create(self, validated_data):
        from .services import VisitService
        request = self.context['request']
        patient = validated_data.pop('patient')
        return VisitService().create_visit(patient, validated_data, request.user)

    def update(self, instance, validated_data):
        from .services import VisitService
        request = self.context['request']
        version = validated_data.pop('version', None)
        return VisitService().update_visit(instance, validated_data, request.user, version)
