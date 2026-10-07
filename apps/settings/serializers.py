from rest_framework import serializers
from .models import ClinicSetting

class ClinicSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicSetting
        fields = ['key', 'value']