"""Durable Web Push delivery, without slowing down car and expense saves."""
import json
import logging
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from pywebpush import WebPushException, webpush

from .models import Expense, PushDelivery, PushSubscription, Vehicle

logger = logging.getLogger(__name__)


def configured():
    return bool(settings.PUSH_VAPID_PUBLIC_KEY and settings.PUSH_VAPID_PRIVATE_KEY and settings.PUSH_VAPID_SUBJECT)


def enqueue_creation(event, object_id):
    if not configured():
        return
    if event == 'vehicle':
        vehicle = Vehicle.objects.filter(pk=object_id).first()
    else:
        expense = Expense.objects.select_related('vehicle').filter(pk=object_id).first()
        vehicle = expense.vehicle if expense else None
    if not vehicle:
        return
    subscriptions = PushSubscription.objects.filter(user__is_active=True).filter(
        Q(user__is_staff=True) | Q(user_id=vehicle.owner_id) | Q(user_id=vehicle.driver_id))
    PushDelivery.objects.bulk_create([
        PushDelivery(subscription=sub, vehicle=vehicle, event=event, object_id=object_id)
        for sub in subscriptions
    ], ignore_conflicts=True)


def claim_delivery():
    now = timezone.now()
    with transaction.atomic():
        # A crashed worker's lease becomes eligible again after two minutes.
        jobs = PushDelivery.objects.filter(available_at__lte=now).filter(
            Q(status='pending') | Q(status='processing'))
        kwargs = {'skip_locked': True} if connection.features.has_select_for_update_skip_locked else {}
        job = jobs.select_for_update(**kwargs).order_by('available_at','pk').first()
        if not job:
            return None
        job.status = 'processing'
        job.attempts += 1
        job.available_at = now + timedelta(minutes=2)
        job.save(update_fields=['status','attempts','available_at'])
        return job.pk


def deliver(job_id):
    job = PushDelivery.objects.select_related('subscription__user','vehicle').filter(pk=job_id).first()
    if not job:
        return
    user, vehicle = job.subscription.user, job.vehicle
    # Recheck permissions at send time: assignments may have changed since enqueue.
    if not user.is_active or not (user.is_staff or user.pk in (vehicle.owner_id,vehicle.driver_id)):
        PushDelivery.objects.filter(pk=job_id).update(status='skipped')
        return
    if job.event == 'expense':
        record = Expense.objects.select_related('owner').filter(pk=job.object_id,vehicle=vehicle).first()
        if not record:
            PushDelivery.objects.filter(pk=job_id).update(status='skipped')
            return
        actor = record.owner.first_name or ('An admin' if record.owner.is_staff else 'A driver')
        title, body = 'New expense added', f'{actor} added an expense for {vehicle.name}.'
        url = reverse('expenses') + f'?vehicle={vehicle.pk}'
    else:
        title, body = 'New car added', f'{vehicle.name} was added to the garage.'
        url = reverse('vehicle_detail', args=[vehicle.pk])
    payload = {'title':title,'body':body,'url':url,'tag':f'{job.event}-{job.object_id}','recipient':user.pk}
    sub = job.subscription
    try:
        webpush(subscription_info={'endpoint':sub.endpoint,'keys':{'p256dh':sub.p256dh,'auth':sub.auth}},
                data=json.dumps(payload),vapid_private_key=settings.PUSH_VAPID_PRIVATE_KEY,
                vapid_claims={'sub':settings.PUSH_VAPID_SUBJECT},ttl=3600,timeout=10)
    except WebPushException as exc:
        status = getattr(exc, 'status_code', None)
        if status is None and exc.response is not None:
            status = exc.response.status_code
        if status in (404,410):
            sub.delete()
            return
        retry(job, status)
    except Exception:
        # Do not log subscription URLs, encryption keys, payloads or VAPID secrets.
        retry(job, None)
    else:
        PushDelivery.objects.filter(pk=job_id).update(status='sent')


def retry(job, status):
    terminal = job.attempts >= 5 or (status is not None and 400 <= status < 500 and status not in (408,429))
    PushDelivery.objects.filter(pk=job.pk).update(
        status='failed' if terminal else 'pending',
        available_at=timezone.now()+timedelta(seconds=min(60*2**(job.attempts-1),1800)))
    logger.warning('Push delivery %s %s (provider status %s).',job.pk,'failed' if terminal else 'will retry',status)


def process_pending(limit=50):
    if not configured():
        return 0
    count = 0
    while count < limit:
        job_id = claim_delivery()
        if job_id is None:
            break
        deliver(job_id)
        count += 1
    # Avoid growing an unbounded delivery history.
    PushDelivery.objects.filter(status__in=['sent','failed','skipped'],created_at__lt=timezone.now()-timedelta(days=7)).delete()
    return count
