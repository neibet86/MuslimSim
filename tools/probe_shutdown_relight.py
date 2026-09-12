"""Find out whether the panels relight when MuslimSim releases them.

Three devices with separately verified blackouts - the PU overhead, the WinCtrl
throttle and the PAP3 - all light up at the same moment when Studio closes.
Three independent bugs producing one simultaneous symptom is unlikely; one
cause acting after all three blackouts is not.

There are only two possibilities and they need opposite fixes:

  A. The blackout never reaches the panel, or something re-lights it before the
     handle closes.  That is our bug and we can fix it in software.
  B. The panel firmware returns to its lit power-on state when the last handle
     closes.  Then no "write dark, then close" can ever work, because the
     relight happens after our final write, and the fix has to be something
     else entirely.

This separates them by doing the two halves apart, with a pause you can watch:

  1. open the handle and black the panel out
  2. HOLD it open  -> look at the panel. Dark here means the blackout works.
  3. close the handle
  4. WAIT          -> look again. Lighting up here, with nothing else running,
                      means the firmware did it, not us.

It writes only the captured off values the bridge already uses, and nothing to
the simulator.  MuslimSim Studio and the bridge must be CLOSED; they own these
handles.

Usage:
    python tools/probe_shutdown_relight.py
    python tools/probe_shutdown_relight.py --hold 8 --after 8
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


def countdown(seconds: float, label: str) -> None:
    end = time.monotonic() + seconds
    while True:
        left = end - time.monotonic()
        if left <= 0:
            break
        print("\r    %4.1fs  %s" % (left, label), end="", flush=True)
        time.sleep(0.1)
    print("\r" + " " * 70 + "\r", end="")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hold", type=float, default=6.0,
                    help="seconds to hold the handle open after blacking out")
    ap.add_argument("--after", type=float, default=6.0,
                    help="seconds to wait after closing the handle")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    procs = running_muslimsim(PROJECT)
    if procs and not a.force:
        print("MuslimSim is running:", file=sys.stderr)
        for p in procs:
            print("   " + p, file=sys.stderr)
        print("\nClose Studio and the bridge first; they own these handles.",
              file=sys.stderr)
        return 1

    spec = importlib.util.spec_from_file_location(
        "_relight", PROJECT / "bridge" / "final.py"
    )
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)

    if bridge.hid is None:
        print("The 'hid' package is not installed.", file=sys.stderr)
        return 1

    print("")
    print("=" * 70)
    print("  DOES THE PANEL RELIGHT WHEN WE LET GO?")
    print("=" * 70)
    print("  Watch the WinCtrl throttle backlight through both phases.")
    print("")

    try:
        device = bridge._open_winctrl_trim_display()
    except Exception as exc:
        print("  Could not open the throttle PAC interface: %s" % exc,
              file=sys.stderr)
        return 1

    relit_by_us = False
    try:
        # Wake first, so the panel is definitely lit and the blackout has
        # something to actually turn off.  Otherwise a panel that was already
        # dark proves nothing.
        bridge._winctrl_wake_throttle_outputs(device)
        print("  1. woke the panel  -> it should be LIT now")
        countdown(2.5, "look: the panel should be lit")

        bridge._winctrl_throttle_blackout(device)
        print("  2. blackout sent, handle still OPEN")
        print("     >>> LOOK NOW. Is the panel dark?")
        countdown(a.hold, "handle still open - is it dark?")
        relit_by_us = True
    finally:
        try:
            device.close()
        except Exception:
            pass

    print("  3. handle CLOSED. MuslimSim is now writing nothing at all.")
    print("     >>> LOOK AGAIN. Did it light back up?")
    countdown(a.after, "handle closed - did it relight?")

    print("")
    print("=" * 70)
    print("  Dark in step 2 and still dark in step 3")
    print("     -> the blackout works and holds. The shutdown fault is ours,")
    print("        somewhere between the blackout and process exit.")
    print("")
    print("  Dark in step 2 but LIT in step 3")
    print("     -> the firmware relights when the last handle closes. No")
    print("        'write dark then close' can fix that, and the answer has to")
    print("        be something else - keeping a handle, or a vendor standby")
    print("        command we have not captured.")
    print("")
    print("  LIT in step 2")
    print("     -> the blackout is not reaching the panel at all.")
    print("=" * 70)
    return 0 if relit_by_us else 1


if __name__ == "__main__":
    raise SystemExit(main())
