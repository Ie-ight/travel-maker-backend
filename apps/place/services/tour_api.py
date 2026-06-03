"""한국관광공사 Tour API (KorService2) 클라이언트.

HTTP 호출과 §3 공통 응답 처리(헤더 검사, items 정규화)를 캡슐화한다.
값 단위 정규화(빈 문자열 → None, 좌표 → Decimal 등)와 모델 매핑은 place_sync.py가 담당한다.
"""

from typing import Any

import requests
from django.conf import settings

#: 정상 응답 코드. 그 외(22 트래픽 초과, 30 키 만료 등)는 에러로 처리한다.
RESULT_CODE_OK = "0000"


class TourApiError(Exception):
    """Tour API 호출 실패. resultCode 비정상, HTTP 오류, 비 JSON 응답을 포괄한다."""


def _check_header(response: Any) -> None:
    """response.header.resultCode가 "0000"이 아니면 TourApiError를 던진다."""
    header = (response or {}).get("header") or {}
    code = header.get("resultCode")
    if code != RESULT_CODE_OK:
        msg = header.get("resultMsg", "")
        raise TourApiError(f"Tour API 오류: resultCode={code!r} resultMsg={msg!r}")


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
        mobile_os: str = "ETC",
        mobile_app: str = "TravelMaker",
        timeout: int = 10,
        session: requests.Session | None = None,
    ) -> None:
        self.service_key = service_key if service_key is not None else settings.TOUR_API_CODE
        self.base_url = settings.TOUR_API_BASE_URL.rstrip("/")
        self.mobile_os = mobile_os
        self.mobile_app = mobile_app
        self.timeout = timeout
        self._session = session or requests.Session()

    def _get(self, operation: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        merged: dict[str, Any] = {
            "serviceKey": self.service_key,
            "MobileOS": self.mobile_os,
            "MobileApp": self.mobile_app,
            "_type": "json",
        }
        # None 값 파라미터는 전송하지 않는다.
        merged.update({key: value for key, value in params.items() if value is not None})

        url = f"{self.base_url}/{operation}"
        try:
            response = self._session.get(url, params=merged, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise TourApiError(f"{operation} 호출 실패: {exc}") from exc

        try:
            payload: Any = response.json()
        except ValueError as exc:
            # 키 미등록 등에서 200 + XML 에러가 오는 경우 JSON 파싱 실패.
            raise TourApiError(f"{operation} 응답이 JSON이 아님(인증/키 확인 필요): {response.text[:200]}") from exc

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
    ) -> list[dict[str, Any]]:
        """지역 기반 목록(초기 적재). 좌표·주소·대표 이미지·분류체계 코드를 가져온다."""
        return self._get(
            "areaBasedList2",
            {
                "contentTypeId": content_type_id,
                "lDongRegnCd": ldong_regn_cd,
                "lDongSignguCd": ldong_signgu_cd,
                "numOfRows": num_of_rows,
                "pageNo": page_no,
            },
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
