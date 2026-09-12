"""Find where the MCDU's black specks come from: the drawing, or the panel.

Rendering the PFD frames and counting pixels shows the picture this bridge
draws for the MCDU is clean -- cleaner than the PFP's, which has no specks
reported against it.  So the specks are either in what reaches the glass or
in the panel's own state, and neither is visible from the host.

This separates the two by painting FLAT fields.  A flat field has no marks,
no tapes and no ladder, so the renderer cannot put a speck in one:

  * specks visible on a flat field  -> not the PFD drawing.  It is the panel,
    and the most likely cause is the character plane still holding cells
    under the graphics plane, which would show as a regular pattern rather
    than as scattered dots.

  * flat fields clean, specks only with the PFD up -> the drawing after all,
    and the next step is to photograph the PFD and locate them by eye,
    because no pixel measurement of the rendered frame has found them.

Whether the specks need the FMC path to have run is the second question, so
the fields are painted twice: once as the panel stands, and once after the
FMC path's opening sequence.  A difference implicates the character plane.

It writes only to the display, never to the simulator.  Run it with the
bridge stopped.  Each field is held six seconds -- look closely at the whole
glass, including the corners.

Usage:
    python tools/probe_mcdu_speckle.py
    python tools/probe_mcdu_speckle.py --pfp    # the panel with no complaint
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

HOLD = 6.0

FIELDS = (
    ((128, 128, 132), "mid grey  -- specks show most clearly against this"),
    ((245, 246, 249), "white     -- the PFD's own ink colour"),
    ((20, 101, 211), "blue      -- the attitude ball's sky"),
)


def _load_bridge():
    spec = importlib.util.spec_from_file_location(
        "final", PROJECT / "bridge" / "final.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _paint(bridge, device, identifier, rgb, label: str) -> None:
    canvas = bridge._PfpNativeCanvas(device, identifier=identifier)
    canvas.colour(*rgb)

    # Banded, because one 640x480 fill is larger than a single report carries.
    for top in range(0, 480, 60):
        canvas.fill(0, top, 640, min(60, 480 - top))

    canvas.command(0x103)
    print(f"    {label}   (holding {HOLD:.0f}s)")
    time.sleep(HOLD)


def _run_fmc_opening(bridge, path) -> None:
    """The FMC path's opening sequence, exactly as the bridge performs it."""
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

        for packet in _read_font_packets(
            (PROJECT / "bridge") / bridge.PFP_FMC_FONT_FILENAME
        ):
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
        pid = bridge.PFP_PFD_PID
        identifier = bridge.PFP_PFD_IDENTIFIER
        label = "BB35 PFP"
    else:
        pid = bridge.MCDU_PFD_PID
        identifier = bridge.MCDU_PFD_IDENTIFIER
        label = "BB36 MCDU"

    devices = list(bridge.hid.enumerate(bridge.PFP_PFD_VID, pid))

    if not devices:
        print(f"{label} not found")
        return 2

    path = devices[0]["path"]
    device = bridge.hid.device()
    device.open_path(path)

    try:
        device.set_nonblocking(1)
        bridge._winctrl_display_set_brightness(device, identifier, 0, 128)
        bridge._winctrl_display_set_brightness(device, identifier, 1, 220)

        print(f"{label}: watch the glass for black dots.\n")
        print("  PASS 1 -- the panel as it stands\n")

        for rgb, text in FIELDS:
            _paint(bridge, device, identifier, rgb, text)

        if not args.pfp:
            print("\n  running the FMC path's opening sequence...\n")
            device.close()
            _run_fmc_opening(bridge, path)
            time.sleep(0.3)
            device = bridge.hid.device()
            device.open_path(path)
            device.set_nonblocking(1)

            print("  PASS 2 -- after the character plane has been configured\n")

            for rgb, text in FIELDS:
                _paint(bridge, device, identifier, rgb, text)

    finally:
        try:
            device.close()
        except Exception:
            pass

    print()
    print("  Which pass had the dots?")
    print()
    print("    neither      -> the specks need the PFD on screen; they are in")
    print("                    the drawing, and a photo is the next step")
    print("    both passes  -> the panel speckles regardless of this bridge")
    print("    pass 2 only  -> the character plane is showing through the")
    print("                    graphics plane, and that is the thing to fix")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
