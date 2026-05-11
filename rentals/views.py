import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .demo import ensure_default_extra_services, ensure_demo_vehicles
from .forms import (
    BookingForm,
    CustomerAccountApiForm,
    CustomerLoginForm,
    CustomerProfileForm,
    CustomerRegistrationForm,
    DocumentUploadForm,
)
from .models import Booking, BookingExtra, Customer, DeliveryAgreement, Document, ExtraService, Payment, Vehicle

BENEFITS = [
    {'title': 'Wide Range of Cars', 'copy': 'Choose from economy to luxury vehicles.'},
    {'title': 'Affordable Prices', 'copy': 'Competitive pricing with no hidden fees.'},
    {'title': 'Easy Booking', 'copy': 'Book your car online in just a few minutes.'},
    {'title': '24/7 Support', 'copy': 'Our support team is always ready to assist you.'},
]


def get_default_dashboard_url(user):
    if user.is_staff:
        return reverse('admin_dashboard')
    return reverse('account_dashboard')


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


def build_pricing(vehicle, start_date=None, end_date=None, selected_extras=None):
    selected_extras = list(selected_extras or [])
    if start_date and end_date and end_date >= start_date:
        total_days = (end_date - start_date).days + 1
    else:
        total_days = 3
    subtotal = vehicle.price_per_day * total_days
    extras_breakdown = []
    extras_total = Decimal('0.00')
    for extra in selected_extras:
        extra_total = extra.calculate_total(total_days)
        extras_total += extra_total
        extras_breakdown.append(
            {
                'id': extra.id,
                'name': extra.name,
                'code': extra.code,
                'unit_price': extra.price,
                'pricing_mode': extra.pricing_mode,
                'pricing_label': 'per day' if extra.pricing_mode == 'daily' else 'one-time',
                'total': extra_total,
            }
        )
    taxable_amount = subtotal + extras_total
    taxes = (taxable_amount * Decimal('0.10')).quantize(Decimal('0.01'))
    total = taxable_amount + taxes
    return {
        'total_days': total_days,
        'subtotal': subtotal,
        'selected_extras': extras_breakdown,
        'extras_total': extras_total,
        'taxes': taxes,
        'total': total,
    }


def format_currency(amount):
    amount = amount or Decimal('0.00')
    return f"KES {amount:,.0f}"


def build_chart_points(values, width=640, height=250, padding=28):
    if not values:
        return ''

    max_value = max(max(values), 1)
    usable_width = width - (padding * 2)
    usable_height = height - (padding * 2)
    step_count = max(len(values) - 1, 1)
    step_x = usable_width / step_count

    points = []
    for index, value in enumerate(values):
        x = padding + (step_x * index)
        y = height - padding - ((value / max_value) * usable_height)
        points.append(f'{x:.1f},{y:.1f}')
    return ' '.join(points)


def build_status_gradient(status_rows):
    if not status_rows:
        return 'conic-gradient(#d6ddea 0 100%)'

    gradient_parts = []
    running_total = 0
    for row in status_rows:
        start = running_total
        running_total += row['percentage']
        gradient_parts.append(f"{row['color']} {start:.2f}% {running_total:.2f}%")
    if running_total < 100:
        gradient_parts.append(f"#d6ddea {running_total:.2f}% 100%")
    return f"conic-gradient({', '.join(gradient_parts)})"


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
        return redirect(get_default_dashboard_url(request.user))

    next_url = request.GET.get('next') or request.POST.get('next') or reverse('home')
    login_form = CustomerLoginForm(request=request)
    register_form = CustomerRegistrationForm()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'login':
            login_form = CustomerLoginForm(request.POST, request=request)
            register_form = CustomerRegistrationForm()
            if login_form.is_valid():
                user = login_form.get_user()
                login(request, user)
                if user.is_staff:
                    return redirect(get_default_dashboard_url(user))
                if next_url and next_url not in {reverse('home'), reverse('auth_page')}:
                    return redirect(next_url)
                return redirect(get_default_dashboard_url(user))
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
                if next_url and next_url not in {reverse('home'), reverse('auth_page')}:
                    return redirect(next_url)
                return redirect(get_default_dashboard_url(user))

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


