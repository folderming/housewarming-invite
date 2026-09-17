#!/usr/bin/env python3
"""대기열에 쌓인 글을 Threads 에 올린다. GitHub Actions 러너에서 실행된다.

한 건이 실패해도 나머지는 계속 시도한다. 하나 때문에 그날 물량이
통째로 막히는 게 더 나쁘기 때문이다. 실패분은 대기열에 남아 다음 회차에
다시 시도된다.
"""

import json
import sys
import time

from postqueue import mark_posted, pending
from threads_client import ThreadsClient, ThreadsError

MAX_PER_RUN = 5  # 한 번에 쏟아부으면 스팸으로 보인다. 나눠서 올린다.
GAP_SECONDS = 30


def main() -> int:
    items = pending()
    if not items:
        print("대기열이 비어 있습니다. 할 일 없음.")
        return 0

    try:
        client = ThreadsClient()
    except ThreadsError as e:
        print(f"::error::{e}")
        return 1

    todo = items[:MAX_PER_RUN]
    print(f"대기 {len(items)}건 중 {len(todo)}건 처리합니다.")

    failed = 0
    for i, path in enumerate(todo):
        data = json.loads(path.read_text(encoding="utf-8"))
        try:
            thread_id = client.post(data["text"], data.get("link_attachment"))
            mark_posted(path, thread_id)
            print(f"[{i+1}/{len(todo)}] 게시 완료: {path.name} -> {thread_id}")
        except ThreadsError as e:
            failed += 1
            print(f"::warning::[{i+1}/{len(todo)}] 실패({path.name}): {e}")
        if i < len(todo) - 1:
            time.sleep(GAP_SECONDS)

    if failed:
        print(f"::warning::{failed}건 실패. 대기열에 남아 다음 회차에 다시 시도합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
