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
    http_status: int | None = None,
) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    if raise_http:
        err = requests.HTTPError("boom")
        if http_status is not None:  # 429 등 상태코드를 exc.response.status_code로 전달
            err.response = MagicMock(status_code=http_status)
        resp.raise_for_status.side_effect = err
    else:
        resp.raise_for_status.side_effect = None
    if bad_json:
        resp.json.side_effect = ValueError("not json")
        resp.text = "<OpenAPI_ServiceResponse>error</OpenAPI_ServiceResponse>"
    else:
        resp.json.return_value = payload
    return resp


def _client_returning(resp: MagicMock) -> tuple[TourApiClient, MagicMock]:
    session = MagicMock(spec=requests.Session)
    session.get.return_value = resp
    client = TourApiClient(service_key="test-key", session=session, backoff_base=0, min_interval=0)  # 재시도 sleep 생략
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

    def test_area_based_sync_list_엔드포인트(self) -> None:
        payload = _envelope({"item": [{"contentid": "1", "showflag": "1", "modifiedtime": "20260101000000"}]})
        client, session = _client_returning(_fake_response(payload))
        result = client.area_based_sync_list(14, num_of_rows=2, page_no=1)
        assert result[0]["showflag"] == "1"
        url, params = session.get.call_args[0][0], session.get.call_args[1]["params"]
        assert url.endswith("/areaBasedSyncList2")
        assert params["contentTypeId"] == 14

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


class TestRetry:
    """재시도/백오프(단계 6). backoff_base=0, min_interval=0으로 sleep 없이 검증한다."""

    @staticmethod
    def _session(*responses: MagicMock) -> MagicMock:
        session = MagicMock(spec=requests.Session)
        if len(responses) == 1:
            session.get.return_value = responses[0]
        else:
            session.get.side_effect = list(responses)
        return session

    def test_재시도가능_오류_후_성공(self) -> None:
        # 첫 호출 HTTP 오류(일시) → 재시도 → 성공
        ok = _fake_response(_envelope({"item": [{"contentid": "1"}]}))
        session = self._session(_fake_response(raise_http=True), ok)
        client = TourApiClient(service_key="k", session=session, backoff_base=0, min_interval=0)
        assert client.area_based_list(14)[0]["contentid"] == "1"
        assert session.get.call_count == 2

    def test_재시도_소진_후_실패(self) -> None:
        session = self._session(_fake_response(raise_http=True))
        client = TourApiClient(service_key="k", session=session, backoff_base=0, min_interval=0, max_retries=2)
        with pytest.raises(TourApiError):
            client.area_based_list(14)
        assert session.get.call_count == 3  # 최초 1 + 재시도 2

    def test_트래픽초과_22는_재시도(self) -> None:
        # 단일키: "22"는 키 전환 불가 → 기존대로 백오프 재시도 (회귀 보존)
        ok = _fake_response(_envelope({"item": [{"contentid": "9"}]}))
        session = self._session(_fake_response(_envelope("", result_code="22")), ok)
        client = TourApiClient(service_key="k", session=session, backoff_base=0, min_interval=0)
        assert client.area_based_list(14)[0]["contentid"] == "9"
        assert session.get.call_count == 2

    def test_키_한도22_다음키로_전환(self) -> None:
        # 다중키: 첫 키 "22" → 두 번째 키로 전환해 즉시 재시도 → 성공
        ok = _fake_response(_envelope({"item": [{"contentid": "9"}]}))
        session = self._session(_fake_response(_envelope("", result_code="22")), ok)
        client = TourApiClient(service_keys=["k1", "k2"], session=session, backoff_base=0, min_interval=0)
        assert client.area_based_list(14)[0]["contentid"] == "9"
        assert session.get.call_count == 2
        # 성공한 두 번째 호출은 전환된 키(k2)로 나갔는지 확인
        assert session.get.call_args.kwargs["params"]["serviceKey"] == "k2"

    def test_모든키_소진시_실패(self) -> None:
        # 다중키: 모든 키가 "22" → 마지막 키 백오프 소진 후 실패
        session = self._session(_fake_response(_envelope("", result_code="22")))
        client = TourApiClient(
            service_keys=["k1", "k2"], session=session, backoff_base=0, min_interval=0, max_retries=2
        )
        with pytest.raises(TourApiError):
            client.area_based_list(14)
        # k1 1회 → k2 전환 후 k2에서 최초1 + 백오프 재시도2 = 1 + 3
        assert session.get.call_count == 4

    def test_429_단일키는_백오프_재시도(self) -> None:
        # 단일키: HTTP 429는 전환 불가 → 백오프 재시도 → 성공
        ok = _fake_response(_envelope({"item": [{"contentid": "7"}]}))
        err = _fake_response(raise_http=True, http_status=429)
        session = self._session(err, ok)
        client = TourApiClient(service_key="k", session=session, backoff_base=0, min_interval=0)
        assert client.area_based_list(14)[0]["contentid"] == "7"
        assert session.get.call_count == 2

    def test_429_다중키는_다음키로_전환(self) -> None:
        # 다중키: HTTP 429(키 한도)도 "22"처럼 다음 키로 전환 → 성공
        ok = _fake_response(_envelope({"item": [{"contentid": "7"}]}))
        err = _fake_response(raise_http=True, http_status=429)
        session = self._session(err, ok)
        client = TourApiClient(service_keys=["k1", "k2"], session=session, backoff_base=0, min_interval=0)
        assert client.area_based_list(14)[0]["contentid"] == "7"
        assert session.get.call_count == 2
        assert session.get.call_args.kwargs["params"]["serviceKey"] == "k2"

    def test_throttle_호출간격_확보(self, monkeypatch: Any) -> None:
        # min_interval 설정 시 직전 호출과의 간격만큼 sleep 한다.
        sleeps: list[float] = []
        clock = iter([0.0, 0.0, 0.05, 0.05])  # _throttle당 monotonic 2회 호출
        monkeypatch.setattr("apps.place.services.tour_api.time.monotonic", lambda: next(clock))
        monkeypatch.setattr("apps.place.services.tour_api.time.sleep", lambda s: sleeps.append(s))
        client = TourApiClient(service_key="k", min_interval=0.3)
        client._throttle()  # wait = 0.3 - (0.0 - 0.0) = 0.3
        client._throttle()  # wait = 0.3 - (0.05 - 0.0) = 0.25
        assert sleeps == [pytest.approx(0.3), pytest.approx(0.25)]

    def test_치명_resultCode는_재시도_안함(self) -> None:
        # 30(키 만료)은 치명 → 즉시 실패
        session = self._session(_fake_response(_envelope("", result_code="30")))
        client = TourApiClient(service_key="k", session=session, backoff_base=0, min_interval=0, max_retries=3)
        with pytest.raises(TourApiError):
            client.area_based_list(14)
        assert session.get.call_count == 1

    def test_비JSON_응답은_재시도_안함(self) -> None:
        # 인증/키 문제로 보이는 비-JSON은 치명 → 즉시 실패
        session = self._session(_fake_response(bad_json=True))
        client = TourApiClient(service_key="k", session=session, backoff_base=0, min_interval=0, max_retries=3)
        with pytest.raises(TourApiError):
            client.area_based_list(14)
        assert session.get.call_count == 1
