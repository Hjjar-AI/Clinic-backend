"""Only explicit human-activity heartbeats renew the idle clock."""
from django.conf import settings
from django.contrib.auth import logout
from django.utils import timezone
from .errors import json_error


def expiry(request):
    return float(request.session.get('last_activity', 0)) + settings.SESSION_COOKIE_AGE


def activity_payload(request):
    return {'expires_at': expiry(request), 'server_now': timezone.now().timestamp(), 'session_lifetime': settings.SESSION_COOKIE_AGE}


def mark_activity(request):
    request.session['last_activity'] = timezone.now().timestamp()
    return activity_payload(request)


class SessionIdleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if 'last_activity' not in request.session:
                from django.utils.dateparse import parse_datetime
                opened = parse_datetime(request.session.get('login_time', ''))
                request.session['last_activity'] = opened.timestamp() if opened else 0
            if timezone.now().timestamp() >= expiry(request):
                logout(request)
                if request.path.startswith('/api/'):
                    return json_error('session_expired', 'انتهت الجلسة؛ يرجى تسجيل الدخول', 401)
        return self.get_response(request)
