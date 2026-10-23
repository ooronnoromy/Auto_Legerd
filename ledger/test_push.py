import base64
import json
from datetime import timedelta
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from pywebpush import WebPushException

from .models import Expense, PushDelivery, PushSubscription, User, Vehicle
from .push import claim_delivery, enqueue_creation, process_pending


@override_settings(PUSH_VAPID_PUBLIC_KEY='public-test-key',PUSH_VAPID_PRIVATE_KEY='private-test-key',PUSH_VAPID_SUBJECT='https://garage.example')
class PushTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('01900000001',password='Admin-pass-238!')
        cls.owner = User.objects.create_user('01700000001',password='Owner-pass-238!')
        cls.driver = User.objects.create_user('01800000001',password='Driver-pass-238!')
        cls.other = User.objects.create_user('01600000001',password='Other-pass-238!')
        cls.car = Vehicle.objects.create(owner=cls.owner,driver=cls.driver,name='Axio',plate='AX-1')
        cls.expense = Expense.objects.create(owner=cls.driver,vehicle=cls.car,title='Fuel refill',category='fuel',amount=100,liters=1,date=timezone.localdate())
        public = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
        encode = lambda b: base64.urlsafe_b64encode(b).rstrip(b'=').decode()
        cls.keys = {'p256dh':encode(public),'auth':encode(b'0123456789abcdef')}

    def setUp(self):
        self.client.force_login(self.owner)

    def payload(self,endpoint='https://fcm.googleapis.com/fcm/send/device-token'):
        return {'endpoint':endpoint,'keys':self.keys}

    def subscribe(self,user=None,endpoint=None):
        if user:
            self.client.force_login(user)
        return self.client.post(reverse('push_subscribe'),self.payload(endpoint) if endpoint else self.payload(),content_type='application/json')

    def devices(self):
        for user in [self.admin,self.owner,self.driver,self.other]:
            PushSubscription.objects.create(user=user,endpoint=f'https://fcm.googleapis.com/fcm/send/device-{user.pk}',**self.keys)

    def test_config_is_private_and_never_exposes_signing_key(self):
        response = self.client.get(reverse('push_config'))
        self.assertTrue(response.json()['available'])
        self.assertEqual(response.json()['publicKey'],'public-test-key')
        self.assertEqual(response.json()['userId'],self.owner.pk)
        self.assertNotContains(response,'private-test-key')
        self.assertIn('no-store',response.headers['Cache-Control'])
        self.client.logout()
        self.assertEqual(self.client.get(reverse('push_config')).status_code,302)
        self.assertEqual(self.client.post(reverse('push_subscribe'),self.payload(),content_type='application/json').status_code,302)

    def test_register_updates_existing_device_without_duplicates(self):
        self.assertEqual(self.subscribe().status_code,200)
        self.assertEqual(self.subscribe().status_code,200)
        sub = PushSubscription.objects.get()
        self.assertEqual(sub.user,self.owner)
        self.assertEqual(self.client.session['push_subscription_id'],sub.pk)

    def test_device_rebinds_to_current_account_and_logout_detaches(self):
        self.subscribe()
        self.subscribe(self.driver)
        self.assertEqual(PushSubscription.objects.get().user,self.driver)
        self.client.post(reverse('logout'))
        self.assertFalse(PushSubscription.objects.exists())

    def test_logout_does_not_remove_other_devices(self):
        self.subscribe()
        other_device = PushSubscription.objects.create(user=self.owner,endpoint='https://fcm.googleapis.com/fcm/send/other-phone',**self.keys)
        self.client.post(reverse('logout'))
        self.assertEqual(list(PushSubscription.objects.all()),[other_device])

    def test_unsubscribe_is_scoped_and_post_only(self):
        self.subscribe()
        self.client.force_login(self.other)
        response = self.client.post(reverse('push_unsubscribe'),{'endpoint':self.payload()['endpoint']},content_type='application/json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(PushSubscription.objects.count(),1)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('push_unsubscribe')).status_code,405)
        self.client.post(reverse('push_unsubscribe'),{'endpoint':self.payload()['endpoint']},content_type='application/json')
        self.assertFalse(PushSubscription.objects.exists())

    def test_subscription_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse('push_subscribe'),self.payload(),content_type='application/json').status_code,403)
        config = client.get(reverse('push_config')).json()
        self.assertEqual(client.post(reverse('push_subscribe'),self.payload(),content_type='application/json',HTTP_X_CSRFTOKEN=config['csrfToken']).status_code,200)

    def test_untrusted_endpoints_and_invalid_keys_are_rejected(self):
        for endpoint in ['http://fcm.googleapis.com/x','https://127.0.0.1/x','https://fcm.googleapis.com.evil.test/x',
                         'https://fcm.googleapis.com:444/x','https://user:pass@fcm.googleapis.com/x','https://[::1]/x']:
            with self.subTest(endpoint=endpoint):
                self.assertEqual(self.subscribe(endpoint=endpoint).status_code,400)
        for keys in [{},[],{'auth':'bad','p256dh':self.keys['p256dh']},{'auth':self.keys['auth'],'p256dh':'AAAA'}]:
            response = self.client.post(reverse('push_subscribe'),{'endpoint':self.payload()['endpoint'],'keys':keys},content_type='application/json')
            self.assertEqual(response.status_code,400)
        self.assertFalse(PushSubscription.objects.exists())

    def test_apple_and_firefox_subscriptions_are_accepted(self):
        for endpoint in ['https://web.push.apple.com/Qdevice','https://updates.push.services.mozilla.com/wpush/v2/device']:
            self.assertEqual(self.subscribe(endpoint=endpoint).status_code,200)

    @override_settings(PUSH_VAPID_PRIVATE_KEY='')
    def test_unconfigured_server_is_reported_without_creating_subscriptions(self):
        self.assertFalse(self.client.get(reverse('push_config')).json()['available'])
        self.assertEqual(self.subscribe().status_code,503)
        self.assertFalse(PushSubscription.objects.exists())

    def test_only_creation_not_edits_enqueues_and_recipients_are_deduplicated(self):
        self.devices()
        with self.captureOnCommitCallbacks(execute=True):
            expense = Expense.objects.create(owner=self.driver,vehicle=self.car,title='New expense',category='other',amount=25,date=timezone.localdate())
        jobs = PushDelivery.objects.filter(event='expense',object_id=expense.pk)
        self.assertEqual(set(jobs.values_list('subscription__user_id',flat=True)),{self.admin.pk,self.owner.pk,self.driver.pk})
        enqueue_creation('expense',expense.pk)
        self.assertEqual(jobs.count(),3)
        with self.captureOnCommitCallbacks(execute=True):
            expense.title='Edited';expense.save()
            self.car.name='Edited car';self.car.save()
        self.assertEqual(PushDelivery.objects.count(),3)

    def test_new_car_notifies_admin_owner_and_assigned_driver(self):
        self.devices()
        with self.captureOnCommitCallbacks(execute=True):
            car = Vehicle.objects.create(owner=self.owner,driver=self.driver,name='New car',plate='N-1')
        self.assertEqual(set(PushDelivery.objects.filter(vehicle=car).values_list('subscription__user_id',flat=True)),{self.admin.pk,self.owner.pk,self.driver.pk})

    def test_rolled_back_creation_never_enqueues(self):
        from django.db import transaction
        self.devices()
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    Expense.objects.create(owner=self.driver,vehicle=self.car,title='Rolled back',category='other',amount=10,date=timezone.localdate())
                    raise ValueError('rollback')
            except ValueError:
                pass
        self.assertFalse(PushDelivery.objects.exists())

    def test_inactive_users_do_not_receive_notifications(self):
        self.devices()
        self.driver.is_active=False;self.driver.save()
        enqueue_creation('expense',self.expense.pk)
        self.assertFalse(PushDelivery.objects.filter(subscription__user=self.driver).exists())

    @patch('ledger.push.webpush')
    def test_worker_sends_to_all_authorized_devices_with_correct_links(self,send):
        self.devices()
        enqueue_creation('expense',self.expense.pk)
        self.assertEqual(process_pending(),3)
        self.assertEqual(send.call_count,3)
        self.assertEqual(PushDelivery.objects.filter(status='sent').count(),3)
        payload = json.loads(send.call_args.kwargs['data'])
        self.assertEqual(payload['title'],'New expense added')
        self.assertEqual(payload['url'],reverse('expenses')+f'?vehicle={self.car.pk}')
        self.assertEqual(send.call_args.kwargs['timeout'],10)
        self.assertEqual(process_pending(),0)

    @patch('ledger.push.webpush')
    def test_removed_assignment_revokes_pending_delivery(self,send):
        self.devices()
        enqueue_creation('expense',self.expense.pk)
        self.car.driver=self.other;self.car.save()
        process_pending()
        self.assertEqual(send.call_count,2)
        self.assertEqual(PushDelivery.objects.get(subscription__user=self.driver).status,'skipped')

    @patch('ledger.push.webpush')
    def test_deleted_expense_is_not_sent(self,send):
        self.devices()
        enqueue_creation('expense',self.expense.pk)
        self.expense.delete()
        process_pending()
        send.assert_not_called()

    @patch('ledger.push.webpush')
    def test_expired_subscription_is_removed(self,send):
        self.subscribe()
        enqueue_creation('expense',self.expense.pk)
        send.side_effect=WebPushException('expired',response=Mock(status_code=410))
        process_pending()
        self.assertFalse(PushSubscription.objects.exists())

    @patch('ledger.push.webpush')
    def test_temporary_failure_is_retried_and_permanent_failure_stops(self,send):
        self.subscribe()
        enqueue_creation('expense',self.expense.pk)
        send.side_effect=WebPushException('unavailable',response=Mock(status_code=503))
        with self.assertLogs('ledger.push',level='WARNING'):
            process_pending()
        job=PushDelivery.objects.get()
        self.assertEqual(job.status,'pending')
        self.assertEqual(job.attempts,1)
        self.assertGreater(job.available_at,timezone.now())
        self.assertEqual(process_pending(),0)
        job.available_at=timezone.now()-timedelta(seconds=1);job.save()
        send.side_effect=WebPushException('invalid',response=Mock(status_code=400))
        with self.assertLogs('ledger.push',level='WARNING'):
            process_pending()
        job.refresh_from_db()
        self.assertEqual(job.status,'failed')

    def test_stale_worker_lease_can_be_recovered(self):
        self.subscribe()
        enqueue_creation('expense',self.expense.pk)
        claimed=claim_delivery()
        self.assertIsNotNone(claimed)
        self.assertIsNone(claim_delivery())
        PushDelivery.objects.filter(pk=claimed).update(available_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(claim_delivery(),claimed)

    @patch('deploy.start.signal.signal')
    @patch('deploy.start.subprocess.Popen')
    def test_container_starts_and_stops_push_worker_with_web_service(self,popen,signal):
        from deploy.start import run_with_push_worker
        web=Mock();web.poll.return_value=0;web.wait.return_value=0
        worker=Mock();worker.poll.return_value=None
        popen.side_effect=[web,worker]
        self.assertEqual(run_with_push_worker(['gunicorn','config.wsgi:application']),0)
        self.assertIn('send_push_notifications',popen.call_args_list[1].args[0])
        worker.terminate.assert_called_once()
