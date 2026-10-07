# backend/apps/visits/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Visit, VisitAttachment
from apps.patients.models import Patient
from django.db.models import Q
from core.exceptions import ConflictError
from core.lifecycle import enforce_transition
from core.file_utils import save_uploaded_file
from .scale_validation import normalize_scale_response
from .lab_validation import normalize_lab_values
import os


class VisitService:
    def _validate(self, data, require_complete=False):
        errors = []
        if not data.get('visit_date'):
            errors.append('تاريخ الزيارة مطلوب')
        visit_date = data.get('visit_date')
        follow_up_date = data.get('follow_up_date')
        if visit_date and follow_up_date:
            try:
                follow_up_before_visit = follow_up_date < visit_date
            except TypeError:
                errors.append('تاريخ المتابعة غير صالح')
            else:
                if follow_up_before_visit:
                    errors.append('تاريخ المتابعة لا يمكن أن يسبق تاريخ الزيارة')
        if require_complete and not data.get('main_complaints'):
            errors.append('الشكوى الرئيسية مطلوبة')
        if errors:
            raise ValidationError(errors)

    def _validate_final_sections(self, medications, lab_values):
        invalid_medications = [
            index for index, medication in enumerate(medications or [], start=1)
            if not str(medication.get('name', '')).strip()
            or not str(medication.get('dosage', '')).strip()
            or not str(medication.get('schedule', '')).strip()
        ]
        if invalid_medications:
            raise ValidationError({
                'medications': [f'بيانات الدواء ناقصة في الصفوف: {invalid_medications}'],
            })
        normalize_lab_values(lab_values or [], require_complete=True)

    @transaction.atomic
    def create_visit(self, patient, data, current_user):
        requested_status = data.get('status') or 'draft'
        if requested_status not in {'draft', 'final'}:
            raise ValidationError({'status': ['يجب إنشاء الزيارة كمسودة أو نهائية']})
        allowed_fields = [
            'visit_date', 'main_complaints', 'history_presenting_complaint',
            'treatment_text', 'doctor_notes', 'status', 'status_reason', 'clinical_status', 'accompanied_by',
            'companion_relation', 'follow_up_date', 'pain_level',
            'anxiety_level', 'suicide_risk_level', 'violence_risk_level',
            'firearm_access', 'level_of_care', 'follow_up_type',
            'date_signed', 'signed_by', 'supervisor',
            'diagnosis_discussed', 'plan_discussed', 'clinical_data'
        ]

        # Extract nested input fields before touching scalar fields. The
        # frontend serializer declares these as `*_input` (see
        # VisitSerializer.diagnoses_input etc.), but the old code looked
        # only for the legacy direct keys, so a visit created through the
        # current UI silently stored no diagnoses/medications/labs/scales
        # even though the response was 201. Accept both shapes.
        diagnoses = data.pop('diagnoses_input', None)
        medications = data.pop('medications_input', None)
        lab_values = data.pop('lab_values_input', None)
        scale_responses = data.pop('scale_responses_input', None)

        if diagnoses is None and 'diagnoses' in data:
            diagnoses = data.pop('diagnoses')
        if medications is None and 'medications' in data:
            medications = data.pop('medications')
        if lab_values is None and 'lab_values' in data:
            lab_values = data.pop('lab_values')
        if scale_responses is None and 'scale_responses' in data:
            scale_responses = data.pop('scale_responses')

        self._validate(data, require_complete=requested_status == 'final')
        lab_values = normalize_lab_values(
            lab_values or [], require_complete=requested_status == 'final'
        )
        if requested_status == 'final':
            self._validate_final_sections(medications or [], lab_values)

        visit = Visit(
            patient=patient,
            author=current_user,
            **{k: v for k, v in data.items() if k in allowed_fields}
        )
        visit.save()

        if diagnoses is not None:
            visit.set_diagnoses(diagnoses)
        if medications is not None:
            visit.set_medications(medications)
        if lab_values is not None:
            visit.set_lab_values(lab_values)
        if scale_responses is not None:
            self._save_scale_responses(visit, scale_responses)
        return visit

    @transaction.atomic
    def update_visit(self, visit, data, current_user, expected_version=None):
        visit = Visit.all_objects.select_for_update().get(pk=visit.pk)
        if expected_version is None:
            raise ValidationError(['يجب توفير رقم الإصدار'])
        if visit.version != expected_version:
            raise ConflictError('تم تعديل هذه الزيارة بواسطة مستخدم آخر')
        if visit.status in {'final', 'locked'}:
            raise ValidationError({
                'status': ['يجب تحويل الزيارة إلى معدلة قبل تغيير محتواها']
            })

        merged = {
            'visit_date': data.get('visit_date', visit.visit_date),
            'main_complaints': data.get('main_complaints', visit.main_complaints),
            'follow_up_date': data.get('follow_up_date', visit.follow_up_date),
        }
        target_status = data.get('status', visit.status)
        if target_status != visit.status:
            enforce_transition('visit', visit.status, target_status)
        if 'patient' in data or 'patient_id' in data:
            raise ValidationError(['لا يمكن تغيير المريض المرتبط بالزيارة'])

        diagnoses = data.pop('diagnoses_input', None)
        medications = data.pop('medications_input', None)
        lab_values = data.pop('lab_values_input', None)
        scale_responses = data.pop('scale_responses_input', None)

        if diagnoses is None and 'diagnoses' in data:
            diagnoses = data.pop('diagnoses')
        if medications is None and 'medications' in data:
            medications = data.pop('medications')
        if lab_values is None and 'lab_values' in data:
            lab_values = data.pop('lab_values')
        if scale_responses is None and 'scale_responses' in data:
            scale_responses = data.pop('scale_responses')

        self._validate(merged, require_complete=target_status in {'final', 'locked'})
        effective_labs = normalize_lab_values(
            lab_values if lab_values is not None else visit.get_lab_values(),
            require_complete=target_status in {'final', 'locked'},
        )
        if lab_values is not None:
            lab_values = effective_labs
        if target_status in {'final', 'locked'}:
            self._validate_final_sections(
                medications if medications is not None else visit.get_medications(),
                effective_labs,
            )

        for k, v in data.items():
            if hasattr(visit, k) and k not in ['version', 'patient', 'patient_id']:
                setattr(visit, k, v)

        visit.version += 1
        visit.save()

        if diagnoses is not None:
            visit.set_diagnoses(diagnoses)
        if medications is not None:
            visit.set_medications(medications)
        if lab_values is not None:
            visit.set_lab_values(lab_values)
        if scale_responses is not None:
            self._save_scale_responses(visit, scale_responses)

        return visit

    @transaction.atomic
    def transition(self, visit, target_status, current_user, expected_version=None, reason=''):
        visit = Visit.all_objects.select_for_update().get(pk=visit.pk)
        if expected_version is None:
            raise ValidationError({'version': ['يجب توفير رقم الإصدار']})
        if visit.version != expected_version:
            raise ConflictError('تم تعديل هذه الزيارة بواسطة مستخدم آخر')
        changed = enforce_transition('visit', visit.status, target_status)
        if not changed:
            return visit
        if target_status in {'final', 'locked'}:
            self._validate({
                'visit_date': visit.visit_date,
                'main_complaints': visit.main_complaints,
            }, require_complete=True)
            self._validate_final_sections(visit.get_medications(), visit.get_lab_values())
        if target_status == 'amended' and not str(reason).strip():
            raise ValidationError({'reason': ['سبب التعديل مطلوب']})
        visit.status = target_status
        visit.status_reason = str(reason).strip() if reason else ''
        visit.version += 1
        visit.save(update_fields=['status', 'status_reason', 'version', 'updated_at'])
        return visit

    def _save_scale_responses(self, visit, responses):
        existing_snapshots = {
            response.scale_id: {
                'definition': (response.responses_json or {}).get('__definition'),
                'name': response.scale_name_snapshot,
            }
            for response in visit.scale_responses.all()
        }
        normalized_responses = []
        seen_scale_ids = set()
        for item in responses:
            try:
                item_scale_id = int(item.get('scale_id'))
            except (AttributeError, TypeError, ValueError):
                item_scale_id = None
            existing = existing_snapshots.get(item_scale_id) or {}
            item = normalize_scale_response(
                item, existing.get('definition'), existing.get('name')
            )
            if item['scale_id'] in seen_scale_ids:
                raise ValidationError({
                    'scale_responses': ['لا يمكن تكرار المقياس في الزيارة نفسها'],
                })
            seen_scale_ids.add(item['scale_id'])
            normalized_responses.append(item)

        visit.scale_responses.all().delete()
        for item in normalized_responses:
            visit.scale_responses.create(
                scale_id=item.get('scale_id'),
                scale_name_snapshot=item.get('scale_name', ''),
                responses_json=item.get('responses', {}),
            )

    @transaction.atomic
    def soft_delete_visit(self, visit):
        visit = Visit.all_objects.select_for_update().get(pk=visit.pk)
        if visit.status != 'draft':
            raise ValidationError({
                'status': ['لا يمكن أرشفة سجل سريري معتمد؛ السجلات النهائية تحفظ تاريخياً'],
            })
        now = timezone.now()
        visit.soft_delete()
        visit.attachments.filter(deleted_at__isnull=True).update(
            deleted_at=now,
            is_active=False,
            updated_at=now,
        )
        return True

    @transaction.atomic
    def complete_follow_up(self, visit):
        visit.updated_at = timezone.now()
        visit.follow_up_completed = True
        visit.save(update_fields=['follow_up_completed', 'updated_at'])
        return visit

    @transaction.atomic
    def mark_all_overdue(self, user):
        today = timezone.now().date()
        visits = Visit.objects.filter(
            follow_up_date__lt=today,
            follow_up_completed=False,
        )
        if user.role == 'doctor':
            visits = visits.filter(patient__doctor=user)
        elif user.role == 'receptionist':
            visits = visits.filter(patient__created_by=user)
        count = visits.update(follow_up_completed=True)
        return count


class VisitAttachmentService:
    @transaction.atomic
    def upload_attachment(self, visit, file, uploaded_by):
        path = save_uploaded_file(file, 'visit_attachments', visit.id)
        attachment = VisitAttachment.objects.create(
            visit=visit,
            filename=os.path.basename(path),
            original_filename=file.name,
            filepath=path,
            file_size=file.size,
            mime_type=file.content_type,
            uploaded_by=uploaded_by,
        )
        return attachment

    def soft_delete_attachment(self, attachment):
        attachment.soft_delete()
        return True
