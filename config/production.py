"""Settings for Railway's HTTPS proxy and PostgreSQL service."""
from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F403

DEBUG = False
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith(('DEV-', 'replace-', 'development-')):
    raise ImproperlyConfigured('Set SECRET_KEY to a unique random value of at least 50 characters.')
if not os.getenv('DATABASE_URL') or DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
    raise ImproperlyConfigured('Production requires a PostgreSQL DATABASE_URL from your Railway database service.')

ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', '').split(',') if host.strip()]
ALLOWED_HOSTS.append('healthcheck.railway.app')
railway_domain = os.getenv('RAILWAY_PUBLIC_DOMAIN', '').strip()
if railway_domain:
    ALLOWED_HOSTS.append(railway_domain)
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if origin.strip()]
if railway_domain:
    CSRF_TRUSTED_ORIGINS.append(f'https://{railway_domain}')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r'^healthz/$']
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
MEDIA_ROOT = Path(os.getenv('MEDIA_ROOT', str(Path(os.getenv('RAILWAY_VOLUME_MOUNT_PATH', '/data')) / 'media')))
