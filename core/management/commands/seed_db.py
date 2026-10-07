# backend/core/management/commands/seed_db.py
import os
import secrets

from django.contrib.auth.models import Group, Permission, ContentType
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User as CustomUser
from apps.settings.models import ClinicSetting
from apps.clinical.models import DiagnosisOption, MedicationOption
from apps.tasks.models import UserTask
from core.permissions import ALL_PERMISSIONS, DEFAULT_PERMISSIONS


def _seed_password(env_key):
    """
    Return (password, generated?). If the env var is set, use it;
    otherwise generate a random one. Random passwords are printed
    once and the user is told to rotate on first login.
    """
    env_value = os.environ.get(env_key)
    if env_value:
        return env_value, False
    return secrets.token_urlsafe(10), True


class Command(BaseCommand):
    help = 'Seed database with default users, settings, diagnoses, medications, and tasks.'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding database...')

        # ----- 1. Create permissions (if not already exist) -----
        # We use a generic content type (auth.permission) so that codenames
        # are unique across the whole project. The User.has_perm() override
        # allows matching by codename alone, regardless of content type.
        content_type, _ = ContentType.objects.get_or_create(
            app_label='auth', model='permission'
        )
        for codename, name in ALL_PERMISSIONS.items():
            Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={'name': name}
            )
        self.stdout.write(f'Created {len(ALL_PERMISSIONS)} permissions.')

        # ----- 2. Create groups and assign permissions -----
        for role, perms in DEFAULT_PERMISSIONS.items():
            group, created = Group.objects.get_or_create(name=role)
            perm_list = Permission.objects.filter(codename__in=perms)
            group.permissions.set(perm_list)
            if created:
                self.stdout.write(f'Created group "{role}" with {perm_list.count()} permissions.')
            else:
                self.stdout.write(f'Updated group "{role}" with {perm_list.count()} permissions.')

        # ----- 3. Create default users -----
        # Passwords: if the corresponding env var is set, use it;
        # otherwise generate a random one and print it once. The old
        # hardcoded values (admin123 / doctor123 / receptionist123) are
        # public knowledge in the repo and unsafe to ship. All seeded
        # users get force_password_change=True so they rotate on first
        # login regardless.
        admin, created = CustomUser.objects.get_or_create(
            username='admin',
            defaults={
                'full_name': 'Administrator',
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            pw, generated = _seed_password('ADMIN_PASSWORD')
            admin.set_password(pw)
            admin.force_password_change = True
            admin.save()
            suffix = '  (randomly generated — change immediately)' if generated else ''
            self.stdout.write(self.style.WARNING(
                f'Created admin user: admin / {pw}{suffix}'
            ))
        admin.groups.add(Group.objects.get(name='admin'))

        doctor, created = CustomUser.objects.get_or_create(
            username='doctor1',
            defaults={
                'full_name': 'Doctor One',
                'role': 'doctor',
            }
        )
        if created:
            pw, generated = _seed_password('DOCTOR_PASSWORD')
            doctor.set_password(pw)
            doctor.force_password_change = True
            doctor.save()
            suffix = '  (randomly generated — change immediately)' if generated else ''
            self.stdout.write(self.style.WARNING(
                f'Created doctor user: doctor1 / {pw}{suffix}'
            ))
        doctor.groups.add(Group.objects.get(name='doctor'))

        receptionist, created = CustomUser.objects.get_or_create(
            username='receptionist1',
            defaults={
                'full_name': 'Receptionist One',
                'role': 'receptionist',
            }
        )
        if created:
            pw, generated = _seed_password('RECEPTIONIST_PASSWORD')
            receptionist.set_password(pw)
            receptionist.force_password_change = True
            receptionist.save()
            suffix = '  (randomly generated — change immediately)' if generated else ''
            self.stdout.write(self.style.WARNING(
                f'Created receptionist user: receptionist1 / {pw}{suffix}'
            ))
        receptionist.groups.add(Group.objects.get(name='receptionist'))

        # ----- 4. Default clinic settings -----
        default_settings = {
            'clinic_name': 'عيادة الإتزان',
            'clinic_address': 'دمشق، سوريا',
            'clinic_phone': '+963 11 1234567',
            'theme': 'default',
        }
        for key, value in default_settings.items():
            ClinicSetting.objects.update_or_create(key=key, defaults={'value': value})
        self.stdout.write('Seeded default settings')

        # ----- 5. Diagnoses -----
        diagnoses = [
            ('F32.0', 'Mild Depressive Episode', 'نوبة اكتئابية خفيفة'),
            ('F41.0', 'Panic Disorder', 'اضطراب الهلع'),
            ('F41.1', 'Generalized Anxiety Disorder', 'اضطراب القلق العام'),
            ('F42.0', 'Obsessive-Compulsive Disorder', 'اضطراب الوسواس القهري'),
            ('F43.1', 'Post-Traumatic Stress Disorder', 'اضطراب الكرب التالي للصدمة'),
            ('F31.0', 'Bipolar I Disorder', 'اضطراب ثنائي القطب النوع الأول'),
            ('F20.0', 'Paranoid Schizophrenia', 'فصام بارانويدي'),
        ]
        for code, en, ar in diagnoses:
            DiagnosisOption.objects.get_or_create(
                code=code,
                defaults={'english_name': en, 'arabic_name': ar, 'order': 0}
            )
        self.stdout.write(f'Seeded {len(diagnoses)} diagnoses')

        # ----- 6. Medications -----
        medications = [
            ('Fluoxetine', 'فلوكسيتين', '20mg', 'Prozac', 'بروزاك'),
            ('Sertraline', 'سيرترالين', '50mg', 'Zoloft', 'زولوفت'),
            ('Olanzapine', 'أولانزابين', '5mg', 'Zyprexa', 'زيبريكسا'),
            ('Risperidone', 'ريسبيريدون', '2mg', 'Risperdal', 'ريسبيردال'),
            ('Lorazepam', 'لورازيبام', '1mg', 'Ativan', 'أتيفان'),
            ('Diazepam', 'ديازيبام', '5mg', 'Valium', 'فاليوم'),
        ]
        for gen_en, gen_ar, dose, brand_en, brand_ar in medications:
            MedicationOption.objects.get_or_create(
                generic_english=gen_en,
                dosage=dose,
                defaults={
                    'generic_arabic': gen_ar,
                    'brand_english': brand_en,
                    'brand_arabic': brand_ar,
                    'order': 0,
                }
            )
        self.stdout.write(f'Seeded {len(medications)} medications')

        # ----- 7. Tasks for admin -----
        tasks = [
            ('مراجعة إحصائيات العيادة الشهرية', 'إعداد تقرير شهري شامل', 'high'),
            ('تحديث قائمة الأدوية', 'إضافة الأدوية الجديدة إلى النظام', 'medium'),
            ('مراجعة سياسة الخصوصية', 'تحديث وثائق الخصوصية', 'low'),
        ]
        for title, desc, priority in tasks:
            UserTask.objects.get_or_create(
                title=title,
                defaults={
                    'user': admin,
                    'assigned_to': None,
                    'description': desc,
                    'priority': priority,
                    'due_date': timezone.now().date() + timezone.timedelta(days=7),
                }
            )
        self.stdout.write(f'Seeded {len(tasks)} tasks')

        self.stdout.write(self.style.SUCCESS('Database seeding completed.'))