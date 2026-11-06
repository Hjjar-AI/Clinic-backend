"""Explicitly invoked demo construction; importing ordinary settings never seeds data."""
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import random
from apps.patients.models import Patient
from apps.visits.models import Visit, VisitDiagnosis, VisitMedication
from apps.clinical.models import DiagnosisOption, MedicationOption
from apps.accounts.models import User


@transaction.atomic
def generate_demo_data(num_patients=None, max_visits_per_patient=None):
    # Item #9: default to the DEMO_PATIENTS_COUNT / DEMO_VISITS_PER_PATIENT
    # settings (which read the same-named keys from .env). Previously the
    # .env values were declared but unused — the function signature hardcoded
    # 10 and 3, and bootstrap.py passed nothing.
    if num_patients is None:
        num_patients = getattr(settings, 'DEMO_PATIENTS_COUNT', 10)
    if max_visits_per_patient is None:
        max_visits_per_patient = getattr(settings, 'DEMO_VISITS_PER_PATIENT', 3)

    if type(num_patients) is not int or not 1 <= num_patients <= 1000 or type(max_visits_per_patient) is not int or not 1 <= max_visits_per_patient <= 20:
        raise ValueError('عدد المرضى بين 1 و1000 والزيارات بين 1 و20')
    from faker import Faker
    fake = Faker('ar_SA')
    doctor = User.objects.filter(role__in=['doctor', 'admin'], is_active=True).first()
    if not doctor:
        raise ValueError('لا يوجد طبيب متاح لإنشاء البيانات التجريبية')

    diagnoses = list(DiagnosisOption.objects.filter(is_active=True))
    medications = list(MedicationOption.objects.filter(is_active=True))
    if not diagnoses or not medications:
        raise ValueError('لا توجد تشخيصات أو أدوية مسجلة. قم بتشغيل seed أولاً.')

    used_national_ids = set(Patient.objects.values_list('primary_identifier__value', flat=True))
    patients_created = 0
    for _ in range(num_patients):
        gender = random.choice(['ذكر', 'أنثى'])
        while True:
            national_id = str(random.randint(1000000000, 9999999999))
            if national_id not in used_national_ids:
                used_national_ids.add(national_id)
                break
        from apps.patients.services import PatientService
        patient = PatientService().create_patient(dict(
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
            registration_date=timezone.localdate(),
            care_team_ids=[doctor.pk],
        ), doctor)

        num_visits = random.randint(1, max_visits_per_patient)
        for _ in range(num_visits):
            visit_date = patient.registration_date - timedelta(days=random.randint(0, 30))
            visit = Visit(
                patient=patient,
                visit_date=visit_date,
                main_complaints=random.choice(['قلق', 'اكتئاب', 'توتر', 'أرق', 'هلع']),
                status='draft',
                clinical_status=random.choice(['تحسن', 'تحسن جزئي', 'غير مستقر']),
                pain_level=random.randint(0, 10),
                anxiety_level=random.randint(0, 10),
                suicide_risk_level=random.choice(['Low', 'Moderate', 'High']),
                violence_risk_level=random.choice(['Low', 'Moderate', 'High']),
                level_of_care=random.choice(['Outpatient', 'IOP', 'PHP', 'Inpatient']),
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
                    custom_dosage=med.dosage or 'حسب توجيهات الطبيب',
                    custom_brand=med.brand_arabic or med.brand_english,
                    is_custom=False,
                    controlled_snapshot=med.is_controlled,
                    schedule=random.choice(['صباحاً', 'مساءاً', 'صباحاً ومساءاً']),
                    order=0,
                )

            visit.lab_values = [
                {'name': 'CBC', 'value': 'طبيعي', 'date': visit_date.isoformat(), 'status': 'normal'},
                {'name': 'TSH', 'value': 'طبيعي', 'date': visit_date.isoformat(), 'status': 'normal'},
            ]
            visit.save()
            from apps.visits.services import VisitService
            VisitService().transition(visit, 'final', doctor, visit.version)

        patients_created += 1

    return patients_created
