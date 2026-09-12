"""Find out why the PU dark frame does not darken the panel.

The relight test settled one thing and broke another: the PU stays lit even
with the port wide open and the captured dark frame written.  So this was never
about shutdown sequencing.  The frame itself is not doing what it is meant to.

The dark frame is built by `_pu_safe_dark_packet` and sent three times by
`_pu_write_safe_dark_frame`:

    OVHD,0,4,4,0,<5 spaces>,<5 spaces>,0,0

Three things about it could each explain a panel that stays lit, and they need
different fixes, so this tries them one at a time and lets you watch:

  A. the write never happens - `_pu_write_safe_dark_frame` returns False when
     the port looks closed, and nothing checks its return value
  B. the controller rejects the frame because the two altitude fields are
     blank rather than numeric, and discards the whole line
  C. three frames is not enough, and the panel needs the normal cadence to
     accept a change

Between each variant the panel is driven lit again, so every step starts from
the same visible place and you can tell which one actually worked.

It writes only frames the bridge itself builds, and nothing to the simulator.
Studio and the bridge must be CLOSED; they own COM5.

Usage:
    python tools/probe_pu_dark_frame.py
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
    ap.add_argument("--look", type=float, default=7.0)
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
        "_pudark", PROJECT / "bridge" / "final.py"
    )
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    if bridge.serial is None:
        print("pyserial is not installed.", file=sys.stderr)
        return 1

    args = _Args()

    def frame(mask, brightness, alts, egt=0.0, p1=0):
        return bridge.build_packet(
            p1=p1, apu_temp=egt,
            land_alt=alts, flt_alt=alts,
            light_mask=mask,
            egt_scale=args.egt_scale, egt_offset=args.egt_offset,
            egt_zero_threshold=args.egt_zero_threshold,
            egt_zero_raw=args.egt_zero_raw,
            egt_mid_temp=args.egt_mid_temp, egt_mid_raw=args.egt_mid_raw,
            egt_peak_temp=args.egt_peak_temp, egt_peak_raw=args.egt_peak_raw,
            brightness_raw=brightness,
        ).encode("ascii")

    lit = frame(0xFFFFFFFF, args.egt_peak_raw, 10000.0, egt=320.0)
    dark_blank = bridge._pu_safe_dark_packet(args).encode("ascii")
    dark_numeric = frame(0, 0, 0.0)

    print("")
    print("=" * 76)
    print("  WHY DOES THE PU DARK FRAME NOT DARKEN THE PANEL?")
    print("=" * 76)
    print("  captured dark frame : %r" % dark_blank.decode().rstrip())
    print("  numeric variant     : %r" % dark_numeric.decode().rstrip())
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
            time.sleep(args.interval)

    try:
        bridge._pu_force_serial_line_state(
            ser, bridge.PU_SERIAL_LINE_VALUE_STATE
        )
        look(bridge.PU_SERIAL_CONTROLLER_RESET_SECONDS + 0.5,
             "controller resetting after open")

        print("  is the port actually open? ser.is_open = %s" % ser.is_open)
        print("")

        # ---- A: exactly what shutdown does, with the return value shown ----
        drive(lit, 2.5)
        print("  A. the real shutdown path: _pu_write_safe_dark_frame()")
        sent = bridge._pu_write_safe_dark_frame(ser, args)
        print("     returned %s  <- False means it never wrote anything" % sent)
        print("     >>> LOOK. Did the panel go dark?")
        look(a.look, "A: captured dark frame, 3 writes")

        # ---- B: same values, numeric altitudes instead of blanks ----
        drive(lit, 2.5)
        print("  B. same mask and brightness, but numeric altitude fields")
        for _ in range(3):
            ser.write(dark_numeric)
            time.sleep(args.interval)
        print("     >>> LOOK. Did the panel go dark this time?")
        look(a.look, "B: numeric altitudes")

        # ---- C: the captured frame, but streamed at normal cadence ----
        drive(lit, 2.5)
        print("  C. the captured dark frame, streamed for 2 s at cadence")
        drive(dark_blank, 2.0)
        print("     >>> LOOK. Did the panel go dark this time?")
        look(a.look, "C: captured frame at cadence")

        # Leave it in whichever dark form we can.
        drive(dark_numeric, 1.0)
    finally:
        try:
            ser.close()
        except Exception:
            pass

    print("")
    print("=" * 76)
    print("  A worked  -> the frame is fine; the shutdown ordering is the bug.")
    print("  B worked  -> the controller rejects blank altitude fields. The")
    print("               dark frame must send numeric altitudes.")
    print("  C worked  -> three writes are not enough; it needs the cadence.")
    print("  none      -> the lamps are not driven by P7 mask + P8 the way the")
    print("               dark frame assumes, and that needs a fresh capture.")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
