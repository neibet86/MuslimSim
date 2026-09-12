"""Drive the real B930 RUD TRIM window to find out why it is blank.

Every software layer between a Practice press and this display checks out on
reading -- the catalogue control, the device registration, the lab validation,
the control-server forward, the startup init, and the segment encoding, whose
captured plane values are still asserted by the bridge's own self-test.  So the
next honest step is the hardware itself.

This opens the PAC output interface with the bridge's own
``_open_winctrl_trim_display``, sends the captured wake sequence, and writes a
short sequence of values through the same ``_winctrl_write_trim_display`` the
bridge uses.  Nothing here is a new packet: it is the production path, driven
by hand, so whatever it shows is what Practice mode would have shown.

It DOES write to the display -- that is the point.  It writes nothing to the
simulator, touches no other device, and finishes by restoring the neutral 0.0
the bridge itself writes at startup.

MuslimSim Studio and the bridge must be CLOSED: they own this HID handle, and
two owners is the one thing the project does not allow.

Usage:
    python tools/probe_winctrl_trim_display.py
    python tools/probe_winctrl_trim_display.py --hold 1.5
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))


def running_muslimsim(root: Path):
    if os.name != "nt":
        return []
    r = str(root).replace("'", "''")
    ps = (
        "$r='" + r + "'; Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -match '^(python|pythonw|py|pyw)([0-9.]*)\\.exe$' -and $_.CommandLine -and ("
        "$_.CommandLine -like ('*'+$r+'*MuslimSim Studio.pyw*') -or "
        "$_.CommandLine -like ('*'+$r+'*launch.py*') -or "
        "$_.CommandLine -like ('*'+$r+'*bridge\\final.py*')) } | "
        "ForEach-Object { '{0} {1}' -f $_.ProcessId,$_.Name }"
    )
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=20,
        )
    except Exception:
        return []
    return [x.strip() for x in p.stdout.splitlines() if x.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hold", type=float, default=1.2,
                    help="seconds to leave each value on the window")
    ap.add_argument("--no-wake", action="store_true",
                    help="skip the captured wake sequence, to test whether wake is the missing step")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    procs = running_muslimsim(PROJECT)
    if procs and not a.force:
        print("MuslimSim is running:", file=sys.stderr)
        for p in procs:
            print("   " + p, file=sys.stderr)
        print("\nClose Studio and the bridge first: they own this HID handle.",
              file=sys.stderr)
        return 1

    spec = importlib.util.spec_from_file_location(
        "_trimdisp", PROJECT / "bridge" / "final.py"
    )
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)

    if bridge.hid is None:
        print("The 'hid' package is not installed.", file=sys.stderr)
        return 1

    print("")
    print("=" * 70)
    print("  B930 RUD TRIM WINDOW PROBE")
    print("=" * 70)
    found = bridge.hid.enumerate(bridge.WINCTRL_HID_VID, bridge.WINCTRL_HID_PID)
    print("  VID/PID          : %04X / %04X"
          % (bridge.WINCTRL_HID_VID, bridge.WINCTRL_HID_PID))
    print("  HID interfaces   : %d" % len(found))
    for entry in found:
        print("     usage_page=0x%04X usage=0x%04X  %s"
              % (entry.get("usage_page", 0), entry.get("usage", 0),
                 entry.get("product_string", "")))
    if not found:
        print("\n  The PAC output interface is not present. Nothing can reach the")
        print("  window until Windows enumerates it.", file=sys.stderr)
        return 1

    try:
        device = bridge._open_winctrl_trim_display()
    except Exception as exc:
        print("\n  Could not open the PAC output interface: %s" % exc, file=sys.stderr)
        return 1

    print("")
    try:
        if a.no_wake:
            print("  wake sequence    : SKIPPED (--no-wake)")
        else:
            bridge._winctrl_wake_throttle_outputs(device)
            print("  wake sequence    : sent (%d reports)"
                  % len(bridge.WINCTRL_THROTTLE_WAKE_REPORTS))

        sequence = (
            (-2.5, True, "signed  L 25   <- the captured self-test value"),
            (1.0, True, "signed  R 10"),
            (0.0, True, "signed    00"),
            (4.9, False, "units     49   <- stabilizer trim readout"),
            (15.8, False, "units    158"),
        )
        print("")
        for value, signed, label in sequence:
            written = bridge._winctrl_write_trim_display(device, value, signed=signed)
            print("  wrote %-6s  %s" % (written, label))
            time.sleep(max(0.0, a.hold))

        bridge._winctrl_write_trim_display(device, 0.0, signed=True)
        print("")
        print("  restored 0.0, the same neutral the bridge writes at startup.")
        print("")
        print("  If the window stayed blank for ALL of the above, the fault is")
        print("  below the software: the wake sequence, the PAC interface, or")
        print("  the panel's own power. Re-run with --no-wake to compare.")
        print("  If it showed these values, the display path is healthy and the")
        print("  fault is in what Practice mode sends to it.")
    finally:
        try:
            device.close()
        except Exception:
            pass
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
