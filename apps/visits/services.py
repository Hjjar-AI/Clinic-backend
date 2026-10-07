import json
import os
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from .models import Visit, VisitAttachment, VisitRevision
from apps.patients.models import Patient
from core.mutation import check_mutation
from core.lifecycle import enforce_transition
from core.file_utils import save_uploaded_file
from .scale_validation import normalize_scale_response
from .lab_validation import normalize_lab_values
from .input_validation import normalize_rows, clinical_object, text


class VisitService:
    EDITABLE = {
        'visit_date', 'main_complaints', 'history_presenting_complaint', 'treatment_text',
        'doctor_notes', 'clinical_status', 'accompanied_by', 'companion_relation',
        'follow_up_date', 'pain_level', 'anxiety_level', 'suicide_risk_level',
        'violence_risk_level', 'firearm_access', 'level_of_care', 'follow_up_type',
        'supervisor', 'diagnosis_discussed', 'plan_discussed', 'clinical_data',
    }

    def _validate(self, data, require_complete=False):
        if not data.get('visit_date'):
            raise ValidationError({'visit_date': ['تاريخ الزيارة مطلوب']})
        if data.get('follow_up_date') and data['follow_up_date'] < data['visit_date']:
            raise ValidationError({'follow_up_date': ['تاريخ المتابعة لا يمكن أن يسبق الزيارة']})
        if require_complete and not text(data.get('main_complaints'), 'main_complaints', 100_000):
            raise ValidationError({'main_complaints': ['الشكوى الرئيسية مطلوبة']})

    def _validate_final_sections(self, medications, labs):
        for row in medications:
            if any(not text(row.get(key), 'medications', 200) for key in ('name', 'dosage', 'schedule')):
                raise ValidationError({'medications': ['اسم الدواء والجرعة والتعليمات مطلوبة']})
        normalize_lab_values(labs, require_complete=True)

    def _nested(self, data, visit=None):
        result = {}
        for key in ('diagnoses', 'medications', 'lab_values', 'scale_responses'):
            value = data.pop(key + '_input', data.pop(key, None))
            if value is not None:
                if key in {'diagnoses', 'medications'}:
                    value = normalize_rows(value, key, visit)
                elif key == 'lab_values':
                    value = normalize_lab_values(value)
                elif not isinstance(value, list) or len(value) > 100:
                    raise ValidationError({key: ['قائمة غير صالحة أو كبيرة جداً']})
                result[key] = value
        if 'clinical_data' in data:
            data['clinical_data'] = clinical_object(data['clinical_data'])
        for field in ('signed_by', 'signed_by_id', 'date_signed', 'signed_at'):
            if field in data:
                raise ValidationError({field: ['تحدد بيانات التوقيع بواسطة النظام']})
        return result

    def _save_nested(self, visit, nested):
        for key in ('diagnoses', 'medications', 'lab_values'):
            if key in nested:
                getattr(visit, 'set_' + key)(nested[key])
        if 'scale_responses' in nested:
            self._save_scale_responses(visit, nested['scale_responses'])

    def _sign(self, visit, actor):
        if actor.role not in {'admin', 'doctor'} or not actor.has_perm('edit_visit'):
            raise PermissionDenied('التوقيع مخصص للطبيب المخول')
        self._validate({'visit_date': visit.visit_date, 'main_complaints': visit.main_complaints,
                        'follow_up_date': visit.follow_up_date}, True)
        self._validate_final_sections(visit.get_medications(), visit.get_lab_values())
        visit.signed_by = actor
        visit.signed_at = timezone.now()
        visit.date_signed = timezone.localdate()
        visit.save(update_fields=['signed_by', 'signed_at', 'date_signed', 'updated_at'])
        scalar = {field.name: field.value_from_object(visit) for field in visit._meta.concrete_fields}
        snapshot = json.loads(json.dumps({
            'fields': scalar, 'diagnoses': visit.get_diagnoses(),
            'medications': visit.get_medications(), 'lab_values': visit.get_lab_values(),
            'scales': list(visit.scale_responses.values('scale_id', 'scale_name_snapshot', 'responses_json')),
            'attachments': list(visit.attachments.values('id', 'original_filename', 'filepath', 'file_size')),
            'patient': {'id': visit.patient_id, 'name': visit.patient.get_full_name(),
                        'national_id': visit.patient.national_id, 'dob_year': visit.patient.dob_year,
                        'gender': visit.patient.gender},
            'clinician': {'id': actor.pk, 'name': actor.full_name or actor.username},
        }, cls=DjangoJSONEncoder, allow_nan=False))
        number = (visit.revisions.order_by('-number').values_list('number', flat=True).first() or 0) + 1
        VisitRevision.objects.create(visit=visit, number=number, snapshot=snapshot,
                                     signer=actor, signed_at=visit.signed_at, reason=visit.amendment_reason)

    @transaction.atomic
    def create_visit(self, patient, data, current_user):
        patient = Patient.objects.select_for_update().get(pk=patient.pk)
        data = data.copy()
        status = data.pop('status', 'draft')
        if status not in {'draft', 'final'}:
            raise ValidationError({'status': ['يجب إنشاء الزيارة كمسودة أو نهائية']})
        nested = self._nested(data)
        self._validate(data)
        visit = Visit(patient=patient, author=current_user, status=status,
                      **{key: value for key, value in data.items() if key in self.EDITABLE})
        visit.full_clean(exclude=['patient', 'author', 'signed_by', 'supervisor'])
        visit.save()
        self._save_nested(visit, nested)
        if status == 'final':
            self._sign(visit, current_user)
        return visit

    @transaction.atomic
    def update_visit(self, visit, data, current_user, expected_version=None):
        visit = Visit.all_objects.select_for_update().get(pk=visit.pk)
        check_mutation(visit, expected_version)
        if visit.status in {'final', 'locked'}:
            raise ValidationError({'status': ['افتح تعديلاً قبل تغيير الزيارة المعتمدة']})
        data = data.copy()
        if 'patient' in data or 'patient_id' in data:
            raise ValidationError({'patient_id': ['لا يمكن تغيير مريض الزيارة']})
        status = data.pop('status', visit.status)
        enforce_transition('visit', visit.status, status)
        nested = self._nested(data, visit)
        old_follow_up = visit.follow_up_date
        for key, value in data.items():
            if key in self.EDITABLE:
                setattr(visit, key, value)
        if visit.follow_up_date != old_follow_up:
            visit.follow_up_completed = False
            visit.follow_up_outcome = 'pending'
            visit.follow_up_completed_at = None
            visit.follow_up_completed_by = None
        self._validate({'visit_date': visit.visit_date, 'main_complaints': visit.main_complaints,
                        'follow_up_date': visit.follow_up_date})
        visit.status = status
        visit.version += 1
        visit.full_clean(exclude=['patient', 'author', 'signed_by', 'supervisor'])
        visit.save()
        self._save_nested(visit, nested)
        if status in {'final', 'locked'}:
            self._sign(visit, current_user)
        return visit

    @transaction.atomic
    def transition(self, visit, target_status, current_user, expected_version=None, reason=''):
        visit = Visit.all_objects.select_for_update().get(pk=visit.pk)
        check_mutation(visit, expected_version)
        previous = visit.status
        if not enforce_transition('visit', previous, target_status):
            return visit
        reason = text(reason, 'reason', 500)
        if target_status == 'amended':
            if not reason:
                raise ValidationError({'reason': ['سبب التعديل مطلوب']})
            visit.amendment_reason = reason
        visit.status = target_status
        visit.status_reason = reason
        visit.version += 1
        visit.save()
        if target_status in {'final', 'locked'} and previous != 'final':
            self._sign(visit, current_user)
        return visit

    def _save_scale_responses(self, visit, responses):
        old = {r.scale_id: r for r in visit.scale_responses.all()}
        normalized, seen = [], set()
        for row in responses:
            previous = old.get(row.get('scale_id')) if isinstance(row, dict) else None
            row = normalize_scale_response(row,
                previous.responses_json.get('__definition') if previous else None,
                previous.scale_name_snapshot if previous else None)
            if row['scale_id'] in seen:
                raise ValidationError({'scale_responses': ['لا يمكن تكرار المقياس']})
            seen.add(row['scale_id'])
            normalized.append(row)
        visit.scale_responses.all().delete()
        for row in normalized:
            visit.scale_responses.create(scale_id=row['scale_id'], scale_name_snapshot=row['scale_name'],
                                         responses_json=row['responses'])

    @transaction.atomic
    def soft_delete_visit(self, visit, expected_version=None):
        visit = Visit.all_objects.select_for_update().get(pk=visit.pk)
        check_mutation(visit, expected_version)
        if visit.status != 'draft':
            raise ValidationError({'status': ['السجلات المعتمدة تحفظ تاريخياً']})
        visit.soft_delete()
        return True

    @transaction.atomic
    def complete_follow_up(self, visit, actor, expected_version=None, outcome='completed'):
        visit = Visit.all_objects.select_for_update().get(pk=visit.pk)
        check_mutation(visit, expected_version)
        if not visit.follow_up_date or outcome not in {'completed', 'missed', 'cancelled', 'waived'}:
            raise ValidationError({'follow_up': ['تاريخ ونتيجة متابعة صالحان مطلوبان']})
        visit.follow_up_outcome = outcome
        visit.follow_up_completed = outcome == 'completed'
        visit.follow_up_completed_at = timezone.now()
        visit.follow_up_completed_by = actor
        visit.version += 1
        visit.save()
        return visit

    @transaction.atomic
    def mark_all_overdue(self, user):
        from core.access import accessible_visits
        visits = accessible_visits(user).select_for_update().filter(
            follow_up_date__lt=timezone.localdate(), follow_up_outcome='pending')
        count = 0
        for visit in visits:
            self.complete_follow_up(visit, user, visit.version, 'missed')
            count += 1
        return count


