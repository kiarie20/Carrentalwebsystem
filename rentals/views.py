from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .demo import ensure_demo_vehicles
from .forms import (
    BookingForm,
    CustomerLoginForm,
    CustomerProfileForm,
    CustomerRegistrationForm,
    DocumentUploadForm,
)
from .models import Booking, Customer, DeliveryAgreement, Document, Payment, Vehicle


BOOKING_EXTRAS = [
    {'name': 'Child Seat', 'price': Decimal('5.00'), 'description': 'For safe travel with kids.'},
    {'name': 'GPS Navigation', 'price': Decimal('7.00'), 'description': 'Easy navigation on the go.'},
    {'name': 'Wi-Fi Hotspot', 'price': Decimal('6.00'), 'description': 'Stay connected anywhere.'},
    {'name': 'Additional Insurance', 'price': Decimal('10.00'), 'description': 'Extra protection for peace of mind.'},
]

BENEFITS = [
    {'title': 'Wide Range of Cars', 'copy': 'Choose from economy to luxury vehicles.'},
    {'title': 'Affordable Prices', 'copy': 'Competitive pricing with no hidden fees.'},
    {'title': 'Easy Booking', 'copy': 'Book your car online in just a few minutes.'},
    {'title': '24/7 Support', 'copy': 'Our support team is always ready to assist you.'},
]


def build_vehicle_features(vehicle):
    return [
        f'{vehicle.seat_count} Seats',
        f'{vehicle.door_count} Doors',
        vehicle.transmission or 'Automatic',
        vehicle.fuel_type or 'Petrol',
        vehicle.drive_type or 'AWD',
        'Air Conditioning',
        'Bluetooth',
        'GPS Navigation',
    ]


def build_vehicle_specs(vehicle):
    return [
        ('Year', vehicle.year or 2024),
        ('Mileage', f"{vehicle.mileage or 18000:,} km"),
        ('Engine', vehicle.engine_size or '2.0L'),
        ('Fuel Type', vehicle.fuel_type or 'Petrol'),
        ('Drive Type', vehicle.drive_type or 'FWD'),
        ('Transmission', vehicle.transmission or 'Automatic'),
    ]


def build_pricing(vehicle, start_date=None, end_date=None):
    if start_date and end_date and end_date >= start_date:
        total_days = (end_date - start_date).days + 1
    else:
        total_days = 3
    subtotal = vehicle.price_per_day * total_days
    taxes = (subtotal * Decimal('0.10')).quantize(Decimal('0.01'))
    total = subtotal + taxes
    return {
        'total_days': total_days,
        'subtotal': subtotal,
        'taxes': taxes,
        'total': total,
    }


def home(request):
    ensure_demo_vehicles()
    featured = list(Vehicle.objects.filter(is_featured=True).order_by('price_per_day')[:4])
    if not featured:
        featured = list(Vehicle.objects.order_by('price_per_day')[:4])
    hero_vehicle = featured[1] if len(featured) > 1 else (featured[0] if featured else None)
    cheapest_vehicle = Vehicle.objects.order_by('price_per_day').first()
    vehicle_types = Vehicle.objects.exclude(vehicle_type='').values_list('vehicle_type', flat=True).distinct()
    home_stats = [
        {'label': 'Vehicles Ready', 'value': Vehicle.objects.filter(status='Available').count()},
        {'label': 'Fleet Size', 'value': Vehicle.objects.count()},
        {'label': 'From Per Day', 'value': f"KES {cheapest_vehicle.price_per_day}" if cheapest_vehicle else 'KES 0'},
    ]
    context = {
        'active_page': 'home',
        'hero_vehicle': hero_vehicle,
        'featured_vehicles': featured,
        'benefits': BENEFITS,
        'vehicle_types': vehicle_types,
        'hero_features': build_vehicle_features(hero_vehicle)[:4] if hero_vehicle else [],
        'home_stats': home_stats,
    }
    return render(request, 'home.html', context)


