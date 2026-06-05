# Redis 캐시 키 정의 및 헬퍼
# 모든 cache key는 이 모듈에서 생성한다.


def blacklist_key(jti: str) -> str:
    """JWT refresh token 블랙리스트 키. TTL = 토큰 잔여 만료 시간."""
    return f"blacklist:{jti}"
