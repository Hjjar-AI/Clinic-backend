from core.serializers import StrictFieldsMixin
from core.serializers import domain_validation
from .validation import validate_scale_definition, validate_template_content
from rest_framework import serializers
from .models import (
    DiagnosisOption,
    MedicationOption,
    ClinicalScale,
    ScaleField,
    ClinicalNoteTemplate,
)


class DiagnosisOptionSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    usage_count = serializers.IntegerField(read_only=True, default=0)
    class Meta:
        read_only_fields = ['is_active']
        model = DiagnosisOption
        fields = [
            'id', 'code', 'english_name', 'arabic_name',
            'order', 'is_active', 'version', 'usage_count'
        ]


class MedicationOptionSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    usage_count = serializers.IntegerField(read_only=True, default=0)
    class Meta:
        read_only_fields = ['is_active']
        model = MedicationOption
        fields = [
            'id', 'generic_english', 'generic_arabic', 'dosage',
            'brand_english', 'brand_arabic', 'order', 'is_active',
            'is_controlled', 'version', 'usage_count'
        ]


class ScaleFieldSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = ScaleField
        fields = [
            'id', 'label', 'field_type', 'min_val', 'max_val',
            'step', 'default', 'options', 'order'
        ]
        read_only_fields = ['id', 'order']

    def validate(self, attrs):
        minimum = attrs.get('min_val', getattr(self.instance, 'min_val', 0))
        maximum = attrs.get('max_val', getattr(self.instance, 'max_val', 10))
        step = attrs.get('step', getattr(self.instance, 'step', 1))
        default = attrs.get('default', getattr(self.instance, 'default', minimum))
        domain_validation(validate_scale_definition, minimum, maximum, step, default,
                          attrs.get('field_type', getattr(self.instance, 'field_type', 'slider')))
        attrs['default'] = default
        return attrs


class ClinicalScaleSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    fields = ScaleFieldSerializer(many=True, read_only=True)
    usage_count = serializers.SerializerMethodField()
    max_active_fields = serializers.IntegerField(read_only=True, default=100)

    class Meta:
        model = ClinicalScale
        fields = ['id', 'name', 'description', 'fields', 'max_active_fields', 'is_active', 'usage_count', 'created_at', 'updated_at', 'version']
        read_only_fields = ['id', 'is_active', 'created_at', 'updated_at', 'version']

    def get_usage_count(self, obj):
        annotated = getattr(obj, 'usage_count_value', None)
        if annotated is not None:
            return annotated
        from apps.visits.models import VisitScaleResponse
        return VisitScaleResponse.objects.filter(scale_id=obj.id).count()


class ClinicalNoteTemplateSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    usage_count = serializers.SerializerMethodField()

    class Meta:
        model = ClinicalNoteTemplate
        fields = [
            'id', 'name', 'description', 'category', 'content', 'is_active',
            'usage_count', 'created_at', 'updated_at', 'version',
        ]
        read_only_fields = ['id', 'is_active', 'created_at', 'updated_at', 'version']

    def get_usage_count(self, obj):
        from apps.visits.models import Visit
        return Visit.all_objects.filter(
            clinical_data__applied_template__id=obj.id
        ).count()

    def validate_content(self, value):
        return domain_validation(validate_template_content, value, error_field='content')
