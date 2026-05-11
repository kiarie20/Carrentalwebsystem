from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Customer


@receiver(post_save, sender=User)
def ensure_customer_profile(sender, instance, **kwargs):
    Customer.objects.get_or_create(
        user=instance,
        defaults={
            'phone': '',
            'national_id_number': '',
            'address': 'Nairobi, Kenya',
        },
    )
