import base64
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create a stable VAPID key pair in an ignored local file; never prints private keys.'

    def add_arguments(self, parser):
        parser.add_argument('--subject', required=True, help='Your HTTPS website URL or mailto contact address.')
        parser.add_argument('--configure-local', action='store_true')

    def handle(self, *args, **options):
        subject = options['subject']
        url = urlsplit(subject)
        if not ((url.scheme=='https' and url.hostname) or (url.scheme=='mailto' and '@' in url.path)) or '\n' in subject or '\r' in subject:
            raise CommandError('Use an HTTPS website URL or mailto contact address.')
        output = settings.BASE_DIR / '.run' / 'push-keys.env'
        if output.exists():
            raise CommandError('The key file already exists. Reuse it; do not rotate keys for existing devices.')
        if settings.PUSH_VAPID_PRIVATE_KEY or settings.PUSH_VAPID_PUBLIC_KEY:
            raise CommandError('Push keys are already configured. Reuse the existing key pair.')
        key = ec.generate_private_key(ec.SECP256R1())
        encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b'=').decode()
        public = encode(key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint))
        private = encode(key.private_numbers().private_value.to_bytes(32,'big'))
        text = f'PUSH_VAPID_PUBLIC_KEY={public}\nPUSH_VAPID_PRIVATE_KEY={private}\nPUSH_VAPID_SUBJECT={subject}\n'
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('x',encoding='utf-8') as file:
            file.write(text)
        output.chmod(0o600)
        if options['configure_local']:
            env_file = settings.BASE_DIR / '.env'
            existing = env_file.read_text(encoding='utf-8') if env_file.exists() else ''
            if any(line.partition('=')[0].strip().startswith('PUSH_VAPID_') for line in existing.splitlines() if not line.lstrip().startswith('#')):
                raise CommandError('Keys saved to .run/push-keys.env. Local .env already has push settings; no values were replaced.')
            with env_file.open('a',encoding='utf-8') as file:
                file.write('\n# Web Push signing keys; keep stable and private.\n'+text)
        self.stdout.write(self.style.SUCCESS('Push keys saved to .run/push-keys.env. Keep the private key out of Git.'))
