"""detailIntro2 타입별 필드 매핑 (PlaceInfo, 단계 3).

`detailIntro2` 응답 필드명은 `contenttypeid`마다 다르다. 아래 매핑은 실제 응답으로 실측해 확정했다
(12 관광지·14 문화시설·28 레포츠·32 숙박·38 쇼핑·39 음식점). 축제(15)·여행코스(25)는 PlaceInfo
스키마와 맞지 않아 제외한다. 타입을 추가할 때는 실측 후 이 dict에 한 줄 추가한다.

각 항목은 {PlaceInfo 필드: detailIntro2 API 키}. 해당 타입에 없는 PlaceInfo 필드는 키를 넣지 않아
None으로 남는다. `BOOLEAN_FIELDS`는 "불가"/값 유무로 정규화하는 boolean 필드다(§4).
"""

PLACE_INFO_FIELD_MAP: dict[int, dict[str, str]] = {
    12: {  # 관광지 (usefee/spendtime/discountinfo 없음)
        "operating_hours": "usetime",
        "closed_days": "restdate",
        "parking": "parking",
        "accom_count": "accomcount",
        "pet": "chkpet",
        "baby_carriage": "chkbabycarriage",
        "credit_card": "chkcreditcard",
    },
    14: {  # 문화시설
        "operating_hours": "usetimeculture",
        "closed_days": "restdateculture",
        "parking": "parkingculture",
        "admission_fee": "usefee",
        "spend_time": "spendtime",
        "discount_info": "discountinfo",
        "accom_count": "accomcountculture",
        "pet": "chkpetculture",
        "baby_carriage": "chkbabycarriageculture",
        "credit_card": "chkcreditcardculture",
    },
    28: {  # 레포츠 (spendtime/discountinfo 없음)
        "operating_hours": "usetimeleports",
        "closed_days": "restdateleports",
        "parking": "parkingleports",
        "admission_fee": "usefeeleports",
        "accom_count": "accomcountleports",
        "pet": "chkpetleports",
        "baby_carriage": "chkbabycarriageleports",
        "credit_card": "chkcreditcardleports",
    },
    32: {  # 숙박 (operating_hours는 checkin/checkout 조합이라 place_sync에서 특수 처리)
        "parking": "parkinglodging",
        "accom_count": "accomcountlodging",
    },
    38: {  # 쇼핑 (usefee/spendtime/discountinfo/accomcount 없음)
        "operating_hours": "opentime",
        "closed_days": "restdateshopping",
        "parking": "parkingshopping",
        "pet": "chkpetshopping",
        "baby_carriage": "chkbabycarriageshopping",
        "credit_card": "chkcreditcardshopping",
    },
    39: {  # 음식점 (chkpet/chkbabycarriage/usefee 없음)
        "operating_hours": "opentimefood",
        "closed_days": "restdatefood",
        "parking": "parkingfood",
        "discount_info": "discountinfofood",
        "credit_card": "chkcreditcardfood",
    },
}

#: "불가"/"없음" 포함 시 False, 값 있으면 True, 빈 값이면 None으로 정규화하는 필드.
BOOLEAN_FIELDS = frozenset({"parking", "pet", "baby_carriage", "credit_card"})

#: detailIntro2의 전화번호(infocenter*) 필드명 → Place.tel. 타입마다 키가 다르다(§3).
#: tel은 목록(areaBasedList2)에 축제 외엔 거의 빈 값으로 오고, 실제 번호는 detailIntro2 infocenter*에 온다.
#: 축제(15)·여행코스(25)는 detailIntro2를 호출하지 않으므로(매핑 없음) 목록 tel을 그대로 쓴다.
INFOCENTER_KEY: dict[int, str] = {
    12: "infocenter",
    14: "infocenterculture",
    28: "infocenterleports",
    32: "infocenterlodging",
    38: "infocentershopping",
    39: "infocenterfood",
}

#: 숙박은 운영시간이 단일 필드가 아니라 체크인/체크아웃으로 분리돼 온다(place_sync에서 합친다).
LODGING_TYPE_ID = 32
LODGING_CHECKIN_KEY = "checkintime"
LODGING_CHECKOUT_KEY = "checkouttime"
