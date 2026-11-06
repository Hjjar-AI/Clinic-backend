"""Canonical stored values and labels for this feature."""
from django.db.models import TextChoices


class Verification(TextChoices):
    UNKNOWN = 'unknown', 'Unknown'
    REPORTED = 'reported', 'Reported'
    VERIFIED = 'verified', 'Document verified'

class CareRole(TextChoices):
    DOCTOR = 'doctor', 'Doctor'
    NURSE = 'nurse', 'Nurse'
    THERAPIST = 'therapist', 'Therapist'
    ASSISTANT = 'assistant', 'Assistant'
    COORDINATOR = 'coordinator', 'Coordinator'

class MaritalStatus(TextChoices):
    SINGLE = 'single', 'أعزب / عزباء'
    MARRIED = 'married', 'متزوج / متزوجة'
    DIVORCED = 'divorced', 'مطلق / مطلقة'
    WIDOWED = 'widowed', 'أرمل / أرملة'

class Gender(TextChoices):
    MALE = 'ذكر', 'ذكر'
    FEMALE = 'أنثى', 'أنثى'

class FollowUpMethod(TextChoices):
    IN_PERSON = 'In-person', 'In-person'
    TELEHEALTH = 'Telehealth', 'Telehealth'
    PHONE = 'Phone', 'Phone'

class FollowUpStatus(TextChoices):
    PENDING = 'pending', 'Pending'
    COMPLETED = 'completed', 'Completed'
    MISSED = 'missed', 'Missed'
    CANCELLED = 'cancelled', 'Cancelled'
    WAIVED = 'waived', 'Waived'

class IdentifierType(TextChoices):
    NATIONAL_ID = 'national_id', 'National ID'
    PASSPORT = 'passport', 'Passport'
    OTHER = 'other', 'Other'

class AuthorityScope(TextChoices):
    CONTACT = 'contact', 'Contact'
    RECORDS = 'records', 'Record access'
    DECISIONS = 'decisions', 'Decisions'
    RECORDS_AND_DECISIONS = 'records_and_decisions', 'Records and decisions'

class RecordSource(TextChoices):
    PATIENT = 'patient', 'Patient'
    CONTACT = 'contact', 'Contact'
    CLINICIAN = 'clinician', 'Clinician'
    DOCUMENT = 'document', 'Document'
    OTHER = 'other', 'Other'

class AllergySeverity(TextChoices):
    UNKNOWN = 'unknown', 'Unknown'
    MILD = 'mild', 'Mild'
    MODERATE = 'moderate', 'Moderate'
    SEVERE = 'severe', 'Severe'

class AllergyStatus(TextChoices):
    SUSPECTED = 'suspected', 'Suspected'
    CONFIRMED = 'confirmed', 'Confirmed'
    REFUTED = 'refuted', 'Refuted'
    RESOLVED = 'resolved', 'Resolved'
    ENTERED_IN_ERROR = 'entered_in_error', 'Entered In Error'

class MedicationStatus(TextChoices):
    ACTIVE = 'active', 'Active'
    ON_HOLD = 'on_hold', 'On Hold'
    STOPPED = 'stopped', 'Stopped'
    ENTERED_IN_ERROR = 'entered_in_error', 'Entered In Error'

class SummaryStatus(TextChoices):
    UNKNOWN = 'unknown', 'Unknown'
    NONE_KNOWN = 'none_known', 'None known'
    RECORDED = 'recorded', 'Recorded'

class ContactChannel(TextChoices):
    PHONE = 'phone', 'Phone'
    SMS = 'sms', 'SMS'
    EMAIL = 'email', 'Email'
    NONE = 'none', 'Do not contact'

class DuplicateStatus(TextChoices):
    DISMISSED = 'dismissed', 'Review later'
    DIFFERENT = 'different', 'Different people'
    MERGED = 'merged', 'Merged'
