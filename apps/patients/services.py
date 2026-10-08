from core.mutation import check_mutation
# backend/apps/patients/services.py
import os
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.db.models import Q
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
        'family_history', 'important_notes', 'admission_date', 'doctor',
    }
    IDENTITY_FIELDS = ('first_name', 'father_name', 'surname', 'mother_name')

    def _normalize(self, data):
        data = data.copy()
        for field in self.IDENTITY_FIELDS:
            if field in data and data[field] is not None:
                data[field] = normalize_name(data[field])
        for field in ('phone', 'emergency_contact_phone'):
            if field in data:
                data[field] = normalize_phone(data[field])
        if 'national_id' in data:
            data['national_id'] = normalize_identifier(data['national_id'])
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
            elif not is_edit or (existing and data['national_id'] != existing.national_id):
                query = Patient.objects.filter(national_id=data['national_id'])
                if existing:
                    query = query.exclude(pk=existing.pk)
                if query.exists():
                    errors.append('الرقم الوطني موجود بالفعل')
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
            if not doctor.is_active or doctor.role not in {'doctor', 'admin'}:
                raise ValidationError(['الطبيب المحدد غير صالح'])
            return doctor
        doctor_id = data.get('doctor_id')
        if doctor_id:
            try:
                doctor = User.objects.get(id=doctor_id, role__in=['doctor','admin'], is_active=True)
                return doctor
            except User.DoesNotExist:
                raise ValidationError(['الطبيب المحدد غير صالح'])
        return None

    @transaction.atomic
    def create_patient(self, data, current_user):
        data = self._normalize(data)
        self._validate(data, is_edit=False)
        doctor = self._resolve_doctor(data, current_user)
        if current_user.role == 'admin':
            if doctor is None:
                doctor = current_user
        elif current_user.role == 'receptionist':
            if doctor is None:
                raise ValidationError(['يرجى اختيار الطبيب المسؤول'])
        else:  # doctor
            doctor = current_user

        patient = Patient(
            first_name=data['first_name'],
            father_name=data.get('father_name'),
            surname=data.get('surname'),
            mother_name=data.get('mother_name'),
            dob_year=data.get('dob_year'),
            gender=data.get('gender'),
            national_id=data.get('national_id'),
            marital_status=data.get('marital_status'),
            occupation=data.get('occupation'),
            permanent_address=data.get('permanent_address'),
            phone=data.get('phone'),
            emergency_contact_name=data.get('emergency_contact_name'),
            emergency_contact_relation=data.get('emergency_contact_relation'),
            emergency_contact_phone=data.get('emergency_contact_phone'),
            family_history=data.get('family_history'),
            important_notes=data.get('important_notes'),
            admission_date=data.get('admission_date') or timezone.localdate(),
            doctor=doctor,
            created_by=current_user,
        )
        try:
            with transaction.atomic():
                patient.full_clean()
                patient.save()
        except IntegrityError:
            if patient.national_id and Patient.objects.filter(
                national_id=patient.national_id,
                deleted_at__isnull=True,
                is_active=True,
            ).exists():
                raise ValidationError({'national_id': ['الرقم الوطني موجود بالفعل']})
            raise
        return patient

    @transaction.atomic
    def update_patient(self, patient, data, current_user, expected_version=None):
        patient = Patient.all_objects.select_for_update().get(pk=patient.pk)
        check_mutation(patient, expected_version)
        data = self._normalize(data)
        if expected_version is None:
            raise ValidationError(['يجب توفير رقم الإصدار'])
        if patient.version != expected_version:
            raise ConflictError('تم تعديل هذا المريض بواسطة مستخدم آخر')
        self._validate(data, is_edit=True, existing=patient)

        doctor = self._resolve_doctor(data, current_user)
        if doctor is not None:
            data['doctor'] = doctor

        # Exclude version and doctor_id from assignment loop
        for k, v in data.items():
            if k in self.EDITABLE_FIELDS:
                setattr(patient, k, v)
        patient.version += 1
        try:
            with transaction.atomic():
                patient.full_clean()
                patient.save()
        except IntegrityError:
            if patient.national_id and Patient.objects.filter(
                national_id=patient.national_id,
                deleted_at__isnull=True,
                is_active=True,
            ).exclude(pk=patient.pk).exists():
                raise ValidationError({'national_id': ['الرقم الوطني موجود بالفعل']})
            raise
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
            setattr(patient, field, None)
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
                Q(phone__icontains=search)
            )
        if filters:
            active = filters.get('active')
            if active == 'true':
                qs = qs.filter(is_active=True, deleted_at__isnull=True)
            elif active == 'false' and include_archived:
                qs = qs.filter(Q(is_active=False) | Q(deleted_at__isnull=False))
            completeness = filters.get('completeness')
            incomplete = (
                Q(dob_year__isnull=True)
                | Q(gender__isnull=True) | Q(gender='')
                | Q(national_id__isnull=True) | Q(national_id='')
                | Q(phone__isnull=True) | Q(phone='')
                | Q(doctor__isnull=True)
                | Q(admission_date__isnull=True)
            )
            if completeness == 'incomplete':
                qs = qs.filter(incomplete)
            elif completeness == 'complete':
                qs = qs.exclude(incomplete)
            qs = apply_ordering(qs, filters, {
                'name': 'normalised_full_name',
                'admission_date': 'admission_date',
                'created_at': 'created_at',
                'updated_at': 'updated_at',
            })
        return qs

    def find_duplicates(self, user, data, exclude_id=None):
        data = self._normalize(data)
        qs = self.list_patients(user, {})
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        strong = Q()
        national_id = data.get('national_id')
        phone = data.get('phone')
        if national_id:
            strong |= Q(national_id=national_id)
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
        patient.is_active = True
        patient.deleted_at = None
        patient.full_clean()
        patient.restore()
        return patient

    def get_care_team(self, patient):
        return patient.care_team.select_related('user').all()

    @staticmethod
    def _member_id(user_id):
        from core.mutation import parse_version
        try:
            return parse_version(user_id)
        except ValidationError:
            raise ValidationError({'user_id': ['معرف مستخدم صحيح مطلوب']})

    @transaction.atomic
    def add_care_team_member(self, patient, user_id, role, expected_version=None):
        patient = Patient.all_objects.select_for_update().get(pk=patient.pk)
        check_mutation(patient, expected_version)
        user_id = self._member_id(user_id)
        if not isinstance(role, str) or not role.strip() or len(role.strip()) > 50:
            raise ValidationError({'role': ['دور عضو فريق الرعاية مطلوب وبحد أقصى 50 حرف']})
        if PatientCareTeam.objects.filter(patient=patient, user_id=user_id).exists():
            raise ValidationError(['العضو موجود بالفعل'])
        user = User.objects.filter(id=user_id, is_active=True).first()
        if not user:
            raise ValidationError(['المستخدم غير موجود'])
        member = PatientCareTeam(patient=patient, user=user, role=role.strip())
        member.full_clean()
        member.save()
        patient.version += 1
        patient.save(update_fields=['version', 'updated_at'])
        return member, patient.version

    @transaction.atomic
    def remove_care_team_member(self, patient, user_id, expected_version=None):
        patient = Patient.all_objects.select_for_update().get(pk=patient.pk)
        check_mutation(patient, expected_version)
        user_id = self._member_id(user_id)
        deleted, _ = PatientCareTeam.objects.filter(patient=patient, user_id=user_id).delete()
        if deleted == 0:
            raise ValidationError(['العضو غير موجود'])
        patient.version += 1
        patient.save(update_fields=['version', 'updated_at'])
        return patient.version

class PatientDocumentService:
    @transaction.atomic
    def upload_document(self, patient, file, uploaded_by, category='other', description=''):
        patient = Patient.objects.select_for_update().get(pk=patient.pk)
        from core.upload_security import validate_upload
        validate_upload(file)
        if not isinstance(category, str) or len(category) > 50:
            raise ValidationError({'category': ['فئة غير صالحة']})
        path = save_uploaded_file(file, 'patient_docs', patient.id)
        try:
            doc = PatientDocument(patient=patient, filename=os.path.basename(path), original_filename=file.name,
                filepath=path, file_size=file.verified_size, mime_type=file.verified_mime,
                checksum=file.verified_checksum, category=category, description=description, uploaded_by=uploaded_by)
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
        for field in ('category', 'description'):
            if field in data:
                setattr(doc, field, data[field])
        doc.version += 1
        doc.full_clean()
        doc.save(update_fields=['category', 'description', 'version', 'updated_at'])
        return doc

    @transaction.atomic
    def soft_delete_document(self, doc, expected_version):
        doc = PatientDocument.all_objects.select_for_update().get(pk=doc.pk)
        check_mutation(doc, expected_version)
        doc.soft_delete()
        return True
