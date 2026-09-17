# 쓰레드 신규 계정 + API 연결

한 번만 하면 되는 세팅이다. 30~40분쯤 걸리고, 중간에 심사를 기다릴 필요는 없다.

## 1. 계정 만들기

쓰레드 계정은 인스타그램 계정에 묶여 있다. 그래서 순서가 이렇다.

1. **인스타그램 신규 계정 생성** — 기존 개인 계정과 분리한다. 나중에 계정을
   넘기거나 접을 때 개인 계정이 엮이면 곤란해진다.
2. 인스타그램 계정을 **프로페셔널 계정(크리에이터 또는 비즈니스)** 으로 전환한다.
3. 그 계정으로 **쓰레드 가입**.

계정 이름은 바꾸기 번거로우니 처음에 정하고 간다.

## 2. Meta 앱 만들기

1. developers.facebook.com → 내 앱 → 앱 만들기
2. **use case 는 반드시 "Threads"** 를 고른다. Instagram 도, 일반 Business 도 아니다.
   여기서 잘못 고르면 뒤에서 권한이 안 보인다.
3. 앱 설정에서 **Threads API** 를 추가한다.
4. 권한 두 개를 켠다:
   - `threads_basic` — 모든 엔드포인트에 필수
   - `threads_content_publish` — 글 게시에 필요

## 3. 내 계정을 테스터로 등록

**여기가 핵심이다. 이걸 하면 App Review 없이 내 계정에는 바로 글을 올릴 수 있다.**
심사는 남의 계정에 올릴 때 필요한 것이라 지금은 해당 없다.

두 군데에서 해야 한다:

1. Meta 앱 → 역할(Roles) → 쓰레드 테스터로 내 쓰레드 계정 추가
2. **쓰레드 앱 안에서** 설정 → 계정 → 웹사이트 권한 → 초대 수락

2번을 빼먹는 경우가 많다. 토큰이 계속 안 나오면 여기를 먼저 확인한다.

## 4. 토큰 받기

1. 앱에서 단기 액세스 토큰을 받는다. **1시간이면 만료된다.**
2. 그 토큰을 장기 토큰(60일)으로 교환한다:

```bash
python3 -c "
from autopilot.toss.threads_client import exchange_for_long_lived
print(exchange_for_long_lived('<단기토큰>', '<앱시크릿>'))
"
```

3. 사용자 ID 도 같이 받아 둔다(내 쓰레드 계정의 숫자 ID).

> 이 개발 환경에서는 `graph.threads.net` 이 네트워크 정책에 막혀 있어 위 명령이
> 안 돌아간다. 본인 PC 나 Actions 러너에서 실행해야 한다.

## 5. GitHub Secrets 에 넣기

저장소 → Settings → Secrets and variables → Actions → New repository secret

| 이름 | 값 |
|---|---|
| `THREADS_USER_ID` | 쓰레드 사용자 ID |
| `THREADS_ACCESS_TOKEN` | 60일짜리 장기 토큰 |

**토큰을 코드나 커밋에 넣지 않는다.** Secrets 에만 둔다.

## 6. 게시 흐름

```
링크+스크린샷 주기  ->  글 생성 + 대기열 커밋  ->  Actions 가 게시
      (사람)                   (여기)              (하루 3회 자동)
```

- 대기열: `autopilot/out/queue/*.json`
- 올라간 글: `autopilot/out/posted/` 로 옮겨져 재게시되지 않는다
- 한 회차에 최대 5건, 30초 간격. 한꺼번에 쏟으면 스팸으로 읽힌다
- 쓰레드 제한은 계정당 24시간 250건이라 여유가 많다
- 즉시 올리고 싶으면 Actions 탭에서 "쓰레드 게시" 워크플로를 수동 실행

## 7. 60일마다 할 일

장기 토큰은 60일이면 만료된다. 만료되면 자동 게시가 조용히 멈춘다.

```bash
python3 -c "
from autopilot.toss.threads_client import refresh_long_lived_token
print(refresh_long_lived_token('<현재토큰>'))
"
```

새 토큰을 Secrets 에 다시 넣는다. 달력에 50일 뒤 알림을 걸어두는 편이 안전하다.

## 막혔을 때

| 증상 | 확인할 곳 |
|---|---|
| 권한이 목록에 없음 | use case 를 Threads 로 만들었는지 |
| 토큰이 안 나옴 | 3-2 번, 쓰레드 앱에서 초대를 수락했는지 |
| 게시가 401/403 | 토큰 만료(60일) |
| 컨테이너는 되는데 게시 실패 | 대기 시간 부족. `post(wait=10)` 으로 늘린다 |

실패하면 Actions 로그에 응답 본문이 그대로 찍히도록 해 뒀다. 그걸 그대로 주면
내가 고친다.
