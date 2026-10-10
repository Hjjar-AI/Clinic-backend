from django.conf import settings
from django.test.runner import DiscoverRunner


class IsolatedRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        database = settings.DATABASES['default']
        if database['NAME'] != ':memory:' or database.get('TEST', {}).get('NAME') != ':memory:':
            raise RuntimeError('Clinic tests require the isolated in-memory database.')
        return super().setup_databases(**kwargs)
