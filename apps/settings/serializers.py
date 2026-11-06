from core.serializers import StrictFieldsMixin
from rest_framework import serializers
from .models import ClinicSetting

class ClinicSettingSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = ClinicSetting
        fields = ['key', 'value']