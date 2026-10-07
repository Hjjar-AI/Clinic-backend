import pandas as pd
from datetime import datetime
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.patients.models import Patient
from apps.clinical.models import DiagnosisOption, MedicationOption
from apps.accounts.models import User
from core.normalization import normalize_digits, normalize_identifier, normalize_name, normalize_phone

class BulkImportService:
    def _read_file(self, file_stream):
        try:
            return pd.read_excel(file_stream, dtype=str, keep_default_na=False)
        except Exception:
            file_stream.seek(0)
            return pd.read_csv(file_stream, dtype=str, keep_default_na=False)

    def _patient_kwargs(self, row, doctor_id, created_by_id):
        national_id = normalize_identifier(row.get('الرقم الوطني', ''))
        raw_date = (normalize_digits(row.get('تاريخ الإضافة', '')) or '').strip()
        admission_date = None
        if raw_date:
            for date_format in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y', '%d-%m-%Y'):
                try:
                    admission_date = datetime.strptime(raw_date, date_format).date()
                    break
                except ValueError:
                    continue
            if admission_date is None:
                raise ValueError('تاريخ الإضافة غير صالح')
        raw_dob_year = (normalize_digits(row.get('سنة الميلاد', '')) or '').strip()
        dob_year = int(raw_dob_year) if raw_dob_year else None
        if dob_year is not None and not (1900 <= dob_year <= datetime.now().year):
            raise ValueError('سنة الميلاد غير صالحة')
        return {
            'first_name': normalize_name(row.get('الاسم الأول', ''))[:100],
            'father_name': normalize_name(row.get('اسم الأب', ''))[:100] or None,
            'surname': normalize_name(row.get('اللقب', ''))[:100] or None,
            'mother_name': normalize_name(row.get('اسم الأم', ''))[:100] or None,
            'dob_year': dob_year,
            'gender': row.get('الجنس', ''),
            'national_id': national_id,
            'marital_status': row.get('الحالة الاجتماعية', '')[:50],
            'occupation': row.get('المهنة', '')[:100],
            'phone': normalize_phone(row.get('الهاتف', '')),
            'permanent_address': row.get('العنوان', '')[:500],
            'emergency_contact_name': row.get('جهة اتصال للطوارئ (الاسم)', '')[:100],
            'emergency_contact_relation': row.get('صلة القرابة', '')[:50],
            'emergency_contact_phone': normalize_phone(row.get('هاتف جهة الاتصال', '')),
            'family_history': row.get('التاريخ العائلي', '')[:500],
            'important_notes': row.get('ملاحظات هامة', '')[:500],
            'admission_date': admission_date,
            'doctor_id': doctor_id,
            'created_by_id': created_by_id,
        }

    def preview_patients(self, file_stream, doctor_id, created_by_id):
        results = {'added': 0, 'skipped': 0, 'failed': 0, 'errors': [], 'warnings': [], 'rows': []}
        df = self._read_file(file_stream)
        seen_national_ids = set()
        seen_phones = set()

        for idx, source_row in df.iterrows():
            row = {
                key.strip(): value.strip() if isinstance(value, str) else value
                for key, value in source_row.items()
            }
            if not row.get('الاسم الأول'):
                results['failed'] += 1
                results['errors'].append(f'الصف {idx + 2}: الاسم الأول مفقود')
                results['rows'].append({'row': idx + 2, 'outcome': 'failed', 'reason': 'الاسم الأول مفقود'})
                continue

            national_id = normalize_identifier(row.get('الرقم الوطني', ''))
            phone = normalize_phone(row.get('الهاتف', ''))
            is_duplicate = bool(
                (national_id and (
                    national_id in seen_national_ids
                    or Patient.objects.filter(national_id=national_id).exists()
                ))
                or (phone and (
                    phone in seen_phones
                    or Patient.objects.filter(phone=phone).exists()
                ))
            )
            if is_duplicate:
                results['skipped'] += 1
                results['warnings'].append(
                    f'الصف {idx + 2}: تطابق مع مريض آخر بالرقم الوطني أو الهاتف'
                )
                results['rows'].append({'row': idx + 2, 'outcome': 'duplicate', 'reason': 'تطابق الهوية أو الهاتف'})
                continue

            try:
                patient = Patient(**self._patient_kwargs(row, doctor_id, created_by_id))
                patient.full_clean()
                results['added'] += 1
                results['rows'].append({'row': idx + 2, 'outcome': 'ready', 'reason': ''})
                if national_id:
                    seen_national_ids.add(national_id)
                if phone:
                    seen_phones.add(phone)
            except (ValidationError, ValueError, TypeError) as exc:
                message = getattr(exc, 'message_dict', str(exc))
                results['errors'].append(f'الصف {idx + 2}: {message}')
                results['failed'] += 1
                results['rows'].append({'row': idx + 2, 'outcome': 'failed', 'reason': str(message)})
        return results

    @transaction.atomic
    def import_patients(self, file_stream, doctor_id, created_by_id):
        results = {'added': 0, 'skipped': 0, 'failed': 0, 'errors': [], 'warnings': [], 'rows': []}
        df = self._read_file(file_stream)
        seen_national_ids = set()
        seen_phones = set()

        for idx, row in df.iterrows():
            row = {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()}
            if not row.get('الاسم الأول'):
                results['failed'] += 1
                results['errors'].append(f'الصف {idx + 2}: الاسم الأول مفقود')
                results['rows'].append({'row': idx + 2, 'outcome': 'failed', 'reason': 'الاسم الأول مفقود'})
                continue
            national_id = normalize_identifier(row.get('الرقم الوطني', ''))
            phone = normalize_phone(row.get('الهاتف', ''))
            if (
                (national_id and (national_id in seen_national_ids or Patient.objects.filter(national_id=national_id).exists()))
                or (phone and (phone in seen_phones or Patient.objects.filter(phone=phone).exists()))
            ):
                results['skipped'] += 1
                results['warnings'].append(f"الصف {idx+2}: تطابق مع مريض آخر بالرقم الوطني أو الهاتف")
                results['rows'].append({'row': idx + 2, 'outcome': 'duplicate', 'reason': 'تطابق الهوية أو الهاتف'})
                continue
            try:
                patient = Patient(**self._patient_kwargs(row, doctor_id, created_by_id))
                patient.full_clean()
                # A per-row savepoint keeps one database-level failure from
                # poisoning the transaction for all following rows.
                with transaction.atomic():
                    patient.save()
                results['added'] += 1
                if national_id:
                    seen_national_ids.add(national_id)
                if phone:
                    seen_phones.add(phone)
                results['rows'].append({'row': idx + 2, 'outcome': 'created', 'reason': ''})
            except Exception as e:
                results['errors'].append(f"الصف {idx+2}: {str(e)}")
                results['failed'] += 1
                results['rows'].append({'row': idx + 2, 'outcome': 'failed', 'reason': str(e)})
        return results

