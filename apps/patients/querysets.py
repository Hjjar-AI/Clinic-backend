from django.db import models
from django.utils import timezone


class CareTeamQuerySet(models.QuerySet):
    def unended(self):
        """Includes planned memberships; used for uniqueness and team management."""
        return self.filter(ended_at__isnull=True)

    def effective_at(self, at=None):
        """Current access/display excludes memberships whose start is still future."""
        return self.unended().filter(started_at__lte=at if at is not None else timezone.now())


def care_team_names(patient):
    if hasattr(patient, '_summary_team'):
        return [member.user.full_name or member.user.username for member in patient._summary_team]
    return [member.user.full_name or member.user.username
            for member in patient.care_team.effective_at().select_related('user')]


def summary_queryset(queryset):
    from .models import PatientCareTeam, PatientContact
    return queryset.select_related('primary_identifier').prefetch_related(
        models.Prefetch('care_team', queryset=PatientCareTeam.objects.effective_at().select_related('user').order_by('started_at', 'pk'), to_attr='_summary_team'),
        models.Prefetch('patientcontact_records', queryset=PatientContact.objects.filter(is_active=True, is_primary=True, is_emergency=True), to_attr='_summary_contacts'))
