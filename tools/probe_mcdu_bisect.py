"""Find which step of the FMC sequence turns the graphics plane off.

Graphics work from a fresh power-on and stop once the FMC sequence has run.
That sequence has only three parts, so this applies them one at a time and
paints the screen after each.  Whichever colour fails to appear identifies
the step that switches the plane off, and its inverse is then the fix.

The font is uploaded exactly ONCE.  Repeated uploads corrupt this panel's
glyph table -- that is what produced missing characters in earlier tests, and
it is a property of the hardware worth remembering.

    RED     after the font upload alone
    GREEN   after the background selector (fn 0x104, data 0x0E)
    BLUE    after the grid configuration  (fn 0x118 + fn 0x105)

Run it on a FRESHLY POWER-CYCLED panel, with the bridge stopped, or the first
measurement is not a baseline.  Each colour is held four seconds.

Usage:
    python tools/probe_mcdu_bisect.py
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

HOLD = 4.0


def _load_bridge():
    path = PROJECT / "bridge" / "final.py"
    spec = importlib.util.spec_from_file_location("final", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    bridge = _load_bridge()

    if bridge.hid is None:
        print("hidapi unavailable; install hidapi")
        return 2

    from muslimsim.devices.mcdu_bb36 import (
        _black_background_packet,
        _text_grid_packet,
        _read_font_packets,
    )

    devices = list(
        bridge.hid.enumerate(bridge.PFP_PFD_VID, bridge.MCDU_PFD_PID)
    )

    if not devices:
        print("WINCTRL 32 MCDU CAPTAIN not found")
        return 2

    identifier = bridge.MCDU_PFD_IDENTIFIER
    device = bridge.hid.device()
    device.open_path(devices[0]["path"])

    def paint(rgb, label: str) -> None:
        canvas = bridge._PfpNativeCanvas(device, identifier=identifier)
        canvas.colour(*rgb)

        for top in range(0, 480, 60):
            canvas.fill(0, top, 640, min(60, 480 - top))

        canvas.command(0x103)
        print(f"  {label}   (holding {HOLD:.0f}s)")
        time.sleep(HOLD)

    try:
        device.set_nonblocking(1)

        bridge._winctrl_display_set_brightness(device, identifier, 0, 128)
        bridge._winctrl_display_set_brightness(device, identifier, 1, 220)

        print("Bisecting the FMC sequence.  Watch the panel.\n")

        # 1 -- the font on its own.  Uploaded once, and only once.
        for packet in _read_font_packets(
            (PROJECT / "bridge") / bridge.PFP_FMC_FONT_FILENAME
        ):
            device.write(list(packet))

        time.sleep(0.25)
        paint((220, 0, 0), "RED    after the font upload alone")

        # 2 -- the background selector.
        device.write(list(_black_background_packet()))
        time.sleep(0.15)
        paint((0, 200, 60), "GREEN  after the background selector fn 0x104")

        # 3 -- the grid configuration.
        device.write(list(_text_grid_packet()))
        time.sleep(0.15)
        paint((0, 80, 255), "BLUE   after the grid configuration fn 0x118+0x105")

        print()
        print("Which colours appeared?")
        print()
        print("  all three      -> none of these steps disables graphics;")
        print("                    the cause is the character PAGE write itself")
        print("  red, green     -> the grid configuration disables it")
        print("  red only       -> the background selector disables it")
        print("  none           -> the panel was not in a clean state; power")
        print("                    cycle and run this again first")

    finally:
        try:
            device.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
