"""Bounded workers and lock observations for the owned PostgreSQL profile."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier
from time import monotonic, sleep
from uuid import uuid4

from django.db import connection, connections
from rest_framework.test import APIClient


class PostgresConcurrencyMixin:
    @contextmanager
    def workers(self, count=2):
        # Database timeouts also bound failures in a worker's transaction/lock path.
        with ThreadPoolExecutor(max_workers=count) as pool:
            yield pool

    def worker(self, operation, *, name=None):
        connections.close_all()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET statement_timeout = '15s'")
                cursor.execute("SET lock_timeout = '12s'")
                if name:
                    cursor.execute("SELECT set_config('application_name', %s, false)", [name])
            return operation()
        finally:
            connections.close_all()

    def simultaneous(self, operation):
        barrier = Barrier(2)

        def run(index):
            barrier.wait(timeout=10)
            return operation(index)

        with self.workers() as pool:
            futures = [pool.submit(self.worker, lambda index=index: run(index)) for index in range(2)]
            return [future.result(timeout=20) for future in futures]

    def wait_for_database_lock(self, name, future=None):
        deadline = monotonic() + 10
        while monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity "
                    "WHERE application_name = %s AND wait_event_type = 'Lock')", [name])
                if cursor.fetchone()[0]:
                    return
            if future is not None and future.done():
                result = future.result()
                self.fail(f'Competing worker completed before acquiring the expected lock: {getattr(result, "status_code", type(result).__name__)}')
            sleep(0.02)
        with connection.cursor() as cursor:
            cursor.execute("SELECT application_name, wait_event_type, wait_event FROM pg_stat_activity WHERE datname = current_database()")
            waits = cursor.fetchall()
        self.fail(f'The competing worker never reached the expected database lock: {waits}')

    def waiter_name(self):
        return f'clinic-suite-{uuid4().hex}'

    def api_client(self):
        # Reuse a committed synthetic session; clients and connections are per worker.
        client = APIClient()
        client.cookies.load({name: cookie.value for name, cookie in self.api.cookies.items()})
        return client
