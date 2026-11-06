"""Quiesce HTTP and scheduler work before recovery or catalog replacement.

PostgreSQL coordinates all hosts using session advisory locks. Other database
profiles require a common lock directory on a filesystem supporting shared/exclusive locks on every worker/job host.
"""
from contextlib import contextmanager
from functools import wraps
import threading
import sys
from pathlib import Path
from django.conf import settings
from django.db import connection

_local = threading.local()


def file_lock_backend():
    import portalocker
    if sys.platform == 'win32':
        # One Win32 API/range for both modes, with true blocking acquisition.
        # The CRT exclusive locker otherwise has a finite retry window.
        from portalocker.portalocker import Win32Locker
        return Win32Locker()
    return portalocker


@contextmanager
def operation_gate(exclusive=False):
    depth = getattr(_local, 'depth', 0)
    if depth:
        if exclusive and not _local.exclusive:
            raise RuntimeError('Exclusive work must acquire the operation gate before database work')
        _local.depth += 1
        try:
            yield
        finally:
            _local.depth -= 1
        return
    lock_file = None
    postgres = connection.vendor == 'postgresql'
    if postgres:
        function = 'pg_advisory_lock' if exclusive else 'pg_advisory_lock_shared'
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT {function}(%s)', [731925041])
    else:
        import portalocker
        directory = Path(getattr(settings, 'OPERATION_LOCK_DIR', settings.BACKUP_DIR))
        directory.mkdir(parents=True, exist_ok=True)
        locker = file_lock_backend()
        lock_file = (directory / '.clinic-operation.lock').open('a+b')
        try:
            locker.lock(lock_file, portalocker.LOCK_EX if exclusive else portalocker.LOCK_SH)
        except BaseException:
            lock_file.close()
            raise
    _local.depth, _local.exclusive = 1, exclusive
    try:
        yield
    finally:
        _local.depth = 0
        if postgres:
            function = 'pg_advisory_unlock' if exclusive else 'pg_advisory_unlock_shared'
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT {function}(%s)', [731925041])
        else:
            try:
                locker.unlock(lock_file)
            finally:
                lock_file.close()


def gated(exclusive=False):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with operation_gate(exclusive):
                return function(*args, **kwargs)
        return wrapped
    return decorate


class OperationGateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Enter before session/auth reads; drain already-running requests/jobs.
        exclusive = (request.method == 'POST' and request.path.startswith('/api/v1/backup/')) or (
            request.method in {'POST', 'PUT', 'PATCH', 'DELETE'} and request.path.startswith((
                '/api/v1/options/', '/api/v1/scales/', '/api/v1/templates/', '/api/v1/bulk-import/')))
        with operation_gate(exclusive):
            response = self.get_response(request)
            if getattr(response, 'streaming', False):
                # Protected downloads are buffered before releasing recovery's read gate.
                from django.http import HttpResponse
                buffered = HttpResponse(b''.join(response.streaming_content), status=response.status_code, headers=dict(response.items()))
                # Transfer stream cleanup to the final response. Calling
                # response.close() here emits request_finished while the
                # PostgreSQL gate still owns its database connection.
                buffered._resource_closers.extend(response._resource_closers)
                response._resource_closers.clear()
                return buffered
            return response
