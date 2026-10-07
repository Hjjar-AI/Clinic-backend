from core.access import accessible_patients, accessible_visits

class BaseStatisticsService:
    def get_accessible_patients(self, user):
        return accessible_patients(user)

    def get_accessible_visits(self, user, date_from=None, date_to=None):
        qs = accessible_visits(user).filter(patient__is_active=True, patient__deleted_at__isnull=True)
        if date_from:
            qs = qs.filter(visit_date__gte=date_from)
        if date_to:
            qs = qs.filter(visit_date__lte=date_to)
        return qs