class OptionsImportService:
    @staticmethod
    def _read_file(file_stream):
        try:
            return pd.read_excel(file_stream, dtype=str, keep_default_na=False)
        except Exception:
            file_stream.seek(0)
            return pd.read_csv(file_stream, dtype=str, keep_default_na=False)

    def preview_diagnoses(self, file_stream):
        df = self._read_file(file_stream)
        rows = []
        seen_codes = set()
        for idx, row in df.iterrows():
            code = str(row.iloc[0]).strip() if len(row) > 0 else ''
            english = str(row.iloc[1]).strip() if len(row) > 1 else ''
            if not code or not english:
                rows.append({'row': idx + 2, 'outcome': 'failed', 'reason': 'الكود والاسم الإنجليزي مطلوبان'})
            elif code in seen_codes:
                rows.append({'row': idx + 2, 'outcome': 'duplicate', 'reason': 'كود مكرر داخل الملف'})
            else:
                existing = DiagnosisOption.all_objects.filter(code=code).first()
                outcome = 'update' if existing and existing.is_active else 'reactivate' if existing else 'create'
                rows.append({'row': idx + 2, 'outcome': outcome, 'reason': ''})
                seen_codes.add(code)
        return self._summarize(rows)

    @staticmethod
    def _summarize(rows):
        counts = {'create': 0, 'update': 0, 'reactivate': 0, 'duplicate': 0, 'failed': 0}
        for row in rows:
            counts[row['outcome']] = counts.get(row['outcome'], 0) + 1
        return {'rows': rows, 'counts': counts, 'total': len(rows)}

    @transaction.atomic
    def import_diagnoses(self, file_stream, merge_mode='merge'):
        df = self._read_file(file_stream)
        added = 0
        reactivated = 0
        updated = 0
        rows = []
        seen_codes = set()

        if merge_mode == 'replace':
            # Retire existing options instead of deleting rows referenced by
            # historical visits. Imported matches are reactivated below.
            from django.utils import timezone
            DiagnosisOption.objects.update(is_active=False, deleted_at=timezone.now())

        for idx, row in df.iterrows():
            if len(row) < 3:
                rows.append({'row': idx + 2, 'outcome': 'failed', 'reason': 'يلزم ثلاثة أعمدة'})
                continue
            code = str(row.iloc[0]).strip()
            english = str(row.iloc[1]).strip()
            arabic = str(row.iloc[2]).strip()
            if not code or not english:
                rows.append({'row': idx + 2, 'outcome': 'failed', 'reason': 'الكود والاسم الإنجليزي مطلوبان'})
                continue
            if code in seen_codes:
                rows.append({'row': idx + 2, 'outcome': 'duplicate', 'reason': 'كود مكرر داخل الملف'})
                continue
            seen_codes.add(code)
            # Use all_objects to include soft-deleted records
            existing = DiagnosisOption.all_objects.filter(code=code).first()
            if existing:
                if not existing.is_active:
                    existing.is_active = True
                    existing.deleted_at = None
                    reactivated += 1
                    outcome = 'reactivated'
                else:
                    updated += 1
                    outcome = 'updated'
                existing.english_name = english
                existing.arabic_name = arabic
                existing.save()
            else:
                DiagnosisOption.objects.create(code=code, english_name=english, arabic_name=arabic)
                added += 1
                outcome = 'created'
            rows.append({'row': idx + 2, 'outcome': outcome, 'reason': ''})
        return {'added': added, 'updated': updated, 'reactivated': reactivated, 'rows': rows}

    @transaction.atomic
    def import_medications(self, file_stream, column_map=None, merge_mode='merge'):
        df = self._read_file(file_stream)
        added = 0
        reactivated = 0
        updated = 0
        rows = []
        seen_keys = set()

        if merge_mode in ('replace', 'overwrite'):
            from django.utils import timezone
            MedicationOption.objects.update(is_active=False, deleted_at=timezone.now())

        for idx, row in df.iterrows():
            if column_map:
                def mapped_value(key, default_index):
                    raw_index = column_map.get(key, default_index)
                    if raw_index is None:
                        return ''
                    try:
                        index = int(raw_index)
                    except (TypeError, ValueError):
                        raise ValidationError({key: ['رقم العمود غير صالح']})
                    if index < 0 or index >= len(row):
                        raise ValidationError({key: ['رقم العمود خارج نطاق الملف']})
                    return str(row.iloc[index]).strip()

                generic_en = mapped_value('generic_english', 0)
                generic_ar = mapped_value('generic_arabic', 1)
                dosage = mapped_value('dosage', 2)
                brand_en = mapped_value('brand_english', 3)
                brand_ar = mapped_value('brand_arabic', 4)
            else:
                generic_en = str(row.iloc[0]).strip() if len(row) > 0 else ''
                generic_ar = str(row.iloc[1]).strip() if len(row) > 1 else ''
                dosage = str(row.iloc[2]).strip() if len(row) > 2 else ''
                brand_en = str(row.iloc[3]).strip() if len(row) > 3 else ''
                brand_ar = str(row.iloc[4]).strip() if len(row) > 4 else ''
            if not generic_en:
                rows.append({'row': idx + 2, 'outcome': 'failed', 'reason': 'الاسم العام الإنجليزي مطلوب'})
                continue
            key = (generic_en.casefold(), dosage.casefold(), brand_en.casefold())
            if key in seen_keys:
                rows.append({'row': idx + 2, 'outcome': 'duplicate', 'reason': 'دواء مكرر داخل الملف'})
                continue
            seen_keys.add(key)
            # Use all_objects to include soft-deleted records
            existing = MedicationOption.all_objects.filter(
                generic_english=generic_en,
                dosage=dosage,
                brand_english=brand_en
            ).first()
            if existing:
                if not existing.is_active:
                    existing.is_active = True
                    existing.deleted_at = None
                    reactivated += 1
                    outcome = 'reactivated'
                else:
                    updated += 1
                    outcome = 'updated'
                existing.generic_arabic = generic_ar
                existing.brand_arabic = brand_ar
                existing.save()
            else:
                MedicationOption.objects.create(
                    generic_english=generic_en,
                    generic_arabic=generic_ar,
                    dosage=dosage,
                    brand_english=brand_en,
                    brand_arabic=brand_ar,
                )
                added += 1
                outcome = 'created'
            rows.append({'row': idx + 2, 'outcome': outcome, 'reason': ''})
        return {'added': added, 'updated': updated, 'reactivated': reactivated, 'rows': rows}
