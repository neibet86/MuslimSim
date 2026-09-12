#!/usr/bin/env python3
"""
Drive the PU overhead panel directly over its USB CDC virtual COM port.

Protocol (reverse-engineered from captures/PU_EGT_ZERO.pcapng and friends):
the sim streams one 32-byte ASCII line at ~3.2 Hz to bulk endpoint 0x02 of
USB device 3561:8561 (composite HID + CDC ACM):

    OVHD,<f1>,<f2>,<f3>,<bl>,<disp1>,<disp2>,<leds>,<br>\n
    OVHD,0,4,4,170,     ,     ,0,62          <- PU_EGT_ZERO baseline

  f1     0 or 1        panel/page selector
  f2,f3  4, 4          constant in every capture seen
  bl     0..170        swept in PU_BRIGHT  -> backlight
  disp1  5 chars       right-aligned; "    0", "  600", "-----", blank
  disp2  5 chars       right-aligned; "10000", "23000", "99999", blank
  leds   uint32        annunciator bitmask (0xF0100000, 0x1000, ...)
  br     0..125        swept in PU_BRIGHT  -> display brightness

There is no checksum: identical prefixes appear with different trailing
values, so any field can be set independently.
"""

import argparse
import sys
import time

import serial
from serial.tools import list_ports

VID, PID = 0x3561, 0x8561
BAUD = 115200
PERIOD = 0.31          # capture shows a frame every ~0.309 s

# Baseline captured in PU_EGT_ZERO.pcapng
BASE = dict(f1="0", f2="4", f3="4", bl="170", disp1="     ", disp2="     ",
            leds="0", br="62")

FIELDS = ["f1", "f2", "f3", "bl", "disp1", "disp2", "leds", "br"]


def find_port(explicit=None):
    if explicit:
        return explicit
    for p in list_ports.comports():
        if p.vid == VID and p.pid == PID:
            return p.device
    raise SystemExit(
        f"No COM port with VID:PID {VID:04x}:{PID:04x} found.\n"
        "Plug the panel in, or pass --port COMx. Use --list to see ports."
    )


def disp(v):
    """5-char right-aligned display field, as the sim formats it."""
    if v is None:
        return "     "
    s = str(v)
    return s[-5:] if len(s) > 5 else s.rjust(5)


def build(**over):
    f = dict(BASE)
    for k, v in over.items():
        if v is None:
            continue
        f[k] = disp(v) if k in ("disp1", "disp2") else str(v)
    return "OVHD," + ",".join(f[k] for k in FIELDS) + "\n"


def stream(ser, line, seconds, once):
    data = line.encode("ascii")
    sys.stdout.write(repr(line) + "\n")
    sys.stdout.flush()
    if once:
        ser.write(data)
        ser.flush()
        return
    end = time.time() + seconds if seconds else None
    try:
        while end is None or time.time() < end:
            ser.write(data)
            ser.flush()
            time.sleep(PERIOD)
    except KeyboardInterrupt:
        pass


def main():
    ap = argparse.ArgumentParser(description="Move the PU overhead EGT / displays directly.")
    ap.add_argument("--list", action="store_true", help="list serial ports and exit")
    ap.add_argument("--port", help="COM port (default: auto-detect 3561:8561)")
    ap.add_argument("--egt", help="value for the EGT display (alias for --disp1)")
    ap.add_argument("--disp1", help="left 5-char display")
    ap.add_argument("--disp2", help="right 5-char display")
    ap.add_argument("--bl", help="backlight 0..170")
    ap.add_argument("--br", help="display brightness 0..125")
    ap.add_argument("--leds", help="annunciator bitmask, e.g. 0 or 4027195264")
    ap.add_argument("--f1", help="panel/page selector (0 or 1)")
    ap.add_argument("--raw", help="send this exact line instead of building one")
    ap.add_argument("--no-dtr", action="store_true",
                    help="leave DTR/RTS deasserted (try if writes time out)")
    ap.add_argument("--once", action="store_true", help="send a single frame instead of holding")
    ap.add_argument("--hold", type=float, default=0,
                    help="seconds to keep streaming (0 = until Ctrl+C)")
    ap.add_argument("--sweep", choices=["bl", "br", "disp1", "disp2", "leds"],
                    help="step this field through a range so you can see which gauge moves")
    ap.add_argument("--range", default="0:200:10", help="start:stop:step for --sweep")
    args = ap.parse_args()

    if args.list:
        for p in list_ports.comports():
            tag = "  <-- panel" if (p.vid, p.pid) == (VID, PID) else ""
            print(f"{p.device:<8} {p.vid:04x}:{p.pid:04x} {p.description}{tag}"
                  if p.vid else f"{p.device:<8} {p.description}")
        return

    port = find_port(args.port)
    with serial.Serial(port, BAUD, timeout=0.2, write_timeout=2.0) as ser:
        ser.dtr = not args.no_dtr
        ser.rts = not args.no_dtr
        time.sleep(0.2)
        print(f"# {port} @ {BAUD}  dtr={ser.dtr} rts={ser.rts}", flush=True)

        if args.sweep:
            a, b, step = (int(x) for x in args.range.split(":"))
            for v in range(a, b + 1, step):
                line = build(**{args.sweep: v})
                print(f"{args.sweep}={v:<6} {line!r}")
                for _ in range(4):           # ~1.2 s per step
                    ser.write(line.encode("ascii"))
                    ser.flush()
                    time.sleep(PERIOD)
            return

        if args.raw:
            line = args.raw if args.raw.endswith(chr(10)) else args.raw + chr(10)
        else:
            line = build(f1=args.f1, bl=args.bl, br=args.br, leds=args.leds,
                         disp1=args.egt if args.egt is not None else args.disp1,
                         disp2=args.disp2)
        stream(ser, line, args.hold, args.once)


if __name__ == "__main__":
    main()
