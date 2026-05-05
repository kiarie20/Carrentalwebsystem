from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('book/<int:vehicle_id>/', views.book_vehicle, name='book_vehicle'),
]