def car_list(request):
    ensure_demo_vehicles()
    vehicles = Vehicle.objects.all()

    search_query = request.GET.get('q', '').strip()
    vehicle_type = request.GET.get('type', '').strip()
    transmission = request.GET.get('transmission', '').strip()
    fuel_type = request.GET.get('fuel', '').strip()
    sort = request.GET.get('sort', 'price_asc').strip()

    if search_query:
        vehicles = vehicles.filter(
            Q(name__icontains=search_query)
            | Q(model__icontains=search_query)
            | Q(description__icontains=search_query)
        )
    if vehicle_type:
        vehicles = vehicles.filter(vehicle_type=vehicle_type)
    if transmission:
        vehicles = vehicles.filter(transmission=transmission)
    if fuel_type:
        vehicles = vehicles.filter(fuel_type=fuel_type)

    sort_map = {
        'price_asc': 'price_per_day',
        'price_desc': '-price_per_day',
        'rating_desc': '-rating',
        'name_asc': 'name',
    }
    vehicles = vehicles.order_by(sort_map.get(sort, 'price_per_day'))

    paginator = Paginator(vehicles, 6)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'active_page': 'cars',
        'page_obj': page_obj,
        'search_query': search_query,
        'selected_type': vehicle_type,
        'selected_transmission': transmission,
        'selected_fuel': fuel_type,
        'selected_sort': sort,
        'vehicle_types': Vehicle.objects.exclude(vehicle_type='').values_list('vehicle_type', flat=True).distinct(),
        'transmission_types': Vehicle.objects.exclude(transmission='').values_list('transmission', flat=True).distinct(),
        'fuel_types': Vehicle.objects.exclude(fuel_type='').values_list('fuel_type', flat=True).distinct(),
        'result_count': paginator.count,
    }
    return render(request, 'cars.html', context)


