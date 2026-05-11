from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20)
    national_id_number = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.user.username


class Vehicle(models.Model):
    STATUS_CHOICES = [
        ('Available', 'Available'),
        ('Booked', 'Booked'),
        ('Rented', 'Rented'),
        ('Returned', 'Returned'),
        ('Maintenance', 'Maintenance'),
    ]

    name = models.CharField(max_length=100)
    model = models.CharField(max_length=100, blank=True)
    plate_number = models.CharField(max_length=30, unique=True)
    vehicle_type = models.CharField(max_length=40, blank=True)
    transmission = models.CharField(max_length=40, blank=True, default='Automatic')
    fuel_type = models.CharField(max_length=40, blank=True, default='Petrol')
    seat_count = models.PositiveIntegerField(default=5)
    door_count = models.PositiveIntegerField(default=4)
    year = models.PositiveIntegerField(blank=True, null=True)
    mileage = models.PositiveIntegerField(blank=True, null=True)
    engine_size = models.CharField(max_length=40, blank=True)
    drive_type = models.CharField(max_length=40, blank=True)
    pickup_location = models.CharField(max_length=120, blank=True, default='Nairobi, Kenya')
    dropoff_location = models.CharField(max_length=120, blank=True, default='Nairobi, Kenya')
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=4.5)
    review_count = models.PositiveIntegerField(default=120)
    is_featured = models.BooleanField(default=False)
    price_per_day = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Available')
    next_available_date = models.DateField(blank=True, null=True)
    image = models.ImageField(upload_to='vehicles/', blank=True, null=True)
    image_url = models.URLField(blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} - {self.plate_number}"

    @property
    def primary_image_url(self):
        if self.image:
            return self.image.url
        return self.image_url

    def refresh_availability(self):
        active_bookings = self.booking_set.filter(status__in=['Pending', 'Confirmed'])
        today = timezone.localdate()
        current_booking = active_bookings.filter(start_date__lte=today, end_date__gte=today).first()
        future_booking = active_bookings.filter(start_date__gt=today).order_by('start_date').first()
        latest_booking = active_bookings.order_by('-end_date').first()

        if self.status == 'Maintenance':
            return

        if current_booking:
            self.status = 'Rented' if current_booking.status == 'Confirmed' else 'Booked'
            self.next_available_date = current_booking.end_date
        elif future_booking:
            self.status = 'Booked'
            self.next_available_date = future_booking.end_date
        elif latest_booking and latest_booking.end_date >= today:
            self.status = 'Booked'
            self.next_available_date = latest_booking.end_date
        else:
            self.status = 'Available'
            self.next_available_date = None

        self.save(update_fields=['status', 'next_available_date'])


class Document(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    customer = models.OneToOneField(Customer, on_delete=models.CASCADE)
    national_id_file = models.FileField(upload_to='documents/national_ids/')
    driver_license_file = models.FileField(upload_to='documents/driver_licenses/')
    verification_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='reviewed_documents',
    )
    review_notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.customer.user.username} Documents"

    def mark_reviewed(self, status, reviewed_by=None, notes=''):
        self.verification_status = status
        self.reviewed_at = timezone.now()
        self.reviewed_by = reviewed_by
        self.review_notes = notes
        self.save(update_fields=['verification_status', 'reviewed_at', 'reviewed_by', 'review_notes'])


class Booking(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Cancelled', 'Cancelled'),
        ('Completed', 'Completed'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)
    pickup_location = models.CharField(max_length=120, blank=True, default='Nairobi, Kenya')
    dropoff_location = models.CharField(max_length=120, blank=True, default='Nairobi, Kenya')
    start_date = models.DateField()
    end_date = models.DateField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancel_reason = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.customer.user.username} - {self.vehicle.name}"

    @classmethod
    def has_conflict(cls, vehicle, start_date, end_date, excluded_booking=None):
        bookings = cls.objects.filter(
            vehicle=vehicle,
            status__in=['Pending', 'Confirmed'],
            start_date__lte=end_date,
            end_date__gte=start_date,
        )
        if excluded_booking:
            bookings = bookings.exclude(pk=excluded_booking.pk)
        return bookings.exists()

    @staticmethod
    def calculate_total(vehicle, start_date, end_date):
        rental_days = (end_date - start_date).days + 1
        return vehicle.price_per_day * rental_days

    def can_cancel(self):
        return self.status in ['Pending', 'Confirmed'] and self.start_date > timezone.localdate()

    def cancel(self, reason=''):
        if not self.can_cancel():
            raise ValueError('This booking can no longer be cancelled.')

        self.status = 'Cancelled'
        self.cancelled_at = timezone.now()
        self.cancel_reason = reason.strip()
        self.save(update_fields=['status', 'cancelled_at', 'cancel_reason'])
        self.vehicle.refresh_availability()


class ExtraService(models.Model):
    PRICING_MODE_CHOICES = [
        ('daily', 'Per Day'),
        ('flat', 'One Time'),
    ]

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    pricing_mode = models.CharField(max_length=10, choices=PRICING_MODE_CHOICES, default='daily')
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name

    def calculate_total(self, rental_days):
        if self.pricing_mode == 'daily':
            return self.price * rental_days
        return self.price


class BookingExtra(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='booking_extras')
    service = models.ForeignKey(ExtraService, on_delete=models.PROTECT)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    pricing_mode = models.CharField(max_length=10, choices=ExtraService.PRICING_MODE_CHOICES)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('booking', 'service')

    def __str__(self):
        return f"{self.booking} - {self.service.name}"


class Payment(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
        ('Failed', 'Failed'),
    ]

    booking = models.OneToOneField(Booking, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, default='M-Pesa')
    transaction_code = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    paid_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.booking} - {self.status}"


class DeliveryAgreement(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE)
    delivery_location = models.CharField(max_length=255)
    agreement_signed = models.BooleanField(default=False)
    delivery_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"Agreement for {self.booking}"
