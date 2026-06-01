from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("place", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="place",
            name="rating_avg",
            field=models.DecimalField(decimal_places=1, default=0, max_digits=2),
        ),
    ]
