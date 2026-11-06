"""Persist service-normalized working encounter rows inside the parent mutation."""
from django.db import transaction


@transaction.atomic
def replace_diagnoses(visit, rows):
    visit.visit_diagnoses.all().delete()
    for order, row in enumerate(rows):
        visit.visit_diagnoses.create(diagnosis_id=row.get('id') or None,
            custom_code=row.get('code', ''), custom_name=row.get('name', ''),
            custom_arabic=row.get('arabic_name', ''), order=order)


@transaction.atomic
def replace_medications(visit, rows):
    visit.visit_medications.all().delete()
    for order, row in enumerate(rows):
        visit.visit_medications.create(medication_id=row.get('id') or None,
            custom_name=row.get('name', ''), custom_dosage=row.get('dosage', ''),
            custom_brand=row.get('brand', ''), is_custom=row.get('is_custom', False),
            controlled_snapshot=row['controlled'], schedule=row.get('schedule', ''), order=order)


def replace_lab_values(visit, rows):
    visit.lab_values = rows
    if visit.pk is not None:
        visit.save(update_fields=['lab_values'])


REPLACERS = {'diagnoses': replace_diagnoses, 'medications': replace_medications, 'lab_values': replace_lab_values}
