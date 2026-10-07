# backend/apps/backup/backup_restore.py
import json
import zipfile
from datetime import datetime
from django.db import transaction, connection
from django.conf import settings
from django.utils.dateparse import parse_datetime
from apps.patients.models import Patient
from apps.clinical.models import DiagnosisOption, MedicationOption
from apps.visits.models import Visit, VisitDiagnosis, VisitMedication, VisitAttachment, VisitScaleResponse
from apps.accounts.models import User
from .backup_validation import BackupValidationService


def _coerce_bool(value, default=False):
    """Coerce a user-supplied backup value to a real bool."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'yes', 'y', 'on')
    return bool(value)


def _coerce_datetime(value):
    """Coerce a user-supplied backup value to a datetime or None."""
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return parse_datetime(value)
        except (ValueError, TypeError):
            return None
    return None


class BackupRestoreService:

    def __init__(self):
        self.validation = BackupValidationService()

    def _load_backup_data(self, file_stream):
        """Load and parse backup data from a file stream.
        Returns (signed_data, raw_json_bytes) for signature verification."""
        if file_stream.name.endswith('.zip'):
            with zipfile.ZipFile(file_stream, 'r') as zf:
                raw = zf.read('backup.json')
        else:
            file_stream.seek(0)
            raw = file_stream.read()
            if isinstance(raw, str):
                raw = raw.encode('utf-8')
        backup_data = json.loads(raw)
        signed = backup_data.get('data', backup_data)
        return signed, raw

    def _verify_backup(self, file_stream):
        """Verify the backup signature. Raises ValueError on failure."""
        if file_stream.name.endswith('.zip'):
            with zipfile.ZipFile(file_stream, 'r') as zf:
                raw = zf.read('backup.json')
                try:
                    signature_bytes = zf.read('signature.txt')
                    signature = signature_bytes.decode('utf-8').strip()
                except KeyError:
                    raise ValueError('Backup archive is missing signature.txt')
        else:
            file_stream.seek(0)
            raw = file_stream.read()
            if isinstance(raw, str):
                raw = raw.encode('utf-8')
            backup_data = json.loads(raw)
            signature = backup_data.get('signature')
            if not signature:
                raise ValueError('Backup file is missing its signature')

        if not self.validation.verify_signature(raw, signature):
            raise ValueError('Backup signature verification failed — file may be tampered')

        file_stream.seek(0)

    def preview_restore(self, file_stream):
        try:
            self._verify_backup(file_stream)
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f'Invalid backup file: {e}')

        try:
            signed, _ = self._load_backup_data(file_stream)
        except Exception as e:
            raise ValueError(f'Invalid backup file: {e}')

        patients = signed.get('patients', [])
        diagnoses = signed.get('diagnoses', [])
        medications = signed.get('medications', [])
        visits_count = sum(len(p.get('visits', [])) for p in patients if isinstance(p, dict))
        metadata = signed.get('metadata', {})
        media_files = 0
        if file_stream.name.endswith('.zip'):
            file_stream.seek(0)
            with zipfile.ZipFile(file_stream, 'r') as zf:
                media_files = len([
                    name for name in zf.namelist()
                    if name not in {'backup.json', 'clinic.db', 'signature.txt', 'manifest.json'}
                ])
            file_stream.seek(0)
        return {
            'patients_count': len(patients),
            'visits_count': visits_count,
            'diagnoses_count': len(diagnoses),
            'medications_count': len(medications),
            'media_files_count': media_files,
            'created_at': metadata.get('created_at'),
            'application_version': metadata.get('application_version'),
            'format_version': metadata.get('format_version', 1),
            'compatible': metadata.get('format_version', 1) <= 2,
            'will_replace': ['patients', 'visits', 'diagnoses', 'medications'],
        }

    @transaction.atomic
    def execute_restore(self, file_stream, restore_patients=True, restore_diagnoses=True, restore_medications=True):
        try:
            self._verify_backup(file_stream)
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f'Invalid backup file: {e}')

        try:
            signed, _ = self._load_backup_data(file_stream)
        except Exception as e:
            raise ValueError(f'Invalid backup file: {e}')

        existing_user_ids = set(User.objects.values_list('id', flat=True))

        diagnosis_lookup = {}
        medication_lookup = {}

        if restore_diagnoses:
            DiagnosisOption.objects.all().delete()
            for d in signed.get('diagnoses', []):
                new_d = DiagnosisOption.objects.create(
                    code=d.get('code', ''),
                    english_name=d.get('english_name', ''),
                    arabic_name=d.get('arabic_name', ''),
                    order=d.get('order', 0),
                    is_active=_coerce_bool(d.get('is_active'), default=True),
                )
                diagnosis_lookup[new_d.code] = new_d
        else:
            for d in DiagnosisOption.objects.filter(is_active=True):
                diagnosis_lookup[d.code] = d

        if restore_medications:
            MedicationOption.objects.all().delete()
            for m in signed.get('medications', []):
                new_m = MedicationOption.objects.create(
                    generic_english=m.get('generic_english', ''),
                    generic_arabic=m.get('generic_arabic', ''),
                    dosage=m.get('dosage', ''),
                    brand_english=m.get('brand_english', ''),
                    brand_arabic=m.get('brand_arabic', ''),
                    order=m.get('order', 0),
                    is_active=_coerce_bool(m.get('is_active'), default=True),
                    is_controlled=_coerce_bool(m.get('is_controlled'), default=False),
                )
                key = (new_m.generic_english, new_m.dosage, new_m.brand_english)
                medication_lookup[key] = new_m
        else:
            for m in MedicationOption.objects.filter(is_active=True):
                key = (m.generic_english, m.dosage, m.brand_english)
                medication_lookup[key] = m

        if restore_patients:
            Patient.all_objects.all().delete()
            Visit.all_objects.all().delete()
            VisitDiagnosis.objects.all().delete()
            VisitMedication.objects.all().delete()
            VisitAttachment.all_objects.all().delete()
            VisitScaleResponse.objects.all().delete()

            for p in signed.get('patients', []):
                doctor_id = p.get('doctor_id')
                if doctor_id not in existing_user_ids:
                    doctor_id = None
                created_by_id = p.get('created_by_id')
                if created_by_id not in existing_user_ids:
                    created_by_id = None

                new_patient = Patient(
                    first_name=p.get('first_name', ''),
                    father_name=p.get('father_name', ''),
                    surname=p.get('surname', ''),
                    mother_name=p.get('mother_name', ''),
                    dob_year=p.get('dob_year', 1998),
                    gender=p.get('gender', ''),
                    national_id=p.get('national_id', ''),
                    marital_status=p.get('marital_status', ''),
                    occupation=p.get('occupation', ''),
                    permanent_address=p.get('permanent_address', ''),
                    phone=p.get('phone', ''),
                    emergency_contact_name=p.get('emergency_contact_name', ''),
                    emergency_contact_relation=p.get('emergency_contact_relation', ''),
                    emergency_contact_phone=p.get('emergency_contact_phone', ''),
                    family_history=p.get('family_history', ''),
                    important_notes=p.get('important_notes', ''),
                    doctor_id=doctor_id,
                    created_by_id=created_by_id,
                    admission_date=p.get('admission_date'),
                    deleted_at=_coerce_datetime(p.get('deleted_at')),
                    is_active=_coerce_bool(p.get('is_active'), default=True),
                    version=p.get('version', 1),
                )
                new_patient.save()

                for v in p.get('visits', []):
                    signed_by_id = v.get('signed_by_id')
                    if signed_by_id not in existing_user_ids:
                        signed_by_id = None
                    supervisor_id = v.get('supervisor_id')
                    if supervisor_id not in existing_user_ids:
                        supervisor_id = None
                    author_id = v.get('author_id')
                    if author_id not in existing_user_ids:
                        author_id = None

                    new_visit = Visit(
                        patient=new_patient,
                        visit_date=v.get('visit_date'),
                        main_complaints=v.get('main_complaints', ''),
                        history_presenting_complaint=v.get('history_presenting_complaint', ''),
                        treatment_text=v.get('treatment_text', ''),
                        doctor_notes=v.get('doctor_notes', ''),
                        status=(v.get('status') if v.get('status') in {'draft', 'final', 'amended', 'locked'} else 'final'),
                        status_reason=v.get('status_reason', ''),
                        clinical_status=(
                            v.get('clinical_status', '')
                            or (v.get('status', '') if v.get('status') not in {'draft', 'final', 'amended', 'locked'} else '')
                        ),
                        accompanied_by=v.get('accompanied_by', ''),
                        companion_relation=v.get('companion_relation', ''),
                        follow_up_date=v.get('follow_up_date'),
                        follow_up_completed=_coerce_bool(v.get('follow_up_completed'), default=False),
                        pain_level=v.get('pain_level'),
                        anxiety_level=v.get('anxiety_level'),
                        suicide_risk_level=v.get('suicide_risk_level'),
                        violence_risk_level=v.get('violence_risk_level'),
                        firearm_access=_coerce_bool(v.get('firearm_access'), default=False),
                        level_of_care=v.get('level_of_care'),
                        follow_up_type=v.get('follow_up_type'),
                        date_signed=v.get('date_signed'),
                        signed_by_id=signed_by_id,
                        supervisor_id=supervisor_id,
                        diagnosis_discussed=_coerce_bool(v.get('diagnosis_discussed'), default=False),
                        plan_discussed=_coerce_bool(v.get('plan_discussed'), default=False),
                        clinical_data=v.get('clinical_data', {}),
                        version=v.get('version', 1),
                        author_id=author_id,
                    )
                    new_visit.save()

                    for vd in v.get('diagnoses', []):
                        diagnosis = None
                        code = vd.get('diagnosis_code') or vd.get('custom_code')
                        if code:
                            diagnosis = diagnosis_lookup.get(code)
                        VisitDiagnosis.objects.create(
                            visit=new_visit,
                            diagnosis=diagnosis,
                            custom_code=vd.get('custom_code', ''),
                            custom_name=vd.get('custom_name', ''),
                            custom_arabic=vd.get('custom_arabic', ''),
                            order=vd.get('order', 0),
                        )

                    for vm in v.get('medications', []):
                        medication = None
                        if not _coerce_bool(vm.get('is_custom'), default=False):
                            key = (
                                vm.get('medication_generic_english'),
                                vm.get('medication_dosage'),
                                vm.get('medication_brand_english'),
                            )
                            medication = medication_lookup.get(key)
                        VisitMedication.objects.create(
                            visit=new_visit,
                            medication=medication,
                            custom_name=vm.get('custom_name', ''),
                            custom_dosage=vm.get('custom_dosage', ''),
                            custom_brand=vm.get('custom_brand', ''),
                            is_custom=_coerce_bool(vm.get('is_custom'), default=False),
                            schedule=vm.get('schedule', ''),
                            order=vm.get('order', 0),
                        )

                    for att in v.get('attachments', []):
                        uploaded_by_id = att.get('uploaded_by_id')
                        if uploaded_by_id not in existing_user_ids:
                            uploaded_by_id = None
                        attachment = VisitAttachment(
                            visit=new_visit,
                            filename=att.get('filename', ''),
                            original_filename=att.get('original_filename', ''),
                            filepath=att.get('filepath', ''),
                            file_size=att.get('file_size'),
                            mime_type=att.get('mime_type', ''),
                            uploaded_by_id=uploaded_by_id,
                            deleted_at=_coerce_datetime(att.get('deleted_at')),
                            is_active=_coerce_bool(att.get('is_active'), default=True),
                        )
                        # Bypass auto_now_add so the original created_at is preserved.
                        attachment.save()
                        original_created = _coerce_datetime(att.get('created_at'))
                        if original_created is not None:
                            VisitAttachment.objects.filter(pk=attachment.pk).update(
                                created_at=original_created
                            )

                    for sr in v.get('scale_responses', []):
                        response = VisitScaleResponse(
                            visit=new_visit,
                            scale_id=sr.get('scale_id'),
                            scale_name_snapshot=sr.get('scale_name_snapshot', ''),
                            responses_json=sr.get('responses_json', {}),
                        )
                        response.save()
                        original_created = _coerce_datetime(sr.get('created_at'))
                        if original_created is not None:
                            VisitScaleResponse.objects.filter(pk=response.pk).update(
                                created_at=original_created
                            )

        self._reset_sequences()
        return True

    def _reset_sequences(self):
        if settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
            tables = [
                'patients_patient',
                'visits_visit',
                'visits_visitdiagnosis',
                'visits_visitmedication',
                'visits_visitattachment',
                'visits_visitscaleresponse',
                'clinical_diagnosisoption',
                'clinical_medicationoption',
            ]
            with connection.cursor() as cursor:
                for table in tables:
                    cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
