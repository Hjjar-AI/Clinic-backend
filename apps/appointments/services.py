from core.mutation import check_mutation
# backend/apps/appointments/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, datetime, timedelta, time
from django.conf import settings
from .models import Appointment
from apps.accounts.models import User
from apps.patients.models import Patient
from core.exceptions import ConflictError
from core.lifecycle import enforce_transition, transition_reason


class AppointmentService:
    OCCUPYING_STATUSES = {'scheduled', 'confirmed', 'arrived'}
    WORK_START = time(settings.WORK_START_HOUR, settings.WORK_START_MINUTE)
    WORK_END = time(settings.WORK_END_HOUR, settings.WORK_END_MINUTE)

    @staticmethod
    def _schedule_values(day, clock):
        try:
            if isinstance(day, str):
                day = date.fromisoformat(day)
            if isinstance(clock, str):
                clock = time.fromisoformat(clock)
        except ValueError:
            raise ValidationError({'schedule': ['صيغة التاريخ أو الوقت غير صحيحة']})
        if type(day) is not date or not isinstance(clock, time) or clock.tzinfo is not None:
            raise ValidationError({'schedule': ['تاريخ ووقت محلي صحيحان مطلوبان']})
        return day, clock

    def _lock_doctor_schedule(self, doctor_id):
        """
        Serialize concurrent booking operations for the same doctor.

        Called immediately before every availability check + insert/update
        sequence. Takes a row-level lock on the doctor's User row so that two
        simultaneous requests for the same slot cannot both read "free" and
        both commit (the classic check-then-insert race).

        On Postgres/MySQL this issues SELECT ... FOR UPDATE on the doctor row
        and blocks the second transaction until the first commits. The second
        transaction then re-runs its availability check against a stable
        snapshot that includes the first booking, and correctly rejects.

        On SQLite, select_for_update() is a documented no-op (Django silently
        drops the FOR UPDATE clause). SQLite's single-writer model combined
        with ATOMIC_REQUESTS already serializes the common case; this call is
        harmless there and keeps behaviour uniform across backends.

        We lock the doctor row rather than an Appointment row because the
        conflicting row does not exist yet — there is nothing for
        select_for_update() on Appointment to lock. The doctor row acts as a
        per-doctor scheduling sentinel.
        """
        # .values_list(...).first() emits a plain SELECT with FOR UPDATE
        # attached and avoids instantiating a full User object. Placed inside
        # @transaction.atomic on all callers, so Django will not raise
        # TransactionManagementError.
        User.objects.select_for_update().filter(pk=doctor_id).values_list('id', flat=True).first()

    def _get_occupied_intervals(self, doctor_id, date_obj, exclude_id=None):
        appointments = Appointment.objects.filter(
            doctor_id=doctor_id,
            appointment_date__range=(date_obj - timedelta(days=1), date_obj),
            status__in=['scheduled', 'confirmed', 'arrived'],
        )

        if exclude_id is not None:
            appointments = appointments.exclude(id=exclude_id)

        occupied = []
        for apt in appointments:
            start = datetime.combine(apt.appointment_date, apt.appointment_time)
            duration = apt.duration_minutes or 30
            end = start + timedelta(minutes=duration)
            occupied.append((start, end))
        return occupied

    def is_time_available(self, doctor_id, date_obj, time_obj, duration, exclude_id=None):
        self._validate_duration(duration)
        new_start_dt = datetime.combine(date_obj, time_obj)
        new_end_dt = new_start_dt + timedelta(minutes=duration)
        work_start_dt = datetime.combine(date_obj, self.WORK_START)
        work_end_dt = datetime.combine(date_obj, self.WORK_END)
        if new_start_dt < work_start_dt or new_end_dt > work_end_dt:
            return False

        occupied = self._get_occupied_intervals(doctor_id, date_obj, exclude_id)
        for occ_start, occ_end in occupied:
            occ_start_dt, occ_end_dt = occ_start, occ_end
            if not (new_end_dt <= occ_start_dt or new_start_dt >= occ_end_dt):
                return False
        return True

    @staticmethod
    def _validate_duration(duration):
        if not isinstance(duration, int) or isinstance(duration, bool) or not 1 <= duration <= 1440:
            raise ValidationError({'duration_minutes': ['المدة يجب أن تكون بين 1 و1440 دقيقة']})

    def generate_time_slots(self, doctor_id, date_obj, duration=30):
        self._validate_duration(duration)
        occupied = self._get_occupied_intervals(doctor_id, date_obj)
        slots = []
        current_dt = datetime.combine(date_obj, self.WORK_START)
        end_dt = datetime.combine(date_obj, self.WORK_END)
        while current_dt + timedelta(minutes=duration) <= end_dt:
            time_obj = current_dt.time()
            available = True
            for occ_start, occ_end in occupied:
                occ_start_dt, occ_end_dt = occ_start, occ_end
                if not (current_dt + timedelta(minutes=duration) <= occ_start_dt or current_dt >= occ_end_dt):
                    available = False
                    break
            slots.append({'time': time_obj.strftime('%H:%M'), 'available': available})
            current_dt += timedelta(minutes=duration)
        return slots

    @transaction.atomic
    def create_appointment(self, data):
        patient = data.get('patient')
        doctor = data.get('doctor')
        if not patient or not doctor:
            raise ValidationError(['المريض والطبيب مطلوبان'])

        if isinstance(patient, int):
            patient = Patient.objects.filter(id=patient, deleted_at__isnull=True).first()
        elif isinstance(patient, Patient) and (patient.deleted_at is not None or not patient.is_active):
            patient = None

        if isinstance(doctor, int):
            doctor = User.objects.filter(id=doctor, is_active=True).first()

        if patient:
            patient = Patient.all_objects.select_for_update().get(pk=patient.pk)
        if not patient or not patient.is_active or patient.deleted_at:
            raise ValidationError(['المريض غير موجود أو مؤرشف'])
        if not doctor or not doctor.is_active or doctor.role not in ['doctor', 'admin']:
            raise ValidationError(['الطبيب غير صالح'])

        date_str = data.get('appointment_date')
        time_obj = data.get('appointment_time')
        # F5: the serializer declares `duration_minutes` (the frontend now sends
        # the same key). Read from the canonical name; fall back to `duration`
        # only for legacy callers that still pass the old key.
        duration = data.get('duration_minutes', data.get('duration', 30))

        date_obj, time_obj = self._schedule_values(date_str, time_obj)

        # Acquire the per-doctor booking lock BEFORE the availability check.
        # Without this, two concurrent requests for the same slot can both
        # pass is_time_available() and both commit.
        self._lock_doctor_schedule(doctor.id)

        if not self.is_time_available(doctor.id, date_obj, time_obj, duration):
            raise ValidationError(['هذا الوقت محجوز بالفعل'])

        requested_status = data.get('status', 'scheduled')
        if requested_status != 'scheduled':
            raise ValidationError({'status': ['يجب إنشاء الموعد بحالة مجدول']})

        appointment = Appointment(
            patient=patient,
            doctor=doctor,
            appointment_date=date_obj,
            appointment_time=time_obj,
            duration_minutes=duration,
            status='scheduled',
            notes=data.get('notes', ''),
        )
        appointment.full_clean()
        appointment.save()
        return appointment

    @transaction.atomic
    def update_appointment(self, appointment, data, expected_version=None):
        appointment = Appointment.all_objects.select_for_update().get(pk=appointment.pk)
        check_mutation(appointment, expected_version)
        if expected_version is None:
            raise ValidationError(['يجب توفير رقم الإصدار'])
        if appointment.version != expected_version:
            raise ConflictError('تم تعديل هذا الموعد بواسطة مستخدم آخر')

        # F4: The frontend echoes patient_id/doctor_id on every edit; the
        # serializer maps them to `patient`/`doctor`. Reject only if the VALUE
        # actually differs, not merely because the key is present.
        new_patient = data.get('patient')
        if new_patient is not None and new_patient != appointment.patient:
            raise ValidationError(['لا يمكن تغيير المريض المرتبط بالموعد'])
        new_doctor = data.get('doctor')
        if new_doctor is not None and new_doctor != appointment.doctor:
            raise ValidationError(['لا يمكن تغيير الطبيب المرتبط بالموعد'])

        data = data.copy()
        # Strip these from data so the assignment loop below can't touch them.
        data.pop('patient', None)
        data.pop('doctor', None)
        data.pop('patient_id', None)
        data.pop('doctor_id', None)

        new_date = data.get('appointment_date', appointment.appointment_date)
        new_time = data.get('appointment_time', appointment.appointment_time)
        new_date, new_time = self._schedule_values(new_date, new_time)
        data['appointment_date'], data['appointment_time'] = new_date, new_time
        # F5: canonical key.
        new_duration = data.get('duration_minutes', data.get('duration', appointment.duration_minutes))

        target_status = data.get('status', appointment.status)
        schedule_changed = (
            new_date != appointment.appointment_date
            or new_time != appointment.appointment_time
            or new_duration != appointment.duration_minutes
        )
        if schedule_changed and appointment.status == 'completed':
            raise ValidationError({'status': ['لا يمكن نقل موعد مكتمل']})
        if target_status != appointment.status:
            enforce_transition('appointment', appointment.status, target_status)
            data['status_reason'] = transition_reason(
                data.get('status_reason'), required=target_status in {'cancelled', 'no-show'})

        self._validate_duration(new_duration)
        data['duration_minutes'] = new_duration
        if schedule_changed:
            appointment.reminder_sent = False
            appointment.reminder_sent_hour = False
        # Check availability if date/time/duration changed. Lock the doctor's
        # schedule row before re-checking so this read is serialized against
        # concurrent bookings for the same slot.
        reactivating = (
            target_status in self.OCCUPYING_STATUSES
            and appointment.status not in self.OCCUPYING_STATUSES
        )
        if target_status in self.OCCUPYING_STATUSES and (schedule_changed or reactivating):
            self._lock_doctor_schedule(appointment.doctor_id)
            if not self.is_time_available(appointment.doctor_id, new_date, new_time, new_duration, exclude_id=appointment.id):
                raise ValidationError(['هذا الوقت محجوز بالفعل'])
            appointment.reminder_sent = False
            appointment.reminder_sent_hour = False

        if 'status_reason' in data:
            data['status_reason'] = transition_reason(
                data['status_reason'], required=target_status in {'cancelled', 'no-show'})
        # Reminder delivery state belongs to the scheduler, not API input.
        for k, v in data.items():
            if k in {'appointment_date', 'appointment_time', 'duration_minutes',
                     'status', 'status_reason', 'notes'}:
                setattr(appointment, k, v)
        appointment.version += 1
        appointment.full_clean()
        appointment.save()
        return appointment

    @transaction.atomic
    def reschedule(self, appointment, new_date_str, new_time, expected_version=None):
        appointment = Appointment.all_objects.select_for_update().get(pk=appointment.pk)
        check_mutation(appointment, expected_version)
        if expected_version is None:
            raise ValidationError(['يجب توفير رقم الإصدار'])
        if appointment.version != expected_version:
            raise ConflictError('تم تعديل هذا الموعد بواسطة مستخدم آخر')
        if appointment.status == 'completed':
            raise ValidationError({'status': ['لا يمكن نقل موعد مكتمل']})
        # Item #5: guard strptime so a malformed date string returns a clean
        # ValidationError instead of an unhandled 500.
        try:
            new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            raise ValidationError(['صيغة التاريخ غير صحيحة'])

        if isinstance(new_time, str):
            try:
                new_time = time.fromisoformat(new_time)
            except ValueError:
                raise ValidationError({'appointment_time': ['صيغة الوقت غير صحيحة']})
        if not isinstance(new_time, time) or new_time.tzinfo is not None:
            raise ValidationError({'appointment_time': ['صيغة الوقت غير صحيحة']})

        # Acquire the per-doctor booking lock before the availability check.
        self._lock_doctor_schedule(appointment.doctor_id)

        if not self.is_time_available(appointment.doctor_id, new_date, new_time, appointment.duration_minutes, exclude_id=appointment.id):
            raise ValidationError(['الوقت غير متاح'])
        appointment.appointment_date = new_date
        appointment.appointment_time = new_time
        if appointment.status in {'cancelled', 'no-show'}:
            enforce_transition('appointment', appointment.status, 'scheduled')
            appointment.status = 'scheduled'
            appointment.status_reason = ''
        appointment.reminder_sent = False
        appointment.reminder_sent_hour = False
        appointment.version += 1
        appointment.full_clean()
        appointment.save()
        return appointment

    @transaction.atomic
    def transition(self, appointment, target_status, expected_version=None, reason=''):
        appointment = Appointment.all_objects.select_for_update().get(pk=appointment.pk)
        check_mutation(appointment, expected_version)
        if expected_version is None:
            raise ValidationError({'version': ['يجب توفير رقم الإصدار']})
        if appointment.version != expected_version:
            raise ConflictError('تم تعديل هذا الموعد بواسطة مستخدم آخر')
        changed = enforce_transition('appointment', appointment.status, target_status)
        if not changed:
            return appointment
        reason = transition_reason(reason, required=target_status in {'cancelled', 'no-show'})
        if target_status in self.OCCUPYING_STATUSES and appointment.status not in self.OCCUPYING_STATUSES:
            self._lock_doctor_schedule(appointment.doctor_id)
            if not self.is_time_available(
                appointment.doctor_id, appointment.appointment_date,
                appointment.appointment_time, appointment.duration_minutes,
                exclude_id=appointment.id,
            ):
                raise ValidationError(['هذا الوقت محجوز بالفعل'])
        appointment.status = target_status
        appointment.status_reason = reason
        if target_status == 'scheduled':
            appointment.reminder_sent = False
            appointment.reminder_sent_hour = False
        else:
            appointment.reminder_sent = target_status not in {'confirmed'}
            appointment.reminder_sent_hour = target_status not in {'confirmed'}
        appointment.version += 1
        appointment.full_clean()
        appointment.save(update_fields=[
            'status', 'status_reason', 'reminder_sent', 'reminder_sent_hour', 'version', 'updated_at',
        ])
        return appointment

    def cancel(self, appointment, expected_version=None, reason=''):
        return self.transition(appointment, 'cancelled', expected_version, reason)

    def complete(self, appointment, expected_version=None):
        return self.transition(appointment, 'completed', expected_version)

    @transaction.atomic
    def archive(self, appointment, expected_version=None):
        appointment = Appointment.all_objects.select_for_update().get(pk=appointment.pk)
        check_mutation(appointment, expected_version)
        if appointment.status != 'cancelled':
            raise ValidationError({
                'status': ['لا يمكن أرشفة الموعد قبل إلغائه مع تسجيل السبب'],
            })
        appointment.soft_delete()
        return appointment

    def get_accessible_appointments(self, user):
        from core.access import accessible_appointments
        return accessible_appointments(user).select_related('patient', 'doctor')

    def get_calendar(self, user, view, date_obj, doctor_id=None):
        qs = self.get_accessible_appointments(user).exclude(status='cancelled')
        if doctor_id is not None:
            try:
                qs = qs.filter(doctor_id=int(doctor_id))
            except (TypeError, ValueError):
                raise ValidationError({'doctor_id': ['طبيب غير صالح']})

        if view == 'day':
            start = date_obj
            end = date_obj + timedelta(days=1)
        elif view == 'week':
            start = date_obj - timedelta(days=date_obj.weekday())
            end = start + timedelta(days=7)
        elif view == 'month':
            start = date_obj.replace(day=1)
            if date_obj.month == 12:
                end = date_obj.replace(year=date_obj.year + 1, month=1, day=1)
            else:
                end = date_obj.replace(month=date_obj.month + 1, day=1)
        else:
            start = date_obj
            end = date_obj + timedelta(days=1)

        return qs.select_related('patient', 'doctor').filter(
            appointment_date__gte=start,
            appointment_date__lt=end,
        ).order_by('appointment_date', 'appointment_time')
