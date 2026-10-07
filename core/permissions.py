# backend/core/permissions.py
from rest_framework import permissions
from django.conf import settings

# Custom permission names
PERM_VIEW_PATIENTS = 'view_patients'
PERM_EDIT_PATIENT = 'edit_patient'
PERM_DELETE_PATIENT = 'delete_patient'
PERM_ADD_VISIT = 'add_visit'
PERM_EDIT_VISIT = 'edit_visit'
PERM_DELETE_VISIT = 'delete_visit'
PERM_VIEW_VISITS = 'view_visits'
PERM_VIEW_APPOINTMENTS = 'view_appointments'
PERM_MANAGE_APPOINTMENTS = 'manage_appointments'
PERM_EXPORT_PDF = 'export_pdf'
PERM_EXPORT_WORD = 'export_word'
PERM_MANAGE_USERS = 'manage_users'
PERM_MANAGE_SETTINGS = 'manage_settings'
PERM_MANAGE_BACKUP = 'manage_backup'
PERM_MANAGE_TASKS = 'manage_tasks'
PERM_IMPORT_DATA = 'import_data'
PERM_MANAGE_OPTIONS = 'manage_options'
PERM_EXPORT_OPTIONS = 'export_options'
PERM_VIEW_REPORTS = 'view_reports'
PERM_EXPORT_REPORTS = 'export_reports'
PERM_VIEW_BILLING = 'view_billing'
PERM_MANAGE_BILLING = 'manage_billing'
PERM_MANAGE_TEMPLATES = 'manage_templates'
PERM_MANAGE_PATIENT_DOCUMENTS = 'manage_patient_documents'
PERM_VIEW_REFERRALS = 'view_referrals'

ALL_PERMISSIONS = {
    PERM_VIEW_PATIENTS: 'عرض قائمة المرضى',
    PERM_EDIT_PATIENT: 'تعديل بيانات المريض',
    PERM_DELETE_PATIENT: 'حذف مريض',
    PERM_ADD_VISIT: 'إضافة زيارة',
    PERM_EDIT_VISIT: 'تعديل زيارة',
    PERM_DELETE_VISIT: 'حذف زيارة',
    PERM_VIEW_VISITS: 'عرض الزيارات',
    PERM_VIEW_APPOINTMENTS: 'عرض المواعيد',
    PERM_MANAGE_APPOINTMENTS: 'إدارة المواعيد',
    PERM_EXPORT_PDF: 'تصدير PDF',
    PERM_EXPORT_WORD: 'تصدير Word',
    PERM_MANAGE_USERS: 'إدارة المستخدمين',
    PERM_MANAGE_SETTINGS: 'تغيير الإعدادات',
    PERM_MANAGE_BACKUP: 'النسخ الاحتياطي والاستعادة',
    PERM_MANAGE_TASKS: 'إدارة المهام',
    PERM_IMPORT_DATA: 'استيراد بيانات',
    PERM_MANAGE_OPTIONS: 'إدارة الخيارات',
    PERM_EXPORT_OPTIONS: 'تصدير الخيارات',
    PERM_VIEW_REPORTS: 'عرض التقارير',
    PERM_EXPORT_REPORTS: 'تصدير التقارير',
    PERM_VIEW_BILLING: 'عرض الفواتير',
    PERM_MANAGE_BILLING: 'إدارة الفواتير',
    PERM_MANAGE_TEMPLATES: 'إدارة قوالب الملاحظات السريرية',
    PERM_MANAGE_PATIENT_DOCUMENTS: 'إدارة مرفقات المرضى',
    PERM_VIEW_REFERRALS: 'عرض خطابات التحويل',
}

DEFAULT_PERMISSIONS = {
    'admin': list(ALL_PERMISSIONS.keys()),
    'doctor': [
        PERM_VIEW_PATIENTS, PERM_EDIT_PATIENT, PERM_ADD_VISIT, PERM_EDIT_VISIT,
        PERM_VIEW_VISITS, PERM_VIEW_APPOINTMENTS, PERM_MANAGE_APPOINTMENTS,
        PERM_EXPORT_PDF, PERM_EXPORT_WORD, PERM_VIEW_REPORTS, PERM_EXPORT_REPORTS,
        PERM_VIEW_BILLING, PERM_MANAGE_BILLING, PERM_MANAGE_TEMPLATES,
        PERM_MANAGE_PATIENT_DOCUMENTS, PERM_VIEW_REFERRALS,
    ],
    'receptionist': [
        PERM_VIEW_PATIENTS, PERM_EDIT_PATIENT, PERM_ADD_VISIT, PERM_VIEW_VISITS,
        PERM_VIEW_APPOINTMENTS, PERM_MANAGE_APPOINTMENTS, PERM_VIEW_BILLING,
        PERM_MANAGE_PATIENT_DOCUMENTS, PERM_VIEW_REFERRALS,
    ],
}

