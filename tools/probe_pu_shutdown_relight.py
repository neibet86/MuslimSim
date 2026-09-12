"""Find out whether the PU overhead relights when its COM port closes.

The throttle and the PAP3 now go dark when Studio closes.  The PU still lights
up, and it is the one device on this rig that is driven over a serial CDC port
rather than USB HID - so the HID relight test says nothing about it.

The bridge's own comment at the serial open is the reason to suspect the port
itself:

    Opening the CDC interface resets this controller.

A controller that reboots when the port opens may well reboot when it closes
and the control lines drop, and it would come back in whatever state its
firmware starts in.  If that is what happens, the dark frame MuslimSim sends on
the way out is correct, arrives, and is then thrown away by a reset a moment
later - and no amount of better shutdown code can help.

Same shape as the HID test, so the two are comparable:

  1. open COM5 and send a LIT frame     -> the panel should light
  2. send the captured dark frame, port STILL OPEN
                                         -> look. Dark here means it works.
  3. close the port
  4. wait                                -> look again. Lit here means the
                                            close did it, not us.

It writes only frames the bridge already builds, and nothing to the simulator.
MuslimSim Studio and the bridge must be CLOSED; they own COM5.

Usage:
    python tools/probe_pu_shutdown_relight.py
    python tools/probe_pu_shutdown_relight.py --port COM5 --hold 10 --after 10
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


class _Args:
    """The few fields the captured packet builders read."""

    egt_scale = 1.0
    egt_offset = 0.0
    egt_zero_threshold = 0.0
    egt_zero_raw = 0
    egt_mid_temp = 300.0
    egt_mid_raw = 128
    egt_peak_temp = 700.0
    egt_peak_raw = 255
    interval = 0.05


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
    while time.monotonic() < end:
        print("\r    %4.1fs  %s" % (end - time.monotonic(), label),
              end="", flush=True)
        time.sleep(0.1)
    print("\r" + " " * 72 + "\r", end="")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM5")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--hold", type=float, default=10.0)
    ap.add_argument("--after", type=float, default=10.0)
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
        "_purelight", PROJECT / "bridge" / "final.py"
    )
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)

    if bridge.serial is None:
        print("pyserial is not installed.", file=sys.stderr)
        return 1

    args = _Args()
    lit = bridge.build_packet(
        p1=0,
        apu_temp=320.0,
        land_alt=1000.0,
        flt_alt=10000.0,
        light_mask=0xFFFFFFFF,
        egt_scale=args.egt_scale,
        egt_offset=args.egt_offset,
        egt_zero_threshold=args.egt_zero_threshold,
        egt_zero_raw=args.egt_zero_raw,
        egt_mid_temp=args.egt_mid_temp,
        egt_mid_raw=args.egt_mid_raw,
        egt_peak_temp=args.egt_peak_temp,
        egt_peak_raw=args.egt_peak_raw,
        brightness_raw=args.egt_peak_raw,
    ).encode("ascii")

    print("")
    print("=" * 72)
    print("  DOES THE PU RELIGHT WHEN THE COM PORT CLOSES?")
    print("=" * 72)

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

    try:
        # The controller resets when this interface opens, so give its firmware
        # time to boot before anything is judged by what the panel shows.
        bridge._pu_force_serial_line_state(
            ser, bridge.PU_SERIAL_LINE_VALUE_STATE
        )
        countdown(bridge.PU_SERIAL_CONTROLLER_RESET_SECONDS + 0.5,
                  "controller resetting after open")

        print("  1. sending a LIT frame at cadence")
        end = time.monotonic() + 3.0
        while time.monotonic() < end:
            ser.write(lit)
            time.sleep(args.interval)
        print("     >>> the panel should be LIT now")
        countdown(2.0, "look: lit?")

        print("  2. sending the captured dark frame, port STILL OPEN")
        bridge._pu_write_safe_dark_frame(ser, args)
        print("     >>> LOOK NOW. Is it dark?")
        countdown(a.hold, "port still open - is it dark?")
    finally:
        try:
            ser.close()
        except Exception:
            pass

    print("  3. port CLOSED. MuslimSim is writing nothing at all.")
    print("     >>> LOOK AGAIN. Did it light back up?")
    countdown(a.after, "port closed - did it relight?")

    print("")
    print("=" * 72)
    print("  Dark in 2, still dark in 3")
    print("     -> the port close is innocent and the shutdown fault is ours.")
    print("")
    print("  Dark in 2, LIT in 3")
    print("     -> closing the port resets the controller and it boots lit.")
    print("        The dark frame is correct, arrives, and is then discarded.")
    print("        No shutdown code can fix that; it needs a different answer.")
    print("")
    print("  LIT in 2")
    print("     -> the dark frame is not taking effect even with the port open.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