def car_detail(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    related_vehicles = Vehicle.objects.exclude(id=vehicle.id).filter(vehicle_type=vehicle.vehicle_type)[:3]
    context = {
        'active_page': 'cars',
        'vehicle': vehicle,
        'features': build_vehicle_features(vehicle),
        'specs': build_vehicle_specs(vehicle),
        'pricing': build_pricing(vehicle),
        'related_vehicles': related_vehicles,
        'gallery_items': range(4),
    }
    return render(request, 'car_detail.html', context)


def auth_page(request):
    ensure_demo_vehicles()
    if request.user.is_authenticated:
        return redirect('home')

    next_url = request.GET.get('next') or request.POST.get('next') or reverse('home')
    login_form = CustomerLoginForm(request=request)
    register_form = CustomerRegistrationForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'login':
            login_form = CustomerLoginForm(request.POST, request=request)
            register_form = CustomerRegistrationForm()
            if login_form.is_valid():
                login(request, login_form.get_user())
                return redirect(next_url)
        elif action == 'register':
            register_form = CustomerRegistrationForm(request.POST)
            login_form = CustomerLoginForm(request=request)
            if register_form.is_valid():
                user = register_form.save()
                Customer.objects.create(
                    user=user,
                    phone=register_form.cleaned_data['phone'],
                    address='Nairobi, Kenya',
                )
                login(request, user)
                if next_url == reverse('home'):
                    return redirect('account_dashboard')
                return redirect(next_url)

    context = {
        'active_page': 'auth',
        'login_form': login_form,
        'register_form': register_form,
        'next_url': next_url,
        'benefits': BENEFITS,
        'hero_vehicle': Vehicle.objects.filter(is_featured=True).first() or Vehicle.objects.first(),
    }
    return render(request, 'auth.html', context)


def logout_user(request):
    logout(request)
    return redirect('home')


@login_required(login_url='auth_page')
def account_dashboard(request):
    customer, _ = Customer.objects.get_or_create(
        user=request.user,
        defaults={'phone': '', 'national_id_number': '', 'address': 'Nairobi, Kenya'},
    )
    document = Document.objects.filter(customer=customer).first()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'profile':
            profile_form = CustomerProfileForm(request.POST, instance=customer)
            document_form = DocumentUploadForm(instance=document)
            if profile_form.is_valid():
                profile_form.save()
                return redirect('account_dashboard')
        elif action == 'documents':
            document_form = DocumentUploadForm(
                request.POST,
                request.FILES,
                instance=document,
            )
            profile_form = CustomerProfileForm(instance=customer)
            if document_form.is_valid():
                uploaded_document = document_form.save(commit=False)
                uploaded_document.customer = customer
                uploaded_document.verification_status = 'Pending'
                uploaded_document.save()
                return redirect('account_dashboard')
        else:
            profile_form = CustomerProfileForm(instance=customer)
            document_form = DocumentUploadForm(instance=document)
    else:
        profile_form = CustomerProfileForm(instance=customer)
        document_form = DocumentUploadForm(instance=document)

    bookings = Booking.objects.filter(customer=customer).select_related('vehicle').order_by('-created_at')
    context = {
        'active_page': 'account',
        'customer': customer,
        'document': document,
        'profile_form': profile_form,
        'document_form': document_form,
        'bookings': bookings,
    }
    return render(request, 'account_dashboard.html', context)


def book_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    today = timezone.localdate()
    default_end = today + timedelta(days=2)
    initial = {
        'pickup_location': vehicle.pickup_location,
        'dropoff_location': vehicle.dropoff_location,
        'start_date': today,
        'end_date': default_end,
        'delivery_location': vehicle.pickup_location,
    }
    form = BookingForm(initial=initial)
    context = {
        'active_page': 'cars',
        'vehicle': vehicle,
        'form': form,
        'pricing': build_pricing(vehicle),
        'benefits': BENEFITS,
        'extras': BOOKING_EXTRAS,
    }

    if request.method == 'POST':
        if not request.user.is_authenticated:
            next_url = reverse('book_vehicle', args=[vehicle.id])
            return redirect(f"{reverse('auth_page')}?next={next_url}")

        form = BookingForm(request.POST)
        context['form'] = form

        customer, _ = Customer.objects.get_or_create(
            user=request.user,
            defaults={'phone': '', 'national_id_number': '', 'address': 'Nairobi, Kenya'},
        )
        document = Document.objects.filter(customer=customer).first()
        context['document_status'] = document.verification_status if document else 'Missing'

        if not document or document.verification_status != 'Approved':
            context['error'] = 'Your documents must be approved before you can confirm a booking.'
        elif form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            context['pricing'] = build_pricing(vehicle, start_date, end_date)

            if vehicle.status == 'Maintenance':
                context['error'] = 'This vehicle is currently under maintenance.'
            elif Booking.has_conflict(vehicle, start_date, end_date):
                context['error'] = 'This vehicle is already booked for the selected dates.'
            else:
                total_amount = Booking.calculate_total(vehicle, start_date, end_date)
                with transaction.atomic():
                    booking = Booking.objects.create(
                        customer=customer,
                        vehicle=vehicle,
                        pickup_location=form.cleaned_data['pickup_location'],
                        dropoff_location=form.cleaned_data['dropoff_location'],
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
                    if form.cleaned_data['delivery_location']:
                        DeliveryAgreement.objects.create(
                            booking=booking,
                            delivery_location=form.cleaned_data['delivery_location'],
                            delivery_date=start_date,
                        )
                    vehicle.refresh_availability()

                context['success'] = 'Booking created successfully. Payment is pending confirmation.'
                context['booking'] = booking
                context['pricing'] = build_pricing(vehicle, start_date, end_date)
        else:
            start_date = form.data.get('start_date')
            end_date = form.data.get('end_date')
            if start_date and end_date:
                try:
                    parsed_start = date.fromisoformat(start_date)
                    parsed_end = date.fromisoformat(end_date)
                    context['pricing'] = build_pricing(vehicle, parsed_start, parsed_end)
                except ValueError:
                    pass
    elif request.user.is_authenticated:
        customer = Customer.objects.filter(user=request.user).first()
        if customer:
            document = Document.objects.filter(customer=customer).first()
            context['document_status'] = document.verification_status if document else 'Missing'

    return render(request, 'booking.html', context)
