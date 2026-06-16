from django.db import migrations, models


def convert_gender_null_to_empty(apps, schema_editor):
    User = apps.get_model("user", "User")
    User.objects.filter(gender__isnull=True).update(gender="")


class Migration(migrations.Migration):
    dependencies = [
        ("user", "0011_alter_user_birthday_null_gender_blank"),
    ]

    operations = [
        migrations.RunPython(
            convert_gender_null_to_empty,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="user",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[("M", "남성"), ("F", "여성")],
                default="",
                max_length=6,
                verbose_name="성별",
            ),
        ),
    ]
