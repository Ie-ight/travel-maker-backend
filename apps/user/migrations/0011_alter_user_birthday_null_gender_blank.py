from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0010_userpreference_useractionlog"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="birthday",
            field=models.DateField(blank=True, null=True, verbose_name="생년월일"),
        ),
        migrations.AlterField(
            model_name="user",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[("M", "남성"), ("F", "여성")],
                max_length=6,
                null=True,
                verbose_name="성별",
            ),
        ),
    ]
