from django.db import models


class TaskQuerySet(models.QuerySet):
    def for_user(self, user):
        if not user.is_authenticated or not user.is_active:
            return self.none()
        if user.role == 'admin':
            return self
        return self.filter(models.Q(assigned_to=user) | models.Q(assigned_to__isnull=True))

    def pending(self):
        return self.filter(status__in=['open', 'in_progress'])