@staff_member_required(login_url='admin:login')
def admin_dashboard(request):
    ensure_demo_vehicles()
    ensure_default_extra_services()

    today = timezone.localdate()
    current_month_start = today.replace(day=1)
    active_bookings = Booking.objects.exclude(status='Cancelled')
    paid_revenue = Payment.objects.filter(status='Paid').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    revenue_total = active_bookings.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    pending_payments_total = Payment.objects.filter(status='Pending').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    seven_day_labels = []
    booking_series = []
    completed_series = []
    for offset in range(6, -1, -1):
        current_day = today - timedelta(days=offset)
        seven_day_labels.append(current_day.strftime('%d %b'))
        booking_series.append(Booking.objects.filter(created_at__date=current_day).count())
        completed_series.append(Booking.objects.filter(status='Completed', end_date=current_day).count())

    status_palette = {
        'Confirmed': '#2c66f0',
        'Pending': '#f59e0b',
        'Completed': '#10b981',
        'Cancelled': '#ef4444',
    }
    total_bookings = Booking.objects.count()
    status_rows = []
    for label in ['Confirmed', 'Pending', 'Completed', 'Cancelled']:
        count = Booking.objects.filter(status=label).count()
        percentage = (count / total_bookings * 100) if total_bookings else 0
        status_rows.append(
            {
                'label': label,
                'count': count,
                'percentage': percentage,
                'color': status_palette[label],
            }
        )

    recent_bookings = Booking.objects.select_related('customer__user', 'vehicle').order_by('-created_at')[:5]
    top_vehicles = (
        Vehicle.objects.annotate(
            total_bookings=Count('booking', filter=Q(booking__status__in=['Pending', 'Confirmed', 'Completed'])),
            total_revenue=Sum('booking__total_amount', filter=Q(booking__status__in=['Pending', 'Confirmed', 'Completed'])),
        )
        .order_by('-total_bookings', '-total_revenue', 'name')[:5]
    )

    summary_cards = [
        {
            'label': 'Total Cars',
            'value': f"{Vehicle.objects.count():,}",
            'note': f"{Vehicle.objects.filter(status='Available').count()} available now",
            'tone': 'blue',
            'glyph': 'C',
        },
        {
            'label': 'Total Bookings',
            'value': f"{total_bookings:,}",
            'note': f"{Booking.objects.filter(status='Confirmed').count()} confirmed",
            'tone': 'green',
            'glyph': 'B',
        },
        {
            'label': 'Total Customers',
            'value': f"{Customer.objects.count():,}",
            'note': f"{Document.objects.filter(verification_status='Approved').count()} verified",
            'tone': 'violet',
            'glyph': 'U',
        },
        {
            'label': 'Total Revenue',
            'value': format_currency(revenue_total),
            'note': f"{format_currency(paid_revenue)} collected",
            'tone': 'gold',
            'glyph': 'K',
        },
        {
            'label': 'Pending Payments',
            'value': format_currency(pending_payments_total),
            'note': f"{Payment.objects.filter(status='Pending').count()} awaiting confirmation",
            'tone': 'rose',
            'glyph': 'P',
        },
    ]

    operational_cards = [
        {
            'label': 'New Customers (This Month)',
            'value': f"{Customer.objects.filter(user__date_joined__date__gte=current_month_start).count():,}",
            'note': 'Customer profiles created this month',
            'tone': 'blue',
            'glyph': 'N',
        },
        {
            'label': 'Cars On Rent',
            'value': f"{Vehicle.objects.filter(status__in=['Booked', 'Rented']).count():,}",
            'note': 'Vehicles currently reserved or out',
            'tone': 'green',
            'glyph': 'R',
        },
        {
            'label': 'Upcoming Bookings',
            'value': f"{Booking.objects.filter(start_date__gte=today, status__in=['Pending', 'Confirmed']).count():,}",
            'note': 'Future trips already scheduled',
            'tone': 'gold',
            'glyph': 'U',
        },
        {
            'label': 'Extra Services',
            'value': f"{ExtraService.objects.filter(is_active=True).count():,}",
            'note': 'Active service add-ons available',
            'tone': 'violet',
            'glyph': 'S',
        },
    ]

    context = {
        'summary_cards': summary_cards,
        'operational_cards': operational_cards,
        'recent_bookings': recent_bookings,
        'top_vehicles': top_vehicles,
        'status_rows': status_rows,
        'status_total': total_bookings,
        'status_gradient': build_status_gradient(status_rows),
        'chart_labels': seven_day_labels,
        'booking_series_points': build_chart_points(booking_series),
        'completed_series_points': build_chart_points(completed_series),
        'chart_peak': max(booking_series + completed_series + [1]),
        'today_label': today.strftime('%d %b %Y'),
    }
    return render(request, 'admin_dashboard.html', context)


@login_required(login_url='auth_page')
def account_dashboard(request):
    customer = get_customer_for_user(request.user)
    document = Document.objects.filter(customer=customer).first()

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'profile':
            profile_form = CustomerProfileForm(request.POST, instance=customer)
            if profile_form.is_valid():
                profile_form.save()
                return redirect('account_dashboard')
        else:
            profile_form = CustomerProfileForm(instance=customer)
    else:
        profile_form = CustomerProfileForm(instance=customer)

    bookings = Booking.objects.filter(customer=customer).select_related('vehicle').order_by('-created_at')
    context = {
        'active_page': 'account',
        'customer': customer,
        'document': document,
        'profile_form': profile_form,
        'bookings': bookings,
    }
    return render(request, 'account_dashboard.html', context)


