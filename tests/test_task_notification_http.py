"""Real endpoint contracts for synthetic tasks and user-owned notifications."""
from datetime import timedelta

from django.contrib.auth.models import Permission
from django.utils import timezone
from rest_framework.test import APIClient

from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.tasks.models import UserTask
from apps.tasks.services import TaskService
from .base import ClinicTestCase


class TaskHTTPTests(ClinicTestCase):
    def task(self, assignee=None, **fields):
        return TaskService().create_task(self.admin, {
            'title': 'Synthetic task', 'assigned_to': assignee, **fields,
        })

    def grant_tasks(self, user):
        user.user_permissions.add(Permission.objects.get(codename='manage_tasks'))
        self.api.force_login(user)

    def path(self, row, action=''):
        return f'/api/v1/tasks/{row.pk}/' + (f'{action}/' if action else '')

    def test_create_serializes_optional_due_date_and_ignores_lifecycle_actor_fields(self):
        response = self.write('post', '/api/v1/tasks/', {
            'title': 'Synthetic', 'due_date': None, 'status': 'completed',
            'completed_by': self.doctor.pk, 'order': 99, 'assigned_to_id': self.doctor.pk,
        })
        self.assertEqual(response.status_code, 201, response.content)
        row = UserTask.objects.get(pk=response.json()['data']['id'])
        self.assertEqual((row.user_id, row.assigned_to_id), (self.admin.pk, self.doctor.pk))
        self.assertEqual((row.status, row.version, row.order), ('open', 1, 0))
        self.assertIsNone(row.completed_at)
        self.assertIsNone(row.completed_by_id)
        self.assertIsNone(response.json()['data']['due_date'])

    def test_invalid_create_is_atomic(self):
        for payload in ({'title': ''}, {'title': 'X', 'due_date': ''},
                        {'title': 'X', 'priority': 'urgent'}, {'title': 'X', 'assigned_to_id': 999999}):
            with self.subTest(payload=payload):
                response = self.write('post', '/api/v1/tasks/', payload)
                self.assertEqual(response.status_code, 400, response.content)
                self.assertEqual(UserTask.objects.count(), 0)

    def test_task_permission_is_required_for_reads_and_mutations(self):
        row = self.task(self.doctor)
        self.api.force_login(self.doctor)
        for method, path, data in [('get', '/api/v1/tasks/', {}), ('get', self.path(row), {}),
                                   ('post', '/api/v1/tasks/', {'title': 'Denied'}),
                                   ('put', self.path(row, 'complete'), {'version': 1}),
                                   ('delete', self.path(row), {'version': 1})]:
            with self.subTest(method=method, path=path):
                response = self.api.get(path) if method == 'get' else self.write(method, path, data)
                self.assertEqual(response.status_code, 403)
        row.refresh_from_db()
        self.assertEqual((row.status, row.version), ('open', 1))

    def test_granted_nonadmin_lists_own_and_unassigned_but_not_other_users(self):
        own, shared, private = self.task(self.doctor), self.task(), self.task(self.other_doctor)
        self.grant_tasks(self.doctor)
        items = self.api.get('/api/v1/tasks/').json()['data']['items']
        self.assertEqual({item['id'] for item in items}, {own.pk, shared.pk})
        self.assertEqual(self.api.get(self.path(private)).status_code, 404)
        response = self.write('put', self.path(private, 'complete'), {'version': 1})
        self.assertEqual(response.status_code, 404)
        private.refresh_from_db()
        self.assertEqual(private.status, 'open')

    def test_nonadmin_create_assigns_self_and_rejects_other_assignee(self):
        self.grant_tasks(self.doctor)
        created = self.write('post', '/api/v1/tasks/', {'title': 'Own', 'assigned_to_id': None})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(UserTask.objects.get(pk=created.json()['data']['id']).assigned_to_id, self.doctor.pk)
        denied = self.write('post', '/api/v1/tasks/', {'title': 'Other', 'assigned_to_id': self.other_doctor.pk})
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(UserTask.objects.count(), 1)

    def test_reassignment_rejects_nonadmin_and_resets_reminder_for_admin(self):
        row = self.task(self.doctor)
        row.reminder_sent = True
        row.save(update_fields=['reminder_sent'])
        self.grant_tasks(self.doctor)
        denied = self.write('patch', self.path(row), {'assigned_to_id': self.other_doctor.pk, 'version': 1})
        self.assertEqual(denied.status_code, 403)
        row.refresh_from_db()
        self.assertEqual((row.assigned_to_id, row.version, row.reminder_sent), (self.doctor.pk, 1, True))
        self.api.force_login(self.admin)
        updated = self.write('patch', self.path(row), {'assigned_to_id': self.other_doctor.pk, 'version': 1})
        self.assertEqual(updated.status_code, 200)
        row.refresh_from_db()
        self.assertEqual((row.assigned_to_id, row.version, row.reminder_sent), (self.other_doctor.pk, 2, False))

    def test_versions_reject_missing_conflicting_and_stale_writes(self):
        row = self.task()
        for data, headers in (({'title': 'Missing'}, {}),
                              ({'title': 'Conflicting', 'version': 1}, {'HTTP_IF_MATCH': '2'})):
            response = self.write('patch', self.path(row), data, **headers)
            self.assertEqual(response.status_code, 400)
        updated = self.write('patch', self.path(row), {'title': 'Accepted'}, HTTP_IF_MATCH='"1"')
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()['data']['version'], 2)
        stale = self.write('put', self.path(row, 'complete'), {'version': 1})
        self.assertEqual(stale.status_code, 409)
        row.refresh_from_db()
        self.assertEqual((row.title, row.status, row.version), ('Accepted', 'open', 2))

    def test_completion_replay_preserves_actor_timestamp_and_one_version_increment(self):
        row = self.task()
        path = self.path(row, 'complete')
        first = self.write('put', path, {'version': 1}, key='suite-task-complete-replay')
        replay = self.write('put', path, {'version': 1}, key='suite-task-complete-replay')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.content, first.content)
        self.assertEqual(replay['X-Idempotency-Replayed'], 'true')
        row.refresh_from_db()
        self.assertEqual((row.status, row.completed_by_id, row.version), ('completed', self.admin.pk, 2))
        self.assertIsNotNone(row.completed_at)
        self.assertEqual(self.write('put', path, {'version': 2}).status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.version, 2)

    def test_cancel_requires_reason_and_reopen_clears_terminal_metadata(self):
        row = self.task()
        for reason in ('', '   ', ['bad'], 'X' * 501):
            with self.subTest(reason=reason):
                response = self.write('put', self.path(row, 'cancel'), {'version': 1, 'reason': reason})
                self.assertEqual(response.status_code, 400)
                row.refresh_from_db()
                self.assertEqual((row.status, row.version), ('open', 1))
        cancelled = self.write('put', self.path(row, 'cancel'), {'version': 1, 'reason': '  Synthetic cancellation  '})
        self.assertEqual(cancelled.status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.status_reason, 'Synthetic cancellation')
        self.assertIsNotNone(row.cancelled_at)
        reopened = self.write('put', self.path(row, 'activate'), {'version': 2})
        self.assertEqual(reopened.status_code, 200)
        row.refresh_from_db()
        self.assertEqual((row.status, row.status_reason, row.version), ('open', '', 3))
        self.assertIsNone(row.cancelled_at)
        self.assertIsNone(row.completed_at)

    def test_invalid_transition_and_terminal_edits_leave_inventory_unchanged(self):
        row = self.task()
        for data in ({'version': 1}, {'version': 1, 'status': 'unknown'}):
            self.assertEqual(self.write('put', self.path(row, 'transition'), data).status_code, 400)
        self.assertEqual(self.write('put', self.path(row, 'complete'), {'version': 1}).status_code, 200)
        self.assertEqual(self.write('patch', self.path(row), {'version': 2, 'title': 'Rejected'}).status_code, 400)
        self.assertEqual(self.write('put', self.path(row, 'transition'), {'version': 2, 'status': 'in_progress'}).status_code, 400)
        row.refresh_from_db()
        self.assertEqual((row.title, row.status, row.version), ('Synthetic task', 'completed', 2))

    def test_delete_requires_terminal_state_and_current_version_then_replays_empty_response(self):
        row = self.task()
        self.assertEqual(self.write('delete', self.path(row), {'version': 1}).status_code, 400)
        self.write('put', self.path(row, 'complete'), {'version': 1})
        self.assertEqual(self.write('delete', self.path(row), {'version': 1}).status_code, 409)
        deleted = self.write('delete', self.path(row), {'version': 2}, key='suite-task-delete-replay')
        replay = self.write('delete', self.path(row), {'version': 2}, key='suite-task-delete-replay')
        self.assertEqual((deleted.status_code, replay.status_code), (204, 204))
        self.assertEqual((deleted.content, replay.content), (b'', b''))
        self.assertFalse(UserTask.objects.filter(pk=row.pk).exists())

    def test_reorder_validation_and_scope_are_atomic(self):
        own, shared, private = self.task(self.doctor), self.task(), self.task(self.other_doctor)
        self.grant_tasks(self.doctor)
        before = list(UserTask.objects.order_by('pk').values_list('pk', 'order', 'version'))
        for order, code in (([own.pk, own.pk], 400), ([True], 400), ('bad', 400),
                            ([own.pk, private.pk], 403), ([999999], 403)):
            with self.subTest(order=order):
                response = self.write('put', '/api/v1/tasks/reorder/', {'order': order})
                self.assertEqual(response.status_code, code)
                self.assertEqual(list(UserTask.objects.order_by('pk').values_list('pk', 'order', 'version')), before)
        data = {'order': [shared.pk, own.pk]}
        first = self.write('put', '/api/v1/tasks/reorder/', data, key='suite-task-reorder-replay')
        replay = self.write('put', '/api/v1/tasks/reorder/', data, key='suite-task-reorder-replay')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(replay.content, first.content)
        self.assertEqual(list(UserTask.objects.filter(pk__in=data['order']).order_by('order').values_list('pk', 'version')),
                         [(shared.pk, 2), (own.pk, 2)])

    def test_filters_and_overdue_are_scoped_and_terminal_aware(self):
        due = timezone.localdate() - timedelta(days=1)
        own = self.task(self.doctor, title='Synthetic overdue', due_date=due)
        self.task(self.other_doctor, title='Synthetic private', due_date=due)
        self.grant_tasks(self.doctor)
        response = self.api.get('/api/v1/tasks/', {'search': 'overdue', 'status': 'pending'})
        items = response.json()['data']['items']
        self.assertEqual([item['id'] for item in items], [own.pk])
        self.assertTrue(items[0]['is_overdue'])
        self.write('put', self.path(own, 'complete'), {'version': 1})
        self.assertFalse(self.api.get(self.path(own)).json()['data']['is_overdue'])
        self.assertEqual(self.api.get('/api/v1/tasks/', {'status': 'open'}).json()['data']['items'], [])


