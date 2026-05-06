from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Booking, Customer, Document, Payment, Vehicle


class PublicPageTests(TestCase):
    def test_home_page_seeds_demo_vehicles(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertGreater(Vehicle.objects.count(), 0)
        self.assertContains(response, 'Popular Vehicles')


class BookingWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='customer1@example.com', password='pass12345')
        self.customer = Customer.objects.create(
            user=self.user,
            phone='0712345678',
            national_id_number='12345678',
            address='Nairobi',
        )
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
