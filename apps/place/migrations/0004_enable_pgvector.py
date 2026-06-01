from django.db import migrations
from pgvector.django import VectorExtension


class Migration(migrations.Migration):
    """pgvector 확장 활성화 (CREATE EXTENSION IF NOT EXISTS vector).

    5단계에서 추가할 PlaceFeature.style_vector(VectorField)보다 먼저 적용되도록
    별도 마이그레이션으로 분리한다.
    """

    dependencies = [
        ("place", "0003_tour_api_place_fields"),
    ]

    operations = [
        VectorExtension(),
    ]
