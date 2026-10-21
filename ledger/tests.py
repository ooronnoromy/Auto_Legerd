import csv
import io
import os
import subprocess
import sys
import tempfile
from datetime import date
from decimal import Decimal
from unittest.mock import patch

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
            'password1': 'Created-driver-85!', 'password2': 'Created-driver-85!'})
        self.assertRedirects(response, reverse('users'))
        self.assertTrue(User.objects.get(username='01612345678').check_password('Created-driver-85!'))

    def test_pwa_endpoints_are_public(self):
        self.client.logout()
        response = self.client.get(reverse('manifest'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['icons']), 2)
        self.assertEqual(self.client.get(reverse('service_worker')).status_code, 200)

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
