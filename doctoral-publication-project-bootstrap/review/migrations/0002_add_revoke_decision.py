from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("review", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reviewdecision",
            name="action",
            field=models.CharField(
                choices=[
                    ("approve", "核准"),
                    ("return", "退回"),
                    ("archive", "封存"),
                    ("revoke", "撤銷核准"),
                ],
                db_index=True,
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="reviewdecision",
            name="visibility_after",
            field=models.CharField(blank=True, db_index=True, max_length=24, null=True),
        ),
    ]
