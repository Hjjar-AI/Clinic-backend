# backend/apps/settings/services.py
from django.db import transaction

from .models import ClinicSetting
from .definitions import TEXT_SETTINGS, INTEGER_SETTINGS
from core.cache_utils import get_grouped_key, set_grouped_key, get_group_version


# Sentinel used to distinguish "cache miss" from "cached value happens to equal default".
_CACHE_MISS = object()


class SettingsService:

    # ------------------------------------------------------------
    # Basic settings get/set
    # ------------------------------------------------------------
    def get_setting(self, key, default=''):
        # Read with a unique sentinel so a cache miss is distinguishable
        # from a cached value that legitimately equals `default`. Previously
        # the call site passed `default` as the cache fallback and then
        # tested `is not None`, which meant the DB branch below was dead
        # code — every read returned the fallback, and clinic settings
        # edited through PUT /settings/ were invisible on the next GET.
        generation = get_group_version('settings')
        value = get_grouped_key('settings', key, _CACHE_MISS, version=generation)
        if value is not _CACHE_MISS:
            return value

        try:
            obj = ClinicSetting.objects.get(key=key)
            value = obj.value
        except ClinicSetting.DoesNotExist:
            value = default

        set_grouped_key('settings', key, value, timeout=300, version=generation)
        return value

    def set_setting(self, key, value):
        ClinicSetting.objects.update_or_create(key=key, defaults={'value': value})
        return True

    # ------------------------------------------------------------
    # Clinic info & theme
    # ------------------------------------------------------------
    def _get_bounded_integer(self, key, default, minimum, maximum):
        """Read legacy string settings without allowing malformed values to break APIs/jobs."""
        try:
            value = int(self.get_setting(key, str(default)))
        except (TypeError, ValueError):
            value = default
        return min(max(value, minimum), maximum)

    def get_clinic_info(self):
        from apps.patients.completeness import recommended_fields
        return {
            'version': int(self.get_setting('__version', '1')),
            **{key: self.get_setting(key, spec.default_value()) for key, spec in TEXT_SETTINGS.items()},
            'patient_completeness_fields': recommended_fields(),
            **{key: self._get_bounded_integer(key, spec.default, spec.minimum, spec.maximum)
               for key, spec in INTEGER_SETTINGS.items()},
        }

    @transaction.atomic
    def update_clinic_info(self, data, expected_version=None, *, actor):
        from core.exceptions import ConflictError
        from django.core.exceptions import ValidationError
        limits = {key: spec.max_length for key, spec in TEXT_SETTINGS.items()}
        ranges = {key: (spec.minimum, spec.maximum) for key, spec in INTEGER_SETTINGS.items()}
        normalized = {}
        for key, value in data.items():
            if key == 'version':
                continue
            if key == 'patient_completeness_fields':
                from apps.patients.completeness import ALLOWED_FIELDS
                import json
                if not isinstance(value, list) or any(item not in ALLOWED_FIELDS for item in value):
                    raise ValidationError({key: ['حقول اكتمال غير صالحة']})
                normalized[key] = json.dumps(list(dict.fromkeys(value)))
                continue
            if key in limits:
                if not isinstance(value, str) or len(value) > limits[key]:
                    raise ValidationError({key: ['قيمة غير صالحة أو طويلة جداً']})
                if key == 'theme' and (not value or not all(c.isalnum() or c in '_-' for c in value)):
                    raise ValidationError({'theme': ['اسم السمة غير صالح']})
                normalized[key] = value.strip()
            elif key in ranges:
                try:
                    if isinstance(value, bool) or str(value) != str(int(value)):
                        raise ValueError()
                except (TypeError, ValueError, OverflowError):
                    raise ValidationError({key: ['يلزم عدد صحيح']})
                minimum, maximum = ranges[key]
                if not minimum <= int(value) <= maximum:
                    raise ValidationError({key: ['العدد خارج النطاق']})
                normalized[key] = str(value)
            else:
                raise ValidationError({key: ['حقل غير معروف']})
        ClinicSetting.objects.get_or_create(key='__version', defaults={'value': '1'})
        version = ClinicSetting.objects.select_for_update().get(key='__version')
        from core.access import require_actor_permission
        require_actor_permission(actor, 'manage_settings')
        expected = data.get('version', expected_version)
        if type(expected) is not int or expected != int(version.value):
            raise ConflictError('تغيرت إعدادات العيادة؛ أعد تحميلها')
        for key, value in normalized.items():
            self.set_setting(key, value)
        version.value = str(int(version.value) + 1)
        version.save()
        # Generation updates are visible inside this transaction and commit with these values.
        result = self.get_clinic_info()
        result.update(normalized)
        result['version'] = int(version.value)
        if 'patient_completeness_fields' in normalized:
            import json
            result['patient_completeness_fields'] = json.loads(normalized['patient_completeness_fields'])
        for key in ranges:
            result[key] = int(result[key])
        return result

    def generate_demo_data(self, num_patients=None, max_visits_per_patient=None):
        from .demo import generate_demo_data
        return generate_demo_data(num_patients, max_visits_per_patient)
