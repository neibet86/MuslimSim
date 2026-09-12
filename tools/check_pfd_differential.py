"""Prove the PFD's differential drawing against a full repaint, offline.

The renderer sends only what changed since the last frame.  That is only safe
if a panel fed the differences ends up with exactly the picture a panel fed
complete frames would have.  This tool flies a short synthetic sequence twice:
once into a persistent canvas that receives only the differences, and once into
a fresh canvas per frame that receives everything.  Every frame must match
pixel for pixel.

It also reports the display traffic per frame, in HID reports, which on this
panel is very close to milliseconds.

It never opens the PFP HID device, COM5, the WinCtrl hardware, or X-Plane.

Usage:
    python tools/check_pfd_differential.py
"""

from __future__ import annotations

import argparse
import importlib.util
import math
from pathlib import Path
import sys

from PIL import ImageChops

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))
if str(PROJECT / "tools") not in sys.path:
    sys.path.insert(0, str(PROJECT / "tools"))

from muslimsim.devices import pfp_renderer
from show_pfd_preview import NORMAL, scenario_values


def _emulator():
    spec = importlib.util.spec_from_file_location(
        "_pfp_frame_emulator", PROJECT / "tools" / "render_pfp_frame_png.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _CountingDevice:
    def __init__(self) -> None:
        self.reports = 0

    def write(self, report) -> int:
        self.reports += 1
        return len(report)


def cruise(frames: int) -> list[dict]:
    """Straight and level, with only the airspeed and altitude creeping."""
    return [
        {**NORMAL, "roll": 0.0, "pitch": 2.0, "ias": 250.0 + step * 0.2,
         "altitude": 10000.0 + step * 10.0, "heading": 90.0, "vertical_speed": 600.0}
        for step in range(frames)
    ]


def turning(frames: int) -> list[dict]:
    """A banked turn: the attitude, heading and tapes all move together."""
    return [
        {**NORMAL,
         "roll": 18.0 * math.sin(step / 12.0),
         "pitch": 3.0 + math.sin(step / 9.0),
         "ias": 210.0 + step * 0.4,
         "altitude": 6000.0 + step * 22.0,
         "heading": (120.0 + step * 0.9) % 360.0,
         "vertical_speed": 1200.0}
        for step in range(frames)
    ]


def jitter(frames: int) -> list[dict]:
    """Level cruise as the simulator really sends it: every value trembling."""
    import random

    random.seed(7)
    return [
        {**NORMAL,
         "roll": random.uniform(-0.08, 0.08),
         "pitch": 2.0 + random.uniform(-0.06, 0.06),
         "heading": 90.0 + random.uniform(-0.1, 0.1),
         "ias": 250.0 + step * 0.05 + random.uniform(-0.05, 0.05),
         "altitude": 10000.0 + random.uniform(-1.5, 1.5),
         "vertical_speed": random.uniform(-40.0, 40.0)}
        for step in range(frames)
    ]


def modes_and_extremes(frames: int) -> list[dict]:
    """Exercise target bugs, FMA text, Mach, STD/hPa, and edge values."""
    names = (
        "normal",
        "high",
        "low",
        "zero",
        "extreme",
        "below-sea-level",
        "minimums",
        "minimums-reached",
        "radio-minimums",
    )
    sequence: list[dict] = []
    for index in range(frames):
        values = scenario_values(names[index % len(names)])
        values["target_ias_visible"] = 0.0 if index % 7 == 0 else 1.0
        values["fd_command_visible"] = 0.0 if index % 5 == 0 else 1.0
        sequence.append(values)
    return sequence


def long_steady(frames: int) -> list[dict]:
    """Hold one picture past the old timer and prove no partial swap appears."""
    count = max(frames, 122)
    return [dict(NORMAL) for _ in range(count)]


def run(name: str, sequence: list[dict], emulator, save: Path | None) -> tuple[bool, list[int]]:
    persistent = emulator.PfpFrame()          # keeps its last frame, so it gets differences
    bridge_canvas = None
    device = _CountingDevice()
    try:
        from muslimsim.core.engine import _load_engine

        bridge = _load_engine()
        bridge_canvas = bridge._PfpNativeCanvas(device)
    except Exception as error:  # pragma: no cover - traffic figures are a bonus
        print(f"  (cannot measure traffic: {error})")

    # The reference panel is persistent too, but its last frame is aged out
    # before every draw so it always receives a complete frame.  It therefore
    # makes the same motion-quality decision as the panel under test, and any
    # difference between them is the differential logic alone.
    complete = emulator.PfpFrame()

    ok = True
    costs: list[int] = []
    for index, values in enumerate(sequence):
        pfp_renderer.draw_live_pfd(persistent, values)
        # Force command replay without changing the renderer's motion-quality
        # decision.  Aging the reference state used to turn every reference
        # frame into recovery/economy quality, which compared two different
        # pictures rather than differential versus full output.
        complete._muslimsim_force_full_repaint = True
        pfp_renderer.draw_live_pfd(complete, values)
        difference = ImageChops.difference(persistent.image, complete.image)
        box = difference.getbbox()
        if box is not None:
            ok = False
            print(f"  frame {index}: DIFFERS at {box}")
            if save is not None:
                persistent.image.save(save / f"differential-{name}-{index}-sent.png")
                complete.image.save(save / f"differential-{name}-{index}-expected.png")
            break
        if bridge_canvas is not None:
            before = device.reports
            pfp_renderer.draw_live_pfd(bridge_canvas, values)
            bridge_canvas.command(0x103)
            costs.append(device.reports - before)
    return ok, costs


def check_live_offline_reconnect(emulator) -> bool:
    """A standby page must not leave stale dirty history over the real LCD."""
    from muslimsim.core.engine import _load_engine

    bridge = _load_engine()
    actual = emulator.PfpFrame()
    bridge._pfp_write_graphical_pfd(None, actual, NORMAL)
    bridge._pfp_write_graphical_pfd(None, actual, {})
    bridge._pfp_write_graphical_pfd(None, actual, NORMAL)

    expected = emulator.PfpFrame()
    bridge._pfp_write_graphical_pfd(None, expected, NORMAL)
    difference = ImageChops.difference(actual.image, expected.image)
    box = difference.getbbox()
    if box is not None:
        print(f"live-offline-live: DIFFERS at {box}")
        return False
    if not hasattr(actual, "_muslimsim_pfd_state"):
        print("live-offline-live: renderer state was not rebuilt")
        return False
    print("live-offline-live: complete recovery frame restored exactly")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=40, help="Frames per sequence.")
    parser.add_argument("--save", type=Path, default=None,
                        help="Folder to write the two frames if a mismatch is found.")
    args = parser.parse_args()

    emulator = _emulator()
    failures = 0
    for name, builder in (
        ("cruise", cruise),
        ("turning", turning),
        ("jitter", jitter),
        ("modes-and-extremes", modes_and_extremes),
        ("long-steady-hold", long_steady),
    ):
        sequence = builder(args.frames)
        print(f"{name}: {len(sequence)} frames")
        ok, costs = run(name, sequence, emulator, args.save)
        if not ok:
            failures += 1
            continue
        if costs:
            steady = costs[1:] or costs
            print(f"  identical to a full repaint on every frame")
            print(f"  traffic: first {costs[0]} reports, then "
                  f"{min(steady)}-{max(steady)}, median {sorted(steady)[len(steady) // 2]}")
        else:
            print("  identical to a full repaint on every frame")
    if not check_live_offline_reconnect(emulator):
        failures += 1
    if failures:
        print(f"FAILED: {failures} sequence(s) diverged")
        return 1
    print("PASS: differential drawing matches a full repaint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
