import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Booking, BookingExtra, Customer, Document, ExtraService, Payment, Vehicle


class PublicPageTests(TestCase):
    def test_home_page_seeds_demo_vehicles(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertGreater(Vehicle.objects.count(), 0)
        self.assertContains(response, 'Featured Fleet')
        self.assertContains(response, 'How it works')
        self.assertContains(response, 'Verify Identity')

    def test_admin_login_page_shows_staff_only_message(self):
        response = self.client.get(f"{reverse('admin:login')}?next={reverse('admin_dashboard')}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Admin and worker access only.')
        self.assertContains(response, 'Customer? Use the normal login page instead.')


class BookingWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='customer1@example.com', password='pass12345')
        self.customer = Customer.objects.get(user=self.user)
        self.customer.phone = '0712345678'
        self.customer.national_id_number = '12345678'
        self.customer.address = 'Nairobi'
        self.customer.save()
        self.future_start = timezone.localdate() + timedelta(days=3)
        self.future_end = self.future_start + timedelta(days=2)
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
        delivery_extra = ExtraService.objects.create(
            code='nairobi_delivery',
            name='Nairobi Vehicle Delivery',
            description='Delivery in Nairobi.',
            price=Decimal('2500.00'),
            pricing_mode='flat',
            display_order=1,
        )
        response = self.client.post(
            reverse('book_vehicle', args=[self.vehicle.id]),
            {
                'service_type': 'self_drive',
                'pickup_location': 'Nairobi, Kenya',
                'pickup_latitude': '-1.286389',
                'pickup_longitude': '36.817223',
                'dropoff_location': 'Nairobi, Kenya',
                'dropoff_latitude': '-1.283330',
                'dropoff_longitude': '36.816670',
                'start_date': self.future_start.isoformat(),
                'end_date': self.future_end.isoformat(),
                'delivery_location': 'Westlands',
                'selected_extras': [str(delivery_extra.id)],
            },
        )

        booking = Booking.objects.get()
        self.assertRedirects(response, reverse('booking_payment', args=[booking.id]))
        payment = Payment.objects.get(booking=booking)
        booking_extra = BookingExtra.objects.get(booking=booking, service=delivery_extra)
        self.vehicle.refresh_from_db()

        self.assertEqual(booking.total_amount, Decimal('11000.00'))
        self.assertEqual(booking.status, 'Pending')
        self.assertEqual(booking.service_type, 'self_drive')
        self.assertEqual(booking.service_fee, Decimal('0.00'))
        self.assertEqual(booking.pickup_location, 'Nairobi, Kenya')
        self.assertEqual(str(booking.pickup_latitude), '-1.286389')
        self.assertEqual(str(booking.dropoff_longitude), '36.816670')
        self.assertEqual(payment.amount, Decimal('11000.00'))
        self.assertEqual(payment.status, 'Pending')
        self.assertEqual(booking_extra.total_amount, Decimal('2500.00'))
        self.assertEqual(self.vehicle.status, 'Booked')
        self.assertEqual(self.vehicle.next_available_date, self.future_end)
        self.assertTrue(hasattr(booking, 'deliveryagreement'))

    def test_chauffeur_service_adds_daily_fee_to_booking_total(self):
        self.client.login(username='customer1@example.com', password='pass12345')

        response = self.client.post(
            reverse('book_vehicle', args=[self.vehicle.id]),
            {
                'service_type': 'chauffeur_drive',
                'pickup_location': 'Upper Hill, Nairobi',
                'dropoff_location': 'Karen, Nairobi',
                'start_date': self.future_start.isoformat(),
                'end_date': self.future_end.isoformat(),
            },
        )

        booking = Booking.objects.get()
        payment = Payment.objects.get(booking=booking)

        self.assertRedirects(response, reverse('booking_payment', args=[booking.id]))
        self.assertEqual(booking.service_type, 'chauffeur_drive')
        self.assertEqual(booking.service_fee, Decimal('13500.00'))
        self.assertEqual(booking.total_amount, Decimal('23100.00'))
        self.assertEqual(payment.amount, Decimal('23100.00'))

    def test_payment_submission_marks_booking_paid_and_confirmed(self):
        self.client.login(username='customer1@example.com', password='pass12345')
        start_date = timezone.localdate() + timedelta(days=3)
        end_date = start_date + timedelta(days=2)
        booking = Booking.objects.create(
            customer=self.customer,
            vehicle=self.vehicle,
            pickup_location='Nairobi, Kenya',
            dropoff_location='Nairobi, Kenya',
            start_date=start_date,
            end_date=end_date,
            total_amount=Decimal('7500.00'),
            status='Pending',
        )
        payment = Payment.objects.create(
            booking=booking,
            amount=Decimal('7500.00'),
            status='Pending',
        )

        response = self.client.post(
            reverse('booking_payment', args=[booking.id]),
            {
                'payment_method': 'M-Pesa',
                'payer_phone': '0712345678',
                'transaction_code': 'QWE12345',
                'confirm_terms': 'on',
            },
        )

        self.assertRedirects(response, reverse('booking_confirmation', args=[booking.id]))
        booking.refresh_from_db()
        payment.refresh_from_db()
        self.vehicle.refresh_from_db()

        self.assertEqual(payment.status, 'Paid')
        self.assertEqual(payment.transaction_code, 'QWE12345')
        self.assertEqual(booking.status, 'Confirmed')
        self.assertEqual(self.vehicle.status, 'Booked')

    def test_booking_confirmation_redirects_if_payment_not_done(self):
        self.client.login(username='customer1@example.com', password='pass12345')
        booking = Booking.objects.create(
            customer=self.customer,
            vehicle=self.vehicle,
            pickup_location='Nairobi, Kenya',
            dropoff_location='Nairobi, Kenya',
            start_date=timezone.localdate() + timedelta(days=2),
            end_date=timezone.localdate() + timedelta(days=4),
            total_amount=Decimal('7500.00'),
            status='Pending',
        )
        Payment.objects.create(
            booking=booking,
            amount=Decimal('7500.00'),
            status='Pending',
        )

        response = self.client.get(reverse('booking_confirmation', args=[booking.id]))

        self.assertRedirects(response, reverse('booking_payment', args=[booking.id]))

    def test_mpesa_callback_marks_pending_payment_paid(self):
        booking = Booking.objects.create(
            customer=self.customer,
            vehicle=self.vehicle,
            pickup_location='Nairobi, Kenya',
            dropoff_location='Nairobi, Kenya',
            start_date=timezone.localdate() + timedelta(days=5),
            end_date=timezone.localdate() + timedelta(days=7),
            total_amount=Decimal('8000.00'),
            status='Pending',
        )
        payment = Payment.objects.create(
            booking=booking,
            amount=Decimal('8000.00'),
            payment_method='M-Pesa',
            provider='M-Pesa',
            status='Pending',
            checkout_request_id='checkout-123',
            merchant_request_id='merchant-123',
        )

        response = self.client.post(
            reverse('mpesa_callback'),
            data=json.dumps(
                {
                    'Body': {
                        'stkCallback': {
                            'MerchantRequestID': 'merchant-123',
                            'CheckoutRequestID': 'checkout-123',
                            'ResultCode': 0,
                            'ResultDesc': 'The service request is processed successfully.',
                            'CallbackMetadata': {
                                'Item': [
                                    {'Name': 'Amount', 'Value': 8000},
                                    {'Name': 'MpesaReceiptNumber', 'Value': 'QXE4455'},
                                    {'Name': 'PhoneNumber', 'Value': 254712345678},
                                ]
                            },
                        }
                    }
                }
            ),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(payment.status, 'Paid')
        self.assertEqual(payment.transaction_code, 'QXE4455')
        self.assertEqual(payment.payer_phone, '254712345678')
        self.assertEqual(booking.status, 'Confirmed')

    def test_booking_rejects_overlapping_dates(self):
        self.client.login(username='customer1@example.com', password='pass12345')
        Booking.objects.create(
            customer=self.customer,
            vehicle=self.vehicle,
            pickup_location='Nairobi, Kenya',
            dropoff_location='Nairobi, Kenya',
            start_date=self.future_start,
            end_date=self.future_end,
            total_amount=Decimal('7500.00'),
            status='Confirmed',
        )

        response = self.client.post(
            reverse('book_vehicle', args=[self.vehicle.id]),
            {
                'service_type': 'self_drive',
                'pickup_location': 'Nairobi, Kenya',
                'dropoff_location': 'Nairobi, Kenya',
                'start_date': (self.future_start + timedelta(days=1)).isoformat(),
                'end_date': (self.future_end + timedelta(days=1)).isoformat(),
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
                'service_type': 'self_drive',
                'pickup_location': 'Nairobi, Kenya',
                'dropoff_location': 'Nairobi, Kenya',
                'start_date': self.future_start.isoformat(),
                'end_date': self.future_end.isoformat(),
            },
        )

        self.assertContains(response, 'Upload your documents here before confirming the booking.')
        self.assertEqual(Booking.objects.count(), 0)

    def test_booking_requires_delivery_service_for_delivery_location(self):
        self.client.login(username='customer1@example.com', password='pass12345')

        response = self.client.post(
            reverse('book_vehicle', args=[self.vehicle.id]),
            {
                'service_type': 'self_drive',
                'pickup_location': 'Nairobi, Kenya',
                'dropoff_location': 'Nairobi, Kenya',
                'start_date': self.future_start.isoformat(),
                'end_date': self.future_end.isoformat(),
                'delivery_location': 'Westlands',
            },
        )

        self.assertContains(response, 'Select a delivery service')
        self.assertEqual(Booking.objects.count(), 0)

    def test_booking_redirects_anonymous_users_to_auth(self):
        response = self.client.post(
            reverse('book_vehicle', args=[self.vehicle.id]),
            {
                'pickup_location': 'Nairobi, Kenya',
                'dropoff_location': 'Nairobi, Kenya',
                'start_date': self.future_start.isoformat(),
                'end_date': self.future_end.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('auth_page'), response.url)

    def test_account_dashboard_requires_login(self):
        response = self.client.get(reverse('account_dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('auth_page'), response.url)

    def test_logged_in_customer_visiting_auth_page_is_redirected_to_account(self):
        self.client.login(username='customer1@example.com', password='pass12345')

        response = self.client.get(reverse('auth_page'))

        self.assertRedirects(response, reverse('account_dashboard'))

    def test_booking_page_document_upload_resets_status_to_pending(self):
        self.client.login(username='customer1@example.com', password='pass12345')
        Document.objects.filter(customer=self.customer).update(verification_status='Approved')

        response = self.client.post(
            reverse('book_vehicle', args=[self.vehicle.id]),
            {
                'action': 'documents',
                'national_id_file': SimpleUploadedFile('updated-id.pdf', b'new-id'),
                'driver_license_file': SimpleUploadedFile('updated-dl.pdf', b'new-dl'),
            },
        )

        self.assertEqual(response.status_code, 200)
        document = Document.objects.get(customer=self.customer)
        self.assertEqual(document.verification_status, 'Pending')

    def test_booking_page_shows_document_upload_section_when_not_approved(self):
        self.client.login(username='customer1@example.com', password='pass12345')
        Document.objects.filter(customer=self.customer).update(verification_status='Missing')

        response = self.client.get(reverse('book_vehicle', args=[self.vehicle.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Upload Documents for Verification')


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


class AdminDashboardTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='admin@example.com',
            password='pass12345',
            is_staff=True,
        )
        self.customer_user = User.objects.create_user(username='client@example.com', password='pass12345')
        self.customer = Customer.objects.get(user=self.customer_user)
        self.customer.phone = '0700111222'
        self.customer.address = 'Nairobi'
        self.customer.save()
        self.vehicle = Vehicle.objects.create(
            name='BMW X5',
            model='XDrive',
            plate_number='KDG 909Z',
            vehicle_type='SUV',
            transmission='Automatic',
            fuel_type='Diesel',
            price_per_day=Decimal('15000.00'),
            status='Available',
        )
        self.booking = Booking.objects.create(
            customer=self.customer,
            vehicle=self.vehicle,
            pickup_location='Nairobi',
            dropoff_location='Nairobi',
            start_date=timezone.localdate() + timedelta(days=1),
            end_date=timezone.localdate() + timedelta(days=3),
            total_amount=Decimal('45000.00'),
            status='Confirmed',
        )
        Payment.objects.create(
            booking=self.booking,
            amount=Decimal('45000.00'),
            status='Pending',
        )

    def test_admin_dashboard_requires_staff_login(self):
        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('admin:login'), response.url)

    def test_admin_dashboard_renders_for_staff(self):
        self.client.login(username='admin@example.com', password='pass12345')

        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')
        self.assertContains(response, 'Recent Bookings')
        self.assertContains(response, 'BMW X5')

    def test_logged_in_staff_visiting_auth_page_is_redirected_to_admin_dashboard(self):
        self.client.login(username='admin@example.com', password='pass12345')

        response = self.client.get(reverse('auth_page'))

        self.assertRedirects(response, reverse('admin_dashboard'))

    def test_admin_reports_render_and_export_for_staff(self):
        self.client.login(username='admin@example.com', password='pass12345')

        report_response = self.client.get(reverse('admin_reports'))
        export_response = self.client.get(reverse('export_report_csv', args=['payments']))

        self.assertEqual(report_response.status_code, 200)
        self.assertContains(report_response, 'Reports Center')
        self.assertEqual(export_response.status_code, 200)
        self.assertEqual(export_response['Content-Type'], 'text/csv')
