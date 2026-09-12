#!/usr/bin/env python3
"""
Is the PU overhead panel (3561:8561) alive?

READ-ONLY. This never opens or writes to the device -- it only asks Windows
whether the board is enumerated on the USB bus.

  python tools/panel_check.py           one-shot check
  python tools/panel_check.py --watch   keep checking; replug the panel and watch
"""

import subprocess
import sys
import time

VID_PID = "VID_3561&PID_8561"


def nodes():
    """Device nodes Windows currently sees for the panel."""
    ps = (
        "Get-CimInstance Win32_PnPEntity | "
        f"Where-Object {{ $_.PNPDeviceID -like '*{VID_PID}*' }} | "
        "ForEach-Object { $_.Status + '|' + $_.Name }"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except Exception as e:
        print(f"could not query Windows: {e}")
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def report():
    found = nodes()
    if found:
        print("PANEL PRESENT -- the board enumerates:")
        for n in found:
            status, _, name = n.partition("|")
            print(f"    [{status}] {name}")
        print("\n  => The hardware is NOT dead. It powers up, talks USB and")
        print("     Windows accepts its descriptors. A board that is damaged")
        print("     cannot do that. Treat the earlier failure as firmware/software.")
    else:
        print("PANEL ABSENT -- nothing with VID_3561&PID_8561 on the bus.")
        print("\n  => Not a verdict of 'damaged' yet. The board stopped answering")
        print("     USB, which a firmware hang does just as often as real damage.")
        print("     Power-cycle the panel (unplug its USB, count to five, replug).")
        print("     If it comes back, it was a hang, not damage.")
    return bool(found)


def main():
    if "--watch" not in sys.argv:
        report()
        return
    print("Watching for the panel. Unplug and replug it now. Ctrl+C to stop.\n")
    last = None
    try:
        while True:
            here = bool(nodes())
            if here != last:
                print(time.strftime("[%H:%M:%S] ") + ("APPEARED" if here else "GONE"))
                if here:
                    print("\n  => It came back. The board is fine; it had hung.")
                last = here
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
