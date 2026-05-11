from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0005_document_review_fields_and_booking_cancellation'),
    ]

    operations = [
        migrations.AddField(
            model_name='vehicle',
            name='image_url',
            field=models.URLField(blank=True),
        ),
    ]
