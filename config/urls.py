from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from core.errors import api_not_found

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('core.urls')),
]

# Clinical media is available only through authorized API downloads, including DEBUG.

# SPA fallback – must be last to avoid catching API/admin/static paths
urlpatterns += [
    re_path(r'^api(?:/.*)?$', api_not_found),
    re_path(r'^(?!(?:api|admin|static|media)(?:/|$)).*$', TemplateView.as_view(template_name='index.html')),
]
handler400 = 'core.errors.bad_request'
handler500 = 'core.errors.server_error'
