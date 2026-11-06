import json
from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from .models import Visit, VisitAttachment, VisitRevision
from apps.patients.models import Patient
from core.mutation import check_mutation
from core.exceptions import ConflictError
from core.lifecycle import enforce_transition
from core.file_utils import save_uploaded_file, uploaded_file_metadata
from .scale_validation import normalize_scale_response
from .lab_validation import normalize_lab_values
from .input_validation import normalize_rows, clinical_object, text


def lock_visit(visit_id, actor=None, permission=None):
    """Lock the patient before its encounter, matching patient reconciliation."""
    patient_id = Visit.all_objects.values_list('patient_id', flat=True).get(pk=visit_id)
    Patient.all_objects.select_for_update().get(pk=patient_id)
    visit = Visit.all_objects.select_for_update().get(pk=visit_id)
    if visit.patient_id != patient_id:
        raise ConflictError('تغير ملف المريض؛ أعد تحميل الزيارة')
    if actor is not None:
        from core.access import accessible_visits, require_actor_permission
        actor = require_actor_permission(actor, permission or 'edit_visit')
        if not accessible_visits(actor).filter(pk=visit.pk).exists():
            raise PermissionDenied('غير مصرح بهذا الإجراء على الزيارة')
    return visit


class VisitService:
    EDITABLE = {
        'visit_date', 'main_complaints', 'history_presenting_complaint', 'treatment_text',
        'doctor_notes', 'clinical_status', 'accompanied_by', 'companion_relation',
        'pain_level', 'anxiety_level', 'suicide_risk_level',
        'violence_risk_level', 'firearm_access', 'level_of_care', 'care_basis',
        'supervisor', 'diagnosis_discussed', 'plan_discussed', 'clinical_data',
    }

    def _validate(self, data, require_complete=False):
        if not data.get('visit_date'):
            raise ValidationError({'visit_date': ['تاريخ الزيارة مطلوب']})
        if require_complete and not text(data.get('main_complaints'), 'main_complaints', 100_000):
            raise ValidationError({'main_complaints': ['الشكوى الرئيسية مطلوبة']})

    @staticmethod
    def _follow_up_data(visit):
        from apps.patients.follow_up_services import follow_up_data
        return follow_up_data(visit.follow_up)

    @staticmethod
    def _validate_follow_up(visit):
        if visit.follow_up and visit.follow_up.due_date < visit.visit_date:
            raise ValidationError({'follow_up_input': ['المتابعة لا تسبق الزيارة']})

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
        from .nested import REPLACERS
        for key, replace in REPLACERS.items():
            if key in nested:
                replace(visit, nested[key])
        if 'scale_responses' in nested:
            self._save_scale_responses(visit, nested['scale_responses'])

    def _sign(self, visit, actor):
        from core.access import require_actor_permission
        actor = require_actor_permission(actor, 'edit_visit')
        if actor.role not in {'admin', 'doctor'}:
            raise PermissionDenied('التوقيع مخصص للطبيب المخول')
        self._validate({'visit_date': visit.visit_date, 'main_complaints': visit.main_complaints}, True)
        self._validate_follow_up(visit)
        self._validate_final_sections(visit.get_medications(), visit.get_lab_values())
        visit.signed_by = actor
        visit.signed_at = timezone.now()
        visit.date_signed = timezone.localdate()
        visit.save(update_fields=['signed_by', 'signed_at', 'date_signed', 'updated_at'])
        scalar = {field.name: field.value_from_object(visit) for field in visit._meta.concrete_fields}
        snapshot = json.loads(json.dumps({
            'schema_version': 4, 'follow_up': self._follow_up_data(visit), 'fields': scalar, 'diagnoses': visit.get_diagnoses(),
            'medications': visit.get_medications(), 'lab_values': visit.get_lab_values(),
            'scales': list(visit.scale_responses.values('scale_id', 'scale_name_snapshot', 'responses_json')),
            'attachments': list(visit.attachments.values('id', 'original_filename', 'filepath', 'file_size')),
            'patient': {'id': visit.patient_id, 'name': visit.patient.get_full_name(),
                        'national_id': visit.patient.national_id, 'dob_year': visit.patient.dob_year,
                        'gender': visit.patient.gender, 'patient_number': visit.patient.patient_number},
            'longitudinal': {
                'allergy_status': visit.patient.allergy_status, 'medication_status': visit.patient.medication_status,
                'allergies': list(visit.patient.patientallergy_records.filter(is_active=True).values()),
                'medications': list(visit.patient.patientmedication_records.filter(is_active=True).values())},
            'clinician': {'id': actor.pk, 'name': actor.full_name or actor.username},
        }, cls=DjangoJSONEncoder, allow_nan=False))
        number = (visit.revisions.order_by('-number').values_list('number', flat=True).first() or 0) + 1
        revision = VisitRevision(visit=visit, number=number, snapshot=snapshot,
                                 signer=actor, signed_at=visit.signed_at, reason=visit.amendment_reason)
        from apps.patients.integrity import validate_links
        validate_links(revision)
        revision.full_clean()
        revision.save()

    @transaction.atomic
    def create_visit(self, patient, data, current_user):
        from core.access import require_actor_permission
        current_user = require_actor_permission(current_user, 'add_visit')
        patient = Patient.objects.select_for_update().get(pk=patient.pk)
        from apps.patients.record_services import require_access
        require_access(patient, current_user)
        data = data.copy()
        status = data.pop('status', 'draft')
        if status not in {'draft', 'final'}:
            raise ValidationError({'status': ['يجب إنشاء الزيارة كمسودة أو نهائية']})
        has_plan = 'follow_up_input' in data
        plan = data.pop('follow_up_input', None)
        nested = self._nested(data)
        if 'clinical_data' in data:
            from .instruction_acknowledgement import stamp_instruction_acknowledgement
            data['clinical_data'] = stamp_instruction_acknowledgement(data['clinical_data'], current_user)
        self._validate(data)
        visit = Visit(patient=patient, author=current_user, status=status,
                      **{key: value for key, value in data.items() if key in self.EDITABLE})
        visit.full_clean(exclude=['patient', 'author', 'signed_by', 'supervisor'])
        visit.save()
        self._save_nested(visit, nested)
        if has_plan:
            from apps.patients.follow_up_services import set_visit_follow_up
            set_visit_follow_up(visit, plan, current_user, action='add_visit')
        if status == 'final':
            self._sign(visit, current_user)
        return visit

    @transaction.atomic
    def update_visit(self, visit, data, current_user, expected_version=None):
        visit = lock_visit(visit.pk, current_user)
        check_mutation(visit, expected_version)
        if visit.status in {'final', 'locked'}:
            raise ValidationError({'status': ['افتح تعديلاً قبل تغيير الزيارة المعتمدة']})
        data = data.copy()
        if 'patient' in data or 'patient_id' in data:
            raise ValidationError({'patient_id': ['لا يمكن تغيير مريض الزيارة']})
        status = data.pop('status', visit.status)
        enforce_transition('visit', visit.status, status)
        has_plan = 'follow_up_input' in data
        plan = data.pop('follow_up_input', None)
        opening_version = visit.version
        nested = self._nested(data, visit)
        if 'clinical_data' in data:
            from .instruction_acknowledgement import stamp_instruction_acknowledgement
            data['clinical_data'] = stamp_instruction_acknowledgement(data['clinical_data'], current_user, visit.clinical_data)
        for key, value in data.items():
            if key in self.EDITABLE:
                setattr(visit, key, value)
        self._validate({'visit_date': visit.visit_date, 'main_complaints': visit.main_complaints})
        visit.status = status
        visit.full_clean(exclude=['patient', 'author', 'signed_by', 'supervisor'])
        visit.save()
        self._save_nested(visit, nested)
        if has_plan:
            from apps.patients.follow_up_services import set_visit_follow_up
            set_visit_follow_up(visit, plan, current_user)
        self._validate_follow_up(visit)
        if visit.version == opening_version:
            visit.version += 1
            visit.save(update_fields=['version', 'updated_at'])
        if status in {'final', 'locked'}:
            self._sign(visit, current_user)
        return visit

    @transaction.atomic
    def transition(self, visit, target_status, current_user, expected_version=None, reason=''):
        visit = lock_visit(visit.pk, current_user)
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
    def soft_delete_visit(self, visit, expected_version=None, actor=None):
        from core.request_context import get_current_request
        request = get_current_request()
        actor = actor or (request.user if request else None)
        if actor is None:
            raise PermissionDenied('المستخدم المنفذ مطلوب')
        visit = lock_visit(visit.pk, actor, 'delete_visit')
        check_mutation(visit, expected_version)
        if visit.status != 'draft':
            raise ValidationError({'status': ['السجلات المعتمدة تحفظ تاريخياً']})
        if visit.follow_up:
            from apps.patients.follow_up_services import set_visit_follow_up
            set_visit_follow_up(visit, {'due_date': None, 'reason': 'Draft visit archived'}, actor, action='delete_visit')
        visit.soft_delete()
        return True

    @transaction.atomic
    def mark_all_overdue(self, user):
        from apps.patients.follow_up_services import accessible_follow_ups
        rows = accessible_follow_ups(user).filter(due_date__lt=timezone.localdate(), status='pending')
        patient_ids = set(rows.values_list('patient_id', flat=True))
        list(Patient.all_objects.select_for_update().filter(pk__in=patient_ids).order_by('pk'))
        count = 0
        from apps.patients.record_services import PatientRecordService
        rows = rows.filter(patient_id__in=patient_ids).order_by('patient_id', 'pk')
        for action in rows:
            patient = Patient.objects.select_for_update().get(pk=action.patient_id)
            PatientRecordService().save(patient, 'follow-ups', {'status': 'missed', 'outcome_reason': 'Overdue review'},
                user, patient.version, action.pk, reason='Explicit overdue review')
            count += 1
        return count


