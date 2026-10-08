from core.mutation import check_mutation
# backend/apps/patients/services.py
import os
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.db.models import Q, CharField, TextField
from datetime import date
from .models import Patient, PatientDocument, PatientCareTeam
from apps.accounts.models import User
from django.db import connection
from core.arabic_utils import normalise_arabic
from core.exceptions import ConflictError
from core.file_utils import save_uploaded_file
from core.normalization import (
    NATIONAL_ID_MAX_LENGTH,
    NATIONAL_ID_MIN_LENGTH,
    normalize_identifier,
    normalize_name,
    normalize_phone,
    normalized_search_text,
)
from core.query_utils import apply_ordering

class PatientService:
    EDITABLE_FIELDS = {
        'first_name', 'father_name', 'surname', 'mother_name', 'dob_year', 'gender',
        'national_id', 'marital_status', 'occupation', 'permanent_address', 'phone',
        'emergency_contact_name', 'emergency_contact_relation', 'emergency_contact_phone',
        'family_history', 'important_notes', 'registration_date', 'identity_verification',
        'preferred_language', 'preferred_contact_channel', 'communication_restrictions', 'allergy_status', 'medication_status',
    }
    IDENTITY_FIELDS = ('first_name', 'father_name', 'surname', 'mother_name')
    CORRECTION_FIELDS = set(IDENTITY_FIELDS) | {'dob_year', 'gender', 'national_id', 'phone', 'permanent_address', 'marital_status'}

    def _normalize(self, data):
        data = data.copy()
        if 'admission_date' in data:
            data.setdefault('registration_date', data.pop('admission_date'))
        for field in self.EDITABLE_FIELDS:
            model_field = Patient._meta.get_field(field)
            if isinstance(model_field, (CharField, TextField)) and field in data:
                data[field] = '' if data[field] is None else data[field].strip() if isinstance(data[field], str) else data[field]
        for field in self.IDENTITY_FIELDS:
            if field in data and data[field] is not None:
                data[field] = normalize_name(data[field])
        for field in ('phone', 'emergency_contact_phone'):
            if field in data:
                data[field] = normalize_phone(data[field]) or ''
        if 'national_id' in data:
            data['national_id'] = normalize_identifier(data['national_id']) or ''
        return data

    def _validate(self, data, is_edit=False, existing=None):
        errors = []
        if not is_edit:
            if not data.get('first_name'):
                errors.append('الاسم الأول مطلوب')
            if not data.get('surname'):
                errors.append('اسم العائلة مطلوب')
        else:
            if 'first_name' in data and not data.get('first_name'):
                errors.append('الاسم الأول مطلوب')
            if 'surname' in data and not data.get('surname'):
                errors.append('اسم العائلة مطلوب')

        if data.get('national_id'):
            if not (NATIONAL_ID_MIN_LENGTH <= len(data['national_id']) <= NATIONAL_ID_MAX_LENGTH):
                errors.append('الرقم الوطني غير صالح')
        if data.get('phone'):
            phone = data['phone'].strip()
            if not (phone.startswith('0') or phone.startswith('+963')):
                errors.append('رقم الهاتف غير صالح')
        dob_year = data.get('dob_year')
        if dob_year is not None and (type(dob_year) is not int or not (1900 <= dob_year <= timezone.localdate().year)):
            errors.append('سنة الميلاد غير صالحة')
        if errors:
            raise ValidationError(errors)

    def _resolve_doctor(self, data, current_user):
        doctor = data.get('doctor')
        if doctor and isinstance(doctor, User):
            if not doctor.is_active or doctor.role not in {'doctor'}:
                raise ValidationError(['الطبيب المحدد غير صالح'])
            return doctor
        doctor_id = data.get('doctor_id')
        if doctor_id:
            try:
                doctor = User.objects.get(id=doctor_id, role='doctor', is_active=True)
                return doctor
            except User.DoesNotExist:
                raise ValidationError(['الطبيب المحدد غير صالح'])
        return None

    def _sync_identifier(self, patient, actor, previous=''):
        from .models import PatientIdentifier
        if previous and previous != patient.national_id:
            PatientIdentifier.objects.filter(patient=patient, identifier_type='national_id', value=previous, is_active=True).update(is_active=False, retired_at=timezone.now(), retired_by=actor, retirement_reason='Primary identity corrected')
        if patient.national_id:
            PatientIdentifier.objects.get_or_create(patient=patient, identifier_type='national_id',
                value=patient.national_id, issuer='', is_active=True,
                defaults={'created_by': actor, 'updated_by': actor, 'verification': 'reported'})

    def _verify_profile(self, patient, data, actor, identity_changed=False, previous_verification=None):
        from .models import PatientAllergy, PatientMedication
        if patient.identity_verification == 'verified' and (previous_verification != 'verified' or identity_changed):
            if actor.role not in {'admin', 'doctor'}:
                raise PermissionDenied('تأكيد الهوية مخصص للطبيب أو المدير')
            patient.identity_verified_at, patient.identity_verified_by = timezone.now(), actor
        elif patient.identity_verification != 'verified':
            patient.identity_verified_at, patient.identity_verified_by = None, None
        for field in ('allergy_status', 'medication_status'):
            if field in data and data[field] != 'unknown' and not actor.has_perm('edit_visit'):
                raise PermissionDenied('تسجيل المعلومات السريرية يتطلب صلاحية تعديل الزيارات')
        for field, model, statuses in [('allergy_status', PatientAllergy, ['suspected', 'confirmed']),
                                        ('medication_status', PatientMedication, ['active', 'on_hold'])]:
            if getattr(patient, field) == 'none_known' and patient.pk and model.objects.filter(patient=patient, is_active=True, status__in=statuses).exists():
                raise ValidationError({field: ['توجد سجلات حالية؛ راجعها قبل تسجيل عدم وجود معلومات']})

    @transaction.atomic
    def create_patient(self, data, current_user):
        data = self._normalize(data)
        self._validate(data, is_edit=False)
        doctor = self._resolve_doctor(data, current_user)
        patient = Patient(**{key: value for key, value in data.items() if key in self.EDITABLE_FIELDS})
        patient.registration_date = patient.registration_date or timezone.localdate()
        patient.created_by = current_user
        patient.doctor = doctor  # Compatibility display only; access/assignment is care-team based.
        self._verify_profile(patient, data, current_user)
        patient.full_clean()
        patient.save()
        self._sync_identifier(patient, current_user)
        if patient.emergency_contact_name:
            from .models import PatientContact
            PatientContact.objects.create(patient=patient, name=patient.emergency_contact_name, relationship=patient.emergency_contact_relation, phone=patient.emergency_contact_phone, is_emergency=True, is_primary=True, created_by=current_user, updated_by=current_user)
        members = data.get('care_team_ids', [])
        if not isinstance(members, list) or len(members) > 100:
            raise ValidationError({'care_team_ids': ['قائمة فريق غير صالحة']})
        ids = {self._member_id(value) for value in members}
        if doctor:
            ids.add(doctor.pk)
        if current_user.role != 'admin':
            ids.add(current_user.pk)
        users = list(User.objects.filter(pk__in=ids, is_active=True))
        if len(users) != len(ids):
            raise ValidationError({'care_team_ids': ['يوجد عضو غير متاح']})
        for member in users:
            PatientCareTeam.objects.create(patient=patient, user=member, assigned_by=current_user,
                role='doctor' if member.role == 'doctor' else 'coordinator')
        return patient

    @transaction.atomic
    def update_patient(self, patient, data, current_user, expected_version=None):
        from .models import PatientCorrection
        from .record_services import json_value
        patient = Patient.all_objects.select_for_update().get(pk=patient.pk)
        check_mutation(patient, expected_version)
        previous_identifier = patient.national_id
        previous_verification = patient.identity_verification
        data = self._normalize(data)
        self._validate(data, is_edit=True, existing=patient)
        changes = {key: {'before': json_value(getattr(patient, key)), 'after': json_value(value)}
                   for key, value in data.items() if key in self.CORRECTION_FIELDS and getattr(patient, key) != value}
        reason = data.get('correction_reason', '')
        if changes and (not isinstance(reason, str) or not reason.strip() or len(reason) > 500):
            raise ValidationError({'correction_reason': ['سبب تصحيح البيانات مطلوب (حتى 500 محرف)']})
        for key, value in data.items():
            if key in self.EDITABLE_FIELDS:
                setattr(patient, key, value)
        # Changing verified identity requires explicit re-verification; never silently carry the old assertion.
        if changes and 'identity_verification' not in data:
            patient.identity_verification = 'reported'
        self._verify_profile(patient, data, current_user, bool(changes), previous_verification)
        patient.version += 1
        patient.full_clean()
        patient.save()
        self._sync_identifier(patient, current_user, previous_identifier)
        if changes:
            PatientCorrection.objects.create(patient=patient, actor=current_user, reason=reason.strip(), changes=changes)
        return patient

    @transaction.atomic
    def soft_delete_patient(self, patient, user, expected_version=None):
        if user.role != 'admin':
            raise ValidationError(['غير مصرح لك بهذا الإجراء'])
        patient = Patient.all_objects.select_for_update().get(pk=patient.pk)
        check_mutation(patient, expected_version)
        patient.soft_delete(user, 'Patient archived; clinical history retained')
        return True

    @transaction.atomic
    def anonymize(self, patient, user, expected_version=None):
        # Identity restriction is pseudonymization, not erasure of signed history.
        if user.role != 'admin':
            raise ValidationError(['غير مصرح لك بهذا الإجراء'])
        patient = Patient.all_objects.select_for_update().get(pk=patient.pk)
        check_mutation(patient, expected_version)
        patient.first_name = 'مجهول'
        patient.surname = str(patient.pk)
        for field in ('father_name', 'mother_name', 'national_id', 'phone', 'permanent_address',
                      'emergency_contact_name', 'emergency_contact_phone', 'occupation'):
            setattr(patient, field, '')
        from .models import PatientIdentifier, PatientContact, PatientRepresentative
        PatientIdentifier.objects.filter(patient=patient).update(value=patient.patient_number, issuer='', verification='unknown', is_active=False, retired_at=timezone.now(), retired_by=user, retirement_reason='Identity restricted')
        PatientContact.objects.filter(patient=patient).update(name='Restricted', phone='', email='', notes='', is_active=False, retired_at=timezone.now(), retired_by=user, retirement_reason='Identity restricted')
        PatientRepresentative.objects.filter(patient=patient).update(name='Restricted', phone='', evidence='', is_active=False, retired_at=timezone.now(), retired_by=user, retirement_reason='Identity restricted')
        patient.identity_verification = 'unknown'
        patient.identity_verified_at = None
        patient.identity_verified_by = None
        patient.communication_restrictions = ''
        patient.version += 1
        patient.save()
        patient.soft_delete(user, 'Identity restricted; signed historical records retained')
        return True

    def list_patients(self, user, filters=None):
        include_archived = bool(filters and filters.get('include_archived') == 'true')
        manager = Patient.all_objects if include_archived else Patient.objects
        from core.access import accessible_patients
        qs = accessible_patients(user, include_archived).select_related('doctor')

        search = filters.get('search', '') if filters else ''
        if search:
            normalized_search = normalized_search_text(search)
            if not normalized_search:
                return qs.none()
            # Use normalized search on normalized fields (e.g., normalised_full_name)
            # For now, we keep the original but note: this should be improved.
            qs = qs.filter(
                Q(normalised_full_name__icontains=normalized_search) |
                Q(first_name__icontains=search) |
                Q(father_name__icontains=search) |
                Q(surname__icontains=search) |
                Q(national_id__icontains=search) |
                Q(phone__icontains=search) | Q(patient_number__icontains=search) | Q(patientidentifier_records__value__icontains=search)
            )
        if filters:
            active = filters.get('active')
            if active == 'true':
                qs = qs.filter(is_active=True, deleted_at__isnull=True)
            elif active == 'false' and include_archived:
                qs = qs.filter(Q(is_active=False) | Q(deleted_at__isnull=False))
            completeness = filters.get('completeness')
            from .completeness import incomplete_query
            incomplete = incomplete_query()
            if completeness == 'incomplete':
                qs = qs.filter(incomplete)
            elif completeness == 'complete':
                qs = qs.exclude(incomplete)
            qs = apply_ordering(qs, filters, {
                'name': 'normalised_full_name',
                'admission_date': 'registration_date', 'registration_date': 'registration_date',
                'created_at': 'created_at',
                'updated_at': 'updated_at',
            })
        return qs.distinct()

    def find_duplicates(self, user, data, exclude_id=None):
        data = self._normalize(data)
        qs = self.list_patients(user, {'include_archived': 'true'}).filter(merged_into__isnull=True)
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
            from .models import PatientDuplicateReview
            reviewed = PatientDuplicateReview.objects.filter(Q(patient_id=exclude_id) | Q(other_patient_id=exclude_id), status__in=['dismissed', 'different'])
            hidden = [row.other_patient_id if row.patient_id == exclude_id else row.patient_id for row in reviewed]
            if data.get('include_reviewed') is not True:
                qs = qs.exclude(pk__in=hidden)
        strong = Q()
        national_id = data.get('national_id')
        phone = data.get('phone')
        if national_id:
            strong |= Q(national_id=national_id) | Q(patientidentifier_records__value=national_id, patientidentifier_records__is_active=True)
        if phone:
            strong |= Q(phone=phone)
        name = ' '.join(filter(None, [data.get('first_name'), data.get('father_name'), data.get('surname')]))
        if name and data.get('dob_year'):
            strong |= Q(
                normalised_full_name=normalized_search_text(name),
                dob_year=data['dob_year'],
            )
        if not strong:
            return qs.none()
        return qs.filter(strong).select_related('doctor').order_by('-updated_at')[:10]

    @transaction.atomic
    def restore_patient(self, patient, user, expected_version):
        if user.role != 'admin':
            raise PermissionDenied('الاستعادة مخصصة للمدير')
        patient = Patient.all_objects.select_for_update().get(pk=patient.pk)
        if type(expected_version) is not int or patient.version != expected_version:
            raise ConflictError('تغير السجل؛ أعد تحميله')
        if patient.merged_into_id:
            raise ValidationError('الملف مدمج؛ استخدم الملف الباقي')
        patient.is_active = True
        patient.deleted_at = None
        patient.full_clean()
        patient.restore()
        return patient

    def get_care_team(self, patient):
        return patient.care_team.select_related('user', 'assigned_by', 'ended_by').order_by('ended_at', 'id')

    @staticmethod
    def _member_id(user_id):
        from core.mutation import parse_version
        try:
            return parse_version(user_id)
        except ValidationError:
            raise ValidationError({'user_id': ['معرف مستخدم صحيح مطلوب']})

    @transaction.atomic
    def add_care_team_member(self, patient, user_id, role, expected_version=None, actor=None, reason=''):
        patient = Patient.all_objects.select_for_update().get(pk=patient.pk)
        check_mutation(patient, expected_version)
        if actor is None:
            raise ValidationError('المستخدم المنفذ مطلوب')
        user_id = self._member_id(user_id)
        if not isinstance(role, str) or not role.strip() or len(role.strip()) > 50:
            raise ValidationError({'role': ['دور عضو فريق الرعاية مطلوب وبحد أقصى 50 حرف']})
        if PatientCareTeam.objects.filter(patient=patient, user_id=user_id, ended_at__isnull=True).exists():
            raise ValidationError(['العضو موجود بالفعل'])
        user = User.objects.filter(id=user_id, is_active=True).first()
        if not user:
            raise ValidationError(['المستخدم غير موجود'])
        member = PatientCareTeam(patient=patient, user=user, role=role.strip(), assigned_by=actor)
        member.full_clean()
        member.save()
        patient.version += 1
        patient.save(update_fields=['version', 'updated_at'])
        return member, patient.version

    @transaction.atomic
    def remove_care_team_member(self, patient, user_id, expected_version=None, actor=None, reason=''):
        patient = Patient.all_objects.select_for_update().get(pk=patient.pk)
        check_mutation(patient, expected_version)
        if actor is None:
            raise ValidationError('المستخدم المنفذ مطلوب')
        user_id = self._member_id(user_id)
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
            raise ValidationError({'reason': ['سبب إنهاء العضوية مطلوب']})
        member = PatientCareTeam.objects.filter(patient=patient, user_id=user_id, ended_at__isnull=True).first()
        if not member:
            raise ValidationError(['العضو غير موجود'])
        member.ended_at, member.ended_by, member.removal_reason = timezone.now(), actor, reason.strip()
        member.save()
        patient.version += 1
        patient.save(update_fields=['version', 'updated_at'])
        return patient.version

