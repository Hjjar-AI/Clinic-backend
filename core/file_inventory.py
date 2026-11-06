"""One inventory for protected uploaded files, including archived clinical history."""
from django.apps import apps

CLINICAL_FILE_LABELS = ('patients.patientdocument', 'visits.visitattachment')


def clinical_file_models():
    return tuple(apps.get_model(label) for label in CLINICAL_FILE_LABELS)


def referenced_file_paths():
    return {path for model in clinical_file_models()
            for path in model.all_objects.values_list('filepath', flat=True)}
