"""플레이리스트 컨셉 뱅크.

플리 채널은 음악 자체보다 '언제 트는가'로 소비된다. 그래서 장르가 아니라
장면(scene)을 1순위 축으로 둔다. 제목에 장면이 박혀야 검색과 저장이 붙는다.
"""

from dataclasses import dataclass

# 장면 — 제목의 뼈대. 구체적일수록 강하다("공부할 때" < "새벽 3시 과제 마감 30분 전")
SCENES = [
    {"id": "dawn_convenience", "ko": "새벽 2시 편의점 앞", "mood": "혼자, 약간 나른하고 공허한"},
    {"id": "rainy_bus", "ko": "비 오는 날 퇴근길 버스 창가", "mood": "창밖 번지는 불빛, 지친 안도감"},
    {"id": "deadline", "ko": "마감 3시간 전 책상 앞", "mood": "초조하지만 집중이 필요한"},
    {"id": "sunday_morning", "ko": "일요일 아침 늦잠 깬 방", "mood": "느리고 따뜻한, 서두를 것 없는"},
    {"id": "night_drive", "ko": "한강 야경 드라이브", "mood": "탁 트이고 약간 들뜬"},
    {"id": "first_snow", "ko": "첫눈 오는 날 창가", "mood": "설레고 조용한"},
    {"id": "cafe_corner", "ko": "구석 자리 카페 오후 3시", "mood": "잔잔하고 사색적인"},
    {"id": "before_sleep", "ko": "불 끄고 누운 직후", "mood": "가라앉히는, 생각 정리되는"},
    {"id": "autumn_walk", "ko": "낙엽 밟으며 혼자 걷는 길", "mood": "쓸쓸하되 편안한"},
    {"id": "workout", "ko": "새벽 러닝 시작 직전", "mood": "몸이 깨어나는, 리듬감 있는"},
]

# 장르/사운드 — 실제 음원 생성 프롬프트로 들어가는 축.
SOUNDS = [
    {"id": "lofi", "ko": "로파이 힙합", "prompt": "lo-fi hip hop, dusty vinyl texture, mellow rhodes, soft boom-bap drums, no vocals"},
    {"id": "citypop", "ko": "시티팝", "prompt": "80s japanese city pop instrumental, warm analog synth, clean electric guitar, groovy bass, no vocals"},
    {"id": "jazz", "ko": "재즈 트리오", "prompt": "late night jazz trio, brushed drums, upright bass, soft piano improvisation, no vocals"},
    {"id": "ambient", "ko": "앰비언트", "prompt": "ambient soundscape, slow evolving pads, subtle field recording, deep reverb, no vocals"},
    {"id": "neoclassical", "ko": "네오클래시컬 피아노", "prompt": "neoclassical solo piano, felt piano close-mic, minimal and emotional, no vocals"},
    {"id": "bossa", "ko": "보사노바", "prompt": "bossa nova instrumental, nylon guitar, light shaker, warm and unhurried, no vocals"},
    {"id": "synthwave", "ko": "신스웨이브", "prompt": "chill synthwave, analog arpeggio, wide pads, steady midtempo pulse, no vocals"},
]

# 러닝타임 프리셋. 2시간이 기본이나, 장면에 따라 최적 길이가 다르다.
DURATIONS = [
    {"id": "study_2h", "minutes": 120, "fit": ["deadline", "cafe_corner", "sunday_morning"]},
    {"id": "sleep_3h", "minutes": 180, "fit": ["before_sleep", "first_snow"]},
    {"id": "commute_1h", "minutes": 60, "fit": ["rainy_bus", "night_drive", "workout"]},
]


@dataclass(frozen=True)
class PlaylistConcept:
    scene: dict
    sound: dict
    minutes: int

    @property
    def slug(self) -> str:
        return f"{self.scene['id']}__{self.sound['id']}__{self.minutes}"

    @property
    def title(self) -> str:
        return f"[Playlist] {self.scene['ko']}에 듣는 {self.sound['ko']} | {self.minutes}분"

    @property
    def cover_prompt(self) -> str:
        """썸네일 = 클릭률 전부. 인물 없이 장면만, 텍스트 없이."""
        return (
            f"{self.scene['ko']} 장면의 일러스트레이션. 무드: {self.scene['mood']}. "
            "잔잔한 애니메이션 배경화 스타일, 한 명의 뒷모습 또는 무인 풍경, "
            "따뜻한 색온도와 부드러운 그레인, 텍스트 없음, 로고 없음. 16:9 와이드 구도."
        )

    @property
    def music_prompt(self) -> str:
        return f"{self.sound['prompt']}, mood: {self.scene['mood']}, consistent tempo, seamless loopable"


def duration_for(scene_id: str) -> int:
    for d in DURATIONS:
        if scene_id in d["fit"]:
            return d["minutes"]
    return 120


def all_concepts() -> list[PlaylistConcept]:
    return [
        PlaylistConcept(s, snd, duration_for(s["id"]))
        for s in SCENES
        for snd in SOUNDS
    ]
