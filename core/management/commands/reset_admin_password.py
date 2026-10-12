from core.operation_gate import gated
# backend/core/management/commands/reset_admin_password.py
"""
Reset a user's password and print it (or show a QR code).

Usage:
    python manage.py reset_admin_password
    python manage.py reset_admin_password --username doctor1
    python manage.py reset_admin_password --qr

This is the recovery path when nobody can log in. It bypasses
AuthService.change_password on purpose (that path requires the current
password). The new password is generated locally with `secrets`,
printed once, and never written anywhere else.

Unlike the equivalent command in the reference project, this version
also stamps session_revoked_at on the user. That field is enforced by
core.middleware.SessionRevocationMiddleware, which logs out any
session whose login_time predates the revocation — so rotating the
password actually invalidates existing sessions instead of leaving
stale cookies alive.
"""

import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = 'Reset a user password and print it (optional QR code)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username', '-u',
            default='admin',
            help='Username whose password to reset (default: admin).',
        )
        parser.add_argument(
            '--qr',
            action='store_true',
            help='Print a QR code containing the new password (requires qrcode).',
        )

    @gated()
    def handle(self, *args, **options):
        username = options['username']
        new_pass = secrets.token_urlsafe(12)
        with transaction.atomic():
            user = User.objects.select_for_update().filter(username=username).first()
            if not user:
                self.stderr.write(f'User "{username}" not found.')
                return
            user.set_password(new_pass)
            user.force_password_change = False
            user.session_revoked_at = timezone.now()
            user.version += 1
            user.save(update_fields=['password', 'force_password_change', 'session_revoked_at', 'version'])

        self.stdout.write(self.style.SUCCESS(f'Username: {username}'))
        self.stdout.write(self.style.SUCCESS(f'New password: {new_pass}'))
        self.stdout.write(
            'Store this somewhere safe — it will not be shown again.'
        )

        if options['qr']:
            try:
                import qrcode
                qr = qrcode.QRCode(box_size=1, border=2)
                qr.add_data(new_pass)
                qr.make(fit=True)
                qr.print_ascii(invert=True)
            except ImportError:
                self.stderr.write(
                    'qrcode not installed; skipping QR. '
                    'Install with: pip install qrcode'
                )