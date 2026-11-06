"""Compatibility fields project longitudinal facts without changing their ownership."""
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.verification import stamp_verification

CONTACT_FIELDS = {
    'emergency_contact_name': 'name',
    'emergency_contact_relation': 'relationship',
    'emergency_contact_phone': 'phone',
}


def compatibility_identifier(values):
    get = values.get if isinstance(values, dict) else lambda key: getattr(values, key)
    return get('identifier_type') == 'national_id' and get('issuer') == '' and get('issuing_country') == ''


def sync_profile_identifier(patient, actor, previous=''):
    from .models import PatientIdentifier
    identity = dict(identifier_type='national_id', issuer='', issuing_country='')
    if previous and previous != patient.national_id:
        PatientIdentifier.objects.filter(patient=patient, value=previous, is_active=True, **identity).update(
            is_active=False, retired_at=timezone.now(), retired_by=actor, retirement_reason='Primary identity corrected')
    if patient.national_id:
        PatientIdentifier.objects.get_or_create(patient=patient, value=patient.national_id, is_active=True, **identity,
            defaults={'created_by': actor, 'updated_by': actor, 'verification': 'reported'})


def project_identifier(patient, row, previous, retire=False):
    was_primary = compatibility_identifier(previous) and previous.get('value') == patient.national_id
    new_primary = not patient.national_id and compatibility_identifier(row) and not retire
    if was_primary or new_primary:
        patient.national_id = row.value if compatibility_identifier(row) and not retire else ''
        patient.identity_verification = 'reported'
        stamp_verification(patient, None, prefix='identity_')


def profile_contact_values(patient):
    return {field: getattr(patient, profile) for profile, field in CONTACT_FIELDS.items()}


def project_emergency_contact(patient):
    from .models import PatientContact
    primary = PatientContact.objects.filter(patient=patient, is_active=True, is_primary=True, is_emergency=True).first()
    values = {profile: getattr(primary, field) if primary else '' for profile, field in CONTACT_FIELDS.items()}
    for profile, value in values.items():
        try:
            patient._meta.get_field(profile).clean(value, patient)
        except ValidationError as exc:
            raise ValidationError({CONTACT_FIELDS[profile]: exc.messages}) from exc
    for profile, value in values.items():
        setattr(patient, profile, value)
