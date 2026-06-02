# 한국관광공사 Tour API 수집 명세서

한국관광공사의 국문 관광정보 서비스(KorService2) v4.4 API를 활용하여 장소 데이터를 수집하고, AI 성향 분석 파이프라인에 필요한 필드만 선별해 저장하기 위한 문서입니다.

## 0. 구현 순서

완성된 명세를 한 번에 구현하지 않고, 핵심 모델부터 만들어 실제 응답을 확인하며 단계적으로 확장한다. 각 단계가 끝나면 다음 단계로 넘어가기 전에 실제 데이터로 검증한다.

| 단계 | 목표 | 산출물 | 참고 섹션 |
| :---: | :--- | :--- | :--- |
| 1 | 핵심 모델 확정 + 마이그레이션 | `Place`, `PlaceImage` 모델, pgvector 확장 활성화 | §4, §5 |
| 2 | 소량 수집 흐름 검증 | 한 타입·한 지역으로 `areaBasedList2` → `detailCommon2` → `detailImage2` 파이프라인 동작 확인 | §3, §7 |
| 3 | 운영 정보 보강 | `detailIntro2` 호출, `PlaceInfo` 모델·저장 (타입별 필드 실측) | §3, §4, §6 |
| 4 | 태그 부여 — 결정론 영역 | `Tag` 시드 적재, `지역`(주소 파싱)·`편의성`(`PlaceInfo`) 자동 부여 | §8 |
| 5 | 태그 부여 — AI 영역 + 성향 벡터 | `PlaceFeature.style_vector` 산출, `여행 스타일`·`세부 테마`·`동행` AI 부여 | §4, §5, §9 |
| 6 | 대량 적재 + 운영 | 전체 타입·지역 페이지네이션 적재, 에러/재시도/로깅 | §7 |

### 단계별 설계 의도

- **1~2단계를 먼저 굳히는 이유**: `Place`·`PlaceImage`는 수집량이 많아 재수집 비용이 크다. 소량으로 §3 파싱 주의사항(빈 `items` `""`, 단일 `item` dict, 전부 문자열 등)을 실제 응답에서 검증한 뒤 확장한다.
- **`PlaceInfo`·`PlaceFeature`·태그는 파생 데이터**라 스키마를 비교적 자유롭게 바꿀 수 있다. 서비스 오픈 전에는 마이그레이션 자체보다 Tour API 재수집이 실제 비용이므로, 1~2단계 검증 후에는 3단계 이후를 유연하게 반복한다.
- **3단계에서 타입별 필드 실측**: `detailIntro2` 필드 접미사는 `contenttypeid`마다 다르다. 현재 type 14만 확인됐으므로, 수집 대상 타입을 늘릴 때마다 실제 응답으로 매핑 테이블(§3, §4)을 보완한다.
- **4단계(결정론)와 5단계(AI)를 분리하는 이유**: `지역`·`편의성`은 규칙으로 정확히 결정되므로 AI에 맡기지 않는다(§9 가드레일). AI 비용/지연 없이 먼저 채워두고, AI는 판단이 필요한 `여행 스타일`·`세부 테마`·`동행`과 `style_vector`만 담당한다.

### 진행 체크리스트

작업이 중간에 끊겨도 이 목록에서 이어간다. 항목을 끝낼 때마다 `[x]`로 체크한다.

**1단계 — 핵심 모델 + 마이그레이션**
- [x] `Place` 모델 §5 기준 반영
- [x] `PlaceImage` 모델 §5 기준 반영
- [x] pgvector 확장 활성화 (`CREATE EXTENSION vector` / 마이그레이션)
- [x] `makemigrations` + `migrate`

**2단계 — 소량 수집 흐름 검증**
- [x] `areaBasedList2` 한 타입·한 지역 호출
- [x] §3 파싱 주의사항(빈 `items`, 단일 `item` dict, 전부 문자열) 실제 응답으로 확인
- [x] `detailCommon2`로 `overview`·`homepage` 보강
- [x] `detailImage2`로 이미지 수집·저장
- [x] `Place`·`PlaceImage` 저장 결과 확인

**3단계 — 운영 정보 (`PlaceInfo`)**
- [x] `detailIntro2` 호출 + 타입별 필드 실측 (type 14 외 보완)
- [x] `PlaceInfo` 모델 추가 + 마이그레이션
- [x] `PlaceInfo` 저장 (boolean 정규화 포함)

**4단계 — 태그 (결정론 영역)**
- [ ] `Tag` 시드 적재 (여행 스타일·세부 테마·동행·지역·편의성)
- [ ] `지역` 자동 파싱 부여 (`addr1` 시·도 추출)
- [ ] `편의성` `PlaceInfo` 기반 부여

**5단계 — 태그 (AI 영역) + 성향 벡터**
- [ ] `PlaceFeature` 모델 추가 + 마이그레이션
- [ ] `style_vector` 산출 (§9 계약)
- [ ] `여행 스타일`·`세부 테마`·`동행` AI 부여
- [ ] (실험) 리뷰 검색 보강 A/B 테스트 — 효과 검증 후 정식 편입 검토

**6단계 — 대량 적재 + 운영**
- [ ] 전체 타입·지역 페이지네이션 적재
- [ ] 에러/재시도/로깅

## 1. API 호출 환경 설정

### Base Endpoint

| 항목 | 값 |
| :--- | :--- |
| 서비스 | 한국관광공사 국문 관광정보 서비스 v4.4 (`KorService2`) |
| Base URL | `https://apis.data.go.kr/B551011/KorService2` |
| 호출 방식 | `Base URL + /{operation}` |

예시:

```text
https://apis.data.go.kr/B551011/KorService2/areaBasedList2
https://apis.data.go.kr/B551011/KorService2/detailCommon2
https://apis.data.go.kr/B551011/KorService2/detailImage2
```

### API Key

| 항목 | 값 |
| :--- | :--- |
| 환경변수 | `TOUR_API_CODE` |
| 설정 위치 | `.env`, `envs/.env.local` 등 |
| Django 사용 방식 | `settings`에서 환경변수로 읽어 API 호출 시 `serviceKey`에 전달 |

### 공통 요청 파라미터

