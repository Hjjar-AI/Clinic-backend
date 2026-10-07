import re
import unicodedata

import phonenumbers

from .arabic_utils import normalise_arabic


_DIGIT_TRANSLATION = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')
NATIONAL_ID_MIN_LENGTH = 10
NATIONAL_ID_MAX_LENGTH = 12


def normalize_digits(value):
    if value is None:
        return None
    return str(value).translate(_DIGIT_TRANSLATION)


def normalize_text(value):
    if value is None:
        return None
    value = unicodedata.normalize('NFKC', str(value)).strip()
    return re.sub(r'\s+', ' ', value)


def normalize_name(value):
    value = normalize_text(value)
    return value or ''


def normalize_identifier(value):
    value = normalize_text(value)
    if not value:
        return None
    return re.sub(r'[\s\-]', '', value.translate(_DIGIT_TRANSLATION)).upper()


def normalize_phone(value, default_region='SY'):
    value = normalize_text(value)
    if not value:
        return None
    value = value.translate(_DIGIT_TRANSLATION)
    try:
        parsed = phonenumbers.parse(value, default_region)
        if not phonenumbers.is_possible_number(parsed):
            return value
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return value


def normalized_search_text(value):
    return normalise_arabic(normalize_text(value) or '').casefold()
