# 새벽 자동 실행 런북

예약 세션(Routine)이 이 문서를 그대로 따라 실행한다. 사람이 깨어 있을 필요가 없도록
판단 지점마다 기본값을 정해 두었다.

## 0. 준비 확인

```bash
cd autopilot && pip install -q -r requirements.txt
```

크레딧 잔량을 먼저 본다(`balance`). **30 크레딧 미만이면 영상을 건너뛰고 이미지만
생성한다.** 잔량을 다 태우고 멈추는 것보다 매일 조금씩 나가는 편이 낫다.

## 1. 작업 지시서 생성

```bash
python3 cli.py both
```

`out/<날짜>-fashion.brief.json` 과 `out/<날짜>-playlist.brief.json` 이 나온다.
컨셉은 이미 쓴 것을 배제하고 뽑히므로 중복 걱정은 하지 않아도 된다.

## 2. 트렌드 슬롯 갱신 (주 1회, 월요일에만)

`fashion/concepts.py` 의 `TREND_ITEMS` 는 손으로 박아 둔 값이라 시간이 지나면 낡는다.
월요일 실행분에서만 웹 검색으로 "이번 주 패션 트렌드 아이템"을 확인하고, 바뀐 게
있으면 리스트를 갱신한 뒤 커밋한다. 다른 요일에는 건드리지 않는다.

## 3. 패션 트랙 실행

1. brief 의 `generate.images.prompts` 를 `generate_image_batch` 로 한 번에 제출한다
   (모델 `soul_2`, `aspect_ratio: 9:16`).
2. `jobs_wait` 로 전부 끝날 때까지 기다린다.
3. 완료된 job_id 목록을 `prompts.build_video_prompts(concept, job_ids, n)` 에 넣어
   영상 프롬프트를 만들고, `generate_video_batch` 로 제출한다
   (모델 `veo3_1_lite`, `duration: 8`, `generate_audio: false`).
   - **영상은 이미지를 `start_image` 로 받아야 한다.** 텍스트만으로 다시 생성하면
     인물이 달라져 캐릭터 일관성이 깨진다.
4. 결과를 `show_generation_by_ids` 로 한 번에 정리한다.
5. 틱톡 게시: `tiktok_prepare_publish` → `tiktok_publish`. 캡션은 brief 의
   `captions.tiktok` 을 그대로 쓴다.
6. 유튜브/인스타는 API 미연동 상태이므로, 결과 URL과 캡션을 brief 에 덧붙여
   `out/` 에 남기고 아침에 사람이 올리게 둔다.

## 4. 플레이리스트 트랙 실행

1. 커버: `generate_image` (모델 `nano_banana_pro`, `16:9`), 프롬프트는 brief 의
   `generate.cover.prompt`.
2. 음원: `config/music_providers.json` 의 `active` 가 `null` 이면 **이 단계를 건너뛰고**
   컨셉과 커버만 남긴다. 키가 있으면:

```bash
python3 -c "
from pathlib import Path
from playlist.music import generate_track
import json
b = json.load(open('out/<날짜>-playlist.brief.json'))
m = b['generate']['music']
Path('out/tracks').mkdir(parents=True, exist_ok=True)
for i in range(m['tracks']):
    generate_track(m['prompt'], m['seconds_each'], Path(f'out/tracks/t{i}.mp3'))
"
```

3. 조립:

```bash
python3 -c "
from pathlib import Path
from playlist.assemble import build
print(build(sorted(Path('out/tracks').glob('*.mp3')), Path('out/cover.png'),
            minutes=120, out_dir=Path('out'), slug='today'))
"
```

4. 유튜브 업로드는 미연동이므로 `out/today.mp4` 와 설명란 텍스트를 남겨 둔다.

## 5. 마무리

- `out/state.json` 을 포함해 그날 산출물을 커밋하고 푸시한다.
  상태 파일이 커밋돼야 다음 실행이 중복을 피한다.
- 생성 실패나 크레딧 부족은 조용히 넘어가지 말고 커밋 메시지에 남긴다.

## 하지 말 것

- 쿠팡/지그재그의 **상품 사진을 받아다 캐릭터에 합성하지 않는다.** 판매자 저작물이고,
  파트너스가 제공한 이미지는 비변형 사용이 원칙이다. 상품 사진은 원본 그대로 별도
  컷으로 쓰고, 착용 이미지는 AI로 따로 만든 스타일링 레퍼런스로 둔다.
- 캡션에서 공정위 고지 문구를 빼지 않는다. `captions.build()` 가 자동으로 넣는다.
- 같은 컨셉을 이틀 연속 올리지 않는다. `state.json` 이 막아 주지만, 수동 실행 시 주의.