| 파라미터 | 필수 | 예시 | 설명 |
| :--- | :---: | :--- | :--- |
| `serviceKey` | O | `TOUR_API_CODE` | 공공데이터포털 인증키 |
| `MobileOS` | O | `ETC` | `IOS`, `AND`, `WEB`, `ETC` |
| `MobileApp` | O | `TravelMaker` | 서비스명 |
| `_type` | X | `json` | JSON 응답을 받기 위해 명시 |
| `numOfRows` | X | `100` | 페이지당 결과 수 |
| `pageNo` | X | `1` | 페이지 번호 |

## 2. v4.4 분류 체계 정리

### `cat1`, `cat2`, `cat3`는 사용하지 않는다

한국관광공사 활용매뉴얼 v4.4의 핵심 목록/상세 오퍼레이션은 `lclsSystm1`, `lclsSystm2`, `lclsSystm3` 분류체계를 사용한다. `cat1~cat3`는 일부 예제 응답에 빈 값으로 남아 있는 레거시 호환 필드로 보고, 신규 DB 컬럼/태그 시드/API 필터 기준에서 제외한다.

따라서 `categoryCode2` 기반 설계는 폐기하고, 분류 코드가 필요하면 `lclsSystmCode2`를 기준으로 한다.

### 현재 사용할 코드 체계

| 코드 | 용도 | 저장/활용 판단 |
| :--- | :--- | :--- |
| `contenttypeid` | 관광타입 ID. 아래 8개 타입 구분. `detailIntro2` 호출 시 필수 파라미터 | 저장 권장. 상세 API 호출과 타입별 정책 분기에 필요 |
| `lDongRegnCd` | 법정동 시도 코드 | 미사용. 주소/좌표로 대체 |
| `lDongSignguCd` | 법정동 시군구 코드 | 미사용. 주소/좌표로 대체 |
| `lclsSystm1` | 분류체계 대분류 | 저장 또는 별도 메타 매핑 권장 |
| `lclsSystm2` | 분류체계 중분류 | 저장 또는 별도 메타 매핑 권장 |
| `lclsSystm3` | 분류체계 소분류 | 저장 또는 별도 메타 매핑 권장 |
| `cat1`, `cat2`, `cat3` | 구 서비스 분류 코드 | 미사용 |
| `areacode`, `sigungucode` | 구 지역 코드 | 미사용. 주소/좌표로 대체 |

### `contenttypeid` 값 목록

| 값 | 타입명 | 비고 |
| :---: | :--- | :--- |
| `12` | 관광지 | |
| `14` | 문화시설 | |
| `15` | 축제공연행사 | |
| `25` | 여행코스 | |
| `28` | 레포츠 | |
| `32` | 숙박 | |
| `38` | 쇼핑 | |
| `39` | 음식점 | |

## 3. API 응답 구조

### 공통 응답 처리 주의사항

모든 오퍼레이션 응답은 다음 Tour API 특성을 고려해 파싱해야 한다.

1. **성공 여부는 `header.resultCode`로 판단한다.** `"0000"`만 정상이고, 그 외(`"22"` 트래픽 초과, `"30"` 키 만료/등록되지 않은 키 등)는 에러로 처리하고 재시도/로깅한다.
2. **결과 0건이면 `body.items`가 빈 문자열 `""`로 온다.** `{}`나 `[]`가 아니므로 `items`가 dict인지 먼저 확인한다.
3. **결과가 1건이면 `item`이 리스트가 아니라 단일 객체(dict)로 올 수 있다.** 항상 리스트로 정규화한 뒤 순회한다.
4. **모든 값은 문자열로 온다.** 숫자/좌표(`mapx`, `mapy`, `contentid` 등)는 저장 시 적절한 타입으로 변환한다.
5. **빈 값은 빈 문자열 `""`로 온다.** `null`이 아니므로 `null=True` 필드에 저장할 때는 빈 문자열을 `None`으로 정규화한다.

### `GET /areaBasedList2`

초기 적재에 사용할 목록 API다. 좌표, 주소, 대표 이미지, 분류체계 코드를 가져온다.

```json
{
  "response": {
    "header": {
      "resultCode": "0000",
      "resultMsg": "OK"
    },
    "body": {
      "items": {
        "item": [
          {
            "addr1": "부산광역시 사하구 낙동남로 1240 (하단동)",
            "addr2": "",
            "contentid": "127974",
            "contenttypeid": "12",
            "createdtime": "20031208090000",
            "firstimage": "http://tong.visitkorea.or.kr/cms/resource/21/3497121_image2_1.jpg",
            "firstimage2": "http://tong.visitkorea.or.kr/cms/resource/21/3497121_image3_1.jpg",
            "cpyrhtDivCd": "Type1",
            "mapx": "128.9460030322",
            "mapy": "35.1045320626",
            "mlevel": "6",
            "modifiedtime": "20250618095454",
            "tel": "",
            "title": "을숙도 공원",
            "zipcode": "49435",
            "lDongRegnCd": "26",
            "lDongSignguCd": "380",
            "lclsSystm1": "NA",
            "lclsSystm2": "NA04",
            "lclsSystm3": "NA040500"
          }
        ]
      },
      "numOfRows": 3,
      "pageNo": 1,
      "totalCount": 3
    }
  }
}
```

### `GET /detailCommon2`

AI 성향 분석과 상세 화면에 필요한 `overview`, `homepage`를 보강한다. `contentId`만 필수 요청값이다.

요청 파라미터:

| 파라미터 | 필수 | 예시 | 설명 |
| :--- | :---: | :--- | :--- |
| `MobileOS` | O | `ETC` | OS 구분 |
| `MobileApp` | O | `TESTApp` | 서비스명 |
| `_type` | X | `json` | JSON 응답 형식 |
| `contentId` | O | `2750143` | 콘텐츠 ID |
| `numOfRows` | X | `10` | 한 페이지 결과 수 |
| `pageNo` | X | `1` | 페이지 번호 |
| `serviceKey` | O | `TOUR_API_CODE` | 공공데이터포털 인증키 |

요청 예시:

```text
https://apis.data.go.kr/B551011/KorService2/detailCommon2?MobileOS=ETC&MobileApp=TESTApp&_type=json&contentId=2750143&numOfRows=10&pageNo=1&serviceKey={TOUR_API_CODE}
```

