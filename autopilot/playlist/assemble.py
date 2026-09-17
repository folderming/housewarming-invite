"""생성한 짧은 트랙들을 이어 붙여 장시간 플레이리스트 영상을 만든다.

음악 API는 보통 한 번에 수 분짜리만 내준다. 2시간을 채우려면 여러 트랙을
반복해 이어야 하는데, 그냥 붙이면 이음매가 튀고 같은 순서가 반복되는 게
귀에 잡힌다. 그래서 (1) 인접 중복을 피하는 순서를 만들고 (2) 크로스페이드로
이어 붙인다.
"""

import json
import random
import subprocess
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
CROSSFADE_SEC = 3


def _run(args: list[str]) -> None:
    proc = subprocess.run(
        [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", *args],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패:\n{proc.stderr[-2000:]}")


def duration_of(path: Path) -> float:
    """ffmpeg만으로 길이를 잰다(ffprobe가 없는 환경 대비)."""
    proc = subprocess.run(
        [FFMPEG, "-hide_banner", "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True,
    )
    marker = "time="
    last = proc.stderr.rfind(marker)
    if last == -1:
        raise RuntimeError(f"길이를 읽지 못했습니다: {path}")
    hh, mm, ss = proc.stderr[last + len(marker):last + len(marker) + 11].split(":")
    return int(hh) * 3600 + int(mm) * 60 + float(ss)


def build_order(tracks: list[Path], target_seconds: int, seed: int = 0) -> list[Path]:
    """목표 길이를 채울 때까지, 바로 앞 트랙과 겹치지 않게 순서를 만든다."""
    if not tracks:
        raise ValueError("트랙이 비어 있습니다.")
    lengths = {t: duration_of(t) for t in tracks}
    rng = random.Random(seed)
    order, total, prev = [], 0.0, None

    while total < target_seconds:
        pool = [t for t in tracks if t != prev] or list(tracks)
        pick = rng.choice(pool)
        order.append(pick)
        total += lengths[pick] - CROSSFADE_SEC
        prev = pick
    return order


def concat_audio(order: list[Path], out_path: Path) -> Path:
    """크로스페이드로 이어 붙인다. 트랙이 많아도 필터 그래프 하나로 처리."""
    inputs = []
    for p in order:
        inputs += ["-i", str(p)]

    if len(order) == 1:
        _run([*inputs, "-c:a", "libmp3lame", "-b:a", "192k", str(out_path)])
        return out_path

    steps, prev = [], "[0:a]"
    for i in range(1, len(order)):
        label = f"[x{i}]"
        steps.append(
            f"{prev}[{i}:a]acrossfade=d={CROSSFADE_SEC}:c1=tri:c2=tri{label}"
        )
        prev = label

    _run([
        *inputs,
        "-filter_complex", ";".join(steps),
        "-map", prev,
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(out_path),
    ])
    return out_path


def render_video(audio: Path, cover: Path, out_path: Path) -> Path:
    """정지 커버 + 오디오. 1fps로 굽기 때문에 2시간짜리도 파일이 작다."""
    _run([
        "-loop", "1", "-framerate", "1", "-i", str(cover),
        "-i", str(audio),
        "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
        "-pix_fmt", "yuv420p", "-r", "1", "-g", "2",
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,"
               "pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        str(out_path),
    ])
    return out_path


def tracklist(order: list[Path]) -> list[dict]:
    """유튜브 설명란에 넣을 타임스탬프 목록."""
    rows, t = [], 0.0
    for i, p in enumerate(order):
        rows.append({
            "index": i + 1,
            "start": f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}",
            "track": p.stem,
        })
        t += duration_of(p) - CROSSFADE_SEC
    return rows


def build(tracks: list[Path], cover: Path, minutes: int, out_dir: Path, slug: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    order = build_order(tracks, minutes * 60)
    audio = concat_audio(order, out_dir / f"{slug}.mp3")
    video = render_video(audio, cover, out_dir / f"{slug}.mp4")
    rows = tracklist(order)
    (out_dir / f"{slug}.tracklist.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"audio": str(audio), "video": str(video), "tracks": len(order), "tracklist": rows}
