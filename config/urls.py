from django.contrib import admin
from django.urls import path,include
from ledger.views import healthcheck, protected_media

urlpatterns = [
 path('healthz/', healthcheck, name='healthcheck'),
 path('media/<path:filename>', protected_media, name='protected_media'),
 path('admin/', admin.site.urls),
 path('', include('ledger.urls')),
]
