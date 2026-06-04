"""lclsSystm 분류 코드 → 이름 매핑 (§6).

`sync_lcls_codes` 명령이 lclsSystmCode2에서 받아 같은 폴더의 lcls_codes.json에 저장하고,
AI 태깅(ai_tagging)이 코드 대신 사람이 읽는 분류명(예: "자연 > 섬")을 모델에 전달하는 데 쓴다.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import cast

LCLS_CODES_PATH = Path(__file__).parent / "lcls_codes.json"


@lru_cache(maxsize=1)
def load_lcls_map() -> dict[str, str]:
    """{코드: 이름} 매핑. 파일이 없으면 빈 dict(폴백)."""
    if not LCLS_CODES_PATH.exists():
        return {}
    return cast(dict[str, str], json.loads(LCLS_CODES_PATH.read_text(encoding="utf-8")))


def lcls_label(systm1: str | None, systm2: str | None, systm3: str | None) -> str | None:
    """분류 코드 3단계를 "대분류 > 중분류 > 소분류" 이름으로. 매핑 없는 코드는 코드 그대로. 모두 비면 None."""
    mapping = load_lcls_map()
    parts = [mapping.get(code, code) for code in (systm1, systm2, systm3) if code]
    return " > ".join(parts) if parts else None
