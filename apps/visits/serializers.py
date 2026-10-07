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
                  'admission_date', 'doctor_id', 'created_by_id', 'full_name']

    def get_full_name(self, obj):
        return obj.get_full_name()

class VisitSerializer(serializers.ModelSerializer):
    # Write-only fields for accepting nested data from the frontend
    diagnoses_input = serializers.ListField(write_only=True, required=False)
    medications_input = serializers.ListField(write_only=True, required=False)
    lab_values_input = serializers.ListField(write_only=True, required=False)
    scale_responses_input = serializers.ListField(write_only=True, required=False)

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
    signed_by_id = serializers.PrimaryKeyRelatedField(
        source='signed_by',
        queryset=User.objects.filter(is_active=True),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Visit
        fields = [
            'id', 'patient', 'patient_id', 'visit_date', 'main_complaints',
            'history_presenting_complaint', 'treatment_text', 'doctor_notes',
            'status', 'status_reason', 'clinical_status', 'accompanied_by', 'companion_relation', 'follow_up_date',
            'follow_up_completed', 'pain_level', 'anxiety_level',
            'suicide_risk_level', 'violence_risk_level', 'firearm_access',
            'level_of_care', 'follow_up_type', 'date_signed', 'signed_by',
            'supervisor', 'diagnosis_discussed', 'plan_discussed',
            'clinical_data', 'version', 'author',
            'created_at', 'updated_at', 'deleted_at',
            'diagnoses_input', 'medications_input', 'lab_values_input', 'scale_responses_input',
            'supervisor_id', 'signed_by_id',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'deleted_at', 'author',
                            'signed_by', 'supervisor']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['diagnoses'] = instance.get_diagnoses()
        rep['medications'] = instance.get_medications()
        rep['lab_values'] = instance.get_lab_values()
        rep['scale_responses'] = VisitScaleResponseSerializer(instance.scale_responses.all(), many=True).data
        return rep

    def create(self, validated_data, **kwargs):
        diagnoses = validated_data.pop('diagnoses_input', [])
        medications = validated_data.pop('medications_input', [])
        lab_values = validated_data.pop('lab_values_input', [])
        scale_responses = validated_data.pop('scale_responses_input', [])

        # Merge additional kwargs (e.g., patient, author) passed from view
        for key, value in kwargs.items():
            if key not in validated_data:
                validated_data[key] = value

        visit = Visit.objects.create(**validated_data)
        if diagnoses:
            visit.set_diagnoses(diagnoses)
        if medications:
            visit.set_medications(medications)
        if lab_values:
            visit.set_lab_values(lab_values)
        if scale_responses:
            self._save_scale_responses(visit, scale_responses)
        return visit

    def update(self, instance, validated_data):
        diagnoses = validated_data.pop('diagnoses_input', None)
        medications = validated_data.pop('medications_input', None)
        lab_values = validated_data.pop('lab_values_input', None)
        scale_responses = validated_data.pop('scale_responses_input', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if diagnoses is not None:
            instance.set_diagnoses(diagnoses)
        if medications is not None:
            instance.set_medications(medications)
        if lab_values is not None:
            instance.set_lab_values(lab_values)
        if scale_responses is not None:
            self._save_scale_responses(instance, scale_responses)
        return instance

    def _save_scale_responses(self, visit, responses):
        existing_snapshots = {
            response.scale_id: {
                'definition': (response.responses_json or {}).get('__definition'),
                'name': response.scale_name_snapshot,
            }
            for response in visit.scale_responses.all()
        }
        normalized_responses = []
        seen_scale_ids = set()
        for item in responses:
            try:
                item_scale_id = int(item.get('scale_id'))
            except (AttributeError, TypeError, ValueError):
                item_scale_id = None
            existing = existing_snapshots.get(item_scale_id) or {}
            item = normalize_scale_response(
                item, existing.get('definition'), existing.get('name')
            )
            if item['scale_id'] in seen_scale_ids:
                raise serializers.ValidationError({
                    'scale_responses_input': ['لا يمكن تكرار المقياس في الزيارة نفسها'],
                })
            seen_scale_ids.add(item['scale_id'])
            normalized_responses.append(item)

        visit.scale_responses.all().delete()
        for item in normalized_responses:
            visit.scale_responses.create(
                scale_id=item.get('scale_id'),
                scale_name_snapshot=item.get('scale_name', ''),
                responses_json=item.get('responses', {}),
            )