실제 응답 예시:

```json
{
  "response": {
    "header": {
      "resultCode": "0000",
      "resultMsg": "OK"
    },
    "body": {
      "items": {
        "item": [
          {
            "contentid": "2750143",
            "contenttypeid": "14",
            "title": "가가책방",
            "createdtime": "20210928012011",
            "modifiedtime": "20251111151027",
            "tel": "",
            "telname": "",
            "homepage": "<a href=\"https://brunch.co.kr/@captaindrop\" target=\"_blank\" title=\"새창 : 공식 홈페이지 이동\">https://brunch.co.kr/@captaindrop</a>",
            "firstimage": "http://tong.visitkorea.or.kr/cms/resource/06/3564906_image2_1.jpg",
            "firstimage2": "http://tong.visitkorea.or.kr/cms/resource/06/3564906_image3_1.jpg",
            "cpyrhtDivCd": "Type3",
            "areacode": "34",
            "sigungucode": "1",
            "lDongRegnCd": "44",
            "lDongSignguCd": "150",
            "lclsSystm1": "VE",
            "lclsSystm2": "VE12",
            "lclsSystm3": "VE120100",
            "cat1": "A02",
            "cat2": "A0206",
            "cat3": "A02061000",
            "addr1": "충청남도 공주시 당간지주길 10 (반죽동)",
            "addr2": "(반죽동)",
            "zipcode": "32549",
            "mapx": "127.1219749520",
            "mapy": "36.4521187744",
            "mlevel": "6",
            "overview": "가가책방은 2019년 6월 9일 문을 연 공주시 최초의 동네 책방이다. 2020년 코로나 팬데믹 이후 무인으로 운영되고 있다. 책방에 방문하고자 하는 이는 전화 혹은 SNS로 메시지로 비밀번호와 간단한 이용법을 문의해야 한다. 단독 혹은 촬영장 등으로 공간 예약, 이용은 제한된다. 기본적으로 공유 이용 공간이다. 충분히 공간에 만족했거나 좋았다면 입장료 5,000원을 지불할 수 있다. 무인으로 이용되고 있으므로 이용 후 간단한 정리 정돈을 하고 가야 한다."
          }
        ]
      },
      "numOfRows": 1,
      "pageNo": 1,
      "totalCount": 1
    }
  }
}
```

### `GET /detailImage2`

목록/공통 정보의 `firstimage`, `firstimage2`는 대표 이미지와 썸네일 성격이라 최대 2개 수준만 확보된다. 장소 상세 화면에서 여러 이미지를 보여줘야 하므로, `firstimage`가 있는 장소에 한해 `detailImage2`로 관련 이미지를 추가 수집한다.

현재 관찰한 데이터 기준으로는 `firstimage`가 없으면 `detailImage2`에도 이미지가 없는 경우가 대부분이다. 따라서 `firstimage`가 없는 항목은 장소 저장 대상에서 제외하고, `detailImage2`도 호출하지 않는다.

요청은 `contentId` 기준으로 호출하고, 일반 콘텐츠 이미지는 `imageYN=Y`를 사용한다. 음식점 타입에서 메뉴 이미지를 별도로 가져와야 할 때만 `imageYN=N` 사용을 검토한다.

요청 파라미터:

| 파라미터 | 필수 | 예시 | 설명 |
| :--- | :---: | :--- | :--- |
| `MobileOS` | O | `ETC` | OS 구분 |
| `MobileApp` | O | `TESTApp` | 서비스명 |
| `_type` | X | `json` | JSON 응답 형식 |
| `contentId` | O | `2750143` | 콘텐츠 ID |
| `imageYN` | X | `Y` | `Y`: 콘텐츠 이미지, `N`: 음식점 타입의 음식 메뉴 이미지 |
| `numOfRows` | X | `10` | 한 페이지 결과 수 |
| `pageNo` | X | `1` | 페이지 번호 |
| `serviceKey` | O | `TOUR_API_CODE` | 공공데이터포털 인증키 |

요청 예시:

```text
https://apis.data.go.kr/B551011/KorService2/detailImage2?MobileOS=ETC&MobileApp=TESTApp&_type=json&contentId=2750143&imageYN=Y&numOfRows=10&pageNo=1&serviceKey={TOUR_API_CODE}
```

실제 응답 예시:

```json
{
  "response": {
    "header": {
      "resultCode": "0000",
      "resultMsg": "OK"
    },
    "body": {
      "items": {
        "item": [
          {
            "contentid": "2750143",
            "originimgurl": "http://tong.visitkorea.or.kr/cms/resource/02/3564902_image2_1.jpg",
            "imgname": "공주_가가책방 (5)",
            "smallimageurl": "http://tong.visitkorea.or.kr/cms/resource/02/3564902_image3_1.jpg",
            "cpyrhtDivCd": "Type3",
            "serialnum": "3564902_3"
          },
          {
            "contentid": "2750143",
            "originimgurl": "http://tong.visitkorea.or.kr/cms/resource/03/3564903_image2_1.jpg",
            "imgname": "공주_가가책방 (1)",
            "smallimageurl": "http://tong.visitkorea.or.kr/cms/resource/03/3564903_image3_1.jpg",
            "cpyrhtDivCd": "Type3",
            "serialnum": "3564903_1"
          },
          {
            "contentid": "2750143",
            "originimgurl": "http://tong.visitkorea.or.kr/cms/resource/04/3564904_image2_1.jpg",
            "imgname": "공주_가가책방 (2)",
            "smallimageurl": "http://tong.visitkorea.or.kr/cms/resource/04/3564904_image3_1.jpg",
            "cpyrhtDivCd": "Type3",
            "serialnum": "3564904_4"
          },
          {
            "contentid": "2750143",
            "originimgurl": "http://tong.visitkorea.or.kr/cms/resource/05/3564905_image2_1.jpg",
            "imgname": "공주_가가책방 (3)",
            "smallimageurl": "http://tong.visitkorea.or.kr/cms/resource/05/3564905_image3_1.jpg",
            "cpyrhtDivCd": "Type3",
            "serialnum": "3564905_2"
          }
        ]
      },
      "numOfRows": 4,
      "pageNo": 1,
      "totalCount": 4
    }
  }
}
```

