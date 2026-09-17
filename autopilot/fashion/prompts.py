"""컨셉 -> Higgsfield 생성 프롬프트.

이미지(soul_2)는 0.12크레딧, 영상은 8크레딧 선이다. 약 65배 차이라
'이미지를 많이, 영상을 적게' 뽑는 것이 유일하게 지속 가능한 구조다.
그래서 컷 리스트도 이미지 우선으로 짠다.
"""

import json
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config"


def character() -> dict:
    return json.loads((CONFIG / "character.json").read_text(encoding="utf-8"))


def _identity_block() -> str:
    c = character()
    p = c["physical"]
    return f"{p['base']}. {p['face']}. {p['vibe']}. {c['consistency_anchor']}"


# 한 포스트를 구성하는 컷 구성. 이미지가 캐러셀과 영상 시작프레임을 동시에 겸한다.
SHOT_PLAN = [
    {"id": "hero", "ko": "전신 정면", "desc": "전신이 다 나오는 정면 컷, 코디 전체가 한눈에 보이게"},
    {"id": "detail", "ko": "상체 디테일", "desc": "가슴~허리 크롭, 소재와 핏이 보이게"},
    {"id": "walking", "ko": "걷는 옆모습", "desc": "측면에서 걷는 순간, 옷의 흐름이 보이게"},
    {"id": "sitting", "ko": "앉은 컷", "desc": "그 장소에 자연스럽게 앉거나 기댄 자세"},
    {"id": "back", "ko": "뒷모습", "desc": "뒤에서 본 실루엣과 기장감"},
    {"id": "closeup", "ko": "포인트 아이템", "desc": "신발/가방 등 포인트 아이템 클로즈업, 인물은 일부만"},
]


def image_prompt(concept, shot: dict, scene: str) -> str:
    """soul_2용 이미지 프롬프트 한 개."""
    return (
        f"{_identity_block()} "
        f"장면: {scene}. "
        f"컷: {shot['desc']}. "
        f"스타일링 컨셉: {concept.occasion['ko']} - {concept.occasion['desc']}. "
        f"체형/톤 고려: {concept.angle['desc']}. "
        f"핵심 아이템: {concept.trend}. "
        f"제약: {concept.hook['desc']}. "
        "한국 20대 여성 데일리 패션 화보 톤, 자연광, 필름 그레인 약간, "
        "과한 후보정 없이 실제 사진처럼. 세로 구도."
    )


def scene_for(concept) -> str:
    """상황에 맞는 배경. 배경이 바뀌면 같은 코디도 다른 콘텐츠로 읽힌다."""
    table = {
        "commute": "서울 오피스 밀집가 아침 거리, 유리 건물 반사광",
        "campus": "대학 캠퍼스 벤치와 가로수길, 늦은 오후 햇빛",
        "date": "성수동 골목 카페 앞, 따뜻한 조명",
        "wedding_guest": "호텔 로비 대리석 복도, 부드러운 실내광",
        "travel": "공항 게이트 앞 큰 창가, 역광",
        "daily": "동네 편의점 앞 저녁, 간판 불빛",
        "first_cold": "찬 바람 부는 한강 산책로, 흐린 하늘",
        "transition": "아침 버스 정류장, 옅은 안개",
        "rainy": "비 온 뒤 젖은 아스팔트 골목, 반사되는 불빛",
        "interview": "회사 건물 로비 앞, 깔끔한 채광",
    }
    return table.get(concept.occasion["id"], "서울 도심 거리, 자연광")


def build_image_prompts(concept, n: int) -> list[dict]:
    scene = scene_for(concept)
    shots = SHOT_PLAN[:n]
    return [
        {"index": i, "shot": s["id"], "prompt": image_prompt(concept, s, scene)}
        for i, s in enumerate(shots)
    ]


def build_video_prompts(concept, image_job_ids: list[str], n: int) -> list[dict]:
    """영상은 생성한 이미지를 start_image로 써서 비용과 인물 일관성을 동시에 잡는다."""
    motions = [
        "인물이 천천히 카메라 쪽으로 걸어온다. 카메라는 고정, 옷의 움직임이 보이게.",
        "카메라가 아래에서 위로 부드럽게 틸트업하며 전신을 훑는다.",
        "인물이 제자리에서 반 바퀴 돌아 뒷모습에서 정면으로 바뀐다.",
    ]
    out = []
    for i in range(min(n, len(image_job_ids))):
        out.append({
            "index": i,
            "start_image": image_job_ids[i],
            "prompt": f"{motions[i % len(motions)]} {scene_for(concept)}. 자연스러운 속도, 슬로우모션 아님.",
        })
    return out
