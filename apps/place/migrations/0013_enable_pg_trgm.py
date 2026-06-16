from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False  # CREATE EXTENSION은 일부 PG 환경(AWS RDS 등)에서 트랜잭션 내 실행 시 실패할 수 있음
    # 롤백 순서: 0014(GIN 인덱스)를 먼저 롤백한 뒤 이 마이그레이션을 롤백해야 함
    # gin_trgm_ops 의존성이 남아있으면 DROP EXTENSION pg_trgm이 실패한다

    dependencies = [
        ("place", "0012_remove_placefeature_id_remove_placeinfo_id_and_more"),
    ]

    operations = [
        TrigramExtension(),
    ]
