import csv
import io
import os
import subprocess
import sys
import tempfile
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from contextlib import redirect_stderr

from django.conf import settings
from django.db import DatabaseError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse

from .models import Expense, Reminder, User, Vehicle


class ApplicationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('01712345678', password='Test-driver-82!')
        cls.other = User.objects.create_user('01812345678', password='Test-driver-83!')
        cls.admin = User.objects.create_superuser('01912345678', password='Test-admin-84!')
        cls.vehicle = Vehicle.objects.create(owner=cls.user, name='My Car', plate='DHAKA-1', odometer=100)
        cls.foreign_vehicle = Vehicle.objects.create(owner=cls.other, name='Private Car', plate='DHAKA-2')
        cls.expense = Expense.objects.create(owner=cls.user, vehicle=cls.vehicle, category='fuel',
            title='Fuel stop', amount=Decimal('500.00'), date=date.today(), liters=Decimal('5.00'))
        cls.foreign_expense = Expense.objects.create(owner=cls.other, vehicle=cls.foreign_vehicle,
            category='other', title='Private expense', amount=Decimal('900.00'), date=date.today())
        cls.reminder = Reminder.objects.create(owner=cls.user, vehicle=cls.vehicle, title='Service', due_odometer=500)
        cls.foreign_reminder = Reminder.objects.create(owner=cls.other, vehicle=cls.foreign_vehicle, title='Private service')

    def setUp(self):
        self.client.force_login(self.user)

    def test_authenticated_pages_render(self):
        pages = ['dashboard', 'vehicles', 'vehicle_add', 'expenses', 'expense_add',
                 'reminders', 'reminder_add', 'reports']
        for name in pages:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        for name, obj in [('vehicle_edit', self.vehicle), ('expense_edit', self.expense), ('reminder_edit', self.reminder)]:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name, args=[obj.pk])).status_code, 200)

    def test_login_and_logout(self):
        self.client.logout()
        self.assertRedirects(self.client.get('/'), '/login/?next=/')
        response = self.client.post(reverse('login'), {'username': self.user.username, 'password': 'Test-driver-82!'})
        self.assertRedirects(response, '/')
        self.assertRedirects(self.client.post(reverse('logout')), '/login/')

    def test_dashboard_vehicle_summary_uses_only_selected_vehicle(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['vehicle_total'], Decimal('500.00'))
        self.assertEqual(response.context['last_fuel'], self.expense)
        self.assertIsNone(response.context['last_service'])
        self.assertNotContains(response, 'Private Car')

    def test_expense_search_preserves_owner_scope(self):
        response = self.client.get(reverse('expenses'), {'q': 'Fuel stop'})
        self.assertEqual(list(response.context['items']), [self.expense])
        response = self.client.get(reverse('expenses'), {'q': 'Private'})
        self.assertEqual(list(response.context['items']), [])
        response = self.client.get(reverse('expenses'), {'q': 'My Car'})
        self.assertEqual(list(response.context['items']), [self.expense])

    def test_other_cost_card_excludes_fuel_and_maintenance(self):
        parking = Expense.objects.create(owner=self.user, vehicle=self.vehicle,
            category='parking', title='Parking', amount=Decimal('50.00'), date=date.today())
        response = self.client.get(reverse('expenses'), {'group': 'other'})
        self.assertEqual(list(response.context['items']), [parking])

    def test_vehicle_creation(self):
        response = self.client.post(reverse('vehicle_add'), {'name': 'New Car', 'plate': 'NEW-1', 'fuel_type': 'Petrol', 'odometer': 25})
        self.assertRedirects(response, reverse('vehicles'))
        self.assertEqual(Vehicle.objects.get(name='New Car').owner, self.user)

    def test_expense_creation_updates_odometer(self):
        response = self.client.post(reverse('expense_add'), {'vehicle': self.vehicle.pk, 'category': 'fuel',
            'title': 'Refuel', 'amount': '250.00', 'date': date.today().isoformat(), 'liters': '2.50', 'odometer': 200})
        self.assertRedirects(response, reverse('expenses'))
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.odometer, 200)
        self.assertEqual(Expense.objects.get(title='Refuel').owner, self.user)

    def test_fuel_requires_positive_quantity(self):
        response = self.client.post(reverse('expense_add'), {'vehicle': self.vehicle.pk, 'category': 'fuel',
            'title': 'Bad fuel', 'amount': '250.00', 'date': date.today().isoformat(), 'liters': '-1'})
        self.assertContains(response, 'Enter a positive fuel quantity.')
        self.assertFalse(Expense.objects.filter(title='Bad fuel').exists())

    def test_cannot_assign_another_users_vehicle(self):
        for name, payload in [
            ('expense_add', {'vehicle': self.foreign_vehicle.pk, 'category': 'other', 'title': 'Invalid', 'amount': '10', 'date': date.today().isoformat()}),
            ('reminder_add', {'vehicle': self.foreign_vehicle.pk, 'title': 'Invalid', 'due_odometer': 200}),
        ]:
            with self.subTest(page=name):
                response = self.client.post(reverse(name), payload)
                self.assertEqual(response.status_code, 200)
                self.assertIn('vehicle', response.context['form'].errors)
        self.assertFalse(Expense.objects.filter(title='Invalid').exists())
        self.assertFalse(Reminder.objects.filter(title='Invalid').exists())

    def test_foreign_records_are_inaccessible(self):
        for name, obj in [('vehicle_edit', self.foreign_vehicle), ('expense_edit', self.foreign_expense), ('reminder_edit', self.foreign_reminder)]:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name, args=[obj.pk])).status_code, 404)
        response = self.client.post(reverse('expense_delete', args=[self.foreign_expense.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Expense.objects.filter(pk=self.foreign_expense.pk).exists())

    def test_lists_and_reports_exclude_other_users(self):
        for name in ['dashboard', 'vehicles', 'expenses', 'reminders', 'reports']:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertNotContains(response, 'Private')
        response = self.client.get(reverse('reports'))
        self.assertEqual(response.context['grand'], Decimal('500.00'))

    def test_csv_exports_only_own_expenses(self):
        response = self.client.get(reverse('export_csv'))
        rows = list(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(len(rows), 2)
        self.assertIn('Fuel stop', rows[1])
        self.assertNotIn('Private expense', response.content.decode())

    def test_reminder_creation_and_completion(self):
        response = self.client.post(reverse('reminder_add'), {'vehicle': self.vehicle.pk, 'title': 'Oil change', 'due_odometer': 1000})
        self.assertRedirects(response, reverse('reminders'))
        item = Reminder.objects.get(title='Oil change')
        response = self.client.post(reverse('reminder_edit', args=[item.pk]), {'vehicle': self.vehicle.pk,
            'title': item.title, 'due_odometer': 1000, 'completed': 'on'})
        self.assertRedirects(response, reverse('reminders'))
        item.refresh_from_db()
        self.assertTrue(item.completed)

    def test_expense_delete_requires_post(self):
        url = reverse('expense_delete', args=[self.expense.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), reverse('expenses'))
        self.assertFalse(Expense.objects.filter(pk=self.expense.pk).exists())

    def test_staff_pages_and_user_creation(self):
        for name in ['users', 'user_add']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)
        self.client.force_login(self.admin)
        for name in ['users', 'user_add', 'admin:index']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        response = self.client.post(reverse('user_add'), {'username': '01612345678',
            'password1': 'Created-driver-85!', 'password2': 'Created-driver-85!', 'vehicle': self.vehicle.pk})
        self.assertRedirects(response, reverse('users'))
        self.assertTrue(User.objects.get(username='01612345678').check_password('Created-driver-85!'))
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.driver.username, '01612345678')
        self.assertEqual(self.vehicle.owner, self.user)

    def test_pwa_endpoints_are_public(self):
        self.client.logout()
        response = self.client.get(reverse('manifest'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['icons']), 2)
        self.assertEqual(self.client.get(reverse('service_worker')).status_code, 200)

    def test_mobile_navigation_and_screens(self):
        for page in ['dashboard', 'vehicles', 'expenses', 'profile', 'profile_edit', 'password_change', 'help', 'service_centers', 'reports', 'reminders']:
            with self.subTest(page=page):
                response = self.client.get(reverse(page))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'aria-label="Main navigation"')
                for destination in ['dashboard', 'vehicles', 'expense_add', 'expenses', 'profile']:
                    self.assertContains(response, f'href="{reverse(destination)}"')

    def test_car_details_are_private_and_show_real_totals(self):
        response = self.client.get(reverse('vehicle_detail', args=[self.vehicle.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total'], Decimal('500.00'))
        self.assertEqual(response.context['liters'], Decimal('5.00'))
        self.assertNotContains(response, 'Private Car')
        self.assertEqual(self.client.get(reverse('vehicle_detail', args=[self.foreign_vehicle.pk])).status_code, 404)

    def test_expense_shortcuts_prefill_type_and_own_vehicle(self):
        response = self.client.get(reverse('expense_add'), {'category': 'fuel', 'vehicle': self.vehicle.pk})
        self.assertEqual(response.context['form'].initial['category'], 'fuel')
        self.assertEqual(str(response.context['form'].initial['vehicle']), str(self.vehicle.pk))
        response = self.client.get(reverse('expense_add'), {'category': 'maintenance', 'vehicle': self.foreign_vehicle.pk})
        self.assertEqual(response.context['form'].initial['category'], 'maintenance')
        self.assertNotIn('vehicle', response.context['form'].initial)

    def test_profile_edit_cannot_change_permissions_or_other_users(self):
        response = self.client.post(reverse('profile_edit'), {'username': '01799999999', 'first_name': 'Driver',
            'last_name': 'One', 'email': 'driver@example.com', 'is_staff': 'on', 'is_superuser': 'on'})
        self.assertRedirects(response, reverse('profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, '01799999999')
        self.assertEqual(self.user.email, 'driver@example.com')
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.other.refresh_from_db()
        self.assertEqual(self.other.username, '01812345678')

    def test_profile_phone_validation_and_uniqueness(self):
        for phone in ['not-a-phone', self.other.username]:
            with self.subTest(phone=phone):
                response = self.client.post(reverse('profile_edit'), {'username': phone})
                self.assertEqual(response.status_code, 200)
                self.assertIn('username', response.context['form'].errors)

    def test_password_change_retains_session_and_rejects_wrong_password(self):
        data = {'old_password': 'wrong-password', 'new_password1': 'Changed-driver-96!', 'new_password2': 'Changed-driver-96!'}
        response = self.client.post(reverse('password_change'), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('old_password', response.context['form'].errors)
        data['old_password'] = 'Test-driver-82!'
        self.assertRedirects(self.client.post(reverse('password_change'), data), reverse('profile'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Changed-driver-96!'))
        self.assertEqual(self.client.get(reverse('profile')).status_code, 200)

    def test_reminder_calendar_filters_dates_and_completes_own_items(self):
        self.reminder.due_date = date.today()
        self.reminder.save()
        response = self.client.get(reverse('reminders'), {'day': date.today().isoformat()})
        self.assertEqual(list(response.context['items']), [self.reminder])
        self.assertTrue(any(day['has_reminder'] for week in response.context['calendar_weeks'] for day in week))
        self.assertRedirects(self.client.post(reverse('reminder_toggle', args=[self.reminder.pk])), reverse('reminders'))
        self.reminder.refresh_from_db()
        self.assertTrue(self.reminder.completed)
        self.assertEqual(self.client.get(reverse('reminder_toggle', args=[self.reminder.pk])).status_code, 405)
        self.assertEqual(self.client.post(reverse('reminder_toggle', args=[self.foreign_reminder.pk])).status_code, 404)
        response = self.client.get(reverse('reminders'), {'status': 'upcoming', 'view': 'list'})
        self.assertNotIn(self.reminder, response.context['items'])

    def test_analytics_period_and_vehicle_history_filters(self):
        Expense.objects.create(owner=self.user, vehicle=self.vehicle, category='maintenance', title='Earlier service',
            amount=Decimal('100.00'), date=date(2020, 1, 5), station='My Service Center')
        response = self.client.get(reverse('reports'), {'period': 'custom', 'start': '2020-01-01', 'end': '2020-01-31'})
        self.assertEqual(response.context['grand'], Decimal('100.00'))
        self.assertEqual(response.context['count'], 1)
        self.assertEqual(response.context['totals'][0]['label'], 'Maintenance')
        response = self.client.get(reverse('reports'), {'period': 'custom', 'start': 'invalid', 'end': '2020-01-31'})
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('expenses'), {'vehicle': self.foreign_vehicle.pk})
        self.assertEqual(len(response.context['items']), 0)
        response = self.client.get(reverse('expenses'), {'station': 'My Service Center'})
        self.assertEqual(len(response.context['items']), 1)
        self.assertContains(self.client.get(reverse('service_centers')), 'My Service Center')

    def test_profile_and_account_endpoints_require_login(self):
        self.client.logout()
        for page in ['profile', 'profile_edit', 'password_change', 'service_centers', 'help']:
            self.assertEqual(self.client.get(reverse(page)).status_code, 302)

    def test_healthcheck_requires_no_login_and_checks_database(self):
        self.client.logout()
        response = self.client.get(reverse('healthcheck'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        self.assertIn('no-store', response.headers['Cache-Control'])
        with patch('ledger.views.connection.cursor', side_effect=DatabaseError('private database detail')):
            response = self.client.get(reverse('healthcheck'))
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, 'private database detail', status_code=503)

    def test_uploaded_photos_require_owner_or_staff_in_production(self):
        from PIL import Image
        photo = io.BytesIO()
        Image.new('RGB', (2, 2)).save(photo, format='PNG')
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory, DEBUG=False):
            self.vehicle.photo.save('vehicle.png', SimpleUploadedFile('vehicle.png', photo.getvalue()), save=True)
            self.expense.receipt_photo.save('receipt.png', SimpleUploadedFile('receipt.png', photo.getvalue()), save=True)
            self.expense.pump_photo.save('pump.png', SimpleUploadedFile('pump.png', photo.getvalue()), save=True)
            for field in [self.vehicle.photo, self.expense.receipt_photo, self.expense.pump_photo]:
                url = field.url
                with self.subTest(url=url):
                    self.client.force_login(self.user)
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(b''.join(response.streaming_content), photo.getvalue())
                    self.assertIn('no-store', response.headers['Cache-Control'])
                    self.client.force_login(self.other)
                    self.assertEqual(self.client.get(url).status_code, 404)
                    self.client.force_login(self.admin)
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(b''.join(response.streaming_content), photo.getvalue())
                    self.client.logout()
                    self.assertEqual(self.client.get(url).status_code, 302)


class ProductionConfigurationTests(SimpleTestCase):
    def test_railway_starts_without_optional_media_volume(self):
        from deploy.start import prepare_media
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with redirect_stderr(output):
                prepare_media(os.path.join(directory, 'media'), {'RAILWAY_ENVIRONMENT_ID': 'test'})
            self.assertTrue(os.path.isdir(os.path.join(directory, 'media')))
            self.assertIn('temporary storage', output.getvalue())

    def test_railway_uses_persistent_media_without_warning(self):
        from deploy.start import prepare_media
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with redirect_stderr(output):
                prepare_media(os.path.join(directory, 'media'), {
                    'RAILWAY_ENVIRONMENT_ID': 'test', 'RAILWAY_VOLUME_MOUNT_PATH': directory,
                })
            self.assertTrue(os.path.isdir(os.path.join(directory, 'media')))
            self.assertEqual(output.getvalue(), '')

    def production_check(self, **overrides):
        environment = {
            **os.environ,
            'DJANGO_SETTINGS_MODULE': 'config.production',
            'SECRET_KEY': 'Railway-test-secret-with-at-least-fifty-characters-1234567890',
            'DATABASE_URL': 'postgresql://test:test@localhost:5432/test',
            'RAILWAY_PUBLIC_DOMAIN': 'autoledger-test.up.railway.app',
            **overrides,
        }
        return subprocess.run([sys.executable, 'manage.py', 'check', '--deploy', '--fail-level', 'WARNING'],
            cwd=settings.BASE_DIR, env=environment, capture_output=True, text=True)

    def test_production_passes_django_deployment_checks(self):
        result = self.production_check()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_rejects_placeholder_secret(self):
        result = self.production_check(SECRET_KEY='replace-this-secret')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Set SECRET_KEY', result.stderr)

    def test_production_rejects_missing_postgres_url(self):
        result = self.production_check(DATABASE_URL='')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Production requires a PostgreSQL DATABASE_URL', result.stderr)
