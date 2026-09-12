"""Send PU CONNECT's own all-the-way-down frame and see if the panel holds it.

The owner noticed that PU CONNECT MSFS has a brightness control which overrides
the physical knob, and asked whether MuslimSim could send that on the way out.

Their capture (PU_Brightness.pcapng, device 49 endpoint 0x02) shows PU CONNECT
speaking the same `OVHD,` protocol we do, and moving three separate fields:

    P2   1 .. 14
    P3   1 .. 14
    P8   0 .. 250        <- our P8_MAX is 125, half the vendor's range

Its resting, everything-down frame is:

    OVHD,0,1,1,0,12345,12345,0,0

MuslimSim's dark frame is:

    OVHD,0,4,4,0,<blank>,<blank>,0,0

We have never sent P2=1 or P3=1.  Those two fields sit at a hard-coded 4 that
the bridge documents nowhere, while the vendor treats them as controls with a
minimum of 1.  If they are brightness channels, our "dark" frame has two of
them still up.

This sends the vendor's own minimum, verbatim from the capture, then stops
sending and waits - because the open question is not whether the panel goes
dark but whether it stays dark once nothing is talking to it.

It writes nothing to the simulator.  Studio and the bridge must be CLOSED.

Usage:
    python tools/probe_pu_vendor_minimum.py
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

# Captured verbatim from PU CONNECT MSFS.  Not composed, not inferred.
VENDOR_MINIMUM = b"OVHD,0,1,1,0,12345,12345,0,0\n"
VENDOR_LIT = b"OVHD,0,14,14,0,12345,12345,0,250\n"
# What MuslimSim calls dark today, for comparison in the same session.
MUSLIMSIM_DARK = b"OVHD,0,4,4,0,     ,     ,0,0\n"


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


def look(seconds, label):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        print("\r      %4.1fs  %s" % (end - time.monotonic(), label),
              end="", flush=True)
        time.sleep(0.1)
    print("\r" + " " * 76 + "\r", end="")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM5")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--look", type=float, default=10.0)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    procs = running_muslimsim(PROJECT)
    if procs and not a.force:
        print("MuslimSim is running:", file=sys.stderr)
        for p in procs:
            print("   " + p, file=sys.stderr)
        print("\nClose Studio and the bridge first; they own COM5.",
              file=sys.stderr)
        return 1

    spec = importlib.util.spec_from_file_location(
        "_puvendor", PROJECT / "bridge" / "final.py"
    )
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    if bridge.serial is None:
        print("pyserial is not installed.", file=sys.stderr)
        return 1

    print("")
    print("=" * 76)
    print("  PU CONNECT'S OWN MINIMUM, SENT BY US")
    print("=" * 76)
    print("  vendor minimum : %r" % VENDOR_MINIMUM.decode().strip())
    print("  our dark frame : %r" % MUSLIMSIM_DARK.decode().strip())
    print("                          ^ ^                    P2 and P3")
    print("")

    try:
        ser = bridge.serial.Serial(
            port=a.port, baudrate=a.baud,
            bytesize=bridge.serial.EIGHTBITS,
            parity=bridge.serial.PARITY_NONE,
            stopbits=bridge.serial.STOPBITS_ONE,
            timeout=0, write_timeout=None,
            xonxoff=False, rtscts=False, dsrdtr=False,
        )
    except Exception as exc:
        print("  Could not open %s: %s" % (a.port, exc), file=sys.stderr)
        return 1

    def drive(packet, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            ser.write(packet)
            time.sleep(0.05)

    try:
        bridge._pu_force_serial_line_state(
            ser, bridge.PU_SERIAL_LINE_VALUE_STATE
        )
        look(bridge.PU_SERIAL_CONTROLLER_RESET_SECONDS + 0.5,
             "controller resetting after open")

        print("  1. vendor's FULL brightness, 3 s")
        drive(VENDOR_LIT, 3.0)
        print("     >>> the panel should be brightly lit")
        look(2.0, "look: bright?")

        print("  2. vendor's MINIMUM, streamed 3 s, then we STOP SENDING")
        drive(VENDOR_MINIMUM, 3.0)
        print("     >>> LOOK. Dark now? And does it STAY dark?")
        print("     (nothing is being sent from here on - port still open)")
        look(a.look, "vendor minimum, stream stopped")

        print("  3. our own dark frame, same treatment, for comparison")
        drive(VENDOR_LIT, 2.0)
        drive(MUSLIMSIM_DARK, 3.0)
        print("     >>> LOOK. Same, better or worse than step 2?")
        look(a.look, "MuslimSim dark frame, stream stopped")

        print("  4. vendor minimum once more, then the port closes")
        drive(VENDOR_MINIMUM, 3.0)
    finally:
        try:
            ser.close()
        except Exception:
            pass

    print("     >>> port CLOSED. Does it stay dark now?")
    look(a.look, "port closed after vendor minimum")

    print("")
    print("=" * 76)
    print("  Step 2 dark and it STAYED dark")
    print("     -> P2=1,P3=1 is the missing piece. Our dark frame leaves two")
    print("        brightness channels at 4, and that is why it never held.")
    print("")
    print("  Step 2 dark but it came back, same as step 3")
    print("     -> the vendor frame is no better than ours; the panel simply")
    print("        does not hold any state, and this cannot be fixed by us.")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
