from core.mutation import check_mutation
# backend/apps/patients/services.py
from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.db.models import Q
from .models import Patient, PatientDocument, PatientCareTeam
from apps.accounts.models import User
from core.exceptions import ConflictError
from core.file_utils import save_uploaded_file, uploaded_file_metadata
from core.normalization import normalized_search_text
from core.query_utils import apply_ordering
from core.verification import stamp_verification
from .validation import EDITABLE_FIELDS, IDENTITY_FIELDS, CORRECTION_FIELDS, CLINICAL_PROFILE_FIELDS, normalize_profile_data, validate_profile_data
from .projections import CONTACT_FIELDS, sync_profile_identifier, profile_contact_values

def end_care_team_membership(member, actor, reason):
    # Cancelling a planned membership must not produce an end before its start.
    member.ended_at = max(timezone.now(), member.started_at)
    member.ended_by, member.removal_reason = actor, reason
    member.save()


class PatientService:
    EDITABLE_FIELDS = EDITABLE_FIELDS
    IDENTITY_FIELDS = IDENTITY_FIELDS
    CORRECTION_FIELDS = CORRECTION_FIELDS

    def _normalize(self, data):
        return normalize_profile_data(data)

    def _validate(self, data, is_edit=False, existing=None):
        return validate_profile_data(data, is_edit, existing)

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
        sync_profile_identifier(patient, actor, previous)

    def _verify_profile(self, patient, data, actor, identity_changed=False, previous_verification=None, previous_summaries=None):
        from .models import PatientAllergy, PatientMedication
        stamp_verification(patient, actor, None if identity_changed else previous_verification,
                           prefix='identity_', denial='تأكيد الهوية مخصص للطبيب أو المدير')
        for field in ('family_history', 'important_notes'):
            if field in data and data[field] != (previous_summaries or {}).get(field, '') and not actor.has_perm('edit_visit'):
                raise PermissionDenied('تعديل المعلومات السريرية يتطلب صلاحية تعديل الزيارات')
        for field in ('allergy_status', 'medication_status'):
            if field in data and data[field] != (previous_summaries or {}).get(field, 'unknown') and not actor.has_perm('edit_visit'):
                raise PermissionDenied('تسجيل المعلومات السريرية يتطلب صلاحية تعديل الزيارات')
        for field, model, statuses in [('allergy_status', PatientAllergy, ['suspected', 'confirmed']),
                                        ('medication_status', PatientMedication, ['active', 'on_hold'])]:
            if getattr(patient, field) in {'none_known', 'unknown'} and patient.pk and model.objects.filter(patient=patient, is_active=True, status__in=statuses).exists():
                raise ValidationError({field: ['توجد سجلات حالية؛ راجعها قبل تسجيل عدم وجود معلومات']})

    def prepare_create(self, data, current_user):
        """Validate the same proposed aggregate for preview and creation, without writes."""
        data = self._normalize(data)
        self._validate(data, is_edit=False)
        doctor = self._resolve_doctor(data, current_user)
        patient = Patient(**{key: value for key, value in data.items() if key in self.EDITABLE_FIELDS})
        patient.registration_date = patient.registration_date or timezone.localdate()
        patient.created_by = current_user
        patient.doctor = doctor  # Compatibility display only; access/assignment is care-team based.
        self._verify_profile(patient, data, current_user)
        patient.full_clean()
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
        if patient.emergency_contact_name:
            from .models import PatientContact
            contact = PatientContact(patient=patient, is_emergency=True, is_primary=True,
                                     created_by=current_user, updated_by=current_user, **profile_contact_values(patient))
            contact.full_clean(exclude=['patient'])
        return patient, users

    @transaction.atomic
    def create_patient(self, data, current_user):
        patient, users = self.prepare_create(data, current_user)
        patient.save()
        self._sync_identifier(patient, current_user)
        if patient.emergency_contact_name:
            from .models import PatientContact
            PatientContact.objects.create(patient=patient, is_emergency=True, is_primary=True,
                created_by=current_user, updated_by=current_user, **profile_contact_values(patient))
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
        previous_summaries = {field: getattr(patient, field) for field in ('allergy_status', 'medication_status', 'family_history', 'important_notes')}
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
        identity_changed = any(key in changes for key in set(self.IDENTITY_FIELDS) | {'dob_year', 'gender', 'national_id'})
        if identity_changed and 'identity_verification' not in data:
            patient.identity_verification = 'reported'
        self._verify_profile(patient, data, current_user, identity_changed, previous_verification, previous_summaries)
        patient.version += 1
        patient.full_clean()
        patient.save()
        self._sync_identifier(patient, current_user, previous_identifier)
        contact_fields = CONTACT_FIELDS
        if any(key in changes for key in contact_fields):
            from .models import PatientContact
            from .record_services import PatientRecordService
            primary = PatientContact.objects.filter(patient=patient, is_active=True, is_primary=True).first()
            if primary and not primary.is_emergency:
                raise ValidationError({'emergency_contact_name': ['عدّل الاتصال الأساسي من سجل الاتصالات أولاً']})
            fields = profile_contact_values(patient)
            fields.update(is_primary=True, is_emergency=True)
            retire = not fields['name']
            if retire and (fields['phone'] or fields['relationship']):
                raise ValidationError({'emergency_contact_name': ['اسم جهة الاتصال مطلوب']})
            if primary or not retire:
                PatientRecordService().save(patient, 'contacts', {} if retire else fields,
                    current_user, patient.version, primary.pk if primary else None, retire=retire, reason=reason)
                patient.refresh_from_db()
        if changes:
            narrative = {key: value for key, value in changes.items() if key in CLINICAL_PROFILE_FIELDS}
            demographic = {key: value for key, value in changes.items() if key not in narrative}
            if demographic:
                PatientCorrection.objects.create(patient=patient, actor=current_user, reason=reason.strip(), changes=demographic)
            if narrative:
                PatientCorrection.objects.create(patient=patient, actor=current_user, reason=reason.strip(), changes=narrative, record_type='clinical-profile')
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
        if PatientCareTeam.objects.unended().filter(patient=patient, user_id=user_id).exists():
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
        member = PatientCareTeam.objects.unended().filter(patient=patient, user_id=user_id).first()
        if not member:
            raise ValidationError(['العضو غير موجود'])
        end_care_team_membership(member, actor, reason.strip())
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
            doc = PatientDocument(patient=patient, **uploaded_file_metadata(file, path),
                category=category, description=description, uploaded_by=uploaded_by,
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
