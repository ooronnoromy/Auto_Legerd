"""Prepare runtime storage and start Gunicorn on Railway's assigned port."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.production')

def prepare_media(media_root, environment):
    media_root = Path(media_root)
    if environment.get('RAILWAY_ENVIRONMENT_ID'):
        mount_path = environment.get('RAILWAY_VOLUME_MOUNT_PATH')
        if not mount_path or not media_root.resolve().is_relative_to(Path(mount_path).resolve()):
            print(
                'WARNING: Uploaded photos are using temporary storage. Attach a Railway '
                'volume and set MEDIA_ROOT to a directory inside its mount path '
                '(for example /data/media) to preserve photos across deployments.',
                file=sys.stderr,
                flush=True,
            )
    media_root.mkdir(parents=True, exist_ok=True)


def main():
    import django
    django.setup()
    from django.conf import settings

    prepare_media(settings.MEDIA_ROOT, os.environ)
    os.execvp('gunicorn', ['gunicorn', 'config.wsgi:application', '--config', 'gunicorn.conf.py'])


if __name__ == '__main__':
    main()
