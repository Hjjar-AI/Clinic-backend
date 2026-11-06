"""Record scope shared by lists, details, exports, creation and dashboards.

Scope never replaces the endpoint's action permission.
"""
from django.db.models import Q


def patient_scope(user):
    if not user.is_authenticated or not user.is_active:
        return Q(pk__in=[])
    if user.role == 'admin':
        return Q()
    from apps.patients.models import PatientCareTeam
    membership = Q(pk__in=PatientCareTeam.objects.effective_at().filter(user=user).values('patient_id'))
    if user.role == 'doctor':
        return Q(visits__author=user) | membership
    if user.role == 'receptionist':
        return Q(created_by=user) | membership
    return Q(pk__in=[])


def accessible_patients(user, include_archived=False):
    from apps.patients.models import Patient
    manager = Patient.all_objects if include_archived else Patient.objects
    return manager.filter(patient_scope(user)).distinct()


def accessible_visits(user):
    from apps.visits.models import Visit
    return Visit.objects.filter(patient__in=accessible_patients(user, True))


def accessible_appointments(user):
    from apps.appointments.models import Appointment
    qs = Appointment.objects.all()
    if user.role == 'admin':
        return qs
    if user.role == 'doctor':
        return qs.filter(doctor=user)
    return qs.filter(patient__in=accessible_patients(user, True))


def accessible_invoices(user):
    from apps.billing.models import Invoice
    return Invoice.objects.filter(patient__in=accessible_patients(user, True))


def require_actor_permission(actor, permission):
    """Re-read effective grants at a service boundary, without trusting cached actors."""
    from django.core.exceptions import PermissionDenied
    from apps.accounts.models import User
    current = User.objects.filter(pk=getattr(actor, 'pk', None), is_active=True).first()
    if current is None or not current.has_perm(permission):
        raise PermissionDenied('غير مصرح بهذا الإجراء')
    return current


def require_patient_actor(patient, actor, permission, *, include_archived=False):
    """Call after locking an existing parent; creation callers check their grant."""
    from django.core.exceptions import PermissionDenied
    current = require_actor_permission(actor, permission)
    if not accessible_patients(current, include_archived).filter(pk=patient.pk).exists():
        raise PermissionDenied('غير مصرح بالوصول إلى الملف')
    return current
