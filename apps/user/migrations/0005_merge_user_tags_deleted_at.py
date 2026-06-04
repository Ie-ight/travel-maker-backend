from django.db import migrations


class Migration(migrations.Migration):
    """0004_user_tags + 0005_user_is_staff merge"""

    dependencies = [
        ("user", "0004_user_tags"),
        ("user", "0005_user_is_staff"),
    ]

    operations = []
