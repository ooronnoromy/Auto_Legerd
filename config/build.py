"""Only used to collect public assets while building the Docker image."""
from .settings import *  # noqa: F403

DEBUG = False
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
