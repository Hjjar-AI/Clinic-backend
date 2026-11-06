"""Approved-history selectors never order encounters by unsigned working facts."""
from django.db.models import OuterRef, Subquery
from .models import VisitRevision


def latest_signed_revision(visit):
    return visit.revisions.order_by('-number').first()


def latest_approved_revisions(visits):
    latest_number = VisitRevision.objects.filter(visit_id=OuterRef('visit_id')).order_by('-number').values('number')[:1]
    return VisitRevision.objects.filter(visit__in=visits, number=Subquery(latest_number))


def order_by_approved_date(revisions, *, tie_breakers=('-visit_id',)):
    return revisions.order_by('-snapshot__fields__visit_date', *tie_breakers)