class VisitAttachmentService:
    @transaction.atomic
    def upload_attachment(self, visit, file, uploaded_by, expected_version=None):
        visit = Visit.objects.select_for_update().get(pk=visit.pk)
        check_mutation(visit, expected_version)
        if visit.status not in {'draft', 'amended'}:
            raise ValidationError({'visit': ['افتح تعديلاً قبل إضافة مرفق إلى سجل معتمد']})
        from core.upload_security import validate_upload
        validate_upload(file)
        path = save_uploaded_file(file, 'visit_attachments', visit.id)
        try:
            attachment = VisitAttachment.objects.create(visit=visit, filename=os.path.basename(path),
                original_filename=file.name, filepath=path, file_size=file.verified_size, checksum=file.verified_checksum,
                mime_type=file.verified_mime, uploaded_by=uploaded_by)
            visit.version += 1
            visit.save(update_fields=['version', 'updated_at'])
            return attachment
        except Exception:
            from django.core.files.storage import default_storage
            default_storage.delete(path)
            raise

    @transaction.atomic
    def soft_delete_attachment(self, attachment, expected_version=None):
        visit = Visit.objects.select_for_update().get(pk=attachment.visit_id)
        check_mutation(visit, expected_version)
        if visit.status not in {'draft', 'amended'}:
            raise ValidationError({'visit': ['لا يمكن حذف مرفقات سجل معتمد']})
        attachment.soft_delete()
        visit.version += 1
        visit.save(update_fields=['version', 'updated_at'])
        return True
