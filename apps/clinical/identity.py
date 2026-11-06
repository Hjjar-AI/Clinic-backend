"""Catalog identity uses the same database expressions as the unique constraint."""
from django.db import connection
from django.db.models import Value
from django.db.models.functions import Lower, Trim

MEDICATION_IDENTITY_FIELDS = ('generic_english', 'dosage', 'brand_english')
MEDICATION_TEXT_FIELDS = ('generic_english', 'generic_arabic', 'dosage', 'brand_english', 'brand_arabic')


def medication_identity(values):
    # Python casefold differs from SQL LOWER (notably for non-ASCII names).
    # Ask the configured database, including when the catalog is still empty.
    with connection.cursor() as cursor:
        cursor.execute('SELECT LOWER(TRIM(%s)), LOWER(TRIM(%s)), LOWER(TRIM(%s))',
                       [values.get(field) or '' for field in MEDICATION_IDENTITY_FIELDS])
        return tuple(cursor.fetchone())


def catalog_identity_lookup(queryset, values):
    if queryset.model._meta.model_name == 'diagnosisoption':
        return queryset.filter(code=values['code'])
    for index, field in enumerate(MEDICATION_IDENTITY_FIELDS):
        alias = f'catalog_identity_{index}'
        queryset = queryset.alias(**{alias: Lower(Trim(field))}).filter(
            **{alias: Lower(Trim(Value(values.get(field) or '')))})
    return queryset
