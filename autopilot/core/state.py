"""무엇을 이미 썼는지 기록해 중복을 막는다.

자동화의 실패는 대부분 "같은 걸 또 올림"에서 온다. 조합 수가 아무리 많아도
매번 랜덤이면 생일 문제로 금방 겹치므로, 쓴 slug를 파일에 남기고 배제한다.
"""

import json
import random
from datetime import date
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parent.parent / "out"
STATE_FILE = STATE_DIR / "state.json"


def _load() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"used": {}, "runs": []}


def _save(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def pick(track: str, candidates: list, key=lambda c: c.slug, seed: str | None = None):
    """아직 안 쓴 후보 중 하나를 고르고 즉시 사용 처리한다.

    전부 소진되면 가장 오래된 것부터 재사용한다(기록은 갱신).
    """
    state = _load()
    used = state["used"].setdefault(track, {})

    fresh = [c for c in candidates if key(c) not in used]
    # 같은 날 여러 번 뽑을 때 시드가 같으면 인접한 후보만 나온다.
    # 이미 쓴 개수를 시드에 섞어 호출마다 분포를 흩는다.
    rng = random.Random(seed or f"{date.today().isoformat()}:{track}:{len(used)}")

    if fresh:
        chosen = rng.choice(fresh)
    else:
        oldest = min(used.items(), key=lambda kv: kv[1])[0]
        chosen = next((c for c in candidates if key(c) == oldest), rng.choice(candidates))

    used[key(chosen)] = date.today().isoformat()
    _save(state)
    return chosen


def log_run(track: str, payload: dict) -> None:
    state = _load()
    state["runs"].append({"track": track, "date": date.today().isoformat(), **payload})
    state["runs"] = state["runs"][-200:]
    _save(state)


def recent(track: str, n: int = 10) -> list[dict]:
    return [r for r in _load()["runs"] if r["track"] == track][-n:]
