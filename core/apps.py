from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import core.signals  # noqa: F401
        import core.cache_signals  # noqa: F401
        import apps.accounts.signals  # noqa: F401
        import apps.notifications.signals  # noqa: F401
        # Registration only: no startup database queries.
