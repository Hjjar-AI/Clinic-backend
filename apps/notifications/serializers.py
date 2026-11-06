from core.serializers import StrictFieldsMixin
from rest_framework import serializers
from .models import Notification

class NotificationSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'link', 'type', 'is_read', 'created_at']
        read_only_fields = fields
