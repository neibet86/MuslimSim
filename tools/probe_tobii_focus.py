#!/usr/bin/env python3
"""Measure the real tracker: how noisy it is, and how steady the filter makes it.

    py tools/probe_tobii_focus.py --seconds 12 --save gaze.txt

Stare at ONE spot for the whole run - a letter on the screen, not a region. The
numbers only mean something if the input really was a single fixation, because
what is being measured is how much of your own tremor reaches the pointer.

Two things are reported. The **steadiness** figure compares the eye against the
pointer *while focus is held*, which is the only fair comparison - when you are
looking around, the pointer is supposed to follow. The **noise** figures
describe the tracker itself, and those are what the thresholds in
`gaze_focus.py` have to be set from.

Read-only: it subscribes to gaze and never calibrates or configures anything.
"""

from __future__ import annotations

from pathlib import Path
import argparse
import math
import sys
import time


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.platform.gaze_focus import FocusSettings, GazeFocus
from muslimsim.platform.tobii_stream import (
    TobiiStream, TobiiUnavailable, find_stream_engine,
)


def percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(fraction * len(ordered)))
    return ordered[index]


def path_length(points):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1])
               for a, b in zip(points, points[1:]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=12.0)
    parser.add_argument("--dll", default=None)
    parser.add_argument("--save", default=None,
                        help="write the raw trace here for offline tuning")
    args = parser.parse_args()

    library = find_stream_engine(args.dll)
    print("Tobii stream engine : %s" % (library or "NOT FOUND"))
    if library is None:
        return 1

    focus = GazeFocus()
    raw = []            # (t, x, y, valid)
    paired = []         # (raw point, pointer point, focused)

    def on_gaze(sample):
        raw.append((sample.timestamp, sample.x, sample.y, sample.valid))
        state = focus.update(
            sample.timestamp, sample.x, sample.y, valid=sample.valid)
        if sample.valid:
            paired.append(((sample.x, sample.y), state.point, state.focused))

    try:
        stream = TobiiStream(dll_path=args.dll, on_gaze=on_gaze)
        stream.start()
    except TobiiUnavailable as exc:
        print("\nTracker unavailable: %s" % exc)
        return 1

    print("device              : %s" % stream.device_url)
    print("\nStare at ONE spot for %.0f s. Do not look away.\n" % args.seconds)

    deadline = time.monotonic() + args.seconds
    try:
        while time.monotonic() < deadline:
            stream.poll(0.10)
    except KeyboardInterrupt:
        pass
    finally:
        stream.stop()

    if not raw:
        print("No samples arrived.")
        return 1

    valid = [row for row in raw if row[3]]
    print("samples             : %d  (%.1f Hz, %.0f%% valid)"
          % (len(raw), len(raw) / args.seconds, 100.0 * len(valid) / len(raw)))
    if len(valid) < 20:
        print("Not enough valid samples to measure anything.")
        return 1

    # --- what the tracker itself is doing ---------------------------------
    centre_x = sum(row[1] for row in valid) / len(valid)
    centre_y = sum(row[2] for row in valid) / len(valid)
    offsets = [math.hypot(row[1] - centre_x, row[2] - centre_y) for row in valid]
    steps = [
        math.hypot(b[1] - a[1], b[2] - a[2]) / max(1e-6, b[0] - a[0])
        for a, b in zip(valid, valid[1:])
    ]
    # Dispersion the way the detector measures it: the widest excursion from
    # the centre of a sliding window the length of the settle time.
    settings = FocusSettings()
    window = max(2, int(settings.settle_seconds * len(valid) / args.seconds))
    dispersions = []
    for start in range(0, max(1, len(valid) - window)):
        chunk = valid[start:start + window]
        cx = sum(row[1] for row in chunk) / len(chunk)
        cy = sum(row[2] for row in chunk) / len(chunk)
        dispersions.append(
            max(math.hypot(row[1] - cx, row[2] - cy) for row in chunk))

    print("\n-- the tracker's own noise (normalised screen units) --")
    print("spread from centre  : median %.4f   90th %.4f   max %.4f"
          % (percentile(offsets, 0.5), percentile(offsets, 0.9), max(offsets)))
    print("window dispersion   : median %.4f   75th %.4f   90th %.4f"
          % (percentile(dispersions, 0.5), percentile(dispersions, 0.75),
             percentile(dispersions, 0.9)))
    print("  (settle_radius is %.4f - focus needs dispersion under it)"
          % settings.settle_radius)
    print("sample speed        : median %.3f   90th %.3f   99th %.3f  /s"
          % (percentile(steps, 0.5), percentile(steps, 0.9),
             percentile(steps, 0.99)))
    print("  (saccade_speed is %.3f - above it the lock releases)"
          % settings.saccade_speed)

    # --- how the filter did -------------------------------------------------
    held = [row for row in paired if row[2]]
    coverage = 100.0 * len(held) / len(paired)
    print("\n-- how steady the pointer was --")
    print("focus coverage      : %.0f%% of a run you spent staring" % coverage)
    if len(held) > 2:
        eye = path_length([row[0] for row in held])
        pointer = path_length([row[1] for row in held])
        print("while focused, eye  : %.4f screen widths" % eye)
        print("while focused, ptr  : %.4f screen widths" % pointer)
        if pointer > 0:
            print("steadier by         : %.0fx" % (eye / pointer))
        else:
            print("steadier by         : pointer did not move at all")
    else:
        print("focus was never held long enough to measure")

    if args.save:
        target = Path(args.save)
        with target.open("w") as handle:
            for stamp, x, y, ok in raw:
                handle.write("%.6f %.6f %.6f %d\n" % (stamp, x, y, 1 if ok else 0))
        print("\ntrace written       : %s (%d samples)" % (target, len(raw)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
