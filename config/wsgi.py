import os
from django.core.wsgi import get_wsgi_application

# Item #4: default to production. The previous default (development) fails
# open with DEBUG=True and ALLOWED_HOSTS=['*'] whenever the env var is not
# set explicitly. Development must now opt in via DJANGO_SETTINGS_MODULE.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
application = get_wsgi_application()