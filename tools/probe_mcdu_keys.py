"""Report which button index each MCDU key reports.

The page cycle is bound to a button index -- 70 on the MCDU, 69 on the PFP --
and if that index is wrong the trigger simply never fires, silently.  Nothing
in the logs would show it, because the detector is never called.

This reads the keypad and prints the index of whatever is pressed, so the
binding can be checked against the real hardware instead of assumed.

It only reads.  It writes nothing to the panel and does not touch the
simulator.  Run it with the bridge stopped, or the bridge's own key reader
will take the reports first.

Usage:
    python tools/probe_mcdu_keys.py
    python tools/probe_mcdu_keys.py --pfp      # the PFP, to compare
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

LISTEN_SECONDS = 45.0


def _load_bridge():
    path = PROJECT / "bridge" / "final.py"
    spec = importlib.util.spec_from_file_location("final", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _button_bits(report) -> int:
    """The 128 button bits a report carries, as one integer."""
    if not report or report[0] != 0x01 or len(report) < 17:
        return -1

    value = 0

    for index in range(16):
        value |= report[1 + index] << (index * 8)

    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pfp", action="store_true")
    parser.add_argument("--seconds", type=float, default=LISTEN_SECONDS)
    args = parser.parse_args()

    bridge = _load_bridge()

    if bridge.hid is None:
        print("hidapi unavailable; install hidapi")
        return 2

    if args.pfp:
        pid, label, expected = bridge.PFP_PFD_PID, "BB35 PFP", 69
    else:
        pid, label, expected = bridge.MCDU_PFD_PID, "BB36 MCDU", 70

    devices = list(bridge.hid.enumerate(bridge.PFP_PFD_VID, pid))

    if not devices:
        print(f"{label} not found")
        return 2

    device = bridge.hid.device()
    device.open_path(devices[0]["path"])

    seen = {}

    try:
        device.set_nonblocking(1)

        print(f"{label}: press keys.  The SLASH key is the one that matters.")
        print(f"This build expects SLASH at index {expected}.")
        print(f"Listening for {args.seconds:.0f} seconds; Ctrl+C to stop early.\n")

        previous = 0
        deadline = time.monotonic() + args.seconds

        while time.monotonic() < deadline:
            report = device.read(64)

            if not report:
                time.sleep(0.002)
                continue

            bits = _button_bits(report)

            if bits < 0:
                continue

            pressed = bits & ~previous
            previous = bits

            for index in range(128):
                if pressed & (1 << index):
                    seen[index] = seen.get(index, 0) + 1
                    note = "   <-- this build's SLASH" if index == expected else ""
                    print(f"  button index {index:>3}{note}")

    except KeyboardInterrupt:
        print("\n  stopped")
    finally:
        try:
            device.close()
        except Exception:
            pass

    print()

    if not seen:
        print("  No key presses were seen at all.  Either nothing was pressed,")
        print("  or the bridge is running and took the reports first.")
    else:
        print("  indices seen:", ", ".join(str(i) for i in sorted(seen)))

        # The routers read bytes 1..13 only, which is 96 of the 128 buttons
        # the HID descriptor declares.  Anything above 95 is invisible to
        # them however correct its index is.
        invisible = [i for i in sorted(seen) if i >= 96]

        if invisible:
            print(f"  NOTE: {invisible} are above index 95, and the bridge's")
            print("        button reader stops at 95 -- it would never see them.")

        if expected in seen:
            print(f"  index {expected} was among them, so the binding is right.")
        else:
            print(f"  index {expected} was NOT seen.  If one of the above is the")
            print("  SLASH key, that is the correct index and this build's is wrong.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
