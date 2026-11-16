# Generated for the irreversible logical-clearance workflow.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("publications", "0006_seed_full_country_reference"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="publicationrecord",
            name="is_purged",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="publicationrecord",
            name="purged_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="publicationrecord",
            name="purged_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="purged_publications", to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
