from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Booking, Customer, Document, Payment, Vehicle


class PublicPageTests(TestCase):
    def test_home_page_seeds_demo_vehicles(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertGreater(Vehicle.objects.count(), 0)
        self.assertContains(response, 'Featured Fleet')


class BookingWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='customer1@example.com', password='pass12345')
        self.customer = Customer.objects.get(user=self.user)
        self.customer.phone = '0712345678'
        self.customer.national_id_number = '12345678'
        self.customer.address = 'Nairobi'
        self.customer.save()
        Document.objects.create(
            customer=self.customer,
            national_id_file=SimpleUploadedFile('id.pdf', b'id'),
            driver_license_file=SimpleUploadedFile('dl.pdf', b'dl'),
            verification_status='Approved',
        )
        self.vehicle = Vehicle.objects.create(
            name='Toyota Corolla',
            model='Axio',
            plate_number='KDA 123A',
            vehicle_type='Sedan',
            transmission='Automatic',
            fuel_type='Petrol',
            seat_count=5,
            door_count=4,
            year=2024,
            mileage=12000,
            engine_size='2.0L',
            drive_type='FWD',
            pickup_location='Nairobi, Kenya',
            dropoff_location='Nairobi, Kenya',
            rating=Decimal('4.6'),
            review_count=120,
            price_per_day=Decimal('2500.00'),
        )

    def test_booking_creates_payment_and_updates_vehicle(self):
        self.client.login(username='customer1@example.com', password='pass12345')
        response = self.client.post(
            reverse('book_vehicle', args=[self.vehicle.id]),
            {
                'pickup_location': 'Nairobi, Kenya',
                'dropoff_location': 'Nairobi, Kenya',
                'start_date': '2026-05-10',
                'end_date': '2026-05-12',
                'delivery_location': 'Westlands',
            },
        )

        self.assertEqual(response.status_code, 200)
        booking = Booking.objects.get()
        payment = Payment.objects.get(booking=booking)
        self.vehicle.refresh_from_db()

        self.assertEqual(booking.total_amount, Decimal('7500.00'))
        self.assertEqual(booking.status, 'Pending')
        self.assertEqual(booking.pickup_location, 'Nairobi, Kenya')
        self.assertEqual(payment.amount, Decimal('7500.00'))
        self.assertEqual(payment.status, 'Pending')
        self.assertEqual(self.vehicle.status, 'Booked')
        self.assertEqual(self.vehicle.next_available_date, date(2026, 5, 12))
        self.assertTrue(hasattr(booking, 'deliveryagreement'))

    def test_booking_rejects_overlapping_dates(self):
        self.client.login(username='customer1@example.com', password='pass12345')
        Booking.objects.create(
            customer=self.customer,
            vehicle=self.vehicle,
            pickup_location='Nairobi, Kenya',
            dropoff_location='Nairobi, Kenya',
            start_date=date(2026, 5, 10),
            end_date=date(2026, 5, 12),
            total_amount=Decimal('7500.00'),
            status='Confirmed',
        )

        response = self.client.post(
            reverse('book_vehicle', args=[self.vehicle.id]),
            {
                'pickup_location': 'Nairobi, Kenya',
                'dropoff_location': 'Nairobi, Kenya',
                'start_date': '2026-05-11',
                'end_date': '2026-05-13',
            },
        )

        self.assertContains(response, 'already booked')
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 0)

    def test_booking_requires_approved_documents(self):
        self.client.login(username='customer1@example.com', password='pass12345')
        Document.objects.filter(customer=self.customer).update(verification_status='Pending')

        response = self.client.post(
            reverse('book_vehicle', args=[self.vehicle.id]),
            {
                'pickup_location': 'Nairobi, Kenya',
                'dropoff_location': 'Nairobi, Kenya',
                'start_date': '2026-05-10',
                'end_date': '2026-05-12',
            },
        )

        self.assertContains(response, 'documents must be approved')
        self.assertEqual(Booking.objects.count(), 0)

    def test_booking_redirects_anonymous_users_to_auth(self):
        response = self.client.post(
            reverse('book_vehicle', args=[self.vehicle.id]),
            {
                'pickup_location': 'Nairobi, Kenya',
                'dropoff_location': 'Nairobi, Kenya',
                'start_date': '2026-05-10',
                'end_date': '2026-05-12',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('auth_page'), response.url)

    def test_account_dashboard_requires_login(self):
        response = self.client.get(reverse('account_dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('auth_page'), response.url)

    def test_document_upload_resets_status_to_pending(self):
        self.client.login(username='customer1@example.com', password='pass12345')
        Document.objects.filter(customer=self.customer).update(verification_status='Approved')

        response = self.client.post(
            reverse('account_dashboard'),
            {
                'action': 'documents',
                'national_id_file': SimpleUploadedFile('updated-id.pdf', b'new-id'),
                'driver_license_file': SimpleUploadedFile('updated-dl.pdf', b'new-dl'),
            },
        )

        self.assertEqual(response.status_code, 302)
        document = Document.objects.get(customer=self.customer)
        self.assertEqual(document.verification_status, 'Pending')


class ApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='apiuser@example.com', password='pass12345')
        self.customer = Customer.objects.get(user=self.user)
        self.customer.phone = '0700000000'
        self.customer.national_id_number = '99887766'
        self.customer.address = 'Nairobi'
        self.customer.save()
        self.vehicle = Vehicle.objects.create(
            name='Honda Fit',
            model='Hybrid',
            plate_number='KDD 001X',
            vehicle_type='Hatchback',
            transmission='Automatic',
            fuel_type='Hybrid',
            price_per_day=Decimal('3000.00'),
            status='Available',
        )

    def test_api_vehicle_list_returns_results(self):
        response = self.client.get(reverse('api_vehicle_list'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['results'][0]['name'], 'Honda Fit')

    def test_api_my_bookings_requires_auth(self):
        response = self.client.get(reverse('api_my_bookings'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('auth_page'), response.url)

    def test_user_creation_auto_creates_customer_profile(self):
        created_user = User.objects.create_user(username='newuser@example.com', password='pass12345')

        self.assertTrue(Customer.objects.filter(user=created_user).exists())

    def test_api_my_profile_returns_logged_in_user_details(self):
        self.client.login(username='apiuser@example.com', password='pass12345')

        response = self.client.get(reverse('api_my_profile'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['email'], 'apiuser@example.com')
        self.assertEqual(payload['phone'], '0700000000')

    def test_api_my_profile_updates_customer_and_user_details(self):
        self.client.login(username='apiuser@example.com', password='pass12345')

        response = self.client.post(
            reverse('api_my_profile'),
            data={
                'full_name': 'API User',
                'email': 'updated@example.com',
                'phone': '0711223344',
                'national_id_number': '44556677',
                'address': 'Westlands',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.customer.refresh_from_db()
        self.assertEqual(self.user.username, 'updated@example.com')
        self.assertEqual(self.user.first_name, 'API User')
        self.assertEqual(self.customer.phone, '0711223344')
        self.assertEqual(self.customer.address, 'Westlands')

    def test_api_my_documents_returns_review_metadata(self):
        self.client.login(username='apiuser@example.com', password='pass12345')
        reviewer = User.objects.create_user(username='reviewer@example.com', password='pass12345')
        Document.objects.create(
            customer=self.customer,
            national_id_file=SimpleUploadedFile('id.pdf', b'id'),
            driver_license_file=SimpleUploadedFile('dl.pdf', b'dl'),
            verification_status='Rejected',
            review_notes='License image is blurry.',
            reviewed_by=reviewer,
            reviewed_at=timezone.now(),
        )

        response = self.client.get(reverse('api_my_documents'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['exists'])
        self.assertEqual(payload['status'], 'Rejected')
        self.assertEqual(payload['review_notes'], 'License image is blurry.')
        self.assertEqual(payload['reviewed_by'], 'reviewer@example.com')

    def test_api_cancel_booking_cancels_future_booking(self):
        self.client.login(username='apiuser@example.com', password='pass12345')
        start_date = timezone.localdate() + timedelta(days=4)
        end_date = start_date + timedelta(days=2)
        booking = Booking.objects.create(
            customer=self.customer,
            vehicle=self.vehicle,
            pickup_location='Nairobi, Kenya',
            dropoff_location='Nairobi, Kenya',
            start_date=start_date,
            end_date=end_date,
            total_amount=Decimal('9000.00'),
            status='Confirmed',
        )
        self.vehicle.refresh_availability()

        response = self.client.post(
            reverse('api_cancel_booking', args=[booking.id]),
            data={'reason': 'Change of travel plans'},
        )

        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        self.vehicle.refresh_from_db()
        self.assertEqual(booking.status, 'Cancelled')
        self.assertEqual(booking.cancel_reason, 'Change of travel plans')
        self.assertIsNotNone(booking.cancelled_at)
        self.assertEqual(self.vehicle.status, 'Available')
