from django.contrib import admin
from django.utils import timezone
from .models import Customer, Vehicle, Document, Booking, Payment, DeliveryAgreement


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'national_id_number', 'address')
    search_fields = ('user__username', 'phone', 'national_id_number')


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'vehicle_type',
        'model',
        'plate_number',
        'price_per_day',
        'status',
        'is_featured',
        'next_available_date',
    )
    list_filter = ('status', 'vehicle_type', 'fuel_type', 'transmission', 'is_featured')
    search_fields = ('name', 'model', 'plate_number', 'pickup_location', 'dropoff_location')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('customer', 'verification_status', 'uploaded_at', 'reviewed_at', 'reviewed_by')
    list_filter = ('verification_status',)
    search_fields = ('customer__user__username', 'review_notes')
    actions = ('approve_documents', 'reject_documents')

    @admin.action(description='Approve selected documents')
    def approve_documents(self, request, queryset):
        queryset.update(
            verification_status='Approved',
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )

    @admin.action(description='Reject selected documents')
    def reject_documents(self, request, queryset):
        queryset.update(
            verification_status='Rejected',
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'customer',
        'vehicle',
        'pickup_location',
        'dropoff_location',
        'start_date',
        'end_date',
        'total_amount',
        'status',
        'cancelled_at',
        'created_at',
    )
    list_filter = ('status', 'start_date')
    search_fields = ('customer__user__username', 'vehicle__name')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('booking', 'amount', 'payment_method', 'transaction_code', 'status', 'paid_at')
    list_filter = ('status', 'payment_method')


@admin.register(DeliveryAgreement)
class DeliveryAgreementAdmin(admin.ModelAdmin):
    list_display = ('booking', 'delivery_location', 'agreement_signed', 'delivery_date')
    list_filter = ('agreement_signed',)