### `GET /detailIntro2`

편의성 태그(§8 참고)와 운영 정보(`PlaceInfo`) 보강에 사용한다. `contentTypeId`가 필수 파라미터이므로 `Place.content_type_id`를 함께 전달해야 한다.

요청 파라미터:

| 파라미터 | 필수 | 예시 | 설명 |
| :--- | :---: | :--- | :--- |
| `MobileOS` | O | `ETC` | OS 구분 |
| `MobileApp` | O | `TESTApp` | 서비스명 |
| `_type` | X | `json` | JSON 응답 형식 |
| `contentId` | O | `2750143` | 콘텐츠 ID |
| `contentTypeId` | O | `14` | 관광타입 ID (12:관광지, 14:문화시설, 15:축제공연행사, 25:여행코스, 28:레포츠, 32:숙박, 38:쇼핑, 39:음식점) |
| `serviceKey` | O | `TOUR_API_CODE` | 공공데이터포털 인증키 |

실제 응답 예시 (`contenttypeid=14` 문화시설):

```json
{
  "response": {
    "header": {
      "resultCode": "0000",
      "resultMsg": "OK"
    },
    "body": {
      "items": {
        "item": [
          {
            "contentid": "2750143",
            "contenttypeid": "14",
            "scale": "",
            "usefee": "1인 5,000원",
            "discountinfo": "",
            "spendtime": "",
            "parkingfee": "",
            "infocenterculture": "0507-1486-4982",
            "accomcountculture": "",
            "usetimeculture": "07:00~24:00",
            "restdateculture": "연중무휴",
            "parkingculture": "불가능",
            "chkbabycarriageculture": "",
            "chkpetculture": "",
            "chkcreditcardculture": ""
          }
        ]
      },
      "numOfRows": 1,
      "pageNo": 1,
      "totalCount": 1
    }
  }
}
```

편의성 태그 판단에 사용하는 필드는 `contenttypeid`마다 접미사가 다르다. 아래는 type 14 기준이며, 12·28·32·38·39 타입의 실측 매핑은 §4 "타입별 `detailIntro2` 필드 매핑"을 참고한다.

| 편의성 태그 | contenttypeid=14 필드 | 태그 부여 조건 |
| :--- | :--- | :--- |
| 주차 가능 여부 | `parkingculture` | 값이 비어 있지 않고 "불가"가 아닐 때 |
| 반려동물 동반 가능 | `chkpetculture` | 값이 비어 있지 않고 "불가"가 아닐 때 |
| 무료 입장 여부 | `usefee` | 값이 비어 있거나 "무료"일 때 |
| 유아 동반 가능 | `chkbabycarriageculture` | 값이 비어 있지 않고 "불가"가 아닐 때 |
| 카드 결제 가능 | `chkcreditcardculture` | 값이 비어 있지 않고 "불가"가 아닐 때 |

## 4. 저장 필드 매핑

### `Place` 저장 권장 필드

출처 컬럼은 해당 필드를 어떤 오퍼레이션 응답에서 채우는지를 나타낸다. `areaBasedList2`에 대부분 포함되며, `overview`/`homepage`는 `detailCommon2`에서만 온다.

| API 필드 | 모델 필드 | 출처 | 타입 제안 | Null | 설명 |
| :--- | :--- | :--- | :--- | :---: | :--- |
| `contentid` | `content_id` | `areaBasedList2` | `IntegerField(unique=True, db_index=True)` | X | Tour API 고유 식별자 |
| `contenttypeid` | `content_type_id` | `areaBasedList2` | `PositiveSmallIntegerField(db_index=True)` | X | 상세 API 호출과 타입별 처리 기준 |
| `title` | `place_name` | `areaBasedList2` | `CharField(max_length=100)` | X | 장소명 |
| `mapy` | `latitude` | `areaBasedList2` | `DecimalField(max_digits=18, decimal_places=14)` | O | 위도 |
| `mapx` | `longitude` | `areaBasedList2` | `DecimalField(max_digits=18, decimal_places=14)` | O | 경도 |
| `overview` | `description` | `detailCommon2` | `TextField(null=True, blank=True)` | O | AI 성향 분석 입력 텍스트 |
| `addr1` | `address_primary` | `areaBasedList2` | `CharField(max_length=255)` | O | 기본 주소 |
| `addr2` | `address_detail` | `areaBasedList2` | `CharField(max_length=255)` | O | 상세 주소 |
| `tel` | `tel` | `areaBasedList2` | `CharField(max_length=50)` | O | 전화번호 |
| `homepage` | `homepage` | `detailCommon2` | `URLField` 또는 `TextField` | O | 원문 HTML이 올 수 있으므로 정제 필요 |
| `zipcode` | `zipcode` | `areaBasedList2` | `CharField(max_length=10)` | O | 우편번호 |
| `lclsSystm1` | `lcls_systm1` | `areaBasedList2` | `CharField(max_length=20, db_index=True)` | O | 분류체계 대분류 |
| `lclsSystm2` | `lcls_systm2` | `areaBasedList2` | `CharField(max_length=20, db_index=True)` | O | 분류체계 중분류 |
| `lclsSystm3` | `lcls_systm3` | `areaBasedList2` | `CharField(max_length=20, db_index=True)` | O | 분류체계 소분류 |

### `PlaceInfo` 저장 필드 (`detailIntro2` 기반)

`PlaceInfo`는 `Place`와 1:1로 연결되는 선택적 테이블이다. `detailIntro2` 호출 전이나 실패해도 `Place`는 독립적으로 동작한다. 필드명 접미사(`XXX`)는 `contenttypeid`마다 다르므로 타입별 매핑이 필요하다 (현재 type 14 기준 확인).

