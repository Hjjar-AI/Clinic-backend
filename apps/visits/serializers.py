# backend/apps/visits/serializers.py
from rest_framework import serializers
from .models import Visit, VisitDiagnosis, VisitMedication, VisitAttachment, VisitScaleResponse
from apps.patients.models import Patient
from apps.accounts.models import User
from .scale_validation import normalize_scale_response

class VisitDiagnosisSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitDiagnosis
        fields = ['id', 'diagnosis', 'custom_code', 'custom_name', 'custom_arabic', 'order']

class VisitMedicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitMedication
        fields = ['id', 'medication', 'custom_name', 'custom_dosage', 'custom_brand', 'is_custom', 'schedule', 'order']

class VisitAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitAttachment
        fields = ['id', 'original_filename', 'file_size', 'mime_type', 'created_at']

class VisitScaleResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = VisitScaleResponse
        fields = ['scale_id', 'scale_name_snapshot', 'responses_json']

class PatientSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = ['id', 'first_name', 'father_name', 'surname', 'mother_name',
                  'dob_year', 'gender', 'national_id', 'phone', 'permanent_address',
                  'registration_date', 'patient_number', 'doctor_id', 'created_by_id', 'full_name']

    def get_full_name(self, obj):
        return obj.get_full_name()

class VisitSerializer(serializers.ModelSerializer):
    # Write-only fields for accepting nested data from the frontend
    diagnoses_input = serializers.ListField(child=serializers.DictField(), max_length=200, write_only=True, required=False)
    medications_input = serializers.ListField(child=serializers.DictField(), max_length=200, write_only=True, required=False)
    lab_values_input = serializers.ListField(child=serializers.DictField(), max_length=200, write_only=True, required=False)
    scale_responses_input = serializers.ListField(child=serializers.DictField(), max_length=200, write_only=True, required=False)

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
            'id', 'patient', 'patient_id', 'visit_date', 'main_complaints',
            'history_presenting_complaint', 'treatment_text', 'doctor_notes',
            'status', 'status_reason', 'clinical_status', 'accompanied_by', 'companion_relation', 'follow_up_date',
            'follow_up_completed', 'pain_level', 'anxiety_level',
            'suicide_risk_level', 'violence_risk_level', 'firearm_access',
            'level_of_care', 'care_basis', 'follow_up_type', 'date_signed', 'signed_by',
            'supervisor', 'diagnosis_discussed', 'plan_discussed',
            'clinical_data', 'version', 'author',
            'created_at', 'updated_at', 'deleted_at',
            'diagnoses_input', 'medications_input', 'lab_values_input', 'scale_responses_input',
            'supervisor_id', 'signed_by_id', 'signed_at', 'follow_up_outcome', 'follow_up_completed_at', 'follow_up_completed_by',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'deleted_at', 'author',
                            'signed_by', 'signed_by_id', 'date_signed', 'supervisor', 'follow_up_completed', 'signed_at', 'follow_up_outcome', 'follow_up_completed_at', 'follow_up_completed_by']

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
