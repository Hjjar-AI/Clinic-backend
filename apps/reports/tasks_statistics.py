# backend/apps/reports/tasks_statistics.py
from django.db.models import Q
from apps.tasks.models import UserTask

class TaskStatisticsService:
    def get_completed_tasks_count(self, user):
        if user.role == 'admin':
            return UserTask.objects.filter(status='completed').count()
        return UserTask.objects.filter(
            Q(assigned_to=user) | Q(assigned_to__isnull=True),
            status='completed'
        ).count()

    def get_pending_tasks_count(self, user):
        if user.role == 'admin':
            return UserTask.objects.filter(status__in=['open', 'in_progress']).count()
        return UserTask.objects.filter(
            Q(assigned_to=user) | Q(assigned_to__isnull=True),
            status__in=['open', 'in_progress']
        ).count()