class VisitAttachmentService:
    @transaction.atomic
    def upload_attachment(self, visit, file, uploaded_by, expected_version=None):
        visit = lock_visit(visit.pk, uploaded_by, 'manage_patient_documents')
        check_mutation(visit, expected_version)
        if visit.status not in {'draft', 'amended'}:
            raise ValidationError({'visit': ['افتح تعديلاً قبل إضافة مرفق إلى سجل معتمد']})
        from core.upload_security import validate_upload
        validate_upload(file)
        path = save_uploaded_file(file, 'visit_attachments', visit.id)
        try:
            attachment = VisitAttachment.objects.create(visit=visit, uploaded_by=uploaded_by,
                **uploaded_file_metadata(file, path))
            visit.version += 1
            visit.save(update_fields=['version', 'updated_at'])
            return attachment
        except Exception:
            from django.core.files.storage import default_storage
            default_storage.delete(path)
            raise

    @transaction.atomic
    def soft_delete_attachment(self, attachment, expected_version=None, actor=None):
        from core.request_context import get_current_request
        request = get_current_request()
        actor = actor or (request.user if request else None)
        if actor is None:
            raise PermissionDenied('المستخدم المنفذ مطلوب')
        visit = lock_visit(attachment.visit_id, actor, 'manage_patient_documents')
        check_mutation(visit, expected_version)
        if visit.status not in {'draft', 'amended'}:
            raise ValidationError({'visit': ['لا يمكن حذف مرفقات سجل معتمد']})
        attachment.soft_delete()
        visit.version += 1
        visit.save(update_fields=['version', 'updated_at'])
        return True
