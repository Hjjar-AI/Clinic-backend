# backend/apps/backup/retention.py
"""
Backup retention policy.

Keeps every backup from the last BACKUP_SAFETY_DAYS days, then one per
ISO week within the next window, then one per calendar month, then one
per calendar year forever.

Windows are read from Django settings, which in turn read the same
keys from .env with sensible defaults:

    BACKUP_SAFETY_DAYS      (default 30)   -- daily band
    BACKUP_WEEKLY_DAYS      (default 90)   -- weekly band, days back from now
    BACKUP_MONTHLY_DAYS     (default 365)  -- monthly band, days back from now
"""

import os
import re
from datetime import datetime, timedelta

from django.conf import settings

# Filename format written by core/management/commands/auto_backup.py.
BACKUP_FILENAME_PATTERN = re.compile(r'^clinic_backup_(\d{8})_(\d{6})\.zip$')


def _days(setting_name, default):
    try:
        return int(getattr(settings, setting_name, default))
    except (TypeError, ValueError):
        return default


def _parse_backup_date(filename):
    m = BACKUP_FILENAME_PATTERN.match(filename)
    if not m:
        return None
    try:
        dt_str = m.group(1) + m.group(2)
        return datetime.strptime(dt_str, '%Y%m%d%H%M%S')
    except ValueError:
        return None


def apply_backup_retention(directory, dry_run=False):
    """
    Apply the retention policy to `directory`.

    Returns {'kept': int, 'deleted': int}. On a missing directory,
    returns zeros rather than raising — the caller (a scheduled
    command) should not crash if backups have never been created.
    """
    daily_days = _days('BACKUP_SAFETY_DAYS', 30)
    weekly_days = _days('BACKUP_WEEKLY_DAYS', 90)
    monthly_days = _days('BACKUP_MONTHLY_DAYS', 365)

    now = datetime.now()
    files = []
    try:
        for entry in os.scandir(directory):
            if entry.is_file():
                dt = _parse_backup_date(entry.name)
                if dt:
                    files.append((entry.name, dt))
    except FileNotFoundError:
        return {'kept': 0, 'deleted': 0}

    if not files:
        return {'kept': 0, 'deleted': 0}

    files.sort(key=lambda x: x[1])
    daily_cutoff = now - timedelta(days=daily_days)
    weekly_cutoff = now - timedelta(days=weekly_days)
    monthly_cutoff = now - timedelta(days=monthly_days)

    keep = set()

    # Daily: keep everything within the last `daily_days` days.
    for fname, dt in files:
        if dt >= daily_cutoff:
            keep.add(fname)

    # Weekly: one per ISO week, in the band [weekly_cutoff, daily_cutoff).
    weekly = {}
    for fname, dt in files:
        if weekly_cutoff <= dt < daily_cutoff:
            iso_year, iso_week, _ = dt.isocalendar()
            key = (iso_year, iso_week)
            if key not in weekly or dt > weekly[key][1]:
                weekly[key] = (fname, dt)
    for fname, _ in weekly.values():
        keep.add(fname)

    # Monthly: one per calendar month, in the band [monthly_cutoff, weekly_cutoff).
    monthly = {}
    for fname, dt in files:
        if monthly_cutoff <= dt < weekly_cutoff:
            key = (dt.year, dt.month)
            if key not in monthly or dt > monthly[key][1]:
                monthly[key] = (fname, dt)
    for fname, _ in monthly.values():
        keep.add(fname)

    # Yearly: one per calendar year, older than monthly_cutoff.
    yearly = {}
    for fname, dt in files:
        if dt < monthly_cutoff:
            key = dt.year
            if key not in yearly or dt > yearly[key][1]:
                yearly[key] = (fname, dt)
    for fname, _ in yearly.values():
        keep.add(fname)

    deleted = 0
    for fname, _ in files:
        if fname not in keep:
            filepath = os.path.join(directory, fname)
            if not dry_run:
                try:
                    os.unlink(filepath)
                except OSError:
                    # Don't let a single permission error abort the sweep.
                    continue
            deleted += 1

    return {'kept': len(keep), 'deleted': deleted}