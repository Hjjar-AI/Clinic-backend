"""Recommendations are configurable and never determine whether a record is valid."""
import json
from django.db.models import Q

DEFAULT_FIELDS = ['dob_year', 'gender', 'registration_date']
ALLOWED_FIELDS = DEFAULT_FIELDS + ['national_id', 'phone', 'care_team', 'preferred_language']

def recommended_fields():
    from apps.settings.services import SettingsService
    raw = SettingsService().get_setting('patient_completeness_fields', json.dumps(DEFAULT_FIELDS))
    try:
        values = json.loads(raw)
        if not isinstance(values, list) or any(value not in ALLOWED_FIELDS for value in values):
            return DEFAULT_FIELDS
        return list(dict.fromkeys(values))
    except (TypeError, ValueError):
        return DEFAULT_FIELDS

def completeness(patient):
    fields = recommended_fields()
    missing = [field for field in fields if not (patient.care_team.filter(ended_at__isnull=True).exists()
               if field == 'care_team' else getattr(patient, field))]
    return {'complete': not missing, 'missing_fields': missing,
            'percent': round((len(fields) - len(missing)) / len(fields) * 100) if fields else 100,
            'recommended_fields': fields, 'validity': 'independent'}

def incomplete_query():
    result = Q(pk__in=[])
    for field in recommended_fields():
        if field == 'care_team':
            from .models import PatientCareTeam
            result |= ~Q(pk__in=PatientCareTeam.objects.filter(ended_at__isnull=True).values('patient_id'))
        elif field in ('dob_year', 'registration_date'):
            result |= Q(**{field + '__isnull': True})
        else:
            result |= Q(**{field: ''})
    return result