# -------------------------------
# DRF permission classes
# -------------------------------

class HasViewPatients(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_VIEW_PATIENTS)

class HasEditPatient(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_EDIT_PATIENT)

class HasDeletePatient(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_DELETE_PATIENT)

class HasAddVisit(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_ADD_VISIT)

class HasEditVisit(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_EDIT_VISIT)

class HasDeleteVisit(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_DELETE_VISIT)

class HasViewVisits(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_VIEW_VISITS)

class HasViewAppointments(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_VIEW_APPOINTMENTS)

class HasManageAppointments(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_MANAGE_APPOINTMENTS)

class HasExportPdf(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_EXPORT_PDF)

class HasExportWord(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_EXPORT_WORD)

class HasManageUsers(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_MANAGE_USERS)

class HasManageSettings(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_MANAGE_SETTINGS)

class HasManageBackup(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_MANAGE_BACKUP)

class HasManageTasks(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_MANAGE_TASKS)

class HasImportData(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_IMPORT_DATA)

class HasManageOptions(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_MANAGE_OPTIONS)

class HasExportOptions(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_EXPORT_OPTIONS)

class HasViewReports(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_VIEW_REPORTS)

class HasExportReports(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_EXPORT_REPORTS)

class HasViewBilling(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_VIEW_BILLING)

class HasManageBilling(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_MANAGE_BILLING)

class HasManageTemplates(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_MANAGE_TEMPLATES)

class HasManagePatientDocuments(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_MANAGE_PATIENT_DOCUMENTS)

class HasViewReferrals(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_VIEW_REFERRALS)


class IsAdminRole(permissions.BasePermission):
    message = 'هذا الإجراء مخصص للمدير'

    def has_permission(self, request, view):
        return request.user.role == 'admin'


# -------------------------------
# View-level permission classes
# -------------------------------

# FIX: previously named `CanViewDoctors`, which broke `apps/accounts/views.py`
# (it imports `HasViewDoctors`). Renamed to match the Has<Action><Noun>
# convention used by every other view-level permission in this file.
class HasViewDoctors(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.has_perm(PERM_MANAGE_USERS) or request.user.has_perm(PERM_VIEW_PATIENTS)

# Backward-compat alias. Nothing in the codebase references the old name,
# but keeping it costs nothing and avoids breaking any out-of-tree import.
CanViewDoctors = HasViewDoctors


# -------------------------------
# Object-level permission classes (unchanged)
# -------------------------------

class CanAccessPatient(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.has_perm(PERM_VIEW_PATIENTS):
            if user.role == 'admin':
                return True
            if user.role == 'doctor':
                return obj.doctor_id == user.id
            if user.role == 'receptionist':
                return obj.doctor_id == user.id or obj.created_by_id == user.id
        return False

class CanAccessVisit(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if obj.deleted_at:
            return False
        user = request.user
        if user.has_perm(PERM_VIEW_VISITS) or user.has_perm(PERM_EDIT_VISIT):
            if user.role == 'admin':
                return True
            if user.role == 'doctor':
                return obj.patient.doctor_id == user.id or obj.author_id == user.id
            if user.role == 'receptionist':
                return obj.patient.created_by_id == user.id
        return False

class CanAccessAppointment(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if obj.deleted_at:
            return False
        user = request.user
        if user.has_perm(PERM_VIEW_APPOINTMENTS) or user.has_perm(PERM_MANAGE_APPOINTMENTS):
            if user.role == 'admin':
                return True
            if user.role == 'doctor':
                return obj.doctor_id == user.id
            if user.role == 'receptionist':
                return obj.patient.created_by_id == user.id
        return False

class CanAccessInvoice(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if obj.deleted_at:
            return False
        user = request.user
        if user.has_perm(PERM_VIEW_BILLING) or user.has_perm(PERM_MANAGE_BILLING):
            if user.role == 'admin':
                return True
            if user.role == 'doctor':
                return obj.patient.doctor_id == user.id
            if user.role == 'receptionist':
                return obj.patient.created_by_id == user.id
        return False

# Aliases for backward compatibility (if any)
def has_permission(user, perm_name):
    return user.has_perm(perm_name)
