"""One error envelope for Django middleware and DRF responses."""
from django.http import JsonResponse

STATUS_CODES = {400: 'validation_error', 401: 'not_authenticated', 403: 'permission_denied',
    404: 'not_found', 405: 'method_not_allowed', 409: 'conflict', 410: 'operation_expired',
    413: 'payload_too_large', 415: 'unsupported_media_type', 429: 'throttled',
    500: 'internal_error', 503: 'service_unavailable'}


def error_payload(code, message, status, errors=None):
    if not isinstance(code, str):
        code = STATUS_CODES.get(status, f'http_{status}')
    return {'error': {'code': code, 'status': status, 'message': str(message), 'errors': errors or {}}}


def json_error(code, message, status, errors=None):
    return JsonResponse(error_payload(code, message, status, errors), status=status)


def csrf_failure(request, reason=''):
    # Never echo cookies, tokens or framework diagnostics.
    return json_error('csrf_failed', 'تعذر التحقق من أمان الطلب؛ حدّث الصفحة وحاول مجدداً', 403)


def api_not_found(request, *args, **kwargs):
    return json_error('not_found', 'مسار API غير موجود', 404)


def bad_request(request, exception):
    if request.path.startswith('/api/'):
        return json_error('validation_error', 'الطلب غير صالح أو يتجاوز الحجم المسموح', 400)
    from django.views.defaults import bad_request as django_bad_request
    return django_bad_request(request, exception)
