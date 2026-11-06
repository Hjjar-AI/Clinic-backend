"""Defaults and accepted bounds for the public clinic settings."""
from dataclasses import dataclass
from django.conf import settings


@dataclass(frozen=True)
class TextSetting:
    default: str
    max_length: int
    setting: str = ''

    def default_value(self):
        return getattr(settings, self.setting, self.default) if self.setting else self.default


@dataclass(frozen=True)
class IntegerSetting:
    default: int
    minimum: int
    maximum: int


TEXT_SETTINGS = {
    'clinic_name': TextSetting('عيادة الإتزان', 200, 'CLINIC_NAME'),
    'clinic_address': TextSetting('', 1000, 'CLINIC_ADDRESS'),
    'clinic_phone': TextSetting('', 50, 'CLINIC_PHONE'),
    'theme': TextSetting('default', 50),
}
INTEGER_SETTINGS = {
    'appointment_reminder_days': IntegerSetting(1, 0, 30),
    'appointment_reminder_hours': IntegerSetting(1, 1, 12),
    'task_reminder_days': IntegerSetting(1, 0, 30),
}
