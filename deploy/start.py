"""Validate runtime storage and start Gunicorn on Railway's assigned port."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.production')

import django
django.setup()
from django.conf import settings

media_root = Path(settings.MEDIA_ROOT)
if os.getenv('RAILWAY_ENVIRONMENT_ID'):
    mount_path = os.getenv('RAILWAY_VOLUME_MOUNT_PATH')
    if not mount_path or not media_root.resolve().is_relative_to(Path(mount_path).resolve()):
        raise RuntimeError('Attach a Railway volume at /data and set MEDIA_ROOT=/data/media so uploads persist.')
media_root.mkdir(parents=True, exist_ok=True)
os.execvp('gunicorn', ['gunicorn', 'config.wsgi:application', '--config', 'gunicorn.conf.py'])
