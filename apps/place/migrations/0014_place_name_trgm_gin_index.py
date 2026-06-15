from django.contrib.postgres.indexes import GinIndex
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("place", "0013_enable_pg_trgm"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="place",
            index=GinIndex(
                fields=["place_name"],
                name="place_name_trgm_gin_idx",
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]
