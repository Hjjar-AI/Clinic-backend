from django.utils import timezone


def year_only_age(birth_year, at=None):
    """An unknown birth year stays unknown; callers choose their display label."""
    return (at if at is not None else timezone.localdate()).year - birth_year if birth_year else None


def display_year_only_age(birth_year, at=None):
    age = year_only_age(birth_year, at)
    return age if age is not None else 'غير محدد'
