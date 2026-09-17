"""딜 하나에서 쓰레드/오픈채팅 글을 만든다.

두 채널은 읽는 태도가 다르다. 쓰레드는 타임라인에 흘러가므로 첫 줄에서
멈춰 세워야 하고, 오픈채팅은 이미 딜을 보러 들어온 사람들이라 가격부터
말하는 게 맞다. 그래서 같은 딜이라도 문장을 따로 만든다.
"""

from .deal import Deal

# 광고 표시는 법적 의무다(공정위 추천·보증 심사지침). 빼는 경로를 두지 않는다.
DISCLOSURE_THREADS = "쉐어링크로 수익이 발생할 수 있어요."
DISCLOSURE_CHAT = "[쉐어링크 · 수익 발생 가능]"


def _hooks(d: Deal) -> list[str]:
    """딜의 성격에 맞는 첫 줄 후보들. 근거 없는 훅은 만들지 않는다."""
    out = []

    if d.unit:
        out.append(f"{d.unit}이면 그냥 쟁여두는 게 맞지 않나")
    if d.discount_pct and d.discount_pct >= 40:
        out.append(f"이거 왜 {d.discount_pct}%나 빠졌지")
    if d.compare_to:
        out.append(f"{d.compare_to} 주고 샀던 거, 여기 {d.price_str}")
    if d.note:
        out.append(f"{d.note}")
    if d.price <= 10000:
        out.append(f"{d.price_str}짜리 치고 괜찮아서 두 번 삼")

    out.append(f"{d.name} 지금 {d.price_str}")
    return out


def threads(d: Deal, variant: int = 0) -> str:
    """쓰레드용. 첫 두 줄만 노출되므로 훅과 핵심을 앞에 몰아 넣는다."""
    hooks = _hooks(d)
    hook = hooks[variant % len(hooks)]

    lines = [hook, ""]

    body = []
    if d.list_price and d.discount_pct:
        body.append(f"{d.list_price:,}원 → {d.price_str} ({d.discount_pct}% 할인)")
    else:
        body.append(f"{d.price_str}")
    if d.unit:
        body.append(d.unit)
    if d.note and d.note != hook:
        body.append(d.note)
    if d.deadline:
        body.append(f"{d.deadline}까지라 급하면 지금.")
    lines += body

    lines += ["", d.url, "", DISCLOSURE_THREADS]
    return "\n".join(lines)


def openchat(d: Deal) -> str:
    """오픈채팅용. 스크롤에 묻히므로 가격과 마감을 맨 위로 올린다."""
    head = f"{d.name} · {d.price_str}"
    if d.discount_pct:
        head += f" ({d.discount_pct}%↓)"

    lines = [DISCLOSURE_CHAT, "", head]
    if d.unit:
        lines.append(f"→ {d.unit}")
    if d.compare_to:
        lines.append(f"→ 참고: {d.compare_to}")
    if d.note:
        lines.append(f"→ {d.note}")
    if d.deadline:
        lines.append(f"⏰ {d.deadline}")
    lines += ["", d.url]
    return "\n".join(lines)


def variants(d: Deal, n: int = 3) -> list[str]:
    """같은 딜을 며칠 간격으로 다시 올릴 때 쓸 변형들."""
    return [threads(d, i) for i in range(min(n, len(_hooks(d))))]


def build_all(d: Deal) -> dict:
    problems = d.validate()
    if problems:
        return {"ok": False, "problems": problems}
    return {
        "ok": True,
        "threads": threads(d),
        "threads_variants": variants(d),
        "openchat": openchat(d),
    }
