from django.contrib.auth.signals import user_logged_out
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Expense, PushSubscription, Vehicle
from .push import configured, enqueue_creation


@receiver(post_save, sender=Vehicle, dispatch_uid='push-new-vehicle')
@receiver(post_save, sender=Expense, dispatch_uid='push-new-expense')
def creation_notification(sender, instance, created, raw=False, **kwargs):
    if created and not raw and configured():
        event = 'vehicle' if sender is Vehicle else 'expense'
        transaction.on_commit(lambda: enqueue_creation(event, instance.pk), robust=True)


@receiver(user_logged_out, dispatch_uid='push-device-logout')
def detach_device(sender, request, user, **kwargs):
    if request is not None and user is not None:
        device_id = request.session.get('push_subscription_id')
        if device_id:
            PushSubscription.objects.filter(pk=device_id,user=user).delete()
