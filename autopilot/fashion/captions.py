"""플랫폼별 캡션 조립.

공정위 표시는 선택이 아니라 의무다. 제휴 링크가 하나라도 들어가는 순간
캡션 최상단에 고지 문구가 붙도록 구조적으로 강제한다(빼먹을 수 없게).
"""

import json
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config"


def affiliate_config() -> dict:
    return json.loads((CONFIG / "affiliate.json").read_text(encoding="utf-8"))


BASE_TAGS = ["데일리룩", "오늘의코디", "코디추천", "패션추천", "옷추천"]

TAGS_BY_OCCASION = {
    "commute": ["출근룩", "오피스룩", "직장인코디"],
    "campus": ["캠퍼스룩", "대학생코디", "학교갈때"],
    "date": ["데이트룩", "소개팅룩"],
    "wedding_guest": ["하객룩", "결혼식하객"],
    "travel": ["여행룩", "공항패션"],
    "daily": ["동네룩", "편안한코디"],
    "first_cold": ["가을코디", "간절기아우터"],
    "transition": ["간절기코디", "환절기룩"],
    "rainy": ["비오는날코디"],
    "interview": ["면접룩", "취준생"],
}

TAGS_BY_ANGLE = {
    "body_short_leg": ["숏다리코디", "다리길어보이는"],
    "body_broad": ["어깨넓은체형", "상체커버"],
    "body_slim": ["마른체형코디"],
    "body_curvy": ["통통코디", "체형커버"],
    "tone_cool": ["쿨톤코디"],
    "tone_warm": ["웜톤코디"],
    "one_item": ["하나로여러가지"],
    "minimal_closet": ["옷장털기"],
}


def hashtags(concept, limit: int = 12) -> list[str]:
    tags = (
        BASE_TAGS
        + TAGS_BY_OCCASION.get(concept.occasion["id"], [])
        + TAGS_BY_ANGLE.get(concept.angle["id"], [])
        + [concept.trend.replace(" ", "")]
    )
    seen, out = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:limit]


def _disclosure_lines(links: list[dict]) -> list[str]:
    """제휴 링크가 있으면 반드시 고지. 쿠팡이 섞이면 쿠팡 전용 문구를 쓴다."""
    cfg = affiliate_config()["disclosure"]
    if not links:
        return [cfg["ai_notice"]]
    has_coupang = any(l.get("program") == "coupang_partners" for l in links)
    text = cfg["ko_coupang"] if has_coupang else cfg["ko_short"]
    return [text, cfg["ai_notice"]]


def _link_block(links: list[dict]) -> list[str]:
    if not links:
        return ["🔗 상품 링크 준비 중 (제휴 계정 연동 후 자동 삽입)"]
    return [f"· {l['label']} → {l['url']}" for l in links]


def build(concept, platform: str, links: list[dict] | None = None) -> str:
    links = links or []
    head = _disclosure_lines(links)
    body = [
        "",
        f"{concept.title}",
        "",
        f"이번 포인트는 {concept.trend}.",
        f"{concept.angle['desc']} — 여기에 맞춰 골랐어요.",
        "",
        *_link_block(links),
        "",
    ]
    tags = " ".join(f"#{t}" for t in hashtags(concept))

    if platform == "instagram":
        body.insert(1, "저장해두고 아침에 그대로 따라 입기 👗")
    elif platform == "tiktok":
        body.insert(1, "3초 안에 결론부터 ↓")
    elif platform == "youtube_shorts":
        body.insert(1, "아래 설명란에 아이템별로 정리해뒀어요.")

    lines = head + body + [tags]
    text = "\n".join(lines)

    limits = json.loads((CONFIG / "platforms.json").read_text(encoding="utf-8"))
    cap = limits.get(platform, {}).get("caption_max")
    if cap and len(text) > cap:
        text = text[: cap - 1].rstrip() + "…"
    return text
