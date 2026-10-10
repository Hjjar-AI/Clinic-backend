"""Construct native constraints across Django's check/condition API rename."""
from django import VERSION
from django.db import models


def check_constraint(*, condition, **kwargs):
    """Keep Django 5.0 support while using the current API on Django 5.1+."""
    keyword = 'condition' if VERSION >= (5, 1) else 'check'
    return models.CheckConstraint(**{keyword: condition}, **kwargs)
