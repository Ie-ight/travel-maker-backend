from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("place", "0012_remove_placefeature_id_remove_placeinfo_id_and_more"),
    ]

    operations = [
        TrigramExtension(),
    ]
