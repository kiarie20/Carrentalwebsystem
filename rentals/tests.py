from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Booking, Customer, Document, Payment, Vehicle


class BookingWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='customer1', password='pass12345')
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
            price_per_day=Decimal('2500.00'),
        )

    def test_booking_creates_payment_and_updates_vehicle(self):
        response = self.client.post(
            reverse('book_vehicle', args=[self.vehicle.id]),
            {
                'customer_id': self.customer.id,
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
        self.assertEqual(payment.amount, Decimal('7500.00'))
        self.assertEqual(payment.status, 'Pending')
        self.assertEqual(self.vehicle.status, 'Booked')
        self.assertEqual(self.vehicle.next_available_date, date(2026, 5, 12))
        self.assertTrue(hasattr(booking, 'deliveryagreement'))

    def test_booking_rejects_overlapping_dates(self):
        Booking.objects.create(
            customer=self.customer,
            vehicle=self.vehicle,
            start_date=date(2026, 5, 10),
            end_date=date(2026, 5, 12),
            total_amount=Decimal('7500.00'),
            status='Confirmed',
        )

        response = self.client.post(
            reverse('book_vehicle', args=[self.vehicle.id]),
            {
                'customer_id': self.customer.id,
                'start_date': '2026-05-11',
                'end_date': '2026-05-13',
            },
        )

        self.assertContains(response, 'already booked')
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 0)

    def test_booking_requires_approved_documents(self):
        Document.objects.filter(customer=self.customer).update(verification_status='Pending')

        response = self.client.post(
            reverse('book_vehicle', args=[self.vehicle.id]),
            {
                'customer_id': self.customer.id,
                'start_date': '2026-05-10',
                'end_date': '2026-05-12',
            },
        )

        self.assertContains(response, 'documents must be approved')
        self.assertEqual(Booking.objects.count(), 0)
