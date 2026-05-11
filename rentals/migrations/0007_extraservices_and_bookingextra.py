from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0006_vehicle_image_url'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExtraService',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50, unique=True)),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField()),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('pricing_mode', models.CharField(choices=[('daily', 'Per Day'), ('flat', 'One Time')], default='daily', max_length=10)),
                ('is_active', models.BooleanField(default=True)),
                ('display_order', models.PositiveIntegerField(default=0)),
            ],
            options={
                'ordering': ['display_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='BookingExtra',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('pricing_mode', models.CharField(choices=[('daily', 'Per Day'), ('flat', 'One Time')], max_length=10)),
                ('total_amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('booking', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='booking_extras', to='rentals.booking')),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='rentals.extraservice')),
            ],
            options={
                'unique_together': {('booking', 'service')},
            },
        ),
    ]
