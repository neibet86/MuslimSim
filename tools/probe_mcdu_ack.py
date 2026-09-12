"""Count what the panel acknowledges, before and after the FMC path runs.

The panel answers every 0xF0 output report with an input report of the form
`f0 01 <counter>`, incrementing once per report it processes.  That is the
first feedback found from this hardware, and it separates two possibilities
that have been indistinguishable all along:

  * the panel stops PROCESSING our reports  -> acknowledgements stop or lag
  * the panel processes them and does not RENDER -> acknowledgements keep
    coming while the glass does not change

Everything about the silent-failure problem turns on which of those it is, so
this measures it rather than inferring it.

The sequence is: a fresh session sends a known number of reports and the
acknowledgements are counted; the FMC path's own opening sequence is then
performed, exactly as the bridge performs it; a second fresh session repeats
the measurement.  A drop in the second is the degraded state, caught.

It writes only to the display, never to the simulator, and opens no other
hardware.  Run it with the bridge stopped, ideally on a freshly power-cycled
panel so the first measurement is a clean baseline.

Usage:
    python tools/probe_mcdu_ack.py
    python tools/probe_mcdu_ack.py --pfp     # the panel that behaves
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

ACK_WINDOW = 1.0


def _load_bridge():
    path = PROJECT / "bridge" / "final.py"
    spec = importlib.util.spec_from_file_location("final", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _collect_acks(device, seconds: float):
    """Return the 0xF0 acknowledgement counters seen within the window."""
    counters = []
    deadline = time.monotonic() + seconds

    while time.monotonic() < deadline:
        try:
            report = device.read(64)
        except Exception:
            break

        if not report:
            time.sleep(0.001)
            continue

        if report[0] == 0xF0 and len(report) > 2:
            counters.append(report[2])

    return counters


def _measure(bridge, path, identifier, label: str):
    """Fill the screen from a fresh session and count what comes back."""
    device = bridge.hid.device()
    device.open_path(path)

    try:
        device.set_nonblocking(1)
        _collect_acks(device, 0.2)          # discard anything pending

        canvas = bridge._PfpNativeCanvas(device, identifier=identifier)
        canvas.colour(6, 7, 13)

        for top in range(0, 480, 60):
            canvas.fill(0, top, 640, min(60, 480 - top))

        canvas.command(0x103)

        sent = canvas.sequence - 1
        acks = _collect_acks(device, ACK_WINDOW)

        print(f"  {label}")
        print(f"      reports sent      {sent}")
        print(f"      acknowledged      {len(acks)}")

        if acks:
            print(f"      counter range     0x{min(acks):02X}..0x{max(acks):02X}")

        return sent, len(acks)

    finally:
        try:
            device.close()
        except Exception:
            pass


def _run_fmc_opening(bridge, path, identifier) -> None:
    """Perform the FMC path's opening sequence, as the bridge performs it."""
    from muslimsim.devices.mcdu_bb36 import (
        _black_background_packet,
        _text_grid_packet,
        _read_font_packets,
        _page_packets,
        MCDU_COLUMNS,
        MCDU_ROWS,
    )

    device = bridge.hid.device()
    device.open_path(path)

    try:
        device.set_nonblocking(1)

        font_path = (PROJECT / "bridge").joinpath(bridge.PFP_FMC_FONT_FILENAME)

        for packet in _read_font_packets(font_path):
            device.write(list(packet))

        time.sleep(0.20)
        device.write(list(_black_background_packet()))
        device.write(list(_text_grid_packet()))

        blank = tuple(" " * MCDU_COLUMNS for _ in range(MCDU_ROWS))
        colours = tuple(
            tuple(0x0042 for _ in range(MCDU_COLUMNS)) for _ in range(MCDU_ROWS)
        )

        for packet in _page_packets(blank, colours):
            device.write(list(packet))

    finally:
        try:
            device.close()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pfp", action="store_true")
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

    path = devices[0]["path"]

    print(f"{label}\n")
    before = _measure(bridge, path, identifier, "fresh session, before the FMC path")

    print("\n  running the FMC path's opening sequence...\n")
    _run_fmc_opening(bridge, path, identifier)
    time.sleep(0.3)

    after = _measure(bridge, path, identifier, "fresh session, after the FMC path")

    print()

    if after[1] == 0 and before[1] > 0:
        print("  The panel stopped acknowledging: it is no longer processing")
        print("  what is sent, and silent failure is detectable from the host.")
    elif after[1] >= before[1] > 0:
        print("  The panel acknowledged both times.  It processes the reports")
        print("  and does not render them, so nothing the host sends can be")
        print("  used to tell a working clear from an ignored one.")
    else:
        print("  Acknowledgement count changed; compare the two runs above.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