def book_vehicle(request, vehicle_id):
    ensure_default_extra_services()
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    available_extras = ExtraService.objects.filter(is_active=True)
    today = timezone.localdate()
    default_end = today + timedelta(days=2)
    initial = {
        'pickup_location': vehicle.pickup_location,
        'dropoff_location': vehicle.dropoff_location,
        'start_date': today,
        'end_date': default_end,
        'delivery_location': vehicle.pickup_location,
    }
    form = BookingForm(initial=initial, extra_queryset=available_extras)
    context = {
        'active_page': 'cars',
        'vehicle': vehicle,
        'form': form,
        'pricing': build_pricing(vehicle),
        'benefits': BENEFITS,
        'extra_services': available_extras,
        'selected_extra_ids': [],
        'document_form': None,
    }

    if request.method == 'POST':
        if not request.user.is_authenticated:
            next_url = reverse('book_vehicle', args=[vehicle.id])
            return redirect(f"{reverse('auth_page')}?next={next_url}")

        customer = get_customer_for_user(request.user)
        document = Document.objects.filter(customer=customer).first()
        context['document_status'] = document.verification_status if document else 'Missing'
        action = request.POST.get('action', 'booking')

        if action == 'documents':
            document_form = DocumentUploadForm(
                request.POST,
                request.FILES,
                instance=document,
            )
            context['document_form'] = document_form
            if document_form.is_valid():
                uploaded_document = document_form.save(commit=False)
                uploaded_document.customer = customer
                uploaded_document.verification_status = 'Pending'
                uploaded_document.reviewed_at = None
                uploaded_document.reviewed_by = None
                uploaded_document.review_notes = ''
                uploaded_document.save()
                context['document_status'] = uploaded_document.verification_status
                context['success'] = 'Documents uploaded successfully. They are now awaiting admin verification.'
                context['document_form'] = DocumentUploadForm(instance=uploaded_document)
            else:
                context['error'] = 'Please correct the document upload errors below.'
        else:
            form = BookingForm(request.POST, extra_queryset=available_extras)
            context['form'] = form
            if not document or document.verification_status != 'Approved':
                context['error'] = 'Upload your documents here before confirming the booking.'
            elif form.is_valid():
                start_date = form.cleaned_data['start_date']
                end_date = form.cleaned_data['end_date']
                selected_extras = list(form.cleaned_data['selected_extras'])
                context['selected_extra_ids'] = [str(extra.id) for extra in selected_extras]
                context['pricing'] = build_pricing(vehicle, start_date, end_date, selected_extras)

                if vehicle.status == 'Maintenance':
                    context['error'] = 'This vehicle is currently under maintenance.'
                elif Booking.has_conflict(vehicle, start_date, end_date):
                    context['error'] = 'This vehicle is already booked for the selected dates.'
                else:
                    total_amount = context['pricing']['total']
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
                        for extra in selected_extras:
                            BookingExtra.objects.create(
                                booking=booking,
                                service=extra,
                                unit_price=extra.price,
                                pricing_mode=extra.pricing_mode,
                                total_amount=extra.calculate_total(context['pricing']['total_days']),
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
                    context['pricing'] = build_pricing(vehicle, start_date, end_date, selected_extras)
            else:
                start_date = form.data.get('start_date')
                end_date = form.data.get('end_date')
                selected_extras = list(available_extras.filter(id__in=request.POST.getlist('selected_extras')))
                context['selected_extra_ids'] = [str(extra.id) for extra in selected_extras]
                if start_date and end_date:
                    try:
                        parsed_start = date.fromisoformat(start_date)
                        parsed_end = date.fromisoformat(end_date)
                        context['pricing'] = build_pricing(vehicle, parsed_start, parsed_end, selected_extras)
                    except ValueError:
                        pass
        if context['document_form'] is None:
            context['document_form'] = DocumentUploadForm(instance=document)
    elif request.user.is_authenticated:
        customer = Customer.objects.filter(user=request.user).first()
        if customer:
            document = Document.objects.filter(customer=customer).first()
            context['document_status'] = document.verification_status if document else 'Missing'
            context['document_form'] = DocumentUploadForm(instance=document)
    else:
        context['document_form'] = DocumentUploadForm()

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
        'image': vehicle.primary_image_url,
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
            'extras': [
                {
                    'name': item.service.name,
                    'pricing_mode': item.pricing_mode,
                    'unit_price': str(item.unit_price),
                    'total_amount': str(item.total_amount),
                }
                for item in booking.booking_extras.select_related('service').all()
            ],
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
