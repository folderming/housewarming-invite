"""토스쇼핑 쉐어링크 딜 하나를 표현하는 구조.

쉐어링크는 클릭 후 24시간 안에 결제돼야 수익이 잡힌다. 쿠팡 파트너스보다
창이 훨씬 짧다. 그래서 '예쁘다'로 끝나는 콘텐츠가 아니라 '지금 사야 한다'로
끝나는 콘텐츠여야 한다. 아래 필드가 그 판단에 필요한 최소 정보다.
"""

from dataclasses import dataclass, field


@dataclass
class Deal:
    name: str                      # 상품명 (짧게 다듬은 것)
    price: int                     # 현재가
    url: str                       # 쉐어링크 (반드시 '쉐어링크 공유하기'로 받은 것)
    list_price: int | None = None  # 정가/비교가. 있으면 할인율을 자동 계산한다.
    unit: str | None = None        # "1팩당 400원" 같은 환산 단위. 체감 가격을 만든다.
    category: str = "생활용품"
    note: str | None = None        # 직접 써본 소감 한 줄. 없으면 경험담 훅을 쓰지 않는다.
    deadline: str | None = None    # "오늘 자정", "10000개 한정" 등
    compare_to: str | None = None  # "올리브영 2만원" 같은 비교 대상
    tags: list[str] = field(default_factory=list)

    @property
    def discount_pct(self) -> int | None:
        if not self.list_price or self.list_price <= self.price:
            return None
        return round((1 - self.price / self.list_price) * 100)

    @property
    def price_str(self) -> str:
        return f"{self.price:,}원"

    def validate(self) -> list[str]:
        """올리기 전에 걸러야 할 문제들."""
        problems = []
        if not self.url.strip():
            problems.append("쉐어링크가 비어 있습니다.")
        elif "toss" not in self.url.lower():
            problems.append(f"토스 링크가 아닌 것 같습니다: {self.url}")
        if self.price <= 0:
            problems.append("가격이 올바르지 않습니다.")
        if self.list_price and self.list_price <= self.price:
            problems.append("정가가 현재가보다 낮거나 같습니다. 할인 표현을 쓰면 안 됩니다.")
        return problems
