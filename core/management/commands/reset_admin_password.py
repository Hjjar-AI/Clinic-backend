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

    def handle(self, *args, **options):
        username = options['username']
        user = User.objects.filter(username=username).first()
        if not user:
            self.stderr.write(f'User "{username}" not found.')
            return

        new_pass = secrets.token_urlsafe(12)
        user.set_password(new_pass)

        # Admin recovery should not force a rotation on next login; the
        # operator just performed the rotation by running this command.
        if hasattr(user, 'force_password_change'):
            user.force_password_change = False

        # Invalidate every existing session for this user. The
        # SessionRevocationMiddleware compares each session's stored
        # login_time against this field on every request.
        if hasattr(user, 'session_revoked_at'):
            user.session_revoked_at = timezone.now()

        user.save()

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