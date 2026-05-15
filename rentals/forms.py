from decimal import Decimal

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Customer, Document, ExtraService, ReturnInspection, SERVICE_TYPE_CHOICES
from .mpesa import MpesaGatewayError, normalize_phone_number


class BookingForm(forms.Form):
    service_type = forms.ChoiceField(
        choices=SERVICE_TYPE_CHOICES,
        widget=forms.RadioSelect,
    )
    pickup_location = forms.CharField(max_length=120)
    pickup_latitude = forms.DecimalField(required=False, max_digits=9, decimal_places=6, widget=forms.HiddenInput())
    pickup_longitude = forms.DecimalField(required=False, max_digits=9, decimal_places=6, widget=forms.HiddenInput())
    dropoff_location = forms.CharField(max_length=120)
    dropoff_latitude = forms.DecimalField(required=False, max_digits=9, decimal_places=6, widget=forms.HiddenInput())
    dropoff_longitude = forms.DecimalField(required=False, max_digits=9, decimal_places=6, widget=forms.HiddenInput())
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    delivery_location = forms.CharField(max_length=255, required=False)
    selected_extras = forms.ModelMultipleChoiceField(
        queryset=ExtraService.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        extra_queryset = kwargs.pop('extra_queryset', ExtraService.objects.none())
        super().__init__(*args, **kwargs)
        self.fields['selected_extras'].queryset = extra_queryset
        for field_name in ('pickup_location', 'dropoff_location', 'delivery_location'):
            self.fields[field_name].widget.attrs.update({'autocomplete': 'off'})

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        delivery_location = (cleaned_data.get('delivery_location') or '').strip()
        selected_extras = cleaned_data.get('selected_extras')
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError('Drop-off date cannot be earlier than pick-up date.')
        selected_codes = set(selected_extras.values_list('code', flat=True)) if selected_extras else set()
        delivery_codes = {'nairobi_delivery'}
        if delivery_location and not selected_codes.intersection(delivery_codes):
            raise forms.ValidationError('Select a delivery service if you want the vehicle delivered to your location.')
        if selected_codes.intersection(delivery_codes) and not delivery_location:
            raise forms.ValidationError('Provide the delivery location for the selected delivery service.')
        pickup_latitude = cleaned_data.get('pickup_latitude')
        pickup_longitude = cleaned_data.get('pickup_longitude')
        dropoff_latitude = cleaned_data.get('dropoff_latitude')
        dropoff_longitude = cleaned_data.get('dropoff_longitude')
        if bool(pickup_latitude) != bool(pickup_longitude):
            raise forms.ValidationError('Pick-up location coordinates are incomplete. Please reselect the map pin.')
        if bool(dropoff_latitude) != bool(dropoff_longitude):
            raise forms.ValidationError('Drop-off location coordinates are incomplete. Please reselect the map pin.')
        return cleaned_data


class CustomerRegistrationForm(UserCreationForm):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20)

    class Meta:
        model = User
        fields = ('full_name', 'email', 'phone', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def save(self, commit=True):
        email = self.cleaned_data['email'].strip().lower()
        full_name = self.cleaned_data['full_name'].strip()
        user = super().save(commit=False)
        user.username = email
        user.email = email
        user.first_name = full_name
        if commit:
            user.save()
        return user


class CustomerLoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        self.user = None

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')
        if email and password:
            self.user = authenticate(
                self.request,
                username=email.strip().lower(),
                password=password,
            )
            if self.user is None:
                raise forms.ValidationError('Invalid email or password.')
        return cleaned_data

    def get_user(self):
        return self.user


class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ('phone', 'national_id_number', 'address')


class CustomerAccountApiForm(forms.ModelForm):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()

    class Meta:
        model = Customer
        fields = ('full_name', 'email', 'phone', 'national_id_number', 'address')

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user and not self.is_bound:
            self.fields['full_name'].initial = self.user.first_name
            self.fields['email'].initial = self.user.email or self.user.username

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        user_matches = User.objects.filter(username=email)
        if self.user:
            user_matches = user_matches.exclude(pk=self.user.pk)
        if user_matches.exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def save(self, commit=True):
        customer = super().save(commit=False)
        if self.user:
            customer.user = self.user
            self.user.first_name = self.cleaned_data['full_name'].strip()
            self.user.email = self.cleaned_data['email']
            self.user.username = self.cleaned_data['email']
            if commit:
                self.user.save(update_fields=['first_name', 'email', 'username'])
        if commit:
            customer.save()
        return customer


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ('national_id_file', 'driver_license_file')


class PaymentForm(forms.Form):
    PAYMENT_METHOD_CHOICES = [
        ('M-Pesa', 'M-Pesa'),
        ('Card', 'Debit / Credit Card'),
        ('Bank Transfer', 'Bank Transfer'),
    ]

    payment_method = forms.ChoiceField(choices=PAYMENT_METHOD_CHOICES)
    payer_phone = forms.CharField(max_length=20, required=False)
    transaction_code = forms.CharField(max_length=100, required=False)
    confirm_terms = forms.BooleanField()

    def __init__(self, *args, **kwargs):
        self.live_mpesa = kwargs.pop('live_mpesa', False)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        payer_phone = (cleaned_data.get('payer_phone') or '').strip()
        transaction_code = (cleaned_data.get('transaction_code') or '').strip()

        if payment_method == 'M-Pesa' and not payer_phone:
            self.add_error('payer_phone', 'Enter the phone number used for the M-Pesa payment.')
        elif payment_method == 'M-Pesa' and payer_phone:
            try:
                cleaned_data['payer_phone'] = normalize_phone_number(payer_phone)
            except MpesaGatewayError as exc:
                self.add_error('payer_phone', str(exc))

        if payment_method != 'M-Pesa' and not transaction_code:
            self.add_error('transaction_code', 'Enter the transaction reference for this payment method.')

        if payment_method == 'M-Pesa' and not self.live_mpesa and not transaction_code:
            self.add_error('transaction_code', 'Enter the reference used for the M-Pesa payment or mobile message.')

        if transaction_code and len(transaction_code) < 4:
            self.add_error('transaction_code', 'Enter a valid transaction reference.')

        return cleaned_data


class RentalStartForm(forms.Form):
    FUEL_LEVEL_CHOICES = ReturnInspection.FUEL_LEVEL_CHOICES

    odometer_out = forms.IntegerField(min_value=0)
    fuel_level_out = forms.ChoiceField(choices=FUEL_LEVEL_CHOICES)
    handover_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))
    agreement_signed = forms.BooleanField(required=False, initial=True)


