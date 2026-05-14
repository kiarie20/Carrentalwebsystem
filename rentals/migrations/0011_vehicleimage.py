import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0010_booking_lifecycle_and_returninspection'),
    ]

    operations = [
        migrations.CreateModel(
            name='VehicleImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(blank=True, null=True, upload_to='vehicles/gallery/')),
                ('image_url', models.URLField(blank=True)),
                ('caption', models.CharField(blank=True, max_length=120)),
                ('is_primary', models.BooleanField(default=False)),
                ('display_order', models.PositiveIntegerField(default=0)),
                ('vehicle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gallery_images', to='rentals.vehicle')),
            ],
            options={
                'ordering': ['display_order', 'id'],
            },
        ),
    ]
