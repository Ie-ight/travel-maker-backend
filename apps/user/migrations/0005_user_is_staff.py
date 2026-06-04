from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0004_user_deleted_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_staff",
            field=models.BooleanField(default=False),
        ),
    ]
