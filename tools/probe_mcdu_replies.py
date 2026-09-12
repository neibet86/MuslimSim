"""Listen to what the panel says back on its display channels.

The HID report descriptor declares INPUT reports on 0xF0 and 0xF2 -- the same
channels this bridge writes graphics and character pages to -- and nothing in
MuslimSim has ever read them.  That matters because this panel accepts every
write whether or not it acts on it, so there is currently no way to tell a
command that worked from one that was ignored.  If the controller reports
anything at all, this is where it would arrive.

It sends a small, known sequence and reports every non-keypad report that
comes back, with the delay after the write that produced it.  Keypad reports
(0x01) are counted but not printed, since pressing nothing still produces
them on some builds.

It writes only to the display, never to the simulator, and opens no other
hardware.  Run it with the bridge stopped.

Usage:
    python tools/probe_mcdu_replies.py
    python tools/probe_mcdu_replies.py --pfp     # the PFP, for comparison
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

LISTEN_SECONDS = 1.2


def _load_bridge():
    path = PROJECT / "bridge" / "final.py"
    spec = importlib.util.spec_from_file_location("final", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _drain(device, seconds: float, label: str) -> list:
    """Collect reports for a while, separating keypad traffic from the rest."""
    collected = []
    keypad = 0
    deadline = time.monotonic() + seconds

    while time.monotonic() < deadline:
        try:
            report = device.read(64)
        except Exception as exc:
            print(f"  read failed: {exc}")
            break

        if not report:
            time.sleep(0.002)
            continue

        if report[0] == 0x01:
            keypad += 1
            continue

        collected.append(bytes(report))

    print(f"  [{label}] {len(collected)} non-keypad reports"
          f"{f', {keypad} keypad' if keypad else ''}")

    for report in collected[:12]:
        print(f"      id 0x{report[0]:02X}  {report[:24].hex(' ')}")

    if len(collected) > 12:
        print(f"      ... {len(collected) - 12} more")

    return collected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pfp",
        action="store_true",
        help="Probe the BB35 PFP instead, to compare a panel that behaves",
    )
    args = parser.parse_args()

    bridge = _load_bridge()

    if bridge.hid is None:
        print("hidapi unavailable; install hidapi")
        return 2

    if args.pfp:
        pid, identifier, label = bridge.PFP_PFD_PID, bridge.PFP_PFD_IDENTIFIER, "BB35 PFP"
    else:
        pid, identifier, label = bridge.MCDU_PFD_PID, bridge.MCDU_PFD_IDENTIFIER, "BB36 MCDU"

    devices = list(bridge.hid.enumerate(bridge.PFP_PFD_VID, pid))

    if not devices:
        print(f"{label} not found")
        return 2

    device = bridge.hid.device()
    device.open_path(devices[0]["path"])

    try:
        device.set_nonblocking(1)

        print(f"Listening to {label}.\n")

        _drain(device, LISTEN_SECONDS, "idle, before anything is sent")

        print("\n  -> brightness report (0x02)")
        bridge._winctrl_display_set_brightness(device, identifier, 1, 220)
        _drain(device, LISTEN_SECONDS, "after brightness")

        print("\n  -> one native graphics fill (0xF0)")
        canvas = bridge._PfpNativeCanvas(device, identifier=identifier)
        canvas.colour(6, 7, 13)
        canvas.fill(0, 0, 640, 480)
        canvas.command(0x103)
        _drain(device, LISTEN_SECONDS, "after a graphics fill")

        print("\n  -> a deliberately invalid function id (0x1FF)")
        probe = bridge._PfpNativeCanvas(device, identifier=identifier)
        probe.command(0x1FF)
        probe.flush()
        _drain(device, LISTEN_SECONDS, "after an invalid command")

        print()
        print("If nothing but keypad traffic appears, this panel reports")
        print("nothing about its display state and silent failure cannot be")
        print("detected from the host at all.")
        print()
        print("If reports do appear, compare them against the PFP with --pfp:")
        print("a difference is the feedback this investigation has been missing.")

    finally:
        try:
            device.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