| API 필드 (`contenttypeid=14`) | 모델 필드 | 타입 | 설명 |
| :--- | :--- | :--- | :--- |
| `usetimeculture` | `operating_hours` | `TextField` | 운영시간 |
| `restdateculture` | `closed_days` | `TextField` | 휴무일 |
| `parkingculture` | `parking` | `BooleanField(null=True)` | 주차 가능 여부. "불가"/"없음" 포함 시 False, 값 있으면 True, 빈 값이면 None |
| `usefee` | `admission_fee` | `TextField` | 입장료 원문 텍스트 |
| `spendtime` | `spend_time` | `CharField(max_length=50)` | 관람소요시간 |
| `discountinfo` | `discount_info` | `TextField` | 할인정보 |
| `accomcountculture` | `accom_count` | `CharField(max_length=50)` | 수용인원 |
| `chkpetculture` | `pet` | `BooleanField(null=True)` | 반려동물 동반 가능. "불가"/"없음" 포함 시 False, 값 있으면 True, 빈 값이면 None |
| `chkbabycarriageculture` | `baby_carriage` | `BooleanField(null=True)` | 유모차 대여 가능. "불가"/"없음" 포함 시 False, 값 있으면 True, 빈 값이면 None |
| `chkcreditcardculture` | `credit_card` | `BooleanField(null=True)` | 카드 결제 가능. "불가"/"없음" 포함 시 False, 값 있으면 True, 빈 값이면 None |

#### 타입별 `detailIntro2` 필드 매핑 (실측 확정)

장소 타입 6종을 실제 응답으로 실측해 확정한 매핑이다(`apps/place/services/place_info_mapping.py`). 빈 칸은 해당 타입에 그 필드가 없어 `PlaceInfo` 컬럼이 `None`으로 남는다. 축제(15)·여행코스(25)는 `PlaceInfo` 스키마와 맞지 않아 제외한다. `parking`·`pet`·`baby_carriage`·`credit_card`는 boolean 정규화("불가"/"없음" 포함→False, 값 있으면→True, 빈 값→None. 실데이터에 "불가능" 외 "유모차 없음"처럼 "없음"이 와서 함께 False 처리).

| 모델 필드 | 12 관광지 | 14 문화시설 | 28 레포츠 | 32 숙박 | 38 쇼핑 | 39 음식점 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `operating_hours` | `usetime` | `usetimeculture` | `usetimeleports` | `checkintime`+`checkouttime` 조합 | `opentime` | `opentimefood` |
| `closed_days` | `restdate` | `restdateculture` | `restdateleports` | — | `restdateshopping` | `restdatefood` |
| `parking` | `parking` | `parkingculture` | `parkingleports` | `parkinglodging` | `parkingshopping` | `parkingfood` |
| `admission_fee` | — | `usefee` | `usefeeleports` | — | — | — |
| `spend_time` | — | `spendtime` | — | — | — | — |
| `discount_info` | — | `discountinfo` | — | — | — | `discountinfofood` |
| `accom_count` | `accomcount` | `accomcountculture` | `accomcountleports` | `accomcountlodging` | — | — |
| `pet` | `chkpet` | `chkpetculture` | `chkpetleports` | — | `chkpetshopping` | — |
| `baby_carriage` | `chkbabycarriage` | `chkbabycarriageculture` | `chkbabycarriageleports` | — | `chkbabycarriageshopping` | — |
| `credit_card` | `chkcreditcard` | `chkcreditcardculture` | `chkcreditcardleports` | — | `chkcreditcardshopping` | `chkcreditcardfood` |

> 숙박(32)은 운영시간이 `checkintime`/`checkouttime`으로 분리돼 와서 `operating_hours`에 `"체크인 15:00 / 체크아웃 10:00"` 형태로 합쳐 저장한다(`place_sync._lodging_operating_hours`). 그 외 1:1 필드는 `PLACE_INFO_FIELD_MAP`로, 타입 추가 시 실측 후 한 줄 추가한다.

### 저장하지 않거나 별도 처리할 필드

| API 필드 | 판단 | 이유 |
| :--- | :--- | :--- |
| `cat1`, `cat2`, `cat3` | 저장 안 함 | v4.4 신규 분류 기준이 아니며 일부 응답에서 빈 값으로만 남음 |
| `areacode`, `sigungucode` | 저장 안 함 | 주소와 좌표로 대체 |
| `lDongRegnCd`, `lDongSignguCd` | 저장 안 함 | 행정구역 코드 기반 필터/통계가 현재 범위에 없고 주소와 좌표로 충분함 |
| `createdtime`, `modifiedtime` | 저장 안 함 | Tour API 원천 데이터 관리용 메타 정보이며 현재 추천/상세 화면에서 사용하지 않음 |
| `mlevel` | 저장 안 함 | 지도 줌 레벨 힌트이며 서비스 도메인 데이터 가치가 낮음 |
| `telname` | 저장 안 함 | 전화번호 라벨 성격이며 현재 화면/추천 로직에서 사용하지 않음 |
| `cpyrhtDivCd` | 이미지 메타로 저장 검토 | 이미지 저작권 표기 정책에 필요할 수 있음 |

### `PlaceImage` 매핑

| API 필드 | 모델 필드 | 값 |
| :--- | :--- | :--- |
| `detailImage2.originimgurl` | `image_url` | 원본 이미지 URL. 없으면 `smallimageurl`을 대체 저장 |
| `detailImage2.smallimageurl` | `thumbnail_url` | 썸네일 URL |
| `firstimage` | `image_url` | 장소 저장 여부를 판단하는 1차 필터. `detailImage2`가 비어 있을 때 대표 이미지로 저장 |
| `firstimage2` | `thumbnail_url` | `firstimage`의 썸네일 이미지 |

저장하지 않는 필드: `imgname`, `serialnum`, `cpyrhtDivCd` — 현재 화면/추천 로직에서 사용하지 않음.

중복 방지는 `place + image_url` UniqueConstraint로 처리한다. sync 시 `update_or_create(defaults=..., place=..., image_url=...)` 패턴을 사용한다.

이미지 저장 정책은 다음과 같다.

1. 장소 저장 조건은 `firstimage` 존재 여부다. `firstimage`가 없으면 `Place` 자체를 저장하지 않고 `detailImage2`도 호출하지 않는다.
2. `firstimage`가 있는 장소만 `detailImage2`를 호출해 관련 이미지를 모두 저장한다.
3. `originimgurl`과 `smallimageurl`이 모두 비어 있는 `detailImage2` 항목은 이미지로 저장하지 않는다.
4. `detailImage2` 결과가 있으면 `firstimage`, `firstimage2`는 별도 이미지로 중복 저장하지 않는다.
5. `detailImage2` 결과가 없으면 `firstimage`, `firstimage2`를 대표 이미지/썸네일로 저장한다.
6. 기본 이미지 URL이나 빈 문자열 레코드는 저장하지 않는다.
7. `PlaceImage`에는 `content_id`를 중복 저장하지 않는다. 부모 장소는 `Place.content_id`로 조회하고, 이미지는 `place` 외래 키에 연결한다.
8. 중복 방지는 `place + image_url` UniqueConstraint로 처리하고, sync 시 `update_or_create` 패턴을 사용한다.
9. 대표 이미지는 `order=0` 또는 첫 번째 수집 이미지에 `is_main=True`를 부여한다.

