import logging
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from ledger.push import configured, process_pending


class Command(BaseCommand):
    help = 'Send queued car and expense notifications. --loop runs the delivery worker.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true')

    def handle(self, *args, **options):
        if not configured():
            raise CommandError('Set PUSH_VAPID_PUBLIC_KEY, PUSH_VAPID_PRIVATE_KEY and PUSH_VAPID_SUBJECT first.')
        while True:
            try:
                close_old_connections()
                count = process_pending()
                if not options['loop']:
                    self.stdout.write(f'Processed {count} push deliveries.')
                    return
            except KeyboardInterrupt:
                return
            except Exception:
                if not options['loop']:
                    raise
                logging.getLogger(__name__).error('Push worker cycle failed; retrying in 5 seconds.')
                time.sleep(5)
            time.sleep(2)
