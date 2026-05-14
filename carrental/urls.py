from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rentals import views as rental_views

urlpatterns = [
    path('admin/', rental_views.staff_portal_entry, name='staff_portal_entry'),
    path('admin/<path:legacy_path>/', rental_views.staff_portal_entry, name='legacy_staff_portal_entry'),
    path('django-admin/', admin.site.urls),
    path('', include('rentals.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