### 장소 성향 벡터 테이블

장소 성향 벡터는 `Place` 본체에 합치지 않고 별도 테이블에서 관리한다. 컬럼명은 범용적인 `embedding` 대신 도메인 의미가 드러나는 `style_vector`를 사용한다. 미니 프로젝트 범위에서는 버전, 산출 시각(`computed_at`), 산출 출처(`source`)까지 분리하지 않고 `updated_at`을 최신 계산 시각으로 사용한다.

> 유저 설문 기반 벡터(`user_features`)와 설문 점수 계산 방식은 본 수집 명세 범위 밖이며 별도 추천/설문 문서에서 다룬다.

| 테이블 | 참조 | 벡터 컬럼 | 설명 |
| :--- | :--- | :--- | :--- |
| `place_features` | `place_id` | `style_vector VECTOR(6)` | 장소 설명/태그/AI 분석 결과로 계산한 장소 성향 벡터 |

테이블 컬럼은 단순하게 유지한다.

| 테이블 | 컬럼 |
| :--- | :--- |
| `place_features` | `id`, `place_id`, `style_vector`, `created_at`, `updated_at` |

`style_vector`는 아래 순서의 6차원 고정 벡터다. 저장값은 `0.0~1.0` 정규화 값을 사용한다. `0.5`는 중립, `1.0`은 + 방향 극단, `0.0`은 - 방향 극단이다.

| 인덱스 | 축 | + 방향 | - 방향 |
| :---: | :--- | :--- | :--- |
| 0 | 활동성 | 액티비티형 | 힐링형 |
| 1 | 계획성 | 계획형 | 즉흥형 |
| 2 | 사교성 | 혼자형 | 단체형 |
| 3 | 공간지향 | 자연형 | 도시형 |
| 4 | 경험지향 | 문화형 | 체험형 |
| 5 | 소비스타일 | 가성비형 | 럭셔리형 |

각 방향의 의미는 다음과 같다.

| 축 | + 방향 의미 | - 방향 의미 |
| :--- | :--- | :--- |
| 활동성 | 활동량이 많고 직접 움직이는 일정, 액티비티, 탐험형 장소를 선호 | 휴식, 여유, 회복, 조용한 체류 중심의 장소를 선호 |
| 계획성 | 일정과 동선을 미리 정하고 예측 가능한 여행을 선호 | 현장에서 즉흥적으로 결정하고 유연하게 움직이는 여행을 선호 |
| 사교성 | 혼자만의 시간, 개인 취향, 독립적인 탐방을 선호 | 동행과 함께 즐기거나 사람들과 어울리는 경험을 선호 |
| 공간지향 | 자연, 야외, 풍경, 한적한 공간을 선호 | 도시, 상권, 실내 시설, 접근성 높은 공간을 선호 |
| 경험지향 | 전시, 역사, 지역문화, 감상 중심의 문화 경험을 선호 | 직접 참여, 체험, 놀이, hands-on 활동을 선호 |
| 소비스타일 | 가격 대비 만족도, 합리적 비용, 부담 없는 소비를 선호 | 프리미엄, 고급 시설, 특별한 서비스와 지출 경험을 선호 |

### 장소 벡터 계산 예시 — 가가책방 (`content_id=2750143`)

`overview`, `lclsSystm`, `usefee`, `parkingculture` 등을 종합해 AI가 판단한 예시.

| 인덱스 | 축 | 판단 | 근거 | 값 |
| :---: | :--- | :--- | :--- | :---: |
| 0 | 활동성 | 힐링형 (−) | 조용한 책방, 정적인 체류 | `0.2` |
| 1 | 계획성 | 계획형 (+) | 방문 전 SNS로 비밀번호 문의 필요 | `0.65` |
| 2 | 사교성 | 혼자형 (+) | 무인 운영, 개인 취향 공간 | `0.75` |
| 3 | 공간지향 | 도시형 (−) | 도시 내 골목 책방, 실내 공간 | `0.35` |
| 4 | 경험지향 | 문화형 (+) | 지역 독립 서점, 감상·탐방 중심 | `0.75` |
| 5 | 소비스타일 | 가성비형 (+) | 5,000원 자율 입장료, 부담 없는 공간 | `0.65` |

```python
style_vector = [0.2, 0.65, 0.75, 0.35, 0.75, 0.65]
```

태그: `여행 스타일: 문화` / `세부 테마: 박물관·전시` / `동행: 혼자, 커플` / `지역: 충남` / `편의성: 주차(False)`

## 5. 모델 코드 초안

실제 구현 시 현재 `apps/place/models.py`에 바로 반영하기 전 마이그레이션 영향과 기존 API 응답을 확인한다.

