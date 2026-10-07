from django.db.models import QuerySet
from django.db.models import Q
from django.utils import timezone
from django.db import IntegrityError, transaction
from .models import Notification

class NotificationService:
    def get_for_user(self, user_id, unread_only=False):
        qs = Notification.objects.filter(user_id=user_id)
        if unread_only:
            qs = qs.filter(is_read=False)
        return qs.order_by('-created_at')

    def mark_read(self, notification_id, user_id):
        Notification.objects.filter(id=notification_id, user_id=user_id).update(
            is_read=True,
            updated_at=timezone.now(),
        )
        return True

    def mark_all_read(self, user_id):
        Notification.objects.filter(user_id=user_id, is_read=False).update(
            is_read=True,
            updated_at=timezone.now(),
        )
        return True

    def delete(self, notification_id, user_id):
        Notification.objects.filter(id=notification_id, user_id=user_id).delete()
        return True

    def delete_all_read(self, user_id):
        Notification.objects.filter(user_id=user_id, is_read=True).delete()
        return True

    def retire_related(self, prefix, keep_user_id=None):
        queryset = Notification.objects.filter(
            is_read=False,
            dedupe_key__startswith=prefix,
        )
        if keep_user_id is not None:
            queryset = queryset.exclude(user_id=keep_user_id)
        return queryset.delete()[0]

    def cleanup(self, read_before, unread_before):
        return Notification.objects.filter(
            Q(is_read=True, created_at__lt=read_before)
            | Q(is_read=False, created_at__lt=unread_before)
        ).delete()[0]

    def create(self, user_id, title, message, link=None, type='info', dedupe_key=None):
        payload = {
            'title': title[:200],
            'message': message,
            'link': link,
            'type': type,
        }
        if not dedupe_key:
            return Notification.objects.create(user_id=user_id, **payload)
        try:
            with transaction.atomic():
                notification, _ = Notification.objects.get_or_create(
                    user_id=user_id,
                    dedupe_key=str(dedupe_key)[:200],
                    defaults=payload,
                )
                return notification
        except IntegrityError:
            return Notification.objects.get(user_id=user_id, dedupe_key=str(dedupe_key)[:200])

    def create_for_users(self, user_ids, title, message, link=None, type='info', dedupe_key=None):
        now = timezone.now()
        notifications = [
            Notification(
                user_id=uid,
                title=title[:200],
                message=message,
                link=link,
                type=type,
                dedupe_key=f'{dedupe_key}:{uid}'[:200] if dedupe_key else None,
                created_at=now,
                updated_at=now,
            )
            for uid in user_ids
        ]
        Notification.objects.bulk_create(notifications, ignore_conflicts=bool(dedupe_key))
        return notifications
