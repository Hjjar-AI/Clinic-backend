# backend/core/middleware.py
import uuid
import threading
from django.core.cache import cache
from django.http import JsonResponse
from .request_context import set_current_request

# Endpoint prefixes that require idempotency enforcement
IDEMPOTENT_PATH_PREFIXES = [
    '/api/v1/appointments/',
    '/api/v1/billing/',
    '/api/v1/patients/',
    '/api/v1/visits/',
    '/api/v1/tasks/',
    '/api/v1/prescription/',
    '/api/v1/backup/',
    '/api/v1/bulk-import/',
    '/api/v1/settings/',
    '/api/v1/auth/users/',
]

def should_enforce_idempotency(path):
    return any(path.startswith(prefix) for prefix in IDEMPOTENT_PATH_PREFIXES)

class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_request(request)
        try:
            # Idempotency check for unsafe methods on specific endpoints
            if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and should_enforce_idempotency(request.path):
                idempotency_key = request.headers.get('X-Idempotency-Key')
                if not idempotency_key:
                    return JsonResponse(
                        {'error': {
                            'code': 'idempotency_key_required',
                            'message': 'X-Idempotency-Key header is required for this operation',
                            'errors': {},
                        }},
                        status=400,
                    )
                if idempotency_key:
                    user_id = getattr(request.user, 'id', None)
                    if user_id:
                        cache_key = f'idempotent:{user_id}:{idempotency_key}'
                    else:
                        session_key = request.session.session_key or request.META.get('REMOTE_ADDR')
                        cache_key = f'idempotent:anon:{session_key}:{idempotency_key}'

                    # cache.add() is atomic: SET NX on Redis, add() on
                    # memcached, lock-guarded on LocMemCache. It returns True
                    # only if the key did not already exist. The previous
                    # cache.get() -> cache.set() pair had a window in which
                    # two concurrent requests with the same key could both
                    # pass the get before either set, so both proceeded and
                    # the double-submit guard did nothing.
                    if not cache.add(cache_key, True, timeout=3600):
                        return JsonResponse(
                            {'error': {'code': 'duplicate_request', 'message': 'Request already processed'}},
                            status=409,
                        )
                    try:
                        response = self.get_response(request)
                        if not (200 <= response.status_code < 300):
                            cache.delete(cache_key)
                        return response
                    except Exception:
                        cache.delete(cache_key)
                        raise

            response = self.get_response(request)
            return response
        finally:
            set_current_request(None)


class SessionRevocationMiddleware:
    """
    Middleware that logs out users whose session_revoked_at timestamp is later than
    the session's login_time. This ensures that when a user's password is changed,
    all existing sessions are invalidated.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and user.session_revoked_at:
            login_time_str = request.session.get('login_time')
            from django.utils.dateparse import parse_datetime
            login_time = parse_datetime(login_time_str) if login_time_str else None
            if not login_time or login_time <= user.session_revoked_at:
                # Session predates a password, role, permission, or account
                # security change. Missing legacy login timestamps are not a
                # reason to bypass an explicit revocation marker.
                from django.contrib.auth import logout
                logout(request)
                request.session.flush()
                return JsonResponse(
                    {
                        'error': {
                            'code': 401,
                            'message': 'انتهت الجلسة بسبب تغيير أمني في الحساب',
                        }
                    },
                    status=401,
                )
        response = self.get_response(request)
        return response