class NotificationHTTPTests(ClinicTestCase):
    def notice(self, user=None, read=False):
        row = NotificationService().create((user or self.admin).pk, 'Synthetic notice', 'Synthetic message')
        if read:
            NotificationService().mark_read(row.pk, row.user_id)
        return row

    def test_list_pagination_unread_count_and_filters_are_user_scoped(self):
        unread, read = self.notice(), self.notice(read=True)
        private = self.notice(self.doctor)
        data = self.api.get('/api/v1/notifications/', {'per_page': 1}).json()['data']
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['meta']['unread_count'], 1)
        second = self.api.get('/api/v1/notifications/', {'per_page': 1, 'cursor': data['meta']['next_cursor']}).json()['data']
        self.assertEqual({data['items'][0]['id'], second['items'][0]['id']}, {unread.pk, read.pk})
        filtered = self.api.get('/api/v1/notifications/', {'unread_only': 'true'}).json()['data']
        self.assertEqual([item['id'] for item in filtered['items']], [unread.pk])
        self.assertNotIn(private.pk, [item['id'] for item in filtered['items']])

    def test_foreign_retrieve_delete_and_mark_read_cannot_change_other_users_notice(self):
        row = self.notice(self.doctor)
        path = f'/api/v1/notifications/{row.pk}/'
        self.assertEqual(self.api.get(path).status_code, 404)
        self.assertEqual(self.write('delete', path).status_code, 404)
        # mark_read deliberately succeeds as a scoped no-op for unknown/foreign IDs.
        self.assertEqual(self.write('put', path + 'mark_read/').status_code, 200)
        row.refresh_from_db()
        self.assertFalse(row.is_read)

    def test_repeated_mark_read_does_not_reduce_unread_count_twice(self):
        row, remaining = self.notice(), self.notice()
        path = f'/api/v1/notifications/{row.pk}/mark_read/'
        for _ in range(2):
            self.assertEqual(self.write('put', path).status_code, 200)
            self.assertEqual(self.api.get('/api/v1/notifications/').json()['data']['meta']['unread_count'], 1)
        remaining.refresh_from_db()
        self.assertFalse(remaining.is_read)

    def test_bulk_read_and_delete_are_scoped_and_keep_unread_notices(self):
        own, foreign = self.notice(), self.notice(self.doctor, read=True)
        self.assertEqual(self.write('put', '/api/v1/notifications/mark_all_read/').status_code, 200)
        kept = self.notice()
        result = self.write('delete', '/api/v1/notifications/delete_all_read/')
        self.assertEqual((result.status_code, result.content), (204, b''))
        self.assertFalse(Notification.objects.filter(pk=own.pk).exists())
        self.assertEqual(set(Notification.objects.values_list('pk', flat=True)), {foreign.pk, kept.pk})

    def test_client_cannot_create_or_edit_notification_content(self):
        row = self.notice()
        self.assertEqual(self.write('post', '/api/v1/notifications/', {'title': 'Injected'}).status_code, 405)
        self.assertEqual(self.write('patch', f'/api/v1/notifications/{row.pk}/', {'title': 'Injected'}).status_code, 405)
        row.refresh_from_db()
        self.assertEqual(row.title, 'Synthetic notice')

    def test_anonymous_notification_actions_are_denied(self):
        row = self.notice()
        self.api = APIClient()
        for method, path in [('get', '/api/v1/notifications/'),
                             ('put', f'/api/v1/notifications/{row.pk}/mark_read/'),
                             ('put', '/api/v1/notifications/mark_all_read/'),
                             ('delete', '/api/v1/notifications/delete_all_read/')]:
            with self.subTest(method=method, path=path):
                response = self.api.get(path) if method == 'get' else self.write(method, path)
                self.assertIn(response.status_code, (401, 403))
        row.refresh_from_db()
        self.assertFalse(row.is_read)
