"""Canonical stored values and labels for this feature."""
from django.db.models import TextChoices


class VisitStatus(TextChoices):
    DRAFT = 'draft', 'Draft'
    FINAL = 'final', 'Final'
    AMENDED = 'amended', 'Amended'
    LOCKED = 'locked', 'Locked'

class RiskLevel(TextChoices):
    LOW = 'Low', 'Low'
    MODERATE = 'Moderate', 'Moderate'
    HIGH = 'High', 'High'

class LevelOfCare(TextChoices):
    OUTPATIENT = 'Outpatient', 'Outpatient'
    IOP = 'IOP', 'IOP'
    PHP = 'PHP', 'PHP'
    INPATIENT = 'Inpatient', 'Inpatient'
    RESIDENTIAL = 'Residential', 'Residential'

class CareBasis(TextChoices):
    UNKNOWN = 'unknown', 'Unknown'
    VOLUNTARY = 'voluntary', 'Voluntary'
    INVOLUNTARY = 'involuntary', 'Involuntary'

class AccompaniedBy(TextChoices):
    ALONE = 'alone', 'Alone'
    COMPANION = 'companion', 'With companion'
