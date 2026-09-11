#!/usr/bin/env python3
"""Measure a reference fade animation and turn it into a LidFade curve.

Matching another product's animation by eye does not work: the eye is good at
spotting that two fades differ and useless at saying how. This measures the
reference instead.

Record the effect you want to match (240fps slow motion off a phone is plenty,
a screen recording is better if you can get one), point this at the file, and
it returns the timing curve as a sampled table plus the closest cubic bezier,
ready to drop into config.json.

    ./fit_curve.py reference.mov --crop 900:500:200:150 --apply

Needs ffmpeg and ffprobe on PATH. Nothing else; no third-party packages.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

SAMPLE_COUNT = 121
DOWNSCALE_W = 64
DOWNSCALE_H = 36


# --------------------------------------------------------------------------
# Frame luminance extraction
# --------------------------------------------------------------------------

def require_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        sys.exit(f"error: {name} not found on PATH")
    return path


def probe_fps(path: str) -> float:
    require_tool("ffprobe")
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=avg_frame_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if "/" in out:
        num, den = out.split("/")
        if float(den) == 0:
            sys.exit("error: could not read frame rate; pass --fps")
        return float(num) / float(den)
    return float(out)


def extract_luminance(path: str, crop: str | None) -> list[float]:
    """Mean luminance per frame, 0..1.

    The video is reduced to 64x36 greyscale first. Averaging a tiny image is
    the same number as averaging the full frame but hundreds of times cheaper,
    and it suppresses sensor noise and per-pixel dither that would otherwise
    show up as jitter in the fitted curve.
    """
    require_tool("ffmpeg")
    filters = []
    if crop:
        filters.append(f"crop={crop}")
    filters.append(f"scale={DOWNSCALE_W}:{DOWNSCALE_H}")
    filters.append("format=gray")

    process = subprocess.Popen(
        [
            "ffmpeg", "-v", "error", "-i", path,
            "-vf", ",".join(filters),
            "-f", "rawvideo", "-pix_fmt", "gray", "-",
        ],
        stdout=subprocess.PIPE,
    )
    frame_size = DOWNSCALE_W * DOWNSCALE_H
    values: list[float] = []
    assert process.stdout is not None
    while True:
        chunk = process.stdout.read(frame_size)
        if len(chunk) < frame_size:
            break
        values.append(sum(chunk) / (frame_size * 255.0))
    process.stdout.close()
    process.wait()
    if not values:
        sys.exit("error: ffmpeg produced no frames; check the path and --crop")
    return values


# --------------------------------------------------------------------------
# Normalisation
# --------------------------------------------------------------------------

def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    low = int(math.floor(position))
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def linearize(value: float) -> float:
    """Undo the sRGB transfer function.

    Whether you want this depends on what you are matching. A Core Animation
    opacity ramp is applied to encoded values, so leave it off to match an
    overlay fade. A backlight ramp is physically linear, so turn it on to match
    a display actually dimming.
    """
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def coarse_bounds(progress: list[float]) -> tuple[int, int]:
    """Roughly where the transition sits, using thresholds far enough from the
    plateaus that noise cannot trip them."""
    end = next((i for i, p in enumerate(progress) if p >= 0.9), len(progress) - 1)
    start = 0
    for i in range(end, -1, -1):
        if progress[i] <= 0.1:
            start = i
            break
    return start, end


def estimate_noise(progress: list[float]) -> float:
    """Standard deviation of the still footage at each end of the clip.

    Deliberately sampled from the outermost frames rather than from everything
    outside the coarse bounds: those regions still contain the shallow start
    and end of the ramp, and including them inflates the estimate enough to
    swallow the tails of the animation itself.
    """
    window = max(3, len(progress) // 20)
    if len(progress) < 2 * window + 2:
        return 0.0
    lead = progress[:window]
    tail = progress[-window:]
    mean_lead = sum(lead) / len(lead)
    mean_tail = sum(tail) / len(tail)
    deviations = [v - mean_lead for v in lead] + [v - mean_tail for v in tail]
    return math.sqrt(sum(d * d for d in deviations) / len(deviations))


def precise_bounds(progress: list[float]) -> tuple[int, int, float]:
    """First and last frame of the animation, plus the threshold used.

    Both bounds are found by walking out from the coarse crossings until the
    signal rejoins its plateau. Note the systematic bias this carries: an eased
    curve approaches its endpoints asymptotically, so whatever threshold is
    used clips a frame or two off each end and the measured duration comes out
    slightly short. At 120fps or better that is well under a percent, which is
    why the tool asks for a high frame rate rather than trying to correct it.
    """
    coarse_start, coarse_end = coarse_bounds(progress)
    if coarse_end <= coarse_start:
        sys.exit(
            "error: could not find a complete transition. Trim the clip so it "
            "starts before the fade and ends after it."
        )

    threshold = max(3 * estimate_noise(progress), 0.002)

    start = 0
    for i in range(coarse_start, -1, -1):
        if progress[i] <= threshold:
            start = i
            break

    end = len(progress) - 1
    for i in range(coarse_end, len(progress)):
        if progress[i] >= 1.0 - threshold:
            end = i
            break

    if end <= start:
        sys.exit("error: transition bounds collapsed; try --monotonic")
    return start, end, threshold


def normalise(
    luminance: list[float], direction: str, linear: bool
) -> tuple[list[float], int, int, float]:
    """Map frame luminance onto 0..1 animation progress and locate the fade.

    The plateau levels are read as the 2nd and 98th percentile of the whole
    clip, which is why the recording has to start and end with a couple of
    percent of still footage. Without that the percentile lands inside the
    ramp, the tails get clipped flat, and the animation measures shorter and
    snappier than it really is.
    """
    series = [linearize(v) for v in luminance] if linear else list(luminance)

    high = percentile(series, 0.98)
    low = percentile(series, 0.02)
    if high - low < 1e-4:
        sys.exit(
            "error: the clip has almost no luminance change. Check --crop, "
            "and make sure the recording actually contains the transition."
        )

    if direction == "auto":
        window = max(1, len(series) // 10)
        lead = sum(series[:window]) / window
        tail = sum(series[-window:]) / window
        direction = "out" if tail < lead else "in"

    span = high - low
    if direction == "out":
        raw = [(high - v) / span for v in series]
    else:
        raw = [(v - low) / span for v in series]
    progress = [min(max(p, 0.0), 1.0) for p in raw]

    start, end, threshold = precise_bounds(progress)
    return progress, start, end, threshold


def resample(progress: list[float], start: int, end: int, count: int) -> list[float]:
    window = progress[start : end + 1]
    if len(window) < 2:
        sys.exit("error: transition is shorter than two frames; record at a higher fps")
    out = []
    for i in range(count):
        position = i / (count - 1) * (len(window) - 1)
        low = int(math.floor(position))
        high = min(low + 1, len(window) - 1)
        fraction = position - low
        out.append(window[low] + (window[high] - window[low]) * fraction)
    out[0], out[-1] = 0.0, 1.0
    return out


def enforce_monotonic(samples: list[float]) -> list[float]:
    out = list(samples)
    for i in range(1, len(out)):
        if out[i] < out[i - 1]:
            out[i] = out[i - 1]
    return out


# --------------------------------------------------------------------------
# Bezier fitting
# --------------------------------------------------------------------------

def bezier_component(t: float, a: float, b: float) -> float:
    inverse = 1 - t
    return 3 * inverse * inverse * t * a + 3 * inverse * t * t * b + t ** 3


def bezier_at_x(x: float, x1: float, x2: float, y1: float, y2: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    low, high, t = 0.0, 1.0, x
    for _ in range(60):
        value = bezier_component(t, x1, x2)
        if abs(value - x) < 1e-7:
            break
        if value > x:
            high = t
        else:
            low = t
        t = (low + high) / 2
    return bezier_component(t, y1, y2)


def rmse(params: list[float], samples: list[float]) -> float:
    x1, y1, x2, y2 = params
    # Control points outside this range make the curve non-monotonic in x,
    # which no timing function can represent.
    if not (0.0 <= x1 <= 1.0 and 0.0 <= x2 <= 1.0):
        return 1e6
    total = 0.0
    for i, target in enumerate(samples):
        x = i / (len(samples) - 1)
        error = bezier_at_x(x, x1, x2, y1, y2) - target
        total += error * error
    return math.sqrt(total / len(samples))


def nelder_mead(
    objective, start: list[float], step: float = 0.25, iterations: int = 800
) -> tuple[list[float], float]:
    n = len(start)
    simplex = [list(start)]
    for i in range(n):
        point = list(start)
        point[i] += step
        simplex.append(point)
    scores = [objective(p) for p in simplex]

    for _ in range(iterations):
        order = sorted(range(len(simplex)), key=lambda i: scores[i])
        simplex = [simplex[i] for i in order]
        scores = [scores[i] for i in order]
        if abs(scores[-1] - scores[0]) < 1e-10:
            break

        centroid = [sum(p[i] for p in simplex[:-1]) / n for i in range(n)]
        reflected = [centroid[i] + (centroid[i] - simplex[-1][i]) for i in range(n)]
        reflected_score = objective(reflected)

        if reflected_score < scores[0]:
            expanded = [centroid[i] + 2 * (centroid[i] - simplex[-1][i]) for i in range(n)]
            expanded_score = objective(expanded)
            simplex[-1], scores[-1] = (
                (expanded, expanded_score)
                if expanded_score < reflected_score
                else (reflected, reflected_score)
            )
        elif reflected_score < scores[-2]:
            simplex[-1], scores[-1] = reflected, reflected_score
        else:
            contracted = [
                centroid[i] + 0.5 * (simplex[-1][i] - centroid[i]) for i in range(n)
            ]
            contracted_score = objective(contracted)
            if contracted_score < scores[-1]:
                simplex[-1], scores[-1] = contracted, contracted_score
            else:
                for i in range(1, len(simplex)):
                    simplex[i] = [
                        simplex[0][j] + 0.5 * (simplex[i][j] - simplex[0][j])
                        for j in range(n)
                    ]
                    scores[i] = objective(simplex[i])

    best = min(range(len(simplex)), key=lambda i: scores[i])
    return simplex[best], scores[best]


def fit_bezier(samples: list[float]) -> tuple[list[float], float]:
    """Multi-start because the objective has local minima that a single start
    from the middle of the space reliably falls into."""
    seeds = [
        [0.25, 0.10, 0.25, 1.00],
        [0.42, 0.00, 0.58, 1.00],
        [0.32, 0.00, 0.12, 1.00],
        [0.65, 0.00, 0.35, 1.00],
        [0.10, 0.50, 0.50, 0.90],
    ]
    best_params, best_score = None, float("inf")
    for seed in seeds:
        params, score = nelder_mead(lambda p: rmse(p, samples), seed)
        if score < best_score:
            best_params, best_score = params, score
    assert best_params is not None
    clamped = [
        min(max(best_params[0], 0.0), 1.0),
        best_params[1],
        min(max(best_params[2], 0.0), 1.0),
        best_params[3],
    ]
    return [round(v, 4) for v in clamped], best_score


# --------------------------------------------------------------------------
# Tail-clipping correction
# --------------------------------------------------------------------------

MIN_COVERAGE = 0.90


def interpolate(table: list[float], x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    position = x * (len(table) - 1)
    low = int(position)
    high = min(low + 1, len(table) - 1)
    return table[low] + (table[high] - table[low]) * (position - low)


def x_for_y(y: float, bezier: list[float]) -> float:
    """Inverse of the fitted timing function; valid because a bezier with
    control points inside 0..1 is monotonic in both axes."""
    low, high = 0.0, 1.0
    for _ in range(60):
        mid = (low + high) / 2
        if bezier_at_x(mid, bezier[0], bezier[2], bezier[1], bezier[3]) < y:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def correct_tail_clipping(
    samples: list[float], duration: float, threshold: float
) -> tuple[list[float], float, float]:
    """Recover the part of the animation that the boundary threshold ate.

    Boundary detection can only see the fade once it has moved further than
    the noise floor, so an eased curve always measures a few frames short at
    each end and the surviving window gets stretched over the full time range.
    Fitting a bezier to that window says how much time sits below the
    threshold, which is enough to undo the stretch.

    Applied exactly once, and capped. Iterating looks like it converges and
    then runs away: each pass re-reads its own output as if it were fresh
    measurement, so the correction compounds instead of settling. The cap
    bounds the damage on a heavily eased curve, where the tail genuinely
    disappears under the noise and no amount of arithmetic brings it back.
    """
    bezier, _ = fit_bezier(samples)
    lower = x_for_y(threshold, bezier)
    upper = x_for_y(1.0 - threshold, bezier)
    coverage = max(upper - lower, MIN_COVERAGE)
    if coverage >= 0.999:
        return samples, duration, 1.0

    corrected = []
    for i in range(SAMPLE_COUNT):
        window_x = (i / (SAMPLE_COUNT - 1) - lower) / coverage
        if window_x <= 0:
            corrected.append(0.0)
        elif window_x >= 1:
            corrected.append(1.0)
        else:
            corrected.append(interpolate(samples, window_x))
    return corrected, duration / coverage, coverage


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def config_path() -> Path:
    return Path.home() / "Library/Application Support/LidFade/config.json"


def apply_to_config(samples: list[float], duration: float, bezier: list[float],
                    which: str) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    config = {}
    if path.exists():
        try:
            config = json.loads(path.read_text())
        except json.JSONDecodeError:
            print(f"warning: {path} was not valid JSON; rewriting it", file=sys.stderr)
    config["lut"] = [round(v, 6) for v in samples]
    config["bezier"] = bezier
    if which in ("close", "both"):
        config["closeDuration"] = round(duration, 4)
    if which in ("open", "both"):
        config["openDuration"] = round(duration, 4)
    path.write_text(json.dumps(config, indent=2, sort_keys=True))
    return path


def ascii_plot(samples: list[float], height: int = 12, width: int = 60) -> str:
    rows = []
    for row in range(height, -1, -1):
        level = row / height
        line = []
        for column in range(width):
            index = int(column / (width - 1) * (len(samples) - 1))
            line.append("#" if samples[index] >= level - 0.5 / height else " ")
        rows.append(f"{level:4.1f} |" + "".join(line))
    rows.append("     +" + "-" * width)
    rows.append("      0" + " " * (width - 8) + "time 1")
    return "\n".join(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure a reference fade and emit a LidFade timing curve.")
    parser.add_argument("video", nargs="?", help="recording containing the transition")
    parser.add_argument("--crop", help="ffmpeg crop, w:h:x:y — restrict to the screen area")
    parser.add_argument("--fps", type=float, help="override the detected frame rate")
    parser.add_argument("--direction", choices=["auto", "out", "in"], default="auto")
    parser.add_argument("--linear", action="store_true",
                        help="measure in linear light instead of encoded sRGB")
    parser.add_argument("--monotonic", action="store_true",
                        help="force the curve to never go backwards")
    parser.add_argument("--apply", action="store_true",
                        help="write the result straight into config.json")
    parser.add_argument("--target", choices=["close", "open", "both"], default="close",
                        help="which duration --apply should set")
    parser.add_argument("--json", help="also write the full result to this path")
    parser.add_argument("--no-tail-correction", action="store_true",
                        help="report the raw measured bounds without "
                             "compensating for threshold clipping")
    parser.add_argument("--selftest", action="store_true",
                        help="verify the fitter against a synthetic curve")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    if not args.video:
        parser.error("a video path is required unless --selftest is given")
    if not os.path.exists(args.video):
        sys.exit(f"error: no such file: {args.video}")

    fps = args.fps or probe_fps(args.video)
    luminance = extract_luminance(args.video, args.crop)
    progress, start, end, threshold = normalise(
        luminance, args.direction, args.linear)
    samples = resample(progress, start, end, SAMPLE_COUNT)
    if args.monotonic:
        samples = enforce_monotonic(samples)
    duration = (end - start) / fps
    coverage = 1.0
    if not args.no_tail_correction:
        samples, duration, coverage = correct_tail_clipping(
            samples, duration, threshold)
    bezier, error = fit_bezier(samples)

    print(f"frames analysed : {len(luminance)}  @ {fps:.3f} fps")
    print(f"transition      : frame {start} to {end} (plateau threshold {threshold:.4f})")
    if coverage < 1.0:
        print(f"tail correction : +{(1 / coverage - 1) * 100:.1f}% "
              f"(threshold hid {(1 - coverage) * 100:.1f}% of the animation)")
    print(f"duration        : {duration:.4f} s")
    print(f"closest bezier  : {bezier}  (rmse {error:.5f})")
    if error > 0.02:
        print("note            : the reference is not well described by a cubic "
              "bezier.\n                  Use the sampled table, not the bezier.")
    print()
    print(ascii_plot(samples))

    result = {
        "durationSeconds": round(duration, 4),
        "frameRate": fps,
        "bezier": bezier,
        "bezierRmse": round(error, 6),
        "lut": [round(v, 6) for v in samples],
    }
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2))
        print(f"\nwrote {args.json}")
    if args.apply:
        written = apply_to_config(samples, duration, bezier, args.target)
        print(f"\napplied to {written}")
        print("LidFade reloads it automatically; no restart needed.")


def run_selftest() -> None:
    """Round-trips a known curve through the whole pipeline.

    Generates the luminance a display would emit while animating a known
    bezier, then checks the fitter recovers it. This is the only part of the
    project that can be verified without a Mac, so it carries its weight.
    """
    truth = [0.42, 0.0, 0.58, 1.0]
    fps = 240.0
    frames = 101
    synthetic = [1.0] * 20
    for i in range(frames):
        x = i / (frames - 1)
        synthetic.append(1.0 - bezier_at_x(x, truth[0], truth[2], truth[1], truth[3]))
    synthetic += [0.0] * 20

    progress, start, end, threshold = normalise(synthetic, "auto", linear=False)
    raw = resample(progress, start, end, SAMPLE_COUNT)
    samples, duration, coverage = correct_tail_clipping(
        raw, (end - start) / fps, threshold)
    recovered, error = fit_bezier(samples)

    expected_duration = (frames - 1) / fps
    reference = [
        bezier_at_x(i / (SAMPLE_COUNT - 1), truth[0], truth[2], truth[1], truth[3])
        for i in range(SAMPLE_COUNT)
    ]
    table_error = math.sqrt(
        sum((a - b) ** 2 for a, b in zip(samples, reference)) / SAMPLE_COUNT
    )

    print(f"truth bezier     : {truth}")
    print(f"recovered bezier : {recovered}  (fit rmse {error:.6f})")
    print(f"sampled table    : rmse {table_error:.6f} against the truth curve")
    print(f"tail correction  : coverage {coverage:.4f}")
    print(f"duration         : {duration:.4f}s, expected {expected_duration:.4f}s")

    # Tolerances reflect what boundary detection can actually deliver, not
    # what would be nice. A threshold-based method loses the asymptotic tails
    # of an eased curve; the correction above halves that error and cannot
    # remove it.
    failures = []
    if table_error > 0.015:
        failures.append(f"sampled table rmse {table_error:.6f} > 0.015")
    if error > 0.005:
        failures.append(f"bezier fit rmse {error:.6f} > 0.005")
    relative = abs(duration - expected_duration) / expected_duration
    if relative > 0.06:
        failures.append(f"duration off by {relative * 100:.1f}% (limit 6%)")

    print()
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        sys.exit(1)
    print("PASS: the pipeline reproduces a known curve.")


if __name__ == "__main__":
    main()
