"""한국관광공사 Tour API (KorService2) 클라이언트.

HTTP 호출과 §3 공통 응답 처리(헤더 검사, items 정규화)를 캡슐화한다.
값 단위 정규화(빈 문자열 → None, 좌표 → Decimal 등)와 모델 매핑은 place_sync.py가 담당한다.
"""

import logging
import time
from collections.abc import Sequence
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger("place.sync")

#: 정상 응답 코드. 그 외(22 트래픽 초과, 30 키 만료 등)는 에러로 처리한다.
RESULT_CODE_OK = "0000"
#: 일시 오류라 재시도 가능한 resultCode("22" 트래픽 초과). 그 외 비정상 코드는 치명(인증/파라미터)으로 본다.
RETRYABLE_RESULT_CODES = frozenset({"22"})


class TourApiError(Exception):
    """Tour API 호출 실패. resultCode 비정상, HTTP 오류, 비 JSON 응답을 포괄한다.

    code: 응답 헤더 resultCode(있을 때). retryable: 일시 오류라 재시도 가능 여부.
    """

    def __init__(self, message: str, *, code: str | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def _check_header(response: Any) -> None:
    """response.header.resultCode가 "0000"이 아니면 TourApiError를 던진다.

    "22"(트래픽 초과)만 재시도 가능으로 표시하고, 그 외 비정상 코드는 치명으로 둔다.
    """
    header = (response or {}).get("header") or {}
    code = header.get("resultCode")
    if code != RESULT_CODE_OK:
        msg = header.get("resultMsg", "")
        raise TourApiError(
            f"Tour API 오류: resultCode={code!r} resultMsg={msg!r}",
            code=code,
            retryable=code in RETRYABLE_RESULT_CODES,
        )


def _extract_items(body: Any) -> list[dict[str, Any]]:
    """body.items.item을 항상 리스트로 정규화한다(§3-2, §3-3).

    - 결과 0건이면 items가 빈 문자열 ""로 온다 → [].
    - 결과 1건이면 item이 단일 dict로 올 수 있다 → [item].
    """
    items = (body or {}).get("items")
    if not isinstance(items, dict):  # "" 또는 누락
        return []
    item = items.get("item")
    if isinstance(item, dict):
        return [item]
    if isinstance(item, list):
        return [row for row in item if isinstance(row, dict)]
    return []


class TourApiClient:
    def __init__(
        self,
        service_key: str | None = None,
        *,
        service_keys: Sequence[str] | None = None,
        mobile_os: str = "ETC",
        mobile_app: str = "TravelMaker",
        timeout: int = 10,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        min_interval: float | None = None,
        session: requests.Session | None = None,
    ) -> None:
        # 키 한도("22") 소진 시 순차 전환할 키 목록. 명시 인자 > settings.TOUR_API_CODES 순으로 결정.
        if service_keys is not None:
            keys = [key for key in service_keys if key]
        elif service_key is not None:
            keys = [service_key]
        else:
            keys = list(settings.TOUR_API_CODES) or [settings.TOUR_API_CODE]
        self._service_keys = keys or [""]  # 최소 1개(빈 키여도 기존 인증오류 동작 유지)
        self._key_index = 0
        self.base_url = settings.TOUR_API_BASE_URL.rstrip("/")
        self.mobile_os = mobile_os
        self.mobile_app = mobile_app
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        # 호출 간 최소 간격(초). 미지정 시 settings 값 사용(속도 제한 429 회피).
        self.min_interval = min_interval if min_interval is not None else settings.TOUR_API_MIN_INTERVAL
        self._last_request_ts = 0.0
        self._session = session or requests.Session()

    def _throttle(self) -> None:
        """직전 호출과의 간격이 min_interval보다 짧으면 그 차이만큼 대기한다(초당 속도 제한 회피)."""
        if self.min_interval <= 0:
            return
        wait = self.min_interval - (time.monotonic() - self._last_request_ts)
        if wait > 0:
            time.sleep(wait)
        self._last_request_ts = time.monotonic()

    @property
    def service_key(self) -> str:
        """현재 사용 중인 키(하위호환·로깅용)."""
        return self._service_keys[self._key_index]

    def _rotate_key(self) -> bool:
        """다음 키로 전환한다. 더 이상 남은 키가 없으면 False."""
        if self._key_index + 1 >= len(self._service_keys):
            return False
        self._key_index += 1
        logger.warning("Tour API 키 한도 초과, 다음 키로 전환 (%d/%d)", self._key_index + 1, len(self._service_keys))
        return True

    def _get(self, operation: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """키 전환 + 재시도 래퍼.

        한도 초과("22")는 남은 키가 있으면 다음 키로 전환해 즉시 재시도하고, 일시 오류(타임아웃·5xx·
        마지막 키의 "22")는 지수 백오프로 재시도한다. 치명 오류는 즉시 전파한다.
        """
        base_params: dict[str, Any] = {
            "MobileOS": self.mobile_os,
            "MobileApp": self.mobile_app,
            "_type": "json",
        }
        # None 값 파라미터는 전송하지 않는다.
        base_params.update({key: value for key, value in params.items() if value is not None})
        url = f"{self.base_url}/{operation}"

        attempt = 0
        while True:
            merged = {"serviceKey": self.service_key, **base_params}
            try:
                return self._request_once(operation, url, merged)
            except TourApiError as exc:
                # 키 한도 초과 → 남은 키가 있으면 즉시 다음 키로 전환해 재시도(백오프 없이).
                # data.go.kr은 키 한도를 resultCode "22"(JSON) 또는 HTTP 429 둘 다로 알려준다.
                if exc.code in ("22", "429") and self._rotate_key():
                    logger.info("%s 키 전환 후 재시도", operation)
                    attempt = 0  # 새 키엔 일시 오류 재시도 예산을 새로 부여
                    continue
                # 일시 오류(타임아웃·5xx·429·마지막 키의 "22") → 지수 백오프 재시도
                if exc.retryable and attempt < self.max_retries:
                    delay = self.backoff_base * (2**attempt)
                    if exc.code in ("22", "429"):  # 트래픽 초과·속도 제한은 더 길게 쉬어준다
                        delay = max(delay, self.backoff_base * 8)
                    logger.warning(
                        "%s 일시 오류, %.1fs 후 재시도(%d/%d): %s",
                        operation,
                        delay,
                        attempt + 1,
                        self.max_retries,
                        exc,
                    )
                    if delay:
                        time.sleep(delay)
                    attempt += 1
                    continue
                if exc.retryable:
                    logger.error("%s 재시도 %d회 소진 후 실패: %s", operation, self.max_retries, exc)
                raise

    def _request_once(self, operation: str, url: str, merged: dict[str, Any]) -> list[dict[str, Any]]:
        """한 번의 HTTP 호출 + 파싱. 실패 유형별로 retryable 플래그를 단 TourApiError를 던진다."""
        self._throttle()  # 직전 호출과 간격 확보(속도 제한 429 회피)
        try:
            response = self._session.get(url, params=merged, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:  # 타임아웃·연결·5xx·429 → 일시 오류
            status = getattr(getattr(exc, "response", None), "status_code", None)
            # 429(속도 제한)는 code로 표시해 _get에서 더 길게 쉬게 한다.
            raise TourApiError(
                f"{operation} 호출 실패: {exc}", code=str(status) if status else None, retryable=True
            ) from exc

        try:
            payload: Any = response.json()
        except ValueError as exc:
            # 키 미등록 등에서 200 + XML 에러가 오는 경우 JSON 파싱 실패(치명).
            raise TourApiError(
                f"{operation} 응답이 JSON이 아님(인증/키 확인 필요): {response.text[:200]}", retryable=False
            ) from exc

        body = (payload or {}).get("response")
        _check_header(body)
        return _extract_items((body or {}).get("body"))

    def area_based_list(
        self,
        content_type_id: int,
        *,
        ldong_regn_cd: str | None = None,
        ldong_signgu_cd: str | None = None,
        num_of_rows: int = 10,
        page_no: int = 1,
        arrange: str | None = None,
    ) -> list[dict[str, Any]]:
        """지역 기반 목록(초기 적재). 좌표·주소·대표 이미지·분류체계 코드를 가져온다.

        arrange 정렬: A=제목순(기본·가나다), C=수정일순, D=생성일순, O/Q/R=대표이미지 보유분(제목/수정/생성).
        미지정 시 API 기본값(제목순)으로 나간다.
        """
        return self._get(
            "areaBasedList2",
            {
                "contentTypeId": content_type_id,
                "lDongRegnCd": ldong_regn_cd,
                "lDongSignguCd": ldong_signgu_cd,
                "numOfRows": num_of_rows,
                "pageNo": page_no,
                "arrange": arrange,
            },
        )

    def area_based_sync_list(
        self, content_type_id: int, *, num_of_rows: int = 1000, page_no: int = 1
    ) -> list[dict[str, Any]]:
        """증분 동기화 목록(areaBasedSyncList2, 단계 7). areaBasedList 필드 + showflag(1 공개/0 삭제) + modifiedtime."""
        return self._get(
            "areaBasedSyncList2",
            {"contentTypeId": content_type_id, "numOfRows": num_of_rows, "pageNo": page_no},
        )

    def detail_common(self, content_id: int) -> dict[str, Any] | None:
        """공통 상세(overview·homepage 보강). 결과가 없으면 None."""
        items = self._get("detailCommon2", {"contentId": content_id})
        return items[0] if items else None

    def detail_image(self, content_id: int, *, image_yn: str = "Y") -> list[dict[str, Any]]:
        """콘텐츠 이미지 목록. imageYN=Y는 일반 이미지, N은 음식점 메뉴 이미지."""
        return self._get("detailImage2", {"contentId": content_id, "imageYN": image_yn})

    def detail_intro(self, content_id: int, content_type_id: int) -> dict[str, Any] | None:
        """소개 상세(운영시간·휴무일·주차 등). contentTypeId가 필수 파라미터다. 결과 없으면 None."""
        items = self._get("detailIntro2", {"contentId": content_id, "contentTypeId": content_type_id})
        return items[0] if items else None

    def lcls_systm_code(
        self, *, lcls_systm1: str | None = None, lcls_systm2: str | None = None, num_of_rows: int = 100
    ) -> list[dict[str, Any]]:
        """분류체계 코드 목록(lclsSystmCode2, §6). 파라미터 없으면 1단계, lclsSystm1만 주면 2단계, +lclsSystm2면 3단계."""
        return self._get(
            "lclsSystmCode2",
            {"lclsSystm1": lcls_systm1, "lclsSystm2": lcls_systm2, "numOfRows": num_of_rows},
        )
