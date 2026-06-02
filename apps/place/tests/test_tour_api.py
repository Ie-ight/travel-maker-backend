"""TourApiClient·§3 공통 응답 처리 테스트.

명세 §3 의 실제 샘플 응답 구조와 합성 엣지(빈 items, 단일 item dict 등)를 검증한다.
외부 호출은 requests.Session.get 모킹으로 대체한다.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from apps.place.services.tour_api import (
    TourApiClient,
    TourApiError,
    _check_header,
    _extract_items,
)


def _envelope(items: Any, *, result_code: str = "0000") -> dict[str, Any]:
    """명세 §3 응답 구조(response.header / response.body.items)로 감싼다."""
    return {
        "response": {
            "header": {"resultCode": result_code, "resultMsg": "OK"},
            "body": {"items": items, "numOfRows": 10, "pageNo": 1, "totalCount": 1},
        }
    }


def _fake_response(
    payload: dict[str, Any] | None = None,
    *,
    raise_http: bool = False,
    bad_json: bool = False,
) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.raise_for_status.side_effect = requests.HTTPError("boom") if raise_http else None
    if bad_json:
        resp.json.side_effect = ValueError("not json")
        resp.text = "<OpenAPI_ServiceResponse>error</OpenAPI_ServiceResponse>"
    else:
        resp.json.return_value = payload
    return resp


def _client_returning(resp: MagicMock) -> tuple[TourApiClient, MagicMock]:
    session = MagicMock(spec=requests.Session)
    session.get.return_value = resp
    client = TourApiClient(service_key="test-key", session=session)
    return client, session


class TestExtractItems:
    def test_빈_items_문자열은_빈_리스트(self) -> None:
        # 결과 0건이면 items가 "" 로 온다 (§3-2)
        assert _extract_items({"items": ""}) == []

    def test_items_누락도_빈_리스트(self) -> None:
        assert _extract_items({}) == []

    def test_단일_item_dict는_리스트로_정규화(self) -> None:
        # 결과 1건이면 item이 단일 dict로 올 수 있다 (§3-3)
        result = _extract_items({"items": {"item": {"contentid": "1"}}})
        assert result == [{"contentid": "1"}]

    def test_item_리스트는_그대로(self) -> None:
        result = _extract_items({"items": {"item": [{"contentid": "1"}, {"contentid": "2"}]}})
        assert [row["contentid"] for row in result] == ["1", "2"]

    def test_빈_item은_빈_리스트(self) -> None:
        assert _extract_items({"items": {"item": ""}}) == []


class TestCheckHeader:
    def test_정상코드는_통과(self) -> None:
        _check_header({"header": {"resultCode": "0000", "resultMsg": "OK"}})

    @pytest.mark.parametrize("code", ["22", "30", ""])
    def test_비정상코드는_에러(self, code: str) -> None:
        with pytest.raises(TourApiError):
            _check_header({"header": {"resultCode": code, "resultMsg": "ERR"}})

    def test_헤더_누락도_에러(self) -> None:
        with pytest.raises(TourApiError):
            _check_header({})


class TestTourApiClient:
    def test_area_based_list_파라미터와_반환(self) -> None:
        payload = _envelope({"item": [{"contentid": "127974", "title": "을숙도 공원"}]})
        client, session = _client_returning(_fake_response(payload))

        result = client.area_based_list(12, ldong_regn_cd="26", num_of_rows=5, page_no=1)

        assert result[0]["title"] == "을숙도 공원"
        url, kwargs = session.get.call_args[0][0], session.get.call_args[1]
        assert url.endswith("/areaBasedList2")
        params = kwargs["params"]
        assert params["contentTypeId"] == 12
        assert params["lDongRegnCd"] == "26"
        assert params["_type"] == "json"
        assert params["serviceKey"] == "test-key"

    def test_none_파라미터는_전송하지_않음(self) -> None:
        client, session = _client_returning(_fake_response(_envelope({"item": []})))
        client.area_based_list(14)  # ldong 미지정
        params = session.get.call_args[1]["params"]
        assert "lDongRegnCd" not in params
        assert "lDongSignguCd" not in params

    def test_detail_common_단일결과_dict_반환(self) -> None:
        payload = _envelope({"item": {"contentid": "2750143", "overview": "설명"}})
        client, _ = _client_returning(_fake_response(payload))
        common = client.detail_common(2750143)
        assert common is not None
        assert common["overview"] == "설명"

    def test_detail_common_결과없으면_None(self) -> None:
        client, _ = _client_returning(_fake_response(_envelope("")))
        assert client.detail_common(2750143) is None

    def test_detail_image_리스트_반환(self) -> None:
        payload = _envelope({"item": [{"originimgurl": "a.jpg"}, {"originimgurl": "b.jpg"}]})
        client, _ = _client_returning(_fake_response(payload))
        assert len(client.detail_image(2750143)) == 2

    def test_detail_intro_contentTypeId_전송(self) -> None:
        payload = _envelope({"item": {"contentid": "2750143", "usetimeculture": "07:00~24:00"}})
        client, session = _client_returning(_fake_response(payload))
        intro = client.detail_intro(2750143, 14)
        assert intro is not None
        url, params = session.get.call_args[0][0], session.get.call_args[1]["params"]
        assert url.endswith("/detailIntro2")
        assert params["contentId"] == 2750143
        assert params["contentTypeId"] == 14

    def test_비정상_resultCode는_TourApiError(self) -> None:
        client, _ = _client_returning(_fake_response(_envelope("", result_code="30")))
        with pytest.raises(TourApiError):
            client.area_based_list(14)

    def test_http_오류는_TourApiError(self) -> None:
        client, _ = _client_returning(_fake_response(raise_http=True))
        with pytest.raises(TourApiError):
            client.area_based_list(14)

    def test_비_JSON_응답은_TourApiError(self) -> None:
        client, _ = _client_returning(_fake_response(bad_json=True))
        with pytest.raises(TourApiError):
            client.area_based_list(14)
