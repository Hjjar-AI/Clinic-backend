from apps.tasks.models import UserTask


class TaskStatisticsService:
    def get_completed_tasks_count(self, user):
        return UserTask.objects.for_user(user).filter(status='completed').count()

    def get_pending_tasks_count(self, user):
        return UserTask.objects.for_user(user).pending().count()