```python
from django.db import models
from pgvector.django import VectorField

from apps.core.models import TimeStampModel


class Place(TimeStampModel):
    place_name = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=18, decimal_places=14, null=True, blank=True)
    longitude = models.DecimalField(max_digits=18, decimal_places=14, null=True, blank=True)
    rating_avg = models.DecimalField(max_digits=2, decimal_places=1, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    description = models.TextField(null=True, blank=True)

    content_id = models.IntegerField(unique=True, db_index=True)
    content_type_id = models.PositiveSmallIntegerField(db_index=True)

    address_primary = models.CharField(max_length=255, null=True, blank=True)
    address_detail = models.CharField(max_length=255, null=True, blank=True)
    tel = models.CharField(max_length=50, null=True, blank=True)
    homepage = models.TextField(null=True, blank=True)
    zipcode = models.CharField(max_length=10, null=True, blank=True)

    lcls_systm1 = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    lcls_systm2 = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    lcls_systm3 = models.CharField(max_length=20, null=True, blank=True, db_index=True)

    tags = models.ManyToManyField("Tag", related_name="places", blank=True)

    class Meta:
        db_table = "places"
        indexes = [
            models.Index(fields=["place_name"]),
            models.Index(fields=["content_id"]),
            models.Index(fields=["content_type_id"]),
        ]


class PlaceImage(models.Model):
    place = models.ForeignKey(Place, related_name="images", on_delete=models.CASCADE)
    image_url = models.CharField(max_length=500)
    thumbnail_url = models.CharField(max_length=500, null=True, blank=True)
    is_main = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["place", "image_url"],
                name="unique_place_image_url",
            ),
        ]
        ordering = ["order", "id"]


class PlaceInfo(models.Model):
    place = models.OneToOneField(Place, related_name="info", on_delete=models.CASCADE)
    operating_hours = models.TextField(null=True, blank=True)
    closed_days = models.TextField(null=True, blank=True)
    parking = models.BooleanField(null=True)
    admission_fee = models.TextField(null=True, blank=True)
    spend_time = models.CharField(max_length=50, null=True, blank=True)
    discount_info = models.TextField(null=True, blank=True)
    accom_count = models.CharField(max_length=50, null=True, blank=True)
    pet = models.BooleanField(null=True)
    baby_carriage = models.BooleanField(null=True)
    credit_card = models.BooleanField(null=True)

    class Meta:
        db_table = "place_info"


class PlaceFeature(TimeStampModel):
    place = models.OneToOneField(Place, related_name="feature", on_delete=models.CASCADE)
    style_vector = VectorField(dimensions=6)

    class Meta:
        db_table = "place_features"
```

## 6. 오퍼레이션 사용 범위

### 필수

| 오퍼레이션 | 판단 | 이유 |
| :--- | :--- | :--- |
| `GET /areaBasedList2` | 필수 | 초기 대량 적재. 좌표, 주소, 대표 이미지, 분류체계 코드 확보 |
| `GET /detailCommon2` | 필수 | `overview`가 AI 성향 분석의 핵심 입력값 |
| `GET /detailImage2` | 필수 | `firstimage`가 있는 장소의 관련 이미지를 모두 확보하기 위해 필요. `firstimage`가 없으면 호출하지 않음 |

### 사전 시드 또는 메타 데이터

| 오퍼레이션 | 판단 | 이유 |
| :--- | :--- | :--- |
| `GET /lclsSystmCode2` | 필요 | `lclsSystm1~3` 코드명을 태그/필터/관리자 화면에 매핑 |

### 보류

| 오퍼레이션 | 판단 | 이유 |
| :--- | :--- | :--- |
| `GET /detailIntro2` | 필요 | 편의성 태그 5종 부여 및 `PlaceInfo` 운영 정보(운영시간·휴무일·입장료 등) 보강에 필요. 타입별 필드 접미사가 다르므로 매핑 테이블 참고 |
| `GET /detailInfo2` | 보류 | 반복 정보 구조가 타입별로 달라 우선순위 낮음 |
| `GET /detailPetTour2` | 보류 | 반려동물 동반 정보가 추천 핵심 범위에 들어올 때 확장 |
| `GET /areaBasedSyncList2` | 보류 | 운영 단계에서 관광공사 변경분을 주기적으로 반영할 때 사용. 현재는 초기 적재 중심이라 제외 |

### 제외

| 오퍼레이션 | 판단 | 이유 |
| :--- | :--- | :--- |
| `GET /locationBasedList2` | 제외 | 좌표 저장 후 DB 거리 연산으로 대체 |
| `GET /searchKeyword2` | 제외 | 내부 검색은 로컬 DB 인덱스/검색 쿼리로 처리 |
| `GET /searchFestival2` | 제외 | 축제(`contenttypeid=15`)도 `areaBasedList2`로 통합 수집 가능 |
| `GET /searchStay2` | 제외 | 숙박(`contenttypeid=32`)도 통합 수집 가능 |
| `GET /categoryCode2` | 제외 | v4.4 기준 설계에서 `cat1~cat3`를 사용하지 않음 |
| `GET /areaCode2` | 제외 | 주소와 좌표로 대체 |
| `GET /ldongCode2` | 제외 | 법정동 코드 기반 필터/통계를 현재 범위에서 사용하지 않음 |

## 7. 수집 처리 정책

1. 초기 적재는 `areaBasedList2`를 `contentTypeId`와 지역 범위 기준으로 페이지네이션한다.
2. 목록 응답에서 `firstimage`가 없는 항목은 저장하지 않고 스킵한다. 이 경우 `detailImage2`도 호출하지 않는다.
3. `firstimage`가 있는 항목만 `contentid` 기준으로 `Place`를 `update_or_create`한다.
4. `detailCommon2`를 호출해 `overview`, `homepage`를 보강한다.
5. `detailImage2?contentId={content_id}&imageYN=Y`를 호출해 관련 이미지를 모두 `PlaceImage`로 저장한다.
6. `detailImage2` 결과가 없으면 `firstimage`를 대표 이미지로, `firstimage2`를 썸네일로 저장한다.
7. `createdtime`, `modifiedtime`은 저장하지 않는다.
8. `areaBasedSyncList2` 기반 증분 동기화는 현재 범위에서 구현하지 않는다.
9. `lclsSystmCode2`는 주기적으로 호출하지 않고 코드명 변경 대응이 필요할 때 수동 또는 관리 명령으로 갱신한다.

## 8. 태그 시드 정의

태그는 AI가 장소의 `overview`, `lclsSystm` 코드 등을 분석해 미리 정의된 목록에서 선택해 부여한다. `style_vector`와 데이터적으로 연관되지만 각각 독립적으로 작동한다.

### `여행 스타일` (7개)

장소의 전반적인 여행 성격을 나타낸다.

| tag_name |
| :--- |
| 해변 |
| 산악 |
| 도시 |
| 문화 |
| 미식 |
| 액티비티 |
| 로맨틱 |

### `세부 테마` (20개)

장소의 구체적인 유형을 나타낸다.

