from django.contrib import admin
from django.urls import include, path

urlpatterns = [path('admin/', admin.site.urls), path('accounts/', include('apps.accounts.urls')), path('', include('apps.pulse.urls'))]
handler403 = 'apps.pulse.views.error_403'
handler404 = 'apps.pulse.views.error_404'
handler500 = 'apps.pulse.views.error_500'
