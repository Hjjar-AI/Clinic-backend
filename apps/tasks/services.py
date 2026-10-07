# backend/apps/tasks/services.py
from django.db import transaction, models
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from .models import UserTask
from apps.accounts.models import User
from core.exceptions import ConflictError
from core.lifecycle import enforce_transition
from core.query_utils import apply_ordering

class TaskService:
    def get_for_user(self, user, assigned_filter='', status_filter='', params=None):
        if user.role == 'admin':
            qs = UserTask.objects.all()
            if assigned_filter == 'unassigned':
                qs = qs.filter(assigned_to__isnull=True)
            elif assigned_filter and assigned_filter.isdigit():
                qs = qs.filter(assigned_to_id=int(assigned_filter))
        else:
            qs = UserTask.objects.filter(
                models.Q(assigned_to=user) | models.Q(assigned_to__isnull=True)
            )
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
        qs = apply_ordering(qs, params, {
            'due_date': 'due_date', 'priority': 'priority', 'status': 'status',
            'created_at': 'created_at', 'order': 'order',
        }, default='order')
        return qs.select_related('assigned_to', 'completed_by')

    @transaction.atomic
    def create_task(self, user, data):
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
        task.save()
        return task

    @transaction.atomic
    def update_task(self, task, data, expected_version=None, actor=None):
        """
        Same optimistic-lock contract as the other mutating resources:
          - AppointmentService.update_appointment
          - PatientService.update_patient
          - BillingService.update_invoice
          - VisitService.update_visit
          - AppointmentService.update_appointment

        Missing version -> 400 (ValidationError). Stale version -> 409
        (ConflictError). Previously the equivalent logic lived inline in
        TaskViewSet.perform_update and treated a *missing* version as a 409,
        which broke the contract every sibling resource implements and that
        the frontend was built against.
        """
        task = UserTask.objects.select_for_update().get(pk=task.pk)
        if expected_version is None:
            raise ValidationError(['يجب توفير رقم الإصدار'])
        if task.version != expected_version:
            raise ConflictError('تم تعديل المهمة بواسطة مستخدم آخر')

        if 'assigned_to' in data:
            if actor is None:
                raise PermissionDenied('يجب تحديد المستخدم لتغيير إسناد المهمة')
            assignee_id = getattr(data['assigned_to'], 'pk', data['assigned_to'])
            if actor.role != 'admin' and assignee_id != actor.pk:
                raise PermissionDenied('لا يمكنك إسناد المهمة إلى مستخدم آخر')
        if task.status in {'completed', 'cancelled'}:
            raise ValidationError({'status': ['أعد فتح المهمة قبل تعديلها']})
        data.pop('status', None)
        reminder_changed = (
            ('due_date' in data and data['due_date'] != task.due_date)
            or ('assigned_to' in data and data['assigned_to'] != task.assigned_to)
        )
        for k, v in data.items():
            if k != 'version' and hasattr(task, k):
                setattr(task, k, v)
        if reminder_changed:
            task.reminder_sent = False
        task.version += 1
        task.save()
        return task

    @transaction.atomic
    def transition_task(self, task, target_status, actor, expected_version=None, reason=''):
        task = UserTask.objects.select_for_update().get(pk=task.pk)
        if expected_version is None:
            raise ValidationError({'version': ['يجب توفير رقم الإصدار']})
        if task.version != expected_version:
            raise ConflictError('تم تعديل المهمة بواسطة مستخدم آخر')
        changed = enforce_transition('task', task.status, target_status)
        if not changed:
            return task
        if target_status == 'cancelled' and not str(reason).strip():
            raise ValidationError({'reason': ['سبب الإلغاء مطلوب']})
        task.status = target_status
        task.status_reason = str(reason).strip() if reason else ''
        task.reminder_sent = False
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
        task.save(update_fields=[
            'status', 'status_reason', 'reminder_sent', 'completed_at',
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
    def delete_task(self, task, expected_version=None):
        task = UserTask.objects.select_for_update().get(pk=task.pk)
        from core.mutation import check_mutation
        check_mutation(task, expected_version)
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
        # Get accessible task IDs for the user
        accessible_qs = self.get_for_user(user)
        accessible_ids = set(accessible_qs.values_list('id', flat=True))

        # Check that all provided task IDs are accessible
        provided_ids = set(order_list)
        if not provided_ids.issubset(accessible_ids):
            raise PermissionDenied('لا يمكنك إعادة ترتيب مهام لا تملك صلاحية الوصول إليها')

        # Perform reorder
        for idx, task_id in enumerate(order_list):
            task = self.get_for_user(user).select_for_update().get(pk=task_id)
            task.order = idx
            task.version += 1
            task.save(update_fields=['order', 'version', 'updated_at'])
        return True
