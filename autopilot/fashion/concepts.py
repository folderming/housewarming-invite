"""패션 CPS 콘텐츠의 컨셉 뱅크.

단일 주제 리스트를 쓰면 2주 만에 소재가 마른다. 그래서 축을 셋으로 쪼개
조합으로 뽑는다: 상황(occasion) x 앵글(angle) x 제약(hook). 축이 늘어날수록
조합 수는 곱으로 늘어나므로, 같은 컨셉이 다시 나오기까지의 주기가 길어진다.
"""

from dataclasses import dataclass

# 상황 — "언제 입는 옷인가". 검색/저장을 유발하는 가장 강한 축.
OCCASIONS = [
    {"id": "commute", "ko": "출근룩", "desc": "오피스 캐주얼, 과하지 않고 단정한", "months": None},
    {"id": "campus", "ko": "캠퍼스룩", "desc": "강의실-카페 동선, 편하되 꾸민 티", "months": [3, 4, 5, 9, 10, 11]},
    {"id": "date", "ko": "데이트룩", "desc": "여성스럽되 부담 없는, 사진 잘 나오는", "months": None},
    {"id": "wedding_guest", "ko": "하객룩", "desc": "예의 갖추되 튀지 않는", "months": [3, 4, 5, 9, 10, 11]},
    {"id": "travel", "ko": "여행룩", "desc": "많이 걷고 사진 많이 찍는 날", "months": None},
    {"id": "daily", "ko": "동네 마실룩", "desc": "편의점-카페 5분 거리, 대충인데 봐줄 만한", "months": None},
    {"id": "first_cold", "ko": "첫 추위룩", "desc": "갑자기 기온 떨어진 날 급하게", "months": [10, 11]},
    {"id": "transition", "ko": "간절기룩", "desc": "낮엔 덥고 아침저녁 추운 날", "months": [3, 4, 9, 10]},
    {"id": "rainy", "ko": "비 오는 날 코디", "desc": "젖어도 티 안 나고 눅눅하지 않은", "months": [6, 7, 8, 9]},
    {"id": "interview", "ko": "면접룩", "desc": "신입 기준, 과하지 않은 포멀", "months": [3, 4, 9, 10]},
]

# 앵글 — "누구의 문제를 푸는가". 저장(save)과 공유를 만드는 축.
ANGLES = [
    {"id": "body_short_leg", "ko": "숏다리 보완", "desc": "하체 길이 커버, 상의 기장과 밑위 중심"},
    {"id": "body_broad", "ko": "어깨 넓은 체형", "desc": "상체 볼륨 분산, 넥라인 중심"},
    {"id": "body_slim", "ko": "마른 체형", "desc": "빈약해 보이지 않게 볼륨 채우기"},
    {"id": "body_curvy", "ko": "통통한 체형", "desc": "조이지 않으면서 라인 정리"},
    {"id": "tone_cool", "ko": "쿨톤", "desc": "쿨톤 피부에 붙는 컬러 조합"},
    {"id": "tone_warm", "ko": "웜톤", "desc": "웜톤 피부에 붙는 컬러 조합"},
    {"id": "one_item", "ko": "아이템 하나로 3가지", "desc": "같은 옷 다르게 입기"},
    {"id": "minimal_closet", "ko": "옷장에 이미 있는 것", "desc": "새로 살 건 한 개만"},
]

# 제약(훅) — "왜 지금 눌러야 하는가". 클릭을 만드는 축. 제휴 전환에 직결.
HOOKS = [
    {"id": "budget_30k", "ko": "3만원으로 완성", "desc": "전체 합 3만원 이하", "budget": 30000},
    {"id": "budget_50k", "ko": "5만원 한 장으로", "desc": "전체 합 5만원 이하", "budget": 50000},
    {"id": "single_item", "ko": "딱 한 개만 사면 되는", "desc": "핵심 아이템 1개 + 기본템", "budget": None},
    {"id": "no_iron", "ko": "다림질 안 해도 되는", "desc": "구김 없는 소재 위주", "budget": None},
    {"id": "five_min", "ko": "5분 만에 입고 나가는", "desc": "고민 없는 고정 공식", "budget": None},
    {"id": "all_season", "ko": "가을부터 겨울까지", "desc": "레이어링으로 시즌 확장", "budget": None},
]

# 트렌드 슬롯 — 여기만 주기적으로 갈아 끼우면 전체가 최신으로 유지된다.
# 새벽 세션이 실행될 때 웹 검색으로 갱신하도록 런북에 명시.
TREND_ITEMS = [
    "스웨이드 자켓", "발레코어 플랫", "니트 베스트", "와이드 코듀로이",
    "크롭 가디건", "머플러 레이어드", "청키 로퍼", "브라운 톤 세트업",
]


@dataclass(frozen=True)
class Concept:
    occasion: dict
    angle: dict
    hook: dict
    trend: str

    @property
    def slug(self) -> str:
        return f"{self.occasion['id']}__{self.angle['id']}__{self.hook['id']}"

    @property
    def title(self) -> str:
        """썸네일/첫 3초에 그대로 얹는 한 줄."""
        return f"{self.angle['ko']} {self.occasion['ko']}, {self.hook['ko']}"

    @property
    def brief(self) -> str:
        return (
            f"상황: {self.occasion['ko']}({self.occasion['desc']}) / "
            f"앵글: {self.angle['ko']}({self.angle['desc']}) / "
            f"훅: {self.hook['ko']}({self.hook['desc']}) / "
            f"트렌드 아이템: {self.trend}"
        )


def in_season(occasion: dict, month: int) -> bool:
    return occasion["months"] is None or month in occasion["months"]


def all_concepts(month: int) -> list[Concept]:
    """해당 월에 유효한 전체 조합. 시즌 안 맞는 상황은 걸러낸다."""
    out = []
    for o in OCCASIONS:
        if not in_season(o, month):
            continue
        for a in ANGLES:
            for h in HOOKS:
                for t in TREND_ITEMS:
                    out.append(Concept(o, a, h, t))
    return out
