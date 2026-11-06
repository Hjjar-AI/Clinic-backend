"""Construct native constraints across Django's check/condition API rename."""
from django import VERSION
from django.db import models


def check_constraint(*, condition, **kwargs):
    """Keep Django 5.0 support while using the current API on Django 5.1+."""
    keyword = 'condition' if VERSION >= (5, 1) else 'check'
    return models.CheckConstraint(**{keyword: condition}, **kwargs)


def archive_constraint(name):
    return check_constraint(name=name, condition=(
        models.Q(is_active=True, deleted_at__isnull=True, archived_by__isnull=True, archive_reason='') |
        (models.Q(is_active=False, deleted_at__isnull=False) & ~models.Q(archive_reason=''))))


def retirement_constraint(name):
    return check_constraint(name=name, condition=(
        models.Q(is_active=True, retired_at__isnull=True, retired_by__isnull=True, retirement_reason='') |
        (models.Q(is_active=False, retired_at__isnull=False) & ~models.Q(retirement_reason=''))))


def verification_constraint(name, prefix=''):
    return check_constraint(name=name, condition=(
        models.Q(**{prefix + 'verification': 'verified', prefix + 'verified_at__isnull': False}) |
        models.Q(**{prefix + 'verification__in': ['unknown', 'reported'],
                    prefix + 'verified_at__isnull': True, prefix + 'verified_by__isnull': True})))
