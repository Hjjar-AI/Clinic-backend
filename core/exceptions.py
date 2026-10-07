# backend/core/exceptions.py
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


class ConflictError(Exception):
    """Raised when a version conflict occurs (optimistic locking failure)."""
    pass


def error_response(code, message, errors=None, status_code=None):
    """
    Return a standardised error Response.
    code: usually an HTTP status code or application-specific error code.
    message: human-readable error message.
    errors: optional dictionary of field-level errors.
    """
    if status_code is None:
        status_code = code if isinstance(code, int) else status.HTTP_400_BAD_REQUEST
    data = {
        'error': {
            'code': code,
            'message': message,
            'errors': errors or {},
        }
    }
    return Response(data, status=status_code)


def success_response(data=None, message=None, status_code=status.HTTP_200_OK):
    """
    Return a success Response with optional data and message.
    """
    payload = {}
    if data is not None:
        payload['data'] = data
    if message:
        payload['message'] = message
    return Response(payload, status=status_code)


def custom_exception_handler(exc, context):
    # ---------------------------------------------------------------
    # Handle our own ConflictError FIRST.
    #
    # ConflictError is a plain Exception (not an APIException), so DRF's
    # default handler returns None for it. The previous code only checked
    # for ConflictError *inside* `if response is not None:`, which made
    # the whole branch dead code — every optimistic-lock conflict that
    # raises ConflictError produced an unhandled 500 instead of a clean
    # 409. Handle it before delegating to DRF.
    # ---------------------------------------------------------------
    if isinstance(exc, ConflictError):
        return error_response(
            code=status.HTTP_409_CONFLICT,
            message=str(exc),
            errors={}
        )

    if isinstance(exc, IntegrityError):
        return error_response(
            code=status.HTTP_409_CONFLICT,
            message='تتعارض البيانات مع سجل موجود بالفعل',
            errors={},
        )

    # ---------------------------------------------------------------
    # Handle Django's ValidationError.
    #
    # Service layers across this project (AuthService, AppointmentService,
    # PatientService, BillingService, VisitService, TaskService, ...) raise
    # django.core.exceptions.ValidationError directly. That is NOT an
    # APIException, so DRF's default handler returns None for it and the
    # exception escapes as a 500. Convert it to a normal 400 with a
    # consistent envelope.
    # ---------------------------------------------------------------
    if isinstance(exc, DjangoValidationError):
        message_dict = getattr(exc, 'message_dict', None)
        errors = {
            field: [str(message) for message in messages]
            for field, messages in (message_dict or {}).items()
        }
        messages = [message for field_messages in errors.values() for message in field_messages]
        if not messages:
            messages = list(getattr(exc, 'messages', []) or [str(exc)])
            errors = {'non_field_errors': messages}
        return error_response(
            code=status.HTTP_400_BAD_REQUEST,
            message=' '.join(messages) if messages else 'Validation error',
            errors=errors,
        )

    # ---------------------------------------------------------------
    # Everything else: delegate to DRF's default handler
    # (APIException, Http404, Django PermissionDenied).
    # ---------------------------------------------------------------
    response = exception_handler(exc, context)

    if response is not None:
        data = {
            'error': {
                'code': response.status_code,
                'message': ''
            }
        }
        if hasattr(exc, 'detail'):
            detail = exc.detail
            if isinstance(detail, dict):
                messages = []
                errors = {}
                for field, field_errors in detail.items():
                    if isinstance(field_errors, list):
                        msgs = [str(e) for e in field_errors]
                        errors[field] = msgs
                        messages.extend(msgs)
                    else:
                        errors[field] = [str(field_errors)]
                        messages.append(str(field_errors))
                data['error']['message'] = ' '.join(messages) or 'Validation error'
                data['error']['errors'] = errors
            elif isinstance(detail, list):
                messages = [str(e) for e in detail]
                data['error']['message'] = ' '.join(messages)
            else:
                data['error']['message'] = str(detail)
        else:
            data['error']['message'] = str(exc)
        response.data = data
    return response
