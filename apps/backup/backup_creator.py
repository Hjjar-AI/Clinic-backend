# backend/apps/backup/backup_creator.py
import json
import io
import zipfile
import os
import hmac
import hashlib
from django.utils import timezone
from django.conf import settings
from django.db import connection
from apps.patients.models import Patient
from apps.clinical.models import DiagnosisOption, MedicationOption


class BackupCreatorService:
    def _sign_data(self, data: bytes) -> str:
        key = settings.BACKUP_HMAC_KEY.encode('utf-8')
        return hmac.new(key, data, hashlib.sha256).hexdigest()

    def _patient_to_dict(self, patient):
        patient_data = {
            'id': patient.id,
            'first_name': patient.first_name,
            'father_name': patient.father_name,
            'surname': patient.surname,
            'mother_name': patient.mother_name,
            'dob_year': patient.dob_year,
            'gender': patient.gender,
            'national_id': patient.national_id,
            'marital_status': patient.marital_status,
            'occupation': patient.occupation,
            'permanent_address': patient.permanent_address,
            'phone': patient.phone,
            'emergency_contact_name': patient.emergency_contact_name,
            'emergency_contact_relation': patient.emergency_contact_relation,
            'emergency_contact_phone': patient.emergency_contact_phone,
            'family_history': patient.family_history,
            'important_notes': patient.important_notes,
            'doctor_id': patient.doctor_id,
            'created_by_id': patient.created_by_id,
            'admission_date': patient.admission_date.isoformat() if patient.admission_date else None,
            'deleted_at': patient.deleted_at.isoformat() if patient.deleted_at else None,
            'is_active': patient.is_active,
            'version': patient.version,
            'created_at': patient.created_at.isoformat() if patient.created_at else None,
            'updated_at': patient.updated_at.isoformat() if patient.updated_at else None,
            'visits': []
        }

        for visit in patient.visits.filter(deleted_at__isnull=True):
            visit_data = {
                'id': visit.id,
                'visit_date': visit.visit_date.isoformat() if visit.visit_date else None,
                'main_complaints': visit.main_complaints,
                'history_presenting_complaint': visit.history_presenting_complaint,
                'treatment_text': visit.treatment_text,
                'doctor_notes': visit.doctor_notes,
                'status': visit.status,
                'status_reason': visit.status_reason,
                'clinical_status': visit.clinical_status,
                'accompanied_by': visit.accompanied_by,
                'companion_relation': visit.companion_relation,
                'follow_up_date': visit.follow_up_date.isoformat() if visit.follow_up_date else None,
                'follow_up_completed': visit.follow_up_completed,
                'pain_level': visit.pain_level,
                'anxiety_level': visit.anxiety_level,
                'suicide_risk_level': visit.suicide_risk_level,
                'violence_risk_level': visit.violence_risk_level,
                'firearm_access': visit.firearm_access,
                'level_of_care': visit.level_of_care,
                'follow_up_type': visit.follow_up_type,
                'date_signed': visit.date_signed.isoformat() if visit.date_signed else None,
                'signed_by_id': visit.signed_by_id,
                'supervisor_id': visit.supervisor_id,
                'diagnosis_discussed': visit.diagnosis_discussed,
                'plan_discussed': visit.plan_discussed,
                'clinical_data': visit.clinical_data,
                'version': visit.version,
                'created_at': visit.created_at.isoformat() if visit.created_at else None,
                'updated_at': visit.updated_at.isoformat() if visit.updated_at else None,
                'author_id': visit.author_id,
                'diagnoses': [],
                'medications': [],
                'attachments': [],
                'scale_responses': [],
            }

            for vd in visit.visit_diagnoses.all().order_by('order'):
                visit_data['diagnoses'].append({
                    'diagnosis_id': vd.diagnosis_id,
                    'diagnosis_code': vd.diagnosis.code if vd.diagnosis else None,
                    'custom_code': vd.custom_code,
                    'custom_name': vd.custom_name,
                    'custom_arabic': vd.custom_arabic,
                    'order': vd.order,
                })

            for vm in visit.visit_medications.all().order_by('order'):
                visit_data['medications'].append({
                    'medication_id': vm.medication_id,
                    'medication_generic_english': vm.medication.generic_english if vm.medication else None,
                    'medication_dosage': vm.medication.dosage if vm.medication else None,
                    'medication_brand_english': vm.medication.brand_english if vm.medication else None,
                    'custom_name': vm.custom_name,
                    'custom_dosage': vm.custom_dosage,
                    'custom_brand': vm.custom_brand,
                    'is_custom': vm.is_custom,
                    'schedule': vm.schedule,
                    'order': vm.order,
                })

            for att in visit.attachments.filter(deleted_at__isnull=True):
                visit_data['attachments'].append({
                    'filename': att.filename,
                    'original_filename': att.original_filename,
                    'filepath': att.filepath,
                    'file_size': att.file_size,
                    'mime_type': att.mime_type,
                    'uploaded_by_id': att.uploaded_by_id,
                    'created_at': att.created_at.isoformat() if att.created_at else None,
                    'deleted_at': att.deleted_at.isoformat() if att.deleted_at else None,
                    'is_active': att.is_active,
                })

            for sr in visit.scale_responses.all():
                visit_data['scale_responses'].append({
                    'scale_id': sr.scale_id,
                    'scale_name_snapshot': sr.scale_name_snapshot,
                    'responses_json': sr.responses_json,
                    'created_at': sr.created_at.isoformat() if sr.created_at else None,
                })

            patient_data['visits'].append(visit_data)

        return patient_data

    def create_json_backup(self):
        patients = Patient.objects.filter(deleted_at__isnull=True)
        patients_data = [self._patient_to_dict(p) for p in patients]

        medications = MedicationOption.objects.filter(is_active=True)
        meds_data = [{
            'id': m.id,
            'generic_english': m.generic_english,
            'generic_arabic': m.generic_arabic,
            'dosage': m.dosage,
            'brand_english': m.brand_english,
            'brand_arabic': m.brand_arabic,
            'order': m.order,
            'is_active': m.is_active,
            'is_controlled': m.is_controlled,
            'deleted_at': m.deleted_at.isoformat() if m.deleted_at else None,
        } for m in medications]

        diagnoses = DiagnosisOption.objects.filter(is_active=True)
        diag_data = [{
            'id': d.id,
            'code': d.code,
            'english_name': d.english_name,
            'arabic_name': d.arabic_name,
            'order': d.order,
            'is_active': d.is_active,
            'deleted_at': d.deleted_at.isoformat() if d.deleted_at else None,
        } for d in diagnoses]

        data = {
            'metadata': {
                'created_at': timezone.now().isoformat(),
                'application_version': getattr(settings, 'VERSION', '2.0.0'),
                'format_version': 2,
                'includes': ['patients', 'visits', 'medications', 'diagnoses'],
                'counts': {
                    'patients': len(patients_data),
                    'visits': sum(len(patient['visits']) for patient in patients_data),
                    'medications': len(meds_data),
                    'diagnoses': len(diag_data),
                },
            },
            'patients': patients_data,
            'medications': meds_data,
            'diagnoses': diag_data,
        }
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        signature = self._sign_data(json_str.encode('utf-8'))
        signed_data = {'signature': signature, 'data': data}
        return json.dumps(signed_data, ensure_ascii=False, indent=2)

    def create_full_backup(self):
        buffer = io.BytesIO()

        # Serialize and sign the JSON *before* opening the zip. The old
        # implementation called `buffer.seek(0)` inside the `with
        # zipfile.ZipFile(...)` block; ZipFile writes through the
        # underlying file object at its current position, so the
        # subsequent `writestr('signature.txt', ...)` overwrote the
        # leading local-file-header bytes. The central directory still
        # advertised the original offsets, so `unzip -t` on a downloaded
        # "full" backup reported corruption.
        json_str = self.create_json_backup()
        json_bytes = json_str.encode('utf-8')
        signature = self._sign_data(json_bytes)

        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('backup.json', json_str)

            if settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
                db_path = settings.DATABASES['default']['NAME']
                if os.path.exists(db_path):
                    with connection.cursor() as cursor:
                        cursor.execute('PRAGMA wal_checkpoint(FULL)')
                    zf.write(db_path, 'clinic.db')

            media_root = settings.MEDIA_ROOT
            if os.path.exists(media_root):
                for root, dirs, files in os.walk(media_root):
                    for file in files:
                        full_path = os.path.join(root, file)
                        arcname = os.path.relpath(full_path, media_root)
                        zf.write(full_path, arcname)

            zf.writestr('signature.txt', signature)

            manifest = {
                'created_at': timezone.now().isoformat(),
                'application_version': getattr(settings, 'VERSION', '2.0.0'),
                'format_version': 2,
                'includes': ['database', 'media', 'settings', 'clinical_data'],
                'backup_json_sha256': hashlib.sha256(json_bytes).hexdigest(),
            }
            zf.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))

        buffer.seek(0)
        # Validate immediately so a corrupt archive is never offered as a
        # successful backup download.
        with zipfile.ZipFile(buffer, 'r') as validation_zip:
            bad_member = validation_zip.testzip()
            if bad_member:
                raise ValueError(f'Backup validation failed at {bad_member}')
            if hashlib.sha256(validation_zip.read('backup.json')).hexdigest() != manifest['backup_json_sha256']:
                raise ValueError('Backup checksum validation failed')
        buffer.seek(0)
        return buffer
