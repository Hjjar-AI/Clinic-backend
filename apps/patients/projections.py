"""Profile commands select canonical records; summaries are read-only projections."""
from django.utils import timezone
from core.verification import stamp_verification

CONTACT_FIELDS = {
    'emergency_contact_name': 'name',
    'emergency_contact_relation': 'relationship',
    'emergency_contact_phone': 'phone',
}
PROFILE_RECORD_FIELDS = {'national_id', *CONTACT_FIELDS}


def compatibility_identifier(values):
    get = values.get if isinstance(values, dict) else lambda key: getattr(values, key)
    return get('identifier_type') == 'national_id' and get('issuer') == '' and get('issuing_country') == ''


def sync_profile_identifier(patient, actor, value, reason='Primary identity corrected'):
    from .models import PatientIdentifier
    previous = patient.primary_identifier if patient.primary_identifier_id else None
    if previous and previous.value == value and previous.is_active:
        return
    patient.primary_identifier = None
    if previous and previous.is_active:
        previous.is_active = False
        previous.retired_at, previous.retired_by = timezone.now(), actor
        previous.retirement_reason = reason
        previous.updated_by = actor
        previous.save()
    if value:
        row, _ = PatientIdentifier.objects.get_or_create(patient=patient, value=value, is_active=True,
            identifier_type='national_id', issuer='', issuing_country='',
            defaults={'created_by': actor, 'updated_by': actor, 'verification': 'reported'})
        patient.primary_identifier = row


def project_identifier(patient, row, previous, retire=False):
    was_primary = patient.primary_identifier_id == row.pk
    new_primary = not patient.primary_identifier_id and compatibility_identifier(row) and not retire
    if was_primary or new_primary:
        patient.primary_identifier = row if row.identifier_type == 'national_id' and not retire else None
        patient.identity_verification = 'reported'
        stamp_verification(patient, None, prefix='identity_')


def profile_contact_values(patient, data=None):
    data = data or {}
    return {field: data.get(profile, getattr(patient, profile)) for profile, field in CONTACT_FIELDS.items()}


def project_emergency_contact(patient):
    # No mirrored columns or bounds to maintain. Patient reads the canonical row.
    return patient._emergency_contact()
