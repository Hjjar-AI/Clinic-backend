from core.reminders import renew_reminder
# backend/apps/tasks/services.py
from django.db import transaction, models
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from .models import UserTask
from apps.accounts.models import User
from core.mutation import check_mutation
from core.access import require_actor_permission
from core.lifecycle import enforce_transition, transition_reason
from core.query_utils import apply_ordering

class TaskService:
    @staticmethod
    def _lock_task(task, actor, expected_version):
        task = UserTask.objects.select_for_update().get(pk=task.pk)
        actor = require_actor_permission(actor, 'manage_tasks')
        if not UserTask.objects.for_user(actor).filter(pk=task.pk).exists():
            raise PermissionDenied('غير مصرح بالوصول إلى المهمة')
        check_mutation(task, expected_version)
        return task, actor

    def get_for_user(self, user, assigned_filter='', status_filter='', params=None):
        qs = UserTask.objects.for_user(user)
        if user.role == 'admin':
            if assigned_filter == 'unassigned':
                qs = qs.filter(assigned_to__isnull=True)
            elif assigned_filter and assigned_filter.isdigit():
                qs = qs.filter(assigned_to_id=int(assigned_filter))
        if status_filter in {'pending', 'open'}:
            qs = qs.filter(status='open')
        elif status_filter == 'in_progress':
            qs = qs.filter(status='in_progress')
        elif status_filter == 'completed':
            qs = qs.filter(status='completed')
        elif status_filter == 'cancelled':
            qs = qs.filter(status='cancelled')
        params = params or {}
        search = params.get('search', '').strip()
        if search:
            qs = qs.filter(models.Q(title__icontains=search) | models.Q(description__icontains=search))
        qs = qs.annotate(priority_rank=models.Case(
            models.When(priority='low', then=0), models.When(priority='medium', then=1),
            models.When(priority='high', then=2), default=0, output_field=models.IntegerField()))
        qs = apply_ordering(qs, params, {
            'due_date': 'due_date', 'priority': 'priority_rank', 'status': 'status',
            'created_at': 'created_at', 'order': 'order',
        }, default='order')
        return qs.select_related('assigned_to', 'completed_by')

    @transaction.atomic
    def create_task(self, user, data):
        user = require_actor_permission(user, 'manage_tasks')
        assignee = data.get('assigned_to')
        assigned_to_id = getattr(assignee, 'id', assignee)
        if user.role != 'admin':
            # Non-admin can only assign to themselves or leave unassigned
            if assigned_to_id is not None and assigned_to_id != user.id:
                raise ValidationError(['لا يمكنك إسناد المهمة إلى مستخدم آخر'])
            # Force assignment to self if not admin
            assigned_to_id = user.id
        task = UserTask(
            user=user,
            assigned_to_id=assigned_to_id,
            title=data['title'],
            description=data.get('description', ''),
            priority=data.get('priority', 'low'),
            due_date=data.get('due_date'),
            status='open',
        )
        if task.assigned_to_id and not User.objects.filter(pk=task.assigned_to_id, is_active=True).exists():
            raise ValidationError({'assigned_to': ['المستخدم غير متاح']})
        task.full_clean()
        task.save()
        return task

    @transaction.atomic
    def update_task(self, task, data, expected_version=None, actor=None):
        task, actor = self._lock_task(task, actor, expected_version)

        if 'assigned_to' in data:
            if actor is None:
                raise PermissionDenied('يجب تحديد المستخدم لتغيير إسناد المهمة')
            assignee_id = getattr(data['assigned_to'], 'pk', data['assigned_to'])
            if actor.role != 'admin' and assignee_id != actor.pk:
                raise PermissionDenied('لا يمكنك إسناد المهمة إلى مستخدم آخر')
        if task.status in {'completed', 'cancelled'}:
            raise ValidationError({'status': ['أعد فتح المهمة قبل تعديلها']})
        data = data.copy()
        data.pop('status', None)
        reminder_changed = (
            ('due_date' in data and data['due_date'] != task.due_date)
            or ('assigned_to' in data and data['assigned_to'] != task.assigned_to)
        )
        for k, v in data.items():
            if k in {'title', 'description', 'priority', 'due_date', 'assigned_to'}:
                setattr(task, k, v)
        if reminder_changed:
            renew_reminder(task, 'reminder_sent')
        task.version += 1
        if task.assigned_to_id and not User.objects.filter(pk=task.assigned_to_id, is_active=True).exists():
            raise ValidationError({'assigned_to': ['المستخدم غير متاح']})
        task.full_clean()
        task.save()
        return task

    @transaction.atomic
    def transition_task(self, task, target_status, actor, expected_version=None, reason=''):
        task, actor = self._lock_task(task, actor, expected_version)
        changed = enforce_transition('task', task.status, target_status)
        if not changed:
            return task
        reason = transition_reason(reason, required=target_status == 'cancelled')
        reopening = task.status in {'completed', 'cancelled'} and target_status == 'open'
        task.status = target_status
        task.status_reason = reason
        if reopening:
            renew_reminder(task, 'reminder_sent')
        if target_status == 'completed':
            task.completed_at = timezone.now()
            task.completed_by = actor
            task.cancelled_at = None
        elif target_status == 'cancelled':
            task.cancelled_at = timezone.now()
            task.completed_at = None
            task.completed_by = None
        else:
            task.completed_at = None
            task.completed_by = None
            task.cancelled_at = None
        task.version += 1
        task.full_clean()
        task.save(update_fields=[
            'status', 'status_reason', 'reminder_generation', 'reminder_sent', 'completed_at',
            'completed_by', 'cancelled_at', 'version', 'updated_at',
        ])
        return task

    def complete_task(self, task, actor, expected_version=None):
        return self.transition_task(task, 'completed', actor, expected_version)

    def cancel_task(self, task, actor, expected_version=None, reason=''):
        return self.transition_task(task, 'cancelled', actor, expected_version, reason)

    def activate_task(self, task, actor, expected_version=None):
        return self.transition_task(task, 'open', actor, expected_version)

    @transaction.atomic
    def delete_task(self, task, expected_version=None, *, actor):
        task, actor = self._lock_task(task, actor, expected_version)
        if task.status not in {'completed', 'cancelled'}:
            raise ValidationError({'status': ['لا يمكن حذف مهمة نشطة؛ ألغها أولاً']})
        task.delete()
        return True

    @transaction.atomic
    def reorder_tasks(self, order_list, user):
        """
        Reorder tasks. Validate that all task IDs in order_list are accessible to the user.
        For non-admin users, they can only reorder tasks assigned to them or unassigned.
        """
        if (not isinstance(order_list, list)
                or any(type(task_id) is not int or task_id <= 0 for task_id in order_list)
                or len(order_list) != len(set(order_list))):
            raise ValidationError({'order': ['يجب تقديم قائمة بمعرفات مهام صحيحة دون تكرار']})
        # Lock only task rows, in a stable order. Nullable user joins cannot
        # participate in FOR UPDATE on PostgreSQL.
        tasks = list(self.get_for_user(user).select_related(None).filter(
            pk__in=order_list).order_by('pk').select_for_update())
        if len(tasks) != len(order_list):
            raise PermissionDenied('لا يمكنك إعادة ترتيب مهام لا تملك صلاحية الوصول إليها')
        user = require_actor_permission(user, 'manage_tasks')
        if UserTask.objects.for_user(user).filter(pk__in=order_list).count() != len(order_list):
            raise PermissionDenied('غير مصرح بإعادة ترتيب المهام')
        positions = {task_id: position for position, task_id in enumerate(order_list)}
        for task in tasks:
            task.order = positions[task.pk]
            task.version += 1
            task.save(update_fields=['order', 'version', 'updated_at'])
        return True
