from datetime import datetime

from django.db import transaction
from django.shortcuts import get_object_or_404, render

from .models import Booking, Customer, DeliveryAgreement, Document, Payment, Vehicle


def home(request):
    vehicles = Vehicle.objects.all()
    return render(request, 'home.html', {'vehicles': vehicles})


def book_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    context = {'vehicle': vehicle}

    if request.method == 'POST':
        customer_id = request.POST.get('customer_id')
        start_date_raw = request.POST.get('start_date')
        end_date_raw = request.POST.get('end_date')
        delivery_location = request.POST.get('delivery_location', '').strip()

        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            context['error'] = 'Customer record was not found.'
            return render(request, 'booking.html', context)

        try:
            start_date = datetime.strptime(start_date_raw, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_raw, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            context['error'] = 'Please provide valid start and end dates.'
            return render(request, 'booking.html', context)

        if end_date < start_date:
            context['error'] = 'End date cannot be earlier than start date.'
            return render(request, 'booking.html', context)

        if vehicle.status == 'Maintenance':
            context['error'] = 'This vehicle is currently under maintenance.'
            return render(request, 'booking.html', context)

        document = Document.objects.filter(customer=customer).first()
        if not document or document.verification_status != 'Approved':
            context['error'] = 'Customer documents must be approved before booking.'
            return render(request, 'booking.html', context)

        if Booking.has_conflict(vehicle, start_date, end_date):
            context['error'] = 'This vehicle is already booked for the selected dates.'
            context['next_available_date'] = vehicle.next_available_date
            return render(request, 'booking.html', context)

        total_amount = Booking.calculate_total(vehicle, start_date, end_date)

        with transaction.atomic():
            booking = Booking.objects.create(
                customer=customer,
                vehicle=vehicle,
                start_date=start_date,
                end_date=end_date,
                total_amount=total_amount,
                status='Pending',
            )
            Payment.objects.create(
                booking=booking,
                amount=total_amount,
                status='Pending',
            )
            if delivery_location:
                DeliveryAgreement.objects.create(
                    booking=booking,
                    delivery_location=delivery_location,
                    delivery_date=start_date,
                )
            vehicle.refresh_availability()

        context['success'] = 'Booking created successfully. Payment is pending confirmation.'
        context['booking'] = booking

    return render(request, 'booking.html', context)
