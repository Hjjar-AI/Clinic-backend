"""Record scope shared by lists, details, exports, creation and dashboards.

Scope never replaces the endpoint's action permission.
"""
from django.db.models import Q


def patient_scope(user):
    if not user.is_authenticated or not user.is_active:
        return Q(pk__in=[])
    if user.role == 'admin':
        return Q()
    membership = Q(care_team__user=user)
    if user.role == 'doctor':
        return Q(doctor=user) | Q(visits__author=user) | membership
    if user.role == 'receptionist':
        return Q(created_by=user) | membership
    return Q(pk__in=[])


def accessible_patients(user, include_archived=False):
    from apps.patients.models import Patient
    manager = Patient.all_objects if include_archived else Patient.objects
    return manager.filter(patient_scope(user)).distinct()


def accessible_visits(user):
    from apps.visits.models import Visit
    return Visit.objects.filter(patient__in=accessible_patients(user, True)).distinct()


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
