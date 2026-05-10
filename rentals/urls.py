from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('cars/', views.car_list, name='car_list'),
    path('cars/<int:vehicle_id>/', views.car_detail, name='car_detail'),
    path('book/<int:vehicle_id>/', views.book_vehicle, name='book_vehicle'),
    path('auth/', views.auth_page, name='auth_page'),
    path('account/', views.account_dashboard, name='account_dashboard'),
    path('logout/', views.logout_user, name='logout_user'),
    path('api/vehicles/', views.api_vehicle_list, name='api_vehicle_list'),
    path('api/vehicles/<int:vehicle_id>/', views.api_vehicle_detail, name='api_vehicle_detail'),
    path('api/bookings/me/', views.api_my_bookings, name='api_my_bookings'),
]
