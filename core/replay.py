"""Stored responses require today's action and resource permissions."""
import json
from django.urls import resolve
from rest_framework.exceptions import PermissionDenied


def authorize_replay(request, operation):
    match = resolve(request.path)
    callback = match.func
    view = callback.cls(**callback.initkwargs)
    view.args, view.kwargs = match.args, match.kwargs
    if hasattr(callback, 'actions'):
        view.action_map = callback.actions
    api_request = view.initialize_request(request, *match.args, **match.kwargs)
    view.request = api_request
    view.perform_authentication(api_request)
    view.check_permissions(api_request)
    if not api_request.user.is_active:
        raise PermissionDenied()
    # Collection creation returns a protected resource even without a URL pk.
    pk = match.kwargs.get('pk')
    if pk is None and hasattr(view, 'get_queryset'):
        try:
            body = json.loads(bytes(operation.response_body))
            data = body.get('data', body)
            pk = data.get('id') if isinstance(data, dict) else None
        except (ValueError, UnicodeError):
            pass
    if pk is not None and hasattr(view, 'get_queryset'):
        obj = view.get_queryset().filter(pk=pk).first()
        if obj is None:
            # A deleted resource can return only its empty completion receipt.
            if operation.response_status not in {204, 205}:
                raise PermissionDenied()
        else:
            view.check_object_permissions(api_request, obj)
            if getattr(view, 'action', None) == 'records':
                from apps.patients.record_services import require_access, CLINICAL_KINDS
                require_access(obj, api_request.user, api_request.data.get('kind') in CLINICAL_KINDS, True)
    from .access import accessible_patients, accessible_visits
    patient_id = match.kwargs.get('patient_pk') or api_request.data.get('patient_id')
    if patient_id and not accessible_patients(api_request.user, True).filter(pk=patient_id).exists():
        raise PermissionDenied()
    visit_id = match.kwargs.get('visit_id') or api_request.data.get('visit_id')
    if visit_id and not accessible_visits(api_request.user).filter(pk=visit_id).exists():
        raise PermissionDenied()
    # Issuance services impose an additional clinician/edit requirement.
    if request.path.startswith(('/api/v1/prescription/', '/api/v1/referrals/')):
        if api_request.user.role not in {'doctor', 'admin'} or not api_request.user.has_perm('edit_visit'):
            raise PermissionDenied()
