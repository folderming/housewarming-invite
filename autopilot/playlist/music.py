"""음악 생성 API 어댑터.

제공자마다 엔드포인트와 응답 형태가 다르고 자주 바뀐다. 그래서 스펙을
코드에 박지 않고 config/music_providers.json에서 읽어 조립한다. 제공자를
갈아 끼울 때 고쳐야 하는 곳이 설정 파일 한 곳뿐이 되도록 한 것이다.
"""

import json
import os
import time
from pathlib import Path

import requests

CONFIG = Path(__file__).resolve().parent.parent / "config" / "music_providers.json"


class MusicError(RuntimeError):
    pass


def _cfg() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def _dig(obj, dotted: str):
    """'data.0.audio_url' 같은 경로로 중첩 응답에서 값을 꺼낸다."""
    cur = obj
    for part in dotted.split("."):
        cur = cur[int(part)] if part.isdigit() else cur[part]
    return cur


def _auth_headers(spec: dict) -> dict:
    auth = spec.get("auth") or {}
    token = os.environ.get(auth.get("env", ""), "")
    if not token:
        raise MusicError(
            f"환경변수 {auth.get('env')} 가 비어 있습니다. 키를 넣고 다시 실행하세요."
        )
    if auth["type"] == "bearer":
        return {"Authorization": f"Bearer {token}"}
    return {auth["name"]: token}


def _render(template, **vals):
    if isinstance(template, str):
        return template.format(**vals) if "{" in template else template
    if isinstance(template, dict):
        return {k: _render(v, **vals) for k, v in template.items()}
    return template


def generate_track(prompt: str, seconds: int, out_path: Path, dry_run: bool = False) -> Path:
    """트랙 한 개를 생성해 out_path에 저장하고 경로를 돌려준다."""
    cfg = _cfg()
    name = cfg.get("active")
    if not name:
        raise MusicError(
            "config/music_providers.json 의 active 가 null 입니다. "
            "사용할 제공자 이름(예: 'elevenlabs_music')을 넣으세요."
        )
    spec = cfg["providers"][name]
    body = _render(spec["body"], prompt=prompt, duration_ms=seconds * 1000, duration_s=seconds)

    if dry_run:
        print(f"[dry-run] {spec['method']} {spec['endpoint']}")
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return out_path

    resp = requests.request(
        spec["method"], spec["endpoint"],
        headers={**_auth_headers(spec), "Content-Type": "application/json"},
        json=body, timeout=300,
    )
    resp.raise_for_status()

    if spec.get("response_is_binary"):
        out_path.write_bytes(resp.content)
        return out_path

    data = resp.json()
    poll = spec.get("poll") or {}
    if poll.get("enabled"):
        deadline = time.time() + 600
        while time.time() < deadline:
            if _dig(data, poll["status_path"]) == poll["done_value"]:
                break
            time.sleep(10)
            data = requests.get(
                spec["endpoint"], headers=_auth_headers(spec), timeout=60
            ).json()
        else:
            raise MusicError("음원 생성이 제한 시간 안에 끝나지 않았습니다.")

    url = _dig(data, spec["response_audio_path"])
    out_path.write_bytes(requests.get(url, timeout=300).content)
    return out_path
