"""Repeat the FMC/PFD handoff and watch for the point where the panel stops.

The panel degrades across handoffs: the first is clean, the second leaves a
frame of the previous page, and by the third the PFD will not draw at all.  A
power cycle restores it fully.  So something in the handoff is progressively
disabling the display rather than a clear being aimed wrong.

This performs the handoff's HID work over and over -- open, upload the font,
send the character-mode config, blank the page, clear the graphics plane,
close -- and records what every write returns and how long each phase takes.
If the panel starts refusing writes, or starts taking noticeably longer to
accept them, that shows up here without anyone having to watch the screen.

Nothing here is new protocol: every step is one the bridge already performs on
a handoff.  It writes only to the display, never to the simulator, and opens
no other hardware.  Run it with the bridge stopped.

Usage:
    python tools/probe_mcdu_handoff_wear.py            # 6 cycles
    python tools/probe_mcdu_handoff_wear.py --cycles 12
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))


def _load_bridge():
    """Load bridge/final.py, which owns the native display protocol."""
    path = PROJECT / "bridge" / "final.py"
    spec = importlib.util.spec_from_file_location("final", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _CountingDevice:
    """Wraps the real HID handle and records what every write returns."""

    def __init__(self, device) -> None:
        self._device = device
        self.writes = 0
        self.short = 0
        self.failed = 0
        self.first_failure = None

    def write(self, report):
        self.writes += 1

        try:
            written = self._device.write(report)
        except Exception as exc:
            self.failed += 1

            if self.first_failure is None:
                self.first_failure = f"write {self.writes}: {exc}"

            return -1

        if written is not None and written < len(report):
            self.short += 1

            if self.first_failure is None:
                self.first_failure = (
                    f"write {self.writes}: short, {written} of {len(report)}"
                )

        return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cycles",
        type=int,
        default=6,
        help="How many handoffs to perform (default 6)",
    )
    args = parser.parse_args()

    bridge = _load_bridge()

    if bridge.hid is None:
        print("hidapi unavailable; install hidapi")
        return 2

    devices = list(
        bridge.hid.enumerate(bridge.PFP_PFD_VID, bridge.MCDU_PFD_PID)
    )

    if not devices:
        print("WINCTRL 32 MCDU CAPTAIN (VID 4098 / PID BB36) not found")
        return 2

    path = devices[0].get("path")

    if not path:
        print("Windows did not supply a HID path for the MCDU")
        return 2

    from muslimsim.devices.mcdu_bb36 import (
        _black_background_packet,
        _text_grid_packet,
    )

    font_path = (PROJECT / "bridge").joinpath(bridge.PFP_PFD_FONT_FILENAME)
    font_packets = (
        bridge._load_native_mcdu_font_packets(font_path)
        if font_path.is_file()
        else ()
    )

    print(f"Repeating the handoff {args.cycles} times.\n")
    print(f"  {'cycle':>5}  {'open':>7}  {'font':>7}  {'clear':>7}  "
          f"{'writes':>7}  {'short':>6}  {'failed':>7}")

    trouble = None

    for cycle in range(1, args.cycles + 1):
        started = time.perf_counter()
        handle = bridge.hid.device()
        handle.open_path(path)
        opened = time.perf_counter() - started

        counter = _CountingDevice(handle)

        try:
            try:
                handle.set_nonblocking(1)
            except Exception:
                pass

            started = time.perf_counter()
            for packet in font_packets:
                counter.write(list(packet))
            font_seconds = time.perf_counter() - started

            counter.write(list(_black_background_packet()))
            counter.write(list(_text_grid_packet()))

            started = time.perf_counter()
            canvas = bridge._PfpNativeCanvas(
                counter,
                identifier=bridge.MCDU_PFD_IDENTIFIER,
            )
            canvas.colour(6, 7, 13)
            for top in range(0, 480, 60):
                canvas.fill(0, top, 640, min(60, 480 - top))
            canvas.command(0x103)
            clear_seconds = time.perf_counter() - started

        finally:
            try:
                handle.close()
            except Exception:
                pass

        print(
            f"  {cycle:>5}  {opened:>7.3f}  {font_seconds:>7.3f}  "
            f"{clear_seconds:>7.3f}  {counter.writes:>7}  "
            f"{counter.short:>6}  {counter.failed:>7}"
        )

        if (counter.failed or counter.short) and trouble is None:
            trouble = (cycle, counter.first_failure)

        time.sleep(0.2)

    print()

    if trouble is not None:
        cycle, detail = trouble
        print(f"The panel began refusing writes on cycle {cycle}: {detail}")
        print("That is a signal the bridge can detect and recover from.")
    else:
        print("Every write was accepted on every cycle.")
        print("So the panel fails silently: it keeps acknowledging writes it")
        print("no longer acts on, and only the screen shows the difference.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