| tag_name |
| :--- |
| 해수욕·해안 |
| 수상레저 |
| 캠핑·글램핑 |
| 산·숲·계곡 |
| 자연생태 |
| 자연공원·트레킹 |
| 랜드마크 |
| 공원·거리 |
| 쇼핑 |
| 역사·유적 |
| 박물관·전시 |
| 전통체험 |
| 음식점 |
| 카페·디저트 |
| 시장·먹거리 |
| 육상스포츠 |
| 항공·익스트림 |
| 테마파크·시설 |
| 스파·웰니스 |
| 숙박·리조트 |

### `동행` (4개)

어떤 동행 유형에 어울리는 장소인지를 나타낸다. `가족`은 어린이와 어른을 모두 포함한다.

| tag_name |
| :--- |
| 혼자 |
| 커플 |
| 가족 |
| 친구 |

### `지역` (17개)

장소의 시·도 단위 행정구역. `addr1` 필드에서 파싱해 자동 부여한다.

| tag_name |
| :--- |
| 서울 |
| 인천 |
| 대전 |
| 대구 |
| 광주 |
| 부산 |
| 울산 |
| 세종 |
| 경기 |
| 강원 |
| 충북 |
| 충남 |
| 전북 |
| 전남 |
| 경북 |
| 경남 |
| 제주 |

### `편의성` (5개)

장소의 실용 정보를 나타낸다. `detailIntro2` 응답에서 파싱해 부여한다.

| tag_name | 소스 필드 (contenttypeid=14 기준) |
| :--- | :--- |
| 주차 가능 여부 | `parkingculture` → `PlaceInfo.parking` |
| 반려동물 동반 가능 | `chkpetculture` → `PlaceInfo.pet` |
| 무료 입장 여부 | `usefee` → `PlaceInfo.admission_fee` |
| 유아 동반 가능 | `chkbabycarriageculture` → `PlaceInfo.baby_carriage` |
| 카드 결제 가능 | `chkcreditcardculture` → `PlaceInfo.credit_card` |

타입별 필드명 접미사가 다르므로 실제 구현 시 각 타입의 응답을 확인해 매핑 테이블을 보완한다.

### 태그 부여 방식

| tag_type | 부여 주체 | 입력 데이터 |
| :--- | :--- | :--- |
| 여행 스타일 | AI | `overview`, `lclsSystm`, `contenttypeid` |
| 세부 테마 | AI | `overview`, `lclsSystm`, `contenttypeid` |
| 동행 | AI | `overview` |
| 지역 | 자동 파싱 | `addr1` 시·도 추출 |
| 편의성 | 직접 판단 | `PlaceInfo` boolean 필드 (`True`일 때만 태그 부여) |

### 태그 부여 예시 — 가가책방 (`content_id=2750143`)

태그 수에 상한을 두지 않고 장소 특성에 맞게 부여한다.

| tag_type | tag_name | 부여 근거 |
| :--- | :--- | :--- |
| 여행 스타일 | 문화 | 지역 독립 서점, 감상·탐방 중심 공간 |
| 여행 스타일 | 로맨틱 | 조용하고 감성적인 분위기 |
| 세부 테마 | 박물관·전시 | `contenttypeid=14` (문화시설), `lclsSystm1=VE` |
| 세부 테마 | 랜드마크 | 공주시 최초 동네 책방, 지역 특색 공간 |
| 세부 테마 | 쇼핑 | 책 구매 가능한 서점 공간 |
| 동행 | 혼자 | 무인 운영, 개인 취향 공간 |
| 동행 | 커플 | 조용한 분위기, 소수 방문 적합 |
| 지역 | 충남 | `addr1` = "충청남도 공주시..." → 충남 파싱 |

편의성 태그는 부여되지 않음: 주차 불가(`parking=False`), 유료 입장(`admission_fee="1인 5,000원"`), 반려동물·유아·카드 정보 없음(`null`).

## 9. AI 가공 프롬프트 계약

AI 가공 단계는 `overview` 등을 입력받아 **태그 부여**와 **`style_vector` 산출**을 동시에 수행한다. 프롬프트 문구 자체는 코드에서 튜닝하되, 아래 입출력 계약과 가드레일은 고정한다. 문구를 이 문서에 박지 않는 이유는 잦은 튜닝으로 금방 낡기 때문이다.

### 입력

| 항목 | 출처 | 설명 |
| :--- | :--- | :--- |
| `place_name` | `Place.place_name` | 장소명 |
| `overview` | `Place.description` | 핵심 입력 텍스트 |
| `content_type_id` | `Place.content_type_id` | 타입명으로 변환해 전달 (예: 14 → 문화시설) |
| `lcls_systm1~3` | `Place.lcls_systm*` | `lclsSystmCode2` 코드명과 함께 전달 |
| `address_primary` | `Place.address_primary` | 보조 맥락 |
| 후보 태그 목록 | 태그 시드 | **`여행 스타일`·`세부 테마`·`동행`만** 후보로 제공 |

### 출력 (JSON 스키마 고정)

```json
{
  "tags": {
    "여행 스타일": ["문화", "로맨틱"],
    "세부 테마": ["박물관·전시", "랜드마크", "쇼핑"],
    "동행": ["혼자", "커플"]
  },
  "style_vector": [0.2, 0.65, 0.75, 0.35, 0.75, 0.65],
  "reason": "판단 근거 (디버깅용, DB 저장하지 않음)"
}
```

### 가드레일

1. 태그는 **제공된 후보 목록에서만** 선택한다. 새 태그를 생성하지 않는다.
2. `style_vector`는 **정확히 6개**, 각 값 `0.0~1.0`, **축 순서 고정**(활동성 → 계획성 → 사교성 → 공간지향 → 경험지향 → 소비스타일).
3. **`지역`·`편의성` tag_type은 AI가 부여하지 않는다.** 각각 `addr1` 파싱, `PlaceInfo` 필드로 결정론적으로 처리하므로 후보로 제공하지 않는다.
4. 태그 개수에 상한을 두지 않되, 근거가 명확한 것만 부여한다.

### 예외 처리

- `overview`가 비어 있으면 `lcls_systm`·`content_type_id`만으로 최소 태그를 추정하고, `style_vector`는 중립(`0.5`) 또는 산출 보류를 택한다. 산출 보류 시 `PlaceFeature`를 생성하지 않는다.

가가책방(§4 벡터 예시, §8 태그 예시)이 이 계약의 정답 케이스다.
