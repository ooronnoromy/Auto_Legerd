import io
import tempfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .models import Expense, Reminder, User, Vehicle


class DriverAssignmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('01911111111', password='Admin-example-123!')
        cls.driver = User.objects.create_user('01711111111', password='Driver-example-123!')
        cls.other = User.objects.create_user('01811111111', password='Other-example-123!')
        cls.car = Vehicle.objects.create(owner=cls.admin, driver=cls.driver, name='Assigned Axio', plate='AX-1')
        cls.other_car = Vehicle.objects.create(owner=cls.admin, driver=cls.other, name='Other Car', plate='OT-1')
        cls.free_car = Vehicle.objects.create(owner=cls.admin, name='Available Car', plate='FR-1')
        cls.expense = Expense.objects.create(owner=cls.admin, vehicle=cls.car, category='other',
            title='Car insurance', amount=Decimal('100'), date=timezone.localdate())
        cls.reminder = Reminder.objects.create(owner=cls.admin, vehicle=cls.car, title='Assigned service')

    def setUp(self):
        self.client.force_login(self.admin)

    def user_payload(self, **overrides):
        return {'username': '01611111111', 'first_name': 'New Driver',
                'password1': 'New-driver-example-123!', 'password2': 'New-driver-example-123!',
                'vehicle': self.free_car.pk, **overrides}

    def test_create_driver_assigns_car_without_transferring_ownership(self):
        response = self.client.post(reverse('user_add'), self.user_payload())
        self.assertRedirects(response, reverse('users'))
        driver = User.objects.get(username='01611111111')
        self.free_car.refresh_from_db()
        self.assertEqual(self.free_car.driver, driver)
        self.assertEqual(self.free_car.owner, self.admin)
        self.assertFalse(driver.is_staff)
        self.assertTrue(driver.check_password('New-driver-example-123!'))
        self.assertContains(self.client.get(reverse('users')), self.free_car.name)

    def test_django_admin_can_create_driver_with_car_assignment(self):
        response = self.client.get(reverse('admin:ledger_user_add'))
        self.assertContains(response, 'Assign car')
        response = self.client.post(reverse('admin:ledger_user_add'), {
            'username': '01611111111', 'password1': 'New-driver-example-123!',
            'password2': 'New-driver-example-123!', 'usable_password': 'true',
            'vehicle': self.free_car.pk, '_save': 'Save'})
        self.assertEqual(response.status_code, 302)
        self.free_car.refresh_from_db()
        self.assertEqual(self.free_car.driver.username, '01611111111')
        self.assertEqual(self.free_car.owner, self.admin)

    def test_creation_requires_valid_unassigned_car_and_does_not_create_partial_user(self):
        for car_id in ['', self.car.pk, 999999]:
            with self.subTest(car_id=car_id):
                response = self.client.post(reverse('user_add'), self.user_payload(vehicle=car_id))
                self.assertIn('vehicle', response.context['form'].errors)
                self.assertFalse(User.objects.filter(username='01611111111').exists())
        self.car.refresh_from_db()
        self.assertEqual(self.car.driver, self.driver)

    def test_assignment_endpoints_require_staff(self):
        url = reverse('user_assign', args=[self.other.pk])
        self.client.force_login(self.driver)
        self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(self.client.post(url, {'vehicles': [self.car.pk]}).status_code, 302)
        self.assertEqual(self.client.post(reverse('user_add'), self.user_payload()).status_code, 302)
        self.assertFalse(User.objects.filter(username='01611111111').exists())

    def test_admin_can_assign_multiple_cars_and_remove_assignments(self):
        url = reverse('user_assign', args=[self.driver.pk])
        self.assertContains(self.client.get(url), self.free_car.name)
        self.assertRedirects(self.client.post(url, {'vehicles': [self.car.pk, self.free_car.pk]}), reverse('users'))
        self.assertEqual(set(self.driver.assigned_vehicles.values_list('pk', flat=True)), {self.car.pk, self.free_car.pk})
        self.assertRedirects(self.client.post(url, {}), reverse('users'))
        self.assertFalse(self.driver.assigned_vehicles.exists())
        self.assertTrue(Vehicle.objects.filter(pk=self.car.pk, owner=self.admin).exists())

    def test_assignment_form_does_not_silently_take_another_drivers_car(self):
        response = self.client.post(reverse('user_assign', args=[self.driver.pk]), {'vehicles': [self.other_car.pk]})
        self.assertIn('vehicles', response.context['form'].errors)
        self.other_car.refresh_from_db()
        self.assertEqual(self.other_car.driver, self.other)
        self.car.refresh_from_db()
        self.assertEqual(self.car.driver, self.driver)

    def test_assigned_driver_sees_car_and_its_records_across_app(self):
        self.client.force_login(self.driver)
        for page in ['dashboard', 'vehicles', 'expenses', 'reminders', 'reports', 'profile', 'service_centers']:
            with self.subTest(page=page):
                response = self.client.get(reverse(page))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, self.other_car.name)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['vehicle'], self.car)
        self.assertEqual(response.context['total'], Decimal('100'))
        self.assertEqual(response.context['pending_reminder_count'], 1)
        self.assertContains(self.client.get(reverse('expenses')), self.expense.title)
        self.assertContains(self.client.get(reverse('export_csv')), self.expense.title)
        self.assertEqual(self.client.get(reverse('reports')).context['grand'], Decimal('100'))
        response = self.client.get(reverse('vehicle_detail', args=[self.car.pk]))
        self.assertEqual(response.context['total'], Decimal('100'))
        self.assertNotContains(response, reverse('vehicle_edit', args=[self.car.pk]))
        self.assertEqual(self.client.get(reverse('vehicle_edit', args=[self.car.pk])).status_code, 404)

    def test_driver_logs_fuel_and_reminders_for_assigned_car_and_admin_sees_them(self):
        self.client.force_login(self.driver)
        response = self.client.get(reverse('expense_add'), {'vehicle': self.car.pk})
        self.assertEqual(response.context['form'].initial['vehicle'], self.car.pk)
        self.assertRedirects(self.client.post(reverse('expense_add'), {'vehicle': self.car.pk,
            'category': 'fuel', 'title': 'Driver fuel', 'amount': '250', 'liters': '2.5',
            'date': timezone.localdate().isoformat(), 'odometer': 500}), reverse('expenses'))
        fuel = Expense.objects.get(title='Driver fuel')
        self.assertEqual(fuel.owner, self.driver)
        self.car.refresh_from_db()
        self.assertEqual(self.car.odometer, 500)
        self.assertRedirects(self.client.post(reverse('reminder_add'), {'vehicle': self.car.pk,
            'title': 'Driver reminder', 'due_odometer': 1000}), reverse('reminders'))
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('expenses')), 'Driver fuel')
        self.assertContains(self.client.get(reverse('reminders')), 'Driver reminder')
        self.assertEqual(self.client.get(reverse('vehicle_detail', args=[self.car.pk])).context['total'], Decimal('350'))

    def test_unassigned_car_cannot_be_viewed_or_submitted_by_driver(self):
        self.client.force_login(self.driver)
        self.assertEqual(self.client.get(reverse('vehicle_detail', args=[self.other_car.pk])).status_code, 404)
        response = self.client.post(reverse('expense_add'), {'vehicle': self.other_car.pk,
            'category': 'other', 'title': 'Invalid', 'amount': '5', 'date': timezone.localdate().isoformat()})
        self.assertIn('vehicle', response.context['form'].errors)
        response = self.client.post(reverse('reminder_add'), {'vehicle': self.other_car.pk, 'title': 'Invalid'})
        self.assertIn('vehicle', response.context['form'].errors)

    def test_reassignment_revokes_old_driver_access_including_their_own_records(self):
        expense = Expense.objects.create(owner=self.driver, vehicle=self.car, category='other',
            title='Previous driver expense', amount=10, date=timezone.localdate())
        self.car.driver = self.other
        self.car.save()
        self.client.force_login(self.driver)
        self.assertEqual(self.client.get(reverse('vehicle_detail', args=[self.car.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('expense_edit', args=[expense.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('expense_delete', args=[expense.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('reminder_edit', args=[self.reminder.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('reminder_toggle', args=[self.reminder.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('export_csv')), expense.title)
        self.client.force_login(self.other)
        self.assertContains(self.client.get(reverse('expenses')), expense.title)

    def test_admin_edits_car_assignment_without_changing_owner(self):
        self.car.owner = self.driver
        self.car.save()
        response = self.client.post(reverse('vehicle_edit', args=[self.car.pk]), {
            'name': self.car.name, 'plate': self.car.plate, 'fuel_type': 'Petrol',
            'odometer': 0, 'driver': self.other.pk})
        self.assertRedirects(response, reverse('vehicles'))
        self.car.refresh_from_db()
        self.assertEqual(self.car.driver, self.other)
        self.assertEqual(self.car.owner, self.driver)
        self.client.force_login(self.driver)
        self.client.post(reverse('vehicle_edit', args=[self.car.pk]), {
            'name': self.car.name, 'plate': self.car.plate, 'fuel_type': 'Petrol',
            'odometer': 0, 'driver': self.driver.pk})
        self.car.refresh_from_db()
        self.assertEqual(self.car.driver, self.other)

    def test_assigned_driver_can_fetch_photos_and_loses_access_when_unassigned(self):
        photo = io.BytesIO()
        Image.new('RGB', (2, 2)).save(photo, format='PNG')
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory, DEBUG=False):
            self.car.photo.save('car.png', SimpleUploadedFile('car.png', photo.getvalue()), save=True)
            self.expense.receipt_photo.save('receipt.png', SimpleUploadedFile('receipt.png', photo.getvalue()), save=True)
            self.client.force_login(self.driver)
            for field in [self.car.photo, self.expense.receipt_photo]:
                response = self.client.get(field.url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(b''.join(response.streaming_content), photo.getvalue())
            self.car.driver = None
            self.car.save()
            for field in [self.car.photo, self.expense.receipt_photo]:
                self.assertEqual(self.client.get(field.url).status_code, 404)

    def test_deleting_driver_preserves_admin_owned_car(self):
        self.driver.delete()
        self.car.refresh_from_db()
        self.assertIsNone(self.car.driver)
        self.assertEqual(self.car.owner, self.admin)
