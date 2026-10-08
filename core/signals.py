from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.utils import timezone
from django.core.cache import cache
from django.db import connection
from .models import AuditLog
from .request_context import get_current_request
import json
import hashlib
import hmac
from django.conf import settings
from datetime import date, datetime, time
from decimal import Decimal

# Models we want to audit (add more as needed)
AUDIT_MODELS = [
    'Patient', 'Visit', 'Appointment', 'Invoice', 'UserTask',
    'ClinicalScale', 'DiagnosisOption', 'MedicationOption', 'ClinicalNoteTemplate',
    'PatientDocument', 'VisitAttachment', 'ClinicSetting', 'User',
    'PatientCareTeam', 'PatientIdentifier', 'PatientContact', 'PatientRepresentative', 'PatientAllergy',
    'PatientMedication', 'PatientFollowUp', 'PatientCorrection', 'PatientMerge', 'PatientDuplicateReview',
]

AUDIT_FIELDS = {
    'Patient': ['first_name', 'father_name', 'surname', 'dob_year', 'gender', 'national_id',
                'phone', 'doctor_id', 'registration_date', 'identity_verification', 'allergy_status', 'medication_status', 'is_active', 'deleted_at'],
    'Visit': ['visit_date', 'status', 'status_reason', 'follow_up_date', 'follow_up_completed',
              'follow_up_outcome', 'follow_up_completed_at', 'follow_up_completed_by_id',
              'suicide_risk_level', 'violence_risk_level', 'signed_by_id', 'signed_at', 'version',
              'is_active', 'deleted_at'],
    'Appointment': ['appointment_date', 'appointment_time', 'duration_minutes', 'status',
                    'status_reason', 'doctor_id', 'version', 'is_active', 'deleted_at'],
    'Invoice': ['invoice_number', 'total_amount', 'tax', 'discount', 'final_amount', 'status',
                'status_reason', 'payment_method', 'issued_date', 'due_date', 'version',
                'is_active', 'deleted_at'],
    'UserTask': ['title', 'priority', 'due_date', 'status', 'status_reason', 'assigned_to_id',
                 'completed_at', 'completed_by_id', 'cancelled_at', 'version'],
    'User': ['username', 'full_name', 'role', 'is_active', 'session_revoked_at', 'version'],
    'ClinicSetting': ['key', 'value', 'updated_at'],
    'DiagnosisOption': ['code', 'english_name', 'arabic_name', 'is_active', 'deleted_at'],
    'MedicationOption': ['generic_english', 'generic_arabic', 'dosage', 'is_controlled',
                         'is_active', 'deleted_at'],
    'ClinicalScale': ['name', 'is_active', 'deleted_at'],
    'ClinicalNoteTemplate': ['name', 'category', 'is_active', 'deleted_at'],
    'PatientDocument': ['original_filename', 'category', 'document_date', 'source', 'provider', 'verification', 'verified_at', 'verified_by_id', 'version', 'is_active', 'deleted_at'],
    'VisitAttachment': ['original_filename', 'is_active', 'deleted_at'],
}

SENSITIVE_AUDIT_FIELDS = {'national_id', 'phone'}


def _json_value(value):
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'pk'):
        return value.pk
    return value


def _snapshot(instance):
    fields = AUDIT_FIELDS.get(instance.__class__.__name__, [])
    snapshot = {}
    for field in fields:
        value = _json_value(getattr(instance, field, None))
        if field in SENSITIVE_AUDIT_FIELDS and value:
            digest = hmac.new(
                settings.SECRET_KEY.encode('utf-8'),
                str(value).encode('utf-8'),
                hashlib.sha256,
            ).hexdigest()[:12]
            value = f'[protected:{digest}]'
        snapshot[field] = value
    return snapshot


def _audit_table_exists():
    return 'core_auditlog' in connection.introspection.table_names()


def log_action(user_id, action, entity_type, entity_id, details=None):
    if not _audit_table_exists():
        return
    request = get_current_request()
    ip_address = None
    if request:
        ip_address = request.META.get('REMOTE_ADDR')
    AuditLog.objects.create(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id if entity_id is not None else 0,
        details=details or {},
        ip_address=ip_address,
    )


def _get_current_user_id():
    request = get_current_request()
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        return user.id
    return None


@receiver(post_save)
def log_model_save(sender, instance, created, **kwargs):
    if kwargs.get('raw'):
        return
    if sender == AuditLog:
        return
    if sender.__name__ not in AUDIT_MODELS:
        return
    if hasattr(instance, 'id'):
        before = getattr(instance, '_audit_before', {})
        after = _snapshot(instance)
        changes = {
            field: {'from': before.get(field), 'to': value}
            for field, value in after.items()
            if created or before.get(field) != value
        }
        if not created and not changes:
            return
        action = 'create' if created else 'update'
        if not created and 'status' in changes:
            action = 'status_transition'
        elif not created and changes.get('deleted_at', {}).get('to'):
            action = 'archive'
        elif not created and changes.get('deleted_at', {}).get('from') and not changes['deleted_at']['to']:
            action = 'restore'
        log_action(
            user_id=_get_current_user_id(),
            action=action,
            entity_type=sender.__name__,
            entity_id=instance.id,
            details={
                'summary': f'{action}: {", ".join(changes) if changes else "saved"}',
                'changes': changes,
            },
        )


@receiver(pre_save)
def capture_model_before_save(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    if sender.__name__ not in AUDIT_MODELS or not getattr(instance, 'pk', None):
        instance._audit_before = {}
        return
    try:
        previous = sender._base_manager.get(pk=instance.pk)
        instance._audit_before = _snapshot(previous)
    except sender.DoesNotExist:
        instance._audit_before = {}


@receiver(post_delete)
def log_model_delete(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    if sender == AuditLog:
        return
    if sender.__name__ not in AUDIT_MODELS:
        return
    if hasattr(instance, 'id'):
        log_action(
            user_id=_get_current_user_id(),
            action='delete',
            entity_type=sender.__name__,
            entity_id=instance.id,
        )
