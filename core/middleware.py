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
    '/api/v1/options/',
    '/api/v1/scales/',
    '/api/v1/templates/',
    '/api/v1/referrals/',
]

def should_enforce_idempotency(path):
    return any(path.startswith(prefix) for prefix in IDEMPOTENT_PATH_PREFIXES)

class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import hashlib
        import re
        from django.db import transaction, IntegrityError
        from django.utils import timezone
        from django.http import HttpResponse
        from .models import IdempotencyOperation
        set_current_request(request)
        try:
            user = getattr(request, 'user', None)
            if user and user.is_authenticated and user.force_password_change:
                allowed = {'/api/v1/auth/me/', '/api/v1/auth/change-password/', '/api/v1/auth/logout/'}
                if request.path.startswith('/api/v1/') and request.path not in allowed:
                    return JsonResponse({'error': {'code': 'password_change_required',
                        'message': 'يجب تغيير كلمة المرور أولاً', 'errors': {}}}, status=403)
            unsafe = request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}
            if not unsafe or not should_enforce_idempotency(request.path) or not user or not user.is_authenticated:
                return self.get_response(request)
            key = request.headers.get('X-Idempotency-Key', '')
            if not re.fullmatch(r'[A-Za-z0-9_.:-]{8,100}', key):
                return JsonResponse({'error': {'code': 'idempotency_key_required',
                    'message': 'A valid X-Idempotency-Key header is required', 'errors': {}}}, status=400)
            # Cache raw bytes before CSRF inspects POST, then fingerprint form
            # values and file bytes independently of multipart boundary strings.
            raw_body = request.body
            if request.content_type == 'multipart/form-data':
                import json
                body_digest = hashlib.sha256()
                body_digest.update(json.dumps(sorted((k, request.POST.getlist(k)) for k in request.POST), ensure_ascii=False).encode())
                for name in sorted(request.FILES):
                    for file in request.FILES.getlist(name):
                        body_digest.update(json.dumps([name, file.name, file.content_type]).encode())
                        for chunk in file.chunks(): body_digest.update(chunk)
                        file.seek(0)
                body_hash = body_digest.digest()
            elif request.content_type == 'application/json':
                import json
                try:
                    body_hash = hashlib.sha256(json.dumps(json.loads(raw_body), sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).digest()
                except (ValueError, UnicodeError):
                    body_hash = hashlib.sha256(raw_body).digest()
            else:
                body_hash = hashlib.sha256(raw_body).digest()
            from django.middleware.csrf import CsrfViewMiddleware
            checker = CsrfViewMiddleware(lambda req: None)
            checker.process_request(request)
            csrf_error = checker.process_view(request, lambda req: None, (), {})
            if csrf_error:
                return csrf_error
            fingerprint = hashlib.sha256(request.method.encode() + b'\0' +
                request.get_full_path().encode() + b'\0' + body_hash).hexdigest()
            try:
                with transaction.atomic():
                    operation = IdempotencyOperation.objects.create(user=user, key=key,
                        fingerprint=fingerprint, expires_at=timezone.now() + timezone.timedelta(days=30))
            except IntegrityError:
                operation = IdempotencyOperation.objects.get(user=user, key=key)
                if operation.fingerprint != fingerprint:
                    return JsonResponse({'error': {'code': 'idempotency_key_reused',
                        'message': 'Key was used for a different request', 'errors': {}}}, status=409)
                if operation.state != 'completed':
                    return JsonResponse({'error': {'code': 'request_in_progress',
                        'message': 'Request is still processing; retry with the same key', 'errors': {}}}, status=409)
                response = HttpResponse(bytes(operation.response_body), status=operation.response_status)
                for name, value in operation.response_headers.items():
                    response[name] = value
                response['X-Idempotency-Replayed'] = 'true'
                return response
            try:
                from contextlib import nullcontext
                # Recovery controls their own snapshot/media transaction boundaries.
                boundary = nullcontext() if request.path.startswith('/api/v1/backup/') else transaction.atomic()
                with boundary:
                    response = self.get_response(request)
                    if not 200 <= response.status_code < 300 and not request.path.startswith('/api/v1/backup/'):
                        transaction.set_rollback(True)
                    if 200 <= response.status_code < 300:
                        if getattr(response, 'streaming', False):
                            raise RuntimeError('Idempotent writes must return a buffered response')
                        IdempotencyOperation.objects.filter(pk=operation.pk).update(
                            state='completed', response_body=response.content,
                            response_status=response.status_code,
                            response_headers={name: value for name, value in response.items()
                                if name.lower() in {'content-type', 'content-disposition', 'location',
                                    'x-backup-sha256', 'x-backup-type', 'x-resource-version'}})
                if not 200 <= response.status_code < 300:
                    IdempotencyOperation.objects.filter(pk=operation.pk).delete()
                return response
            except Exception:
                IdempotencyOperation.objects.filter(pk=operation.pk).delete()
                raise
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