class PatientDocumentService:
    @transaction.atomic
    def upload_document(self, patient, file, uploaded_by, category='other', description='', metadata=None):
        patient = Patient.objects.select_for_update().get(pk=patient.pk)
        from core.upload_security import validate_upload
        validate_upload(file)
        if not isinstance(category, str) or len(category) > 50:
            raise ValidationError({'category': ['فئة غير صالحة']})
        path = save_uploaded_file(file, 'patient_docs', patient.id)
        try:
            doc = PatientDocument(patient=patient, filename=os.path.basename(path), original_filename=file.name,
                filepath=path, file_size=file.verified_size, mime_type=file.verified_mime,
                checksum=file.verified_checksum, category=category, description=description, uploaded_by=uploaded_by,
                **{key: value for key, value in (metadata or {}).items() if key in {'document_date', 'source', 'provider', 'verification'}})
            from .record_services import stamp_verification
            stamp_verification(doc, uploaded_by)
            doc.full_clean(exclude=['uploaded_by'])
            doc.save()
            return doc
        except Exception:
            from django.core.files.storage import default_storage
            default_storage.delete(path)
            raise

    @transaction.atomic
    def update_document(self, doc, data, expected_version):
        doc = PatientDocument.all_objects.select_for_update().get(pk=doc.pk)
        check_mutation(doc, expected_version)
        provenance_changed = any(field in data and getattr(doc, field) != data[field] for field in ('document_date', 'source', 'provider'))
        previous_verification = None if provenance_changed else doc.verification
        if provenance_changed and 'verification' not in data:
            doc.verification = 'reported'
        for field in ('category', 'description', 'document_date', 'source', 'provider', 'verification'):
            if field in data:
                setattr(doc, field, data[field])
        from .record_services import stamp_verification
        stamp_verification(doc, data.pop('_actor', None), previous_verification)
        doc.version += 1
        doc.full_clean()
        doc.save()
        return doc

    @transaction.atomic
    def soft_delete_document(self, doc, expected_version):
        doc = PatientDocument.all_objects.select_for_update().get(pk=doc.pk)
        check_mutation(doc, expected_version)
        doc.soft_delete()
        return True
