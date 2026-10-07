# backend/apps/tasks/serializers.py
from rest_framework import serializers
from .models import UserTask
from apps.accounts.models import User
from django.utils import timezone

class TaskSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    assigned_to = serializers.StringRelatedField(read_only=True)
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        source='assigned_to',
        queryset=User.objects.filter(is_active=True),
        write_only=True,
        required=False,
        allow_null=True,
    )
    completed_by_name = serializers.CharField(source='completed_by.full_name', read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = UserTask
        fields = [
            'id', 'title', 'description', 'priority', 'due_date', 'status',
            'assigned_to', 'assigned_to_id', 'created_at', 'completed_at',
            'completed_by', 'completed_by_name', 'cancelled_at', 'status_reason',
            'is_overdue', 'order', 'version'
        ]
        read_only_fields = ['id', 'status', 'assigned_to', 'created_at',
                            'completed_at', 'completed_by', 'cancelled_at', 'order']
        # 'version' is writable now (not in read_only_fields)

    def get_status(self, obj):
        return obj.status_display()

    def get_is_overdue(self, obj):
        return bool(
            obj.due_date
            and obj.due_date < timezone.localdate()
            and obj.status in {'open', 'in_progress'}
        )
