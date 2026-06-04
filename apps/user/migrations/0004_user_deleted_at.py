from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0003_merge_20260602_1155"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="deleted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
