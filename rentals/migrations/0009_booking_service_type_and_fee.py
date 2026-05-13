import decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0008_booking_dropoff_latitude_booking_dropoff_longitude_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='service_fee',
            field=models.DecimalField(decimal_places=2, default=decimal.Decimal('0.00'), max_digits=10),
        ),
        migrations.AddField(
            model_name='booking',
            name='service_type',
            field=models.CharField(
                choices=[
                    ('self_drive', 'Self Drive'),
                    ('chauffeur_drive', 'Chauffeur Service'),
                    ('airport_pickup', 'Airport Pick-up'),
                ],
                default='self_drive',
                max_length=30,
            ),
        ),
    ]
