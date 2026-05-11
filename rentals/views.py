import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .demo import ensure_demo_vehicles
from .forms import (
    BookingForm,
    CustomerAccountApiForm,
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


def get_customer_for_user(user):
    return Customer.objects.get_or_create(
        user=user,
        defaults={'phone': '', 'national_id_number': '', 'address': 'Nairobi, Kenya'},
    )[0]


def get_request_payload(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return None
    return request.POST


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
                customer = get_customer_for_user(user)
                customer.phone = register_form.cleaned_data['phone']
                customer.address = customer.address or 'Nairobi, Kenya'
                customer.save(update_fields=['phone', 'address'])
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
    customer = get_customer_for_user(request.user)
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
                uploaded_document.reviewed_at = None
                uploaded_document.reviewed_by = None
                uploaded_document.review_notes = ''
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

        customer = get_customer_for_user(request.user)
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


def serialize_vehicle(vehicle):
    return {
        'id': vehicle.id,
        'name': vehicle.name,
        'model': vehicle.model,
        'plate_number': vehicle.plate_number,
        'vehicle_type': vehicle.vehicle_type,
        'transmission': vehicle.transmission,
        'fuel_type': vehicle.fuel_type,
        'seat_count': vehicle.seat_count,
        'door_count': vehicle.door_count,
        'year': vehicle.year,
        'mileage': vehicle.mileage,
        'engine_size': vehicle.engine_size,
        'drive_type': vehicle.drive_type,
        'pickup_location': vehicle.pickup_location,
        'dropoff_location': vehicle.dropoff_location,
        'rating': str(vehicle.rating),
        'review_count': vehicle.review_count,
        'price_per_day': str(vehicle.price_per_day),
        'status': vehicle.status,
        'next_available_date': vehicle.next_available_date.isoformat() if vehicle.next_available_date else None,
        'description': vehicle.description,
        'image': vehicle.image.url if vehicle.image else None,
    }


def api_vehicle_list(request):
    if request.method != 'GET':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    vehicles = Vehicle.objects.all()
    query = request.GET.get('q', '').strip()
    vehicle_type = request.GET.get('type', '').strip()
    status = request.GET.get('status', '').strip()

    if query:
        vehicles = vehicles.filter(
            Q(name__icontains=query)
            | Q(model__icontains=query)
            | Q(description__icontains=query)
        )
    if vehicle_type:
        vehicles = vehicles.filter(vehicle_type=vehicle_type)
    if status:
        vehicles = vehicles.filter(status=status)

    data = [serialize_vehicle(vehicle) for vehicle in vehicles.order_by('price_per_day')]
    return JsonResponse({'count': len(data), 'results': data})


def api_vehicle_detail(request, vehicle_id):
    if request.method != 'GET':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    return JsonResponse(serialize_vehicle(vehicle))


@login_required(login_url='auth_page')
def api_my_profile(request):
    customer = get_customer_for_user(request.user)

    if request.method == 'GET':
        return JsonResponse(
            {
                'username': request.user.username,
                'email': request.user.email or request.user.username,
                'full_name': request.user.first_name,
                'phone': customer.phone,
                'national_id_number': customer.national_id_number,
                'address': customer.address,
            }
        )

    if request.method == 'POST':
        payload = get_request_payload(request)
        if payload is None:
            return JsonResponse({'detail': 'Invalid JSON payload.'}, status=400)

        form = CustomerAccountApiForm(payload, instance=customer, user=request.user)
        if form.is_valid():
            updated_customer = form.save()
            return JsonResponse(
                {
                    'detail': 'Profile updated successfully.',
                    'profile': {
                        'username': updated_customer.user.username,
                        'email': updated_customer.user.email,
                        'full_name': updated_customer.user.first_name,
                        'phone': updated_customer.phone,
                        'national_id_number': updated_customer.national_id_number,
                        'address': updated_customer.address,
                    },
                }
            )
        return JsonResponse({'errors': form.errors.get_json_data()}, status=400)

    return JsonResponse({'detail': 'Method not allowed.'}, status=405)


@login_required(login_url='auth_page')
def api_my_documents(request):
    if request.method != 'GET':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    customer = get_customer_for_user(request.user)
    document = Document.objects.filter(customer=customer).first()
    if not document:
        return JsonResponse({'exists': False, 'status': 'Missing'})

    return JsonResponse(
        {
            'exists': True,
            'status': document.verification_status,
            'uploaded_at': document.uploaded_at.isoformat() if document.uploaded_at else None,
            'reviewed_at': document.reviewed_at.isoformat() if document.reviewed_at else None,
            'reviewed_by': document.reviewed_by.username if document.reviewed_by else None,
            'review_notes': document.review_notes,
            'national_id_file': document.national_id_file.url if document.national_id_file else None,
            'driver_license_file': document.driver_license_file.url if document.driver_license_file else None,
        }
    )


@login_required(login_url='auth_page')
def api_my_bookings(request):
    if request.method != 'GET':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    customer = get_customer_for_user(request.user)

    bookings = Booking.objects.filter(customer=customer).select_related('vehicle').order_by('-created_at')
    data = [
        {
            'id': booking.id,
            'vehicle': serialize_vehicle(booking.vehicle),
            'pickup_location': booking.pickup_location,
            'dropoff_location': booking.dropoff_location,
            'start_date': booking.start_date.isoformat(),
            'end_date': booking.end_date.isoformat(),
            'total_amount': str(booking.total_amount),
            'status': booking.status,
            'created_at': booking.created_at.isoformat(),
            'cancelled_at': booking.cancelled_at.isoformat() if booking.cancelled_at else None,
            'cancel_reason': booking.cancel_reason,
            'can_cancel': booking.can_cancel(),
        }
        for booking in bookings
    ]
    return JsonResponse({'count': len(data), 'results': data})


@login_required(login_url='auth_page')
def api_cancel_booking(request, booking_id):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    customer = get_customer_for_user(request.user)
    booking = get_object_or_404(
        Booking.objects.select_related('vehicle'),
        id=booking_id,
        customer=customer,
    )
    payload = get_request_payload(request)
    if payload is None:
        return JsonResponse({'detail': 'Invalid JSON payload.'}, status=400)

    if not booking.can_cancel():
        return JsonResponse({'detail': 'This booking can no longer be cancelled.'}, status=400)

    reason = payload.get('reason', '') if hasattr(payload, 'get') else ''
    booking.cancel(reason=reason)
    return JsonResponse(
        {
            'detail': 'Booking cancelled successfully.',
            'booking': {
                'id': booking.id,
                'status': booking.status,
                'cancelled_at': booking.cancelled_at.isoformat() if booking.cancelled_at else None,
                'cancel_reason': booking.cancel_reason,
            },
        }
    )
