import decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("rentals", "0009_booking_service_type_and_fee"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="booking",
            name="rental_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="booking",
            name="returned_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="booking",
            name="status",
            field=models.CharField(
                choices=[
                    ("Pending", "Pending"),
                    ("Confirmed", "Confirmed"),
                    ("Rented", "Rented"),
                    ("Returned", "Returned"),
                    ("Cancelled", "Cancelled"),
                    ("Completed", "Completed"),
                ],
                default="Pending",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="vehicle",
            name="status",
            field=models.CharField(
                choices=[
                    ("Available", "Available"),
                    ("Booked", "Booked"),
                    ("Rented", "Rented"),
                    ("Returned", "Returned"),
                    ("Maintenance", "Maintenance"),
                ],
                default="Available",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="ReturnInspection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("checked_in_at", models.DateTimeField(blank=True, null=True)),
                ("handover_notes", models.TextField(blank=True)),
                ("actual_return_location", models.CharField(blank=True, max_length=255)),
                ("odometer_out", models.PositiveIntegerField(blank=True, null=True)),
                ("odometer_in", models.PositiveIntegerField(blank=True, null=True)),
                ("fuel_level_out", models.CharField(blank=True, choices=[("Full", "Full"), ("3/4", "3/4"), ("Half", "Half"), ("1/4", "1/4"), ("Empty", "Empty")], max_length=20)),
                ("fuel_level_in", models.CharField(blank=True, choices=[("Full", "Full"), ("3/4", "3/4"), ("Half", "Half"), ("1/4", "1/4"), ("Empty", "Empty")], max_length=20)),
                ("exterior_condition", models.CharField(choices=[("Good", "Good"), ("Needs Attention", "Needs Attention"), ("Damaged", "Damaged")], default="Good", max_length=30)),
                ("interior_condition", models.CharField(choices=[("Good", "Good"), ("Needs Attention", "Needs Attention"), ("Damaged", "Damaged")], default="Good", max_length=30)),
                ("damage_notes", models.TextField(blank=True)),
                ("late_fee", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=10)),
                ("fuel_fee", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=10)),
                ("cleaning_fee", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=10)),
                ("damage_fee", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=10)),
                ("other_fee", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=10)),
                ("requires_maintenance", models.BooleanField(default=False)),
                ("settlement_status", models.CharField(choices=[("No Charges", "No Charges"), ("Pending", "Pending"), ("Paid", "Paid")], default="No Charges", max_length=20)),
                ("settlement_payment_method", models.CharField(blank=True, max_length=50)),
                ("settlement_reference", models.CharField(blank=True, max_length=100)),
                ("settled_at", models.DateTimeField(blank=True, null=True)),
                ("final_notes", models.TextField(blank=True)),
                ("booking", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to="rentals.booking")),
                ("received_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="return_inspections", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
