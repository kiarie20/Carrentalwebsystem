from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Customer, Document, ExtraService


class BookingForm(forms.Form):
    pickup_location = forms.CharField(max_length=120)
    dropoff_location = forms.CharField(max_length=120)
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

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        delivery_location = (cleaned_data.get('delivery_location') or '').strip()
        selected_extras = cleaned_data.get('selected_extras')
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError('Drop-off date cannot be earlier than pick-up date.')
        selected_codes = set(selected_extras.values_list('code', flat=True)) if selected_extras else set()
        delivery_codes = {'nairobi_delivery', 'airport_delivery'}
        if delivery_location and not selected_codes.intersection(delivery_codes):
            raise forms.ValidationError('Select a delivery service if you want the vehicle delivered to your location.')
        if selected_codes.intersection(delivery_codes) and not delivery_location:
            raise forms.ValidationError('Provide the delivery location for the selected delivery service.')
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
