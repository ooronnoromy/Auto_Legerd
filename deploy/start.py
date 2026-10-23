"""Prepare runtime storage and start Gunicorn on Railway's assigned port."""
import os
import sys
import signal
import subprocess
import time
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
    from ledger.push import configured
    command = ['gunicorn', 'config.wsgi:application', '--config', 'gunicorn.conf.py']
    if not configured():
        os.execvp('gunicorn',command)
    raise SystemExit(run_with_push_worker(command))


def run_with_push_worker(command):
    """Run one durable push worker alongside Gunicorn in the existing container."""
    worker_command = [sys.executable,'manage.py','send_push_notifications','--loop']
    web = subprocess.Popen(command)
    worker = subprocess.Popen(worker_command)
    stopping = False

    def stop(signum,frame):
        nonlocal stopping
        stopping = True
        for process in (web,worker):
            if process.poll() is None:
                process.terminate()

    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    try:
        while web.poll() is None and not stopping:
            if worker.poll() is not None:
                print('Push worker exited; restarting.',file=sys.stderr,flush=True)
                time.sleep(3)
                worker = subprocess.Popen(worker_command)
            time.sleep(1)
        if stopping:
            try:
                web.wait(timeout=20)
            except subprocess.TimeoutExpired:
                web.kill()
        return web.wait()
    finally:
        if worker.poll() is None:
            worker.terminate()
            try:
                worker.wait(timeout=15)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait()


if __name__ == '__main__':
    main()
