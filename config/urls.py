from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('core.urls')),
]

# Clinical media is available only through authorized API downloads, including DEBUG.

# SPA fallback – must be last to avoid catching API/admin/static paths
urlpatterns += [
    re_path(r'^.*$', TemplateView.as_view(template_name='index.html')),
]