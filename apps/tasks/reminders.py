from apps.notifications.services import NotificationService


def task_recipient(task):
    return task.assigned_to_id or task.user_id


def task_reminder_prefix(task):
    return f'task-due:{task.pk}:'


def task_reminder_key(task):
    return f'{task_reminder_prefix(task)}{task.reminder_generation}:{task.due_date.isoformat()}'


def notify_task_due(task, *, days=None):
    title = f'موعد تسليم المهمة: {task.title}' if days is None else 'موعد تسليم المهمة'
    message = (f'المهمة "{task.title}" مستحقة بتاريخ {task.due_date}' if days is None
               else f'المهمة "{task.title}" مستحقة بعد {days} يوم/أيام')
    return NotificationService().create(task_recipient(task), title, message, link='/tasks',
        type='warning', dedupe_key=task_reminder_key(task), entity_type='tasks.usertask',
        entity_id=task.pk, occurrence=task.reminder_generation, category='due')
