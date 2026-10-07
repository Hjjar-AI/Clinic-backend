# backend/apps/settings/services.py
from django.core.cache import cache
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import random
from faker import Faker

from .models import ClinicSetting
from apps.patients.models import Patient
from apps.visits.models import Visit, VisitDiagnosis, VisitMedication
from apps.clinical.models import DiagnosisOption, MedicationOption
from apps.accounts.models import User
from core.cache_utils import get_grouped_key, set_grouped_key, invalidate_group


# Sentinel used to distinguish "cache miss" from "cached value happens to equal default".
_CACHE_MISS = object()


class SettingsService:

    # ------------------------------------------------------------
    # Basic settings get/set
    # ------------------------------------------------------------
    def get_setting(self, key, default=''):
        # Read with a unique sentinel so a cache miss is distinguishable
        # from a cached value that legitimately equals `default`. Previously
        # the call site passed `default` as the cache fallback and then
        # tested `is not None`, which meant the DB branch below was dead
        # code — every read returned the fallback, and clinic settings
        # edited through PUT /settings/ were invisible on the next GET.
        value = get_grouped_key('settings', key, _CACHE_MISS)
        if value is not _CACHE_MISS:
            return value

        try:
            obj = ClinicSetting.objects.get(key=key)
            value = obj.value
        except ClinicSetting.DoesNotExist:
            value = default

        set_grouped_key('settings', key, value, timeout=300)
        return value

    def set_setting(self, key, value):
        ClinicSetting.objects.update_or_create(key=key, defaults={'value': value})
        # Invalidate settings group so next get reads fresh from DB.
        invalidate_group('settings')
        return True

    # ------------------------------------------------------------
    # Clinic info & theme
    # ------------------------------------------------------------
    def _get_bounded_integer(self, key, default, minimum, maximum):
        """Read legacy string settings without allowing malformed values to break APIs/jobs."""
        try:
            value = int(self.get_setting(key, str(default)))
        except (TypeError, ValueError):
            value = default
        return min(max(value, minimum), maximum)

    def get_clinic_info(self):
        return {
            'clinic_name': self.get_setting('clinic_name', settings.CLINIC_NAME),
            'clinic_address': self.get_setting('clinic_address', settings.CLINIC_ADDRESS),
            'clinic_phone': self.get_setting('clinic_phone', settings.CLINIC_PHONE),
            'theme': self.get_setting('theme', 'default'),
            'appointment_reminder_days': self._get_bounded_integer('appointment_reminder_days', 1, 0, 30),
            'appointment_reminder_hours': self._get_bounded_integer('appointment_reminder_hours', 1, 1, 12),
            'task_reminder_days': self._get_bounded_integer('task_reminder_days', 1, 0, 30),
        }

    def update_clinic_info(self, data):
        allowed = ['clinic_name', 'clinic_address', 'clinic_phone', 'theme']
        reminder_ranges = {
            'appointment_reminder_days': (0, 30),
            'appointment_reminder_hours': (1, 12),
            'task_reminder_days': (0, 30),
        }
        for key, value in data.items():
            if key in allowed:
                self.set_setting(key, value)
            elif key in reminder_ranges:
                try:
                    parsed = int(value)
                except (TypeError, ValueError):
                    raise ValueError(f'{key} must be an integer')
                minimum, maximum = reminder_ranges[key]
                if not minimum <= parsed <= maximum:
                    raise ValueError(f'{key} must be between {minimum} and {maximum}')
                self.set_setting(key, str(parsed))
        return self.get_clinic_info()

    # ------------------------------------------------------------
    # Demo data generation
    # ------------------------------------------------------------
    @transaction.atomic
    def generate_demo_data(self, num_patients=None, max_visits_per_patient=None):
        # Item #9: default to the DEMO_PATIENTS_COUNT / DEMO_VISITS_PER_PATIENT
        # settings (which read the same-named keys from .env). Previously the
        # .env values were declared but unused — the function signature hardcoded
        # 10 and 3, and bootstrap.py passed nothing.
        if num_patients is None:
            num_patients = getattr(settings, 'DEMO_PATIENTS_COUNT', 10)
        if max_visits_per_patient is None:
            max_visits_per_patient = getattr(settings, 'DEMO_VISITS_PER_PATIENT', 3)

        fake = Faker('ar_SA')
        doctor = User.objects.filter(role__in=['doctor', 'admin'], is_active=True).first()
        if not doctor:
            raise ValueError('لا يوجد طبيب متاح لإنشاء البيانات التجريبية')

        diagnoses = list(DiagnosisOption.objects.filter(is_active=True))
        medications = list(MedicationOption.objects.filter(is_active=True))
        if not diagnoses or not medications:
            raise ValueError('لا توجد تشخيصات أو أدوية مسجلة. قم بتشغيل seed أولاً.')

        used_national_ids = set(Patient.objects.values_list('national_id', flat=True))
        patients_created = 0
        for _ in range(num_patients):
            gender = random.choice(['ذكر', 'أنثى'])
            while True:
                national_id = str(random.randint(1000000000, 9999999999))
                if national_id not in used_national_ids:
                    used_national_ids.add(national_id)
                    break
            patient = Patient(
                first_name=fake.first_name(),
                father_name=fake.first_name_male(),
                surname=fake.last_name(),
                mother_name=fake.first_name_female(),
                dob_year=random.randint(1940, 2015),
                gender=gender,
                national_id=national_id,
                marital_status=random.choice(['أعزب', 'متزوج', 'مطلق', 'أرمل']) if gender == 'ذكر' else random.choice(['عزباء', 'متزوجة', 'مطلقة', 'أرملة']),
                occupation=random.choice(['طبيب', 'مهندس', 'معلم', 'طالب', 'موظف']),
                phone='09' + ''.join([str(random.randint(0, 9)) for _ in range(8)]),
                permanent_address='دمشق، ' + fake.city(),
                admission_date=timezone.now().date(),
                doctor=doctor,
                created_by=doctor,
            )
            patient.save()

            num_visits = random.randint(1, max_visits_per_patient)
            for _ in range(num_visits):
                visit_date = patient.admission_date - timedelta(days=random.randint(0, 30))
                visit = Visit(
                    patient=patient,
                    visit_date=visit_date,
                    main_complaints=random.choice(['قلق', 'اكتئاب', 'توتر', 'أرق', 'هلع']),
                    status='final',
                    clinical_status=random.choice(['تحسن', 'تحسن جزئي', 'غير مستقر']),
                    pain_level=random.randint(0, 10),
                    anxiety_level=random.randint(0, 10),
                    suicide_risk_level=random.choice(['Low', 'Moderate', 'High']),
                    violence_risk_level=random.choice(['Low', 'Moderate', 'High']),
                    level_of_care=random.choice(['Outpatient', 'IOP', 'PHP', 'Inpatient']),
                    follow_up_type=random.choice(['In-person', 'Telehealth', 'Phone']),
                    treatment_text='متابعة العلاج',
                    doctor_notes='تحسن ملحوظ',
                    author=doctor,
                )
                visit.save()

                for diag in random.sample(diagnoses, random.randint(1, min(3, len(diagnoses)))):
                    VisitDiagnosis.objects.create(
                        visit=visit,
                        diagnosis=diag,
                        custom_code=diag.code,
                        custom_name=diag.english_name,
                        custom_arabic=diag.arabic_name,
                        order=0,
                    )

                for med in random.sample(medications, random.randint(0, min(4, len(medications)))):
                    VisitMedication.objects.create(
                        visit=visit,
                        medication=med,
                        custom_name=med.generic_arabic or med.generic_english,
                        custom_dosage=med.dosage or '',
                        custom_brand=med.brand_arabic or med.brand_english,
                        is_custom=False,
                        schedule=random.choice(['صباحاً', 'مساءاً', 'صباحاً ومساءاً']),
                        order=0,
                    )

                visit.clinical_data = {
                    'lab_values': [
                        {'name': 'CBC', 'value': 'طبيعي', 'date': visit_date.isoformat()},
                        {'name': 'TSH', 'value': 'طبيعي', 'date': visit_date.isoformat()},
                    ]
                }
                visit.save()

            patients_created += 1

        return patients_created
