"""Find the background selector value that shows the factory WinCtrl logo.

MuslimSim switches a panel out of its factory logo by sending native function
0x104 with a single selector byte of 0x0E -- that is the "black background"
this bridge draws on.  Returning a panel to its original WinCtrl state needs
the value it starts with, and that value is not recorded anywhere in this
project.

So ask the panel.  This steps the selector through its candidate values,
printing each one as it sends it, and holds long enough to see the result.
Watch the display and note the value printed when the WinCtrl logo appears.

Then tell MuslimSim about it by setting, in bridge/final.py:

    WINCTRL_FACTORY_BACKGROUND = 0x??

and the shutdown restore will put the logo back on both panels.

It finishes by restoring 0x0E, the state the bridge normally leaves behind,
so nothing is left in an unexpected mode.  It writes only to the display,
never to the simulator, and opens no other hardware.

Usage:
    python tools/probe_winctrl_logo.py            # the PFP
    python tools/probe_winctrl_logo.py --mcdu     # the MCDU
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

# The selector is one byte and the black background is 0x0E, so the factory
# value is very likely a small neighbour of it.
CANDIDATES = tuple(range(0x00, 0x10))
HOLD_SECONDS = 2.5


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
        "--mcdu",
        action="store_true",
        help="Probe the BB36 MCDU instead of the BB35 PFP",
    )
    parser.add_argument(
        "--hold",
        type=float,
        default=HOLD_SECONDS,
        help=f"Seconds to hold each value (default {HOLD_SECONDS})",
    )
    args = parser.parse_args()

    bridge = _load_bridge()

    if bridge.hid is None:
        print("hidapi unavailable; install hidapi")
        return 2

    if args.mcdu:
        pid = bridge.MCDU_PFD_PID
        identifier = bridge.MCDU_PFD_IDENTIFIER
        label = "BB36 MCDU"
    else:
        pid = bridge.PFP_PFD_PID
        identifier = bridge.PFP_PFD_IDENTIFIER
        label = "BB35 PFP"

    devices = list(bridge.hid.enumerate(bridge.PFP_PFD_VID, pid))

    if not devices:
        print(f"{label} (VID 4098 / PID {pid:04X}) not found")
        return 2

    path = devices[0].get("path")

    if not path:
        print(f"Windows did not supply a HID path for the {label}")
        return 2

    device = bridge.hid.device()
    device.open_path(path)

    try:
        try:
            device.set_nonblocking(1)
        except Exception:
            pass

        bridge._winctrl_display_set_brightness(device, identifier, 0, 128)
        bridge._winctrl_display_set_brightness(device, identifier, 1, 220)

        print(f"Watch the {label}.  Note the value shown when the logo appears.\n")

        for selector in CANDIDATES:
            marker = "  <- what MuslimSim sends" if selector == 0x0E else ""
            print(f"  selector 0x{selector:02X}{marker}")

            device.write(list(bridge._winctrl_background_packet(
                identifier,
                selector,
            )))
            time.sleep(args.hold)

        # Leave the panel in the state the bridge normally leaves behind.
        device.write(list(bridge._winctrl_background_packet(
            identifier,
            bridge.WINCTRL_BACKGROUND_BLACK,
        )))

        print()
        print("If one of those showed the WinCtrl logo, set in bridge/final.py:")
        print("    WINCTRL_FACTORY_BACKGROUND = 0x??")
        print("and the shutdown restore will put the logo back.")
        print()
        print("If none did, the logo is not a background selector value and")
        print("the panels can only be handed back blank.")

    finally:
        try:
            device.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
