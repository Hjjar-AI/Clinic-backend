from core.reminders import renew_reminder
from core.mutation import check_mutation
from core.access import require_actor_permission, accessible_appointments, accessible_patients
from core.exceptions import ConflictError
# backend/apps/appointments/services.py
from django.db import transaction
from django.core.exceptions import ValidationError
from datetime import date, datetime, timedelta, time
from django.conf import settings
from .models import Appointment
from apps.accounts.models import User
from apps.patients.models import Patient
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
        doctor = User.objects.select_for_update().filter(pk=doctor_id).first()
        if not doctor or not doctor.is_active or doctor.role not in {'doctor', 'admin'}:
            raise ValidationError({'doctor': ['الطبيب غير متاح للحجز']})
        return doctor

    def _get_occupied_intervals(self, doctor_id, date_obj, exclude_id=None):
        appointments = Appointment.objects.filter(
            doctor_id=doctor_id,
            appointment_date__range=(date_obj - timedelta(days=1), date_obj),
            status__in=self.OCCUPYING_STATUSES,
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

    def generate_time_slots(self, doctor_id, date_obj, duration=None):
        duration = settings.DEFAULT_APPOINTMENT_DURATION if duration is None else duration
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

    @staticmethod
    def _lock_mutation(appointment, expected_version, actor):
        patient_id = Appointment.all_objects.values_list('patient_id', flat=True).get(pk=appointment.pk)
        patient = Patient.all_objects.select_for_update().get(pk=patient_id)
        if not patient.is_active or patient.deleted_at is not None:
            raise ConflictError('ملف المريض مؤرشف؛ أعد تحميل الموعد')
        appointment = Appointment.all_objects.select_for_update().get(pk=appointment.pk)
        actor = require_actor_permission(actor, 'manage_appointments')
        if appointment.patient_id != patient_id:
            raise ConflictError('تغير ملف المريض؛ أعد تحميل الموعد')
        if not accessible_appointments(actor).filter(pk=appointment.pk).exists():
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied('غير مصرح بالوصول إلى الموعد')
        check_mutation(appointment, expected_version)
        return appointment

    def _require_available(self, doctor_id, day, clock, duration, exclude_id=None):
        self._lock_doctor_schedule(doctor_id)
        if not self.is_time_available(doctor_id, day, clock, duration, exclude_id):
            raise ValidationError(['هذا الوقت محجوز بالفعل'])

    @staticmethod
    def _apply_status(appointment, target_status, reason='', *, renew_scheduled=True):
        if not enforce_transition('appointment', appointment.status, target_status):
            return False
        appointment.status_reason = transition_reason(reason, required=target_status in {'cancelled', 'no-show'})
        appointment.status = target_status
        if target_status == 'scheduled':
            if renew_scheduled:
                renew_reminder(appointment, 'reminder_sent', 'reminder_sent_hour')
        else:
            appointment.reminder_sent = target_status != 'confirmed'
            appointment.reminder_sent_hour = target_status != 'confirmed'
        return True

    @transaction.atomic
    def create_appointment(self, data, *, actor):
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
        actor = require_actor_permission(actor, 'manage_appointments')
        if (not accessible_patients(actor).filter(pk=patient.pk).exists()
                or (actor.role == 'doctor' and getattr(doctor, 'pk', None) != actor.pk)):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied('غير مصرح بهذا الحجز')
        if not doctor or not doctor.is_active or doctor.role not in ['doctor', 'admin']:
            raise ValidationError(['الطبيب غير صالح'])

        date_str = data.get('appointment_date')
        time_obj = data.get('appointment_time')
        # F5: the serializer declares `duration_minutes` (the frontend now sends
        # the same key). Read from the canonical name; fall back to `duration`
        # only for legacy callers that still pass the old key.
        duration = data.get('duration_minutes', data.get('duration', settings.DEFAULT_APPOINTMENT_DURATION))

        date_obj, time_obj = self._schedule_values(date_str, time_obj)

        self._require_available(doctor.id, date_obj, time_obj, duration)

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
    def update_appointment(self, appointment, data, expected_version=None, *, actor):
        appointment = self._lock_mutation(appointment, expected_version, actor)
        # Clients echo these relations; only an actual reassignment is rejected.
        for field in ('patient', 'doctor'):
            if data.get(field) is not None and data[field] != getattr(appointment, field):
                raise ValidationError({field: ['لا يمكن تغيير الارتباط المسجل للموعد']})
        data = data.copy()
        day, clock = self._schedule_values(data.get('appointment_date', appointment.appointment_date),
                                          data.get('appointment_time', appointment.appointment_time))
        duration = data.get('duration_minutes', data.get('duration', appointment.duration_minutes))
        self._validate_duration(duration)
        schedule_changed = (day, clock, duration) != (appointment.appointment_date, appointment.appointment_time, appointment.duration_minutes)
        previous_status = appointment.status
        if schedule_changed and previous_status == 'completed':
            raise ValidationError({'status': ['لا يمكن نقل موعد مكتمل']})
        target_status = data.get('status', previous_status)
        self._apply_status(appointment, target_status, data.get('status_reason'), renew_scheduled=False)
        reactivating = target_status in self.OCCUPYING_STATUSES and previous_status not in self.OCCUPYING_STATUSES
        if target_status in self.OCCUPYING_STATUSES and (schedule_changed or reactivating):
            self._require_available(appointment.doctor_id, day, clock, duration, appointment.pk)
        if schedule_changed or reactivating:
            renew_reminder(appointment, 'reminder_sent', 'reminder_sent_hour')
        if 'status_reason' in data:
            appointment.status_reason = transition_reason(data['status_reason'], required=target_status in {'cancelled', 'no-show'})
        appointment.appointment_date, appointment.appointment_time, appointment.duration_minutes = day, clock, duration
        if 'notes' in data:
            appointment.notes = data['notes']
        appointment.version += 1
        appointment.full_clean()
        appointment.save()
        return appointment

    @transaction.atomic
    def reschedule(self, appointment, new_date_str, new_time, expected_version=None, *, actor):
        appointment = self._lock_mutation(appointment, expected_version, actor)
        if appointment.status == 'completed':
            raise ValidationError({'status': ['لا يمكن نقل موعد مكتمل']})
        day, clock = self._schedule_values(new_date_str, new_time)
        self._require_available(appointment.doctor_id, day, clock, appointment.duration_minutes, appointment.pk)
        appointment.appointment_date, appointment.appointment_time = day, clock
        if appointment.status in {'cancelled', 'no-show'}:
            self._apply_status(appointment, 'scheduled', renew_scheduled=False)
        renew_reminder(appointment, 'reminder_sent', 'reminder_sent_hour')
        appointment.version += 1
        appointment.full_clean()
        appointment.save()
        return appointment

    @transaction.atomic
    def transition(self, appointment, target_status, expected_version=None, reason='', *, actor):
        appointment = self._lock_mutation(appointment, expected_version, actor)
        previous_status = appointment.status
        if not self._apply_status(appointment, target_status, reason):
            return appointment
        if target_status in self.OCCUPYING_STATUSES and previous_status not in self.OCCUPYING_STATUSES:
            self._require_available(appointment.doctor_id, appointment.appointment_date,
                                    appointment.appointment_time, appointment.duration_minutes, appointment.pk)
        appointment.version += 1
        appointment.full_clean()
        appointment.save(update_fields=[
            'status', 'status_reason', 'reminder_generation', 'reminder_sent', 'reminder_sent_hour', 'version', 'updated_at',
        ])
        return appointment

    def cancel(self, appointment, expected_version=None, reason='', *, actor):
        return self.transition(appointment, 'cancelled', expected_version, reason, actor=actor)

    def complete(self, appointment, expected_version=None, *, actor):
        return self.transition(appointment, 'completed', expected_version, actor=actor)

    @transaction.atomic
    def archive(self, appointment, expected_version=None, *, actor):
        appointment = self._lock_mutation(appointment, expected_version, actor)
        if appointment.status != 'cancelled':
            raise ValidationError({
                'status': ['لا يمكن أرشفة الموعد قبل إلغائه مع تسجيل السبب'],
            })
        appointment.soft_delete(actor)
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
