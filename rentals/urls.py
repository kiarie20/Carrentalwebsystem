from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-reports/', views.admin_reports, name='admin_reports'),
    path('admin-reports/export/<str:report_type>/', views.export_report_csv, name='export_report_csv'),
    path('cars/', views.car_list, name='car_list'),
    path('cars/<int:vehicle_id>/', views.car_detail, name='car_detail'),
    path('book/<int:vehicle_id>/', views.book_vehicle, name='book_vehicle'),
    path('bookings/<int:booking_id>/payment/', views.booking_payment, name='booking_payment'),
    path('bookings/<int:booking_id>/confirmation/', views.booking_confirmation, name='booking_confirmation'),
    path('payments/mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
    path('auth/', views.auth_page, name='auth_page'),
    path('account/', views.account_dashboard, name='account_dashboard'),
    path('logout/', views.logout_user, name='logout_user'),
    path('api/account/profile/', views.api_my_profile, name='api_my_profile'),
    path('api/account/documents/', views.api_my_documents, name='api_my_documents'),
    path('api/vehicles/', views.api_vehicle_list, name='api_vehicle_list'),
    path('api/vehicles/<int:vehicle_id>/', views.api_vehicle_detail, name='api_vehicle_detail'),
    path('api/bookings/me/', views.api_my_bookings, name='api_my_bookings'),
    path('api/bookings/<int:booking_id>/cancel/', views.api_cancel_booking, name='api_cancel_booking'),
]
