"""게시 대기열.

이 개발 환경에서는 graph.threads.net 이 막혀 있어 글을 직접 올릴 수 없다.
그래서 여기서는 글을 대기열에 넣어 커밋만 하고, 실제 게시는 외부망이 열린
GitHub Actions 러너가 맡는다. 올린 글은 posted/ 로 옮겨 재게시를 막는다.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

QUEUE_DIR = Path(__file__).resolve().parent.parent / "out" / "queue"
POSTED_DIR = Path(__file__).resolve().parent.parent / "out" / "posted"


def enqueue(text: str, link: str | None = None, note: str = "") -> Path:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = QUEUE_DIR / f"{stamp}.json"
    path.write_text(
        json.dumps(
            {"text": text, "link_attachment": link, "note": note, "queued_at": stamp},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def pending() -> list[Path]:
    if not QUEUE_DIR.exists():
        return []
    return sorted(QUEUE_DIR.glob("*.json"))


def mark_posted(path: Path, thread_id: str) -> None:
    POSTED_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["thread_id"] = thread_id
    data["posted_at"] = datetime.now(timezone.utc).isoformat()
    (POSTED_DIR / path.name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    path.unlink()
