#!/usr/bin/env python3
"""새벽 자동 실행의 진입점.

역할 분담이 중요하다. 이미지/영상 생성과 틱톡 업로드는 Higgsfield MCP 도구로만
가능하고, 그건 예약 세션의 Claude가 호출한다. 반대로 '무엇을 만들지 정하는 일'
(컨셉 선택, 중복 배제, 프롬프트/캡션 조립)은 결정론적이라 코드가 맡는 편이
싸고 재현 가능하다. 그래서 이 스크립트는 '작업 지시서(brief)'를 뱉고, 세션은
그 지시서대로 생성 도구를 호출한다.
"""

import argparse
import json
from datetime import date
from pathlib import Path

from core import state
from fashion import captions, concepts as fconcepts, prompts

OUT = Path(__file__).resolve().parent / "out"


def fashion_brief(month: int, images: int, videos: int) -> dict:
    pool = fconcepts.all_concepts(month)
    concept = state.pick("fashion", pool)
    image_prompts = prompts.build_image_prompts(concept, images)

    brief = {
        "track": "fashion",
        "date": date.today().isoformat(),
        "concept": {
            "slug": concept.slug,
            "title": concept.title,
            "brief": concept.brief,
            "trend_item": concept.trend,
        },
        "generate": {
            "images": {
                "model": "soul_2",
                "aspect_ratio": "9:16",
                "count": len(image_prompts),
                "est_credits": round(len(image_prompts) * 0.12, 2),
                "prompts": image_prompts,
            },
            "videos": {
                "model": "veo3_1_lite",
                "aspect_ratio": "9:16",
                "duration": 8,
                "count": videos,
                "est_credits": videos * 8,
                "note": "위 이미지의 job_id를 start_image로 넘길 것. 프롬프트는 "
                        "prompts.build_video_prompts(concept, job_ids, n) 로 생성.",
            },
        },
        "captions": {
            p: captions.build(concept, p)
            for p in ("tiktok", "youtube_shorts", "instagram")
        },
        "publish": {
            "tiktok": "MCP tiktok_publish 사용",
            "youtube_shorts": "YouTube Data API (OAuth 필요) — 미연동 시 out/ 에 보관",
            "instagram": "Graph API (비즈니스 계정 필요) — 미연동 시 out/ 에 보관",
        },
    }
    brief["est_credits_total"] = (
        brief["generate"]["images"]["est_credits"] + brief["generate"]["videos"]["est_credits"]
    )
    state.log_run("fashion", {"slug": concept.slug, "title": concept.title})
    return brief


def main() -> None:
    ap = argparse.ArgumentParser(description="새벽 자동 생성 작업 지시서를 만든다")
    ap.add_argument("track", choices=["fashion"], nargs="?", default="fashion")
    ap.add_argument("--month", type=int, default=date.today().month)
    ap.add_argument("--images", type=int, default=6)
    ap.add_argument("--videos", type=int, default=3)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    briefs = [fashion_brief(args.month, args.images, args.videos)]

    for b in briefs:
        path = OUT / f"{b['date']}-{b['track']}.brief.json"
        path.write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{b['track']}] {b['concept']['title']}")
        print(f"  -> {path}")
        if "est_credits_total" in b:
            print(f"  예상 크레딧: {b['est_credits_total']}")


if __name__ == "__main__":
    main()
