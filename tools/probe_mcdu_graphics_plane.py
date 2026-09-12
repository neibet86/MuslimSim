"""Paint a test card on the MCDU that answers the question in one photograph.

Three separate clears run on every FMC/PFD handoff -- the PFD session's own, a
full soft reboot, and the FMC session's on entry -- all report success, and a
frame of the previous page still survives around the FMC menu.  So either
those fills are not reaching the edges of the glass, or something is putting
the pixels back.  One picture separates the two.

This paints the screen in labelled horizontal bands, each a colour that cannot
be confused with flight information, and leaves them up.  Photograph the
screen and the picture says which bands the graphics plane actually reached:

    rows   0- 9   RED      above everything the PFD viewport can draw
    rows  10-36   GREEN    PFD draws here, the FMC page does not cover it
    rows  37-442  BLUE     behind the FMC character page
    rows 443-469  YELLOW   below the FMC page, PFD still draws here
    rows 470-479  MAGENTA  below everything the PFD viewport can draw

If every band shows its colour, fills reach the whole glass and the remnants
are being put back by something else.  If a band keeps old flight information
instead, fills are not reaching that band and the coordinate model is wrong.

It writes only to the display, never to the simulator, and opens no other
hardware.  Run it with the bridge stopped so nothing repaints over the card.

Usage:
    python tools/probe_mcdu_graphics_plane.py             # paint the card
    python tools/probe_mcdu_graphics_plane.py --restore   # back to dark navy
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

BACKGROUND = (6, 7, 13)

# Row ranges chosen from the real geometry: the MCDU's character page is
# 552x406 at (52, 37), and the PFD's viewport maps every draw into rows
# 10..449.  The bands are the regions those two facts create.
BANDS = (
    (0, 10, (220, 0, 0), "RED", "above the PFD viewport"),
    (10, 27, (0, 200, 60), "GREEN", "PFD draws, FMC page does not cover"),
    (37, 406, (0, 80, 255), "BLUE", "behind the FMC page"),
    (443, 27, (255, 200, 0), "YELLOW", "below the FMC page, PFD still draws"),
    (470, 10, (255, 0, 200), "MAGENTA", "below the PFD viewport"),
)


def _load_bridge():
    """Load bridge/final.py, which owns the native display protocol."""
    path = PROJECT / "bridge" / "final.py"
    spec = importlib.util.spec_from_file_location("final", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Put the screen back to the normal dark background",
    )
    parser.add_argument(
        "--no-font",
        action="store_true",
        help="Skip the native font upload",
    )
    parser.add_argument(
        "--test-config-lock",
        action="store_true",
        help=(
            "Paint green, send the character-mode config the FMC path sends, "
            "then paint red.  A screen that stays green means that config "
            "stops the graphics plane accepting anything."
        ),
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

    device = bridge.hid.device()
    device.open_path(path)

    try:
        try:
            device.set_nonblocking(1)
        except Exception:
            pass

        bridge._winctrl_display_set_brightness(
            device, bridge.MCDU_PFD_IDENTIFIER, 0, 128
        )
        bridge._winctrl_display_set_brightness(
            device, bridge.MCDU_PFD_IDENTIFIER, 1, 220
        )

        # The PFD path uploads this before it draws, and it draws
        # successfully.  A session without it painted nothing at all -- not
        # even a flicker -- so this is the one step under test.
        if not args.no_font:
            font_path = (PROJECT / "bridge").joinpath(
                bridge.PFP_PFD_FONT_FILENAME
            )

            if font_path.is_file():
                for packet in bridge._load_native_mcdu_font_packets(font_path):
                    device.write(list(packet))

                print(f"  uploaded the native font ({font_path.name})")
            else:
                print(f"  NATIVE FONT MISSING at {font_path}")
        else:
            print("  skipping the font upload")

        canvas = bridge._PfpNativeCanvas(
            device,
            identifier=bridge.MCDU_PFD_IDENTIFIER,
        )

        if args.restore:
            canvas.colour(*BACKGROUND)

            for top in range(0, 480, 60):
                canvas.fill(0, top, 640, min(60, 480 - top))

            canvas.command(0x103)
            print("MCDU returned to its normal dark background.")
            return 0

        if args.test_config_lock:
            # Green first, proving the plane is accepting drawing right now.
            canvas.colour(0, 200, 60)
            for top in range(0, 480, 60):
                canvas.fill(0, top, 640, min(60, 480 - top))
            canvas.command(0x103)
            print("  painted GREEN -- the plane is accepting drawing")

            time.sleep(1.5)

            # Exactly what the FMC path sends on entry.
            from muslimsim.devices.mcdu_bb36 import (
                _black_background_packet,
                _text_grid_packet,
            )

            device.write(list(_black_background_packet()))
            device.write(list(_text_grid_packet()))
            print("  sent the character-mode config (0x104 + text grid)")

            time.sleep(0.5)

            # Now try to paint over it.
            after = bridge._PfpNativeCanvas(
                device,
                identifier=bridge.MCDU_PFD_IDENTIFIER,
            )
            after.colour(220, 0, 0)
            for top in range(0, 480, 60):
                after.fill(0, top, 640, min(60, 480 - top))
            after.command(0x103)
            print("  painted RED over it")

            print()
            print("  screen is RED   -> the config does not stop drawing")
            print("  screen is GREEN -> the config locks the graphics plane,")
            print("                     which is why nothing clears after the")
            print("                     FMC path has started")
            return 0

        for top, height, colour, name, meaning in BANDS:
            canvas.colour(*colour)
            canvas.fill(0, top, 640, height)
            print(
                f"  rows {top:3d}-{top + height - 1:3d}  {name:8}  {meaning}"
            )

        canvas.command(0x103)

        print()
        print("Photograph the MCDU and send the picture.")
        print()
        print("  every band in its colour  -> fills reach the whole glass,")
        print("                               something is putting the")
        print("                               remnants back")
        print("  a band still showing old  -> fills never reach that band,")
        print("  flight information           and the coordinate model is wrong")
        print()
        print("Then: python tools/probe_mcdu_graphics_plane.py --restore")

    finally:
        try:
            device.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