class ReturnInspectionForm(forms.ModelForm):
    fee_fields = ('late_fee', 'fuel_fee', 'cleaning_fee', 'damage_fee', 'other_fee')

    class Meta:
        model = ReturnInspection
        fields = (
            'actual_return_location',
            'odometer_in',
            'fuel_level_in',
            'exterior_condition',
            'interior_condition',
            'damage_notes',
            'late_fee',
            'fuel_fee',
            'cleaning_fee',
            'damage_fee',
            'other_fee',
            'requires_maintenance',
            'final_notes',
        )
        widgets = {
            'damage_notes': forms.Textarea(attrs={'rows': 3}),
            'final_notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fee_fields:
            self.fields[field_name].required = False
            if self.initial.get(field_name) in (None, ''):
                self.initial[field_name] = Decimal('0.00')

    def clean(self):
        cleaned_data = super().clean()
        odometer_in = cleaned_data.get('odometer_in')
        odometer_out = getattr(self.instance, 'odometer_out', None)

        for field_name in self.fee_fields:
            if cleaned_data.get(field_name) in (None, ''):
                cleaned_data[field_name] = Decimal('0.00')

        if odometer_in is not None and odometer_out is not None and odometer_in < odometer_out:
            self.add_error('odometer_in', 'The returned mileage cannot be lower than the handover mileage.')

        return cleaned_data


class SettlementForm(forms.Form):
    PAYMENT_METHOD_CHOICES = PaymentForm.PAYMENT_METHOD_CHOICES

    payment_method = forms.ChoiceField(choices=PAYMENT_METHOD_CHOICES)
    transaction_reference = forms.CharField(max_length=100)
    confirm_received = forms.BooleanField()

    def clean_transaction_reference(self):
        value = self.cleaned_data['transaction_reference'].strip()
        if len(value) < 4:
            raise forms.ValidationError('Enter a valid settlement reference.')
        return value
