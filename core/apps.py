# backend/core/apps.py
from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import core.signals  # noqa
        # Import app-specific signals to register them
        import apps.accounts.signals  # noqa
        import apps.patients.signals  # noqa
        import apps.visits.signals  # noqa
        import apps.appointments.signals  # noqa
        import apps.billing.signals  # noqa
        import apps.tasks.signals  # noqa
        import apps.notifications.signals  # noqa
        import apps.clinical.signals  # noqa
        import apps.settings.signals  # noqa
        # Do NOT run any database queries here – they cause errors during makemigrations.