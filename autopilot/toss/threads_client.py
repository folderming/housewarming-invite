"""Threads API 클라이언트.

게시는 두 단계다. 먼저 컨테이너를 만들고(create), 그 다음 그 컨테이너를
게시한다(publish). 한 번에 끝나지 않는 건 미디어 처리 시간 때문이고,
텍스트 글도 같은 절차를 따른다.

주의: 이 코드는 개발 환경에서 graph.threads.net 이 막혀 있어 실제 호출로
검증하지 못했다. GitHub Actions 러너에서 처음 돌 때 실패하면 응답 본문을
그대로 찍도록 해 뒀으니 그걸 보고 고치면 된다.
"""

import os
import time

import requests

BASE = "https://graph.threads.net/v1.0"
TOKEN_BASE = "https://graph.threads.net"


class ThreadsError(RuntimeError):
    pass


def _check(resp: requests.Response, what: str) -> dict:
    if not resp.ok:
        raise ThreadsError(f"{what} 실패 [{resp.status_code}]: {resp.text[:800]}")
    return resp.json()


class ThreadsClient:
    def __init__(self, user_id: str | None = None, token: str | None = None):
        self.user_id = user_id or os.environ.get("THREADS_USER_ID", "")
        self.token = token or os.environ.get("THREADS_ACCESS_TOKEN", "")
        if not self.user_id or not self.token:
            raise ThreadsError(
                "THREADS_USER_ID 와 THREADS_ACCESS_TOKEN 이 필요합니다. "
                "GitHub 저장소 Secrets 에 넣으세요."
            )

    def create_container(self, text: str, link_attachment: str | None = None) -> str:
        payload = {"media_type": "TEXT", "text": text, "access_token": self.token}
        if link_attachment:
            payload["link_attachment"] = link_attachment
        data = _check(
            requests.post(f"{BASE}/{self.user_id}/threads", data=payload, timeout=60),
            "컨테이너 생성",
        )
        if "id" not in data:
            raise ThreadsError(f"컨테이너 id 가 응답에 없습니다: {data}")
        return data["id"]

    def publish(self, creation_id: str) -> str:
        data = _check(
            requests.post(
                f"{BASE}/{self.user_id}/threads_publish",
                data={"creation_id": creation_id, "access_token": self.token},
                timeout=60,
            ),
            "게시",
        )
        return data.get("id", "")

    def post(self, text: str, link_attachment: str | None = None, wait: int = 5) -> str:
        """글 하나를 올리고 게시된 글 id 를 돌려준다."""
        cid = self.create_container(text, link_attachment)
        # 컨테이너가 처리될 시간을 준다. 곧바로 publish 하면 종종 실패한다.
        time.sleep(wait)
        return self.publish(cid)


def refresh_long_lived_token(token: str) -> dict:
    """장기 토큰은 60일이면 만료된다. 만료 전에 갱신해야 자동화가 끊기지 않는다."""
    return _check(
        requests.get(
            f"{TOKEN_BASE}/refresh_access_token",
            params={"grant_type": "th_refresh_token", "access_token": token},
            timeout=60,
        ),
        "토큰 갱신",
    )


def exchange_for_long_lived(short_token: str, app_secret: str) -> dict:
    """최초 1회. 1시간짜리 단기 토큰을 60일짜리로 바꾼다."""
    return _check(
        requests.get(
            f"{TOKEN_BASE}/access_token",
            params={
                "grant_type": "th_exchange_token",
                "client_secret": app_secret,
                "access_token": short_token,
            },
            timeout=60,
        ),
        "토큰 교환",
    )
