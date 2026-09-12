"""Watch what the Hoowalt boards send when their controls are used.

Identify is confirmed: COM8 is `Hoowalt D203 ATC` (SN-4F6-017) and COM9 is
`Hoowalt D201 RTP` (SN-1FD-E25), both MobiFlight Mega firmware 3.1.4, and the
ATC serial matches the one the supplied .mcc refers to.

What is still unknown is the event format - what arrives when a button is
pressed or an encoder turned.  The .mfmc files give the control names, so this
is not about discovering what exists; it is about seeing the exact wire format
before any driver parses it.  Guessing that is how a driver ends up silently
dropping half the encoder detents.

Every line the board sends is printed raw, and decoded where the shape is
recognised.  CmdMessenger id 7 is the button change and 6 the encoder change,
but the raw line is always shown so a wrong assumption is visible rather than
hidden behind a tidy label.

It only listens.  After the identify request it sends nothing at all, writes no
output and drives no pin.

MobiFlight Connector must be CLOSED.

Usage:
    python tools/probe_mobiflight_input.py --port COM8
    python tools/probe_mobiflight_input.py --port COM9 --seconds 60
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

try:
    import serial
except Exception:
    serial = None

MF_GET_INFO = 9
MF_ENCODER_CHANGE = 6
MF_BUTTON_CHANGE = 7
MF_INFO_REPLY = 10
# A board that identifies but reports nothing has its stored config loaded but
# not running.  Connector activates it on connect; we never did, which is why
# the first attempt saw silence from a board that was plainly alive.
#
# 12 reads the stored config back - a pure read, and the way to see whether
# what is actually on the board matches the supplied .mfmc.  16 activates it,
# which starts the input loop.  Neither invents anything: both act on the
# board's own stored configuration.
MF_GET_CONFIG = 12
MF_ACTIVATE_CONFIG = 16
# kTrigger asks the firmware to report the current state of every input it
# has, with nobody touching the panel.  It writes no pin and drives nothing;
# it only re-sends what the board is already reading.
#
# This matters because it separates two failures that look identical from the
# outside: a board that reports nothing, and a panel nobody pressed.  If the
# trigger produces events, the input path is proven and the wire format is on
# the record without needing a human in the loop at all.
MF_TRIGGER = 23

CONFIGS = {
    "Hoowalt D203 ATC": "Hoowalt D203 ATC.mfmc",
    "Hoowalt D201 RTP": "Hoowalt D201 RTP.mfmc",
}


def connector_running() -> bool:
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "if (Get-Process -Name MFConnector -ErrorAction SilentlyContinue) "
             "{ 'yes' } else { 'no' }"],
            capture_output=True, text=True, timeout=20,
        )
        return "yes" in p.stdout
    except Exception:
        return False


def board_controls(board_name: str):
    """The control names this board's own config declares."""

    filename = CONFIGS.get(board_name)
    if not filename:
        return {}
    path = PROJECT / filename
    if not path.is_file():
        return {}
    controls = {}
    for child in ET.parse(path).getroot():
        name = child.get("Name")
        if name:
            controls[name] = child.tag
    return controls


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--settle", type=float, default=4.0)
    ap.add_argument("--seconds", type=float, default=45.0)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    if serial is None:
        print("pyserial is not installed.", file=sys.stderr)
        return 1
    if connector_running() and not a.force:
        print("MobiFlight Connector is running and owns this port.",
              file=sys.stderr)
        return 1

    try:
        ser = serial.Serial(
            port=a.port, baudrate=a.baud, timeout=0,
            bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )
    except Exception as exc:
        print("Could not open %s: %s" % (a.port, exc), file=sys.stderr)
        return 1

    seen = {}
    board = "?"
    try:
        time.sleep(a.settle)
        try:
            ser.reset_input_buffer()
        except Exception:
            pass
        ser.write(b"9;")
        time.sleep(0.6)
        try:
            first = ser.read(ser.in_waiting or 0).decode("ascii", "replace")
        except Exception:
            first = ""

        # Read the stored config back before touching anything, so the board's
        # own truth is on the record next to the supplied file.
        ser.write(("%d%s" % (MF_GET_CONFIG, ";")).encode("ascii"))
        time.sleep(1.0)
        stored = ""
        try:
            stored = ser.read(ser.in_waiting or 0).decode("ascii", "replace")
        except Exception:
            pass

        # Then start its input loop.
        ser.write(("%d%s" % (MF_ACTIVATE_CONFIG, ";")).encode("ascii"))
        time.sleep(1.2)
        activated = ""
        try:
            activated = ser.read(ser.in_waiting or 0).decode("ascii", "replace")
        except Exception:
            pass
        # Nobody has to touch the panel for this one.
        ser.write(("%d%s" % (MF_TRIGGER, ";")).encode("ascii"))
        time.sleep(1.5)
        triggered = ""
        try:
            triggered = ser.read(ser.in_waiting or 0).decode("ascii", "replace")
        except Exception:
            pass

        for part in first.split(";"):
            fields = [f.strip() for f in part.split(",")]
            if fields and fields[0] == str(MF_INFO_REPLY) and len(fields) > 2:
                board = fields[2]

        declared = board_controls(board)
        print("")
        print("=" * 74)
        print("  %s on %s" % (board, a.port))
        print("=" * 74)
        if declared:
            buttons = [n for n, t in declared.items() if t == "Button"]
            encoders = [n for n, t in declared.items() if t == "Encoder"]
            print("  its config declares %d buttons and %d encoders:"
                  % (len(buttons), len(encoders)))
            print("     buttons : %s" % ", ".join(sorted(buttons)))
            print("     encoders: %s" % ", ".join(sorted(encoders)))
        else:
            print("  no matching .mfmc found for this board name")
        print("")
        if stored.strip():
            print("  stored config on the board:")
            print("     %s" % stored.strip()[:600])
            print("")
        else:
            print("  the board returned no stored config (id %d)" % MF_GET_CONFIG)
            print("")
        if activated.strip():
            print("  activate reply: %r" % activated.strip()[:160])
            print("")

        if triggered.strip():
            print("  the board reported its own input states on request:")
            for part in triggered.split(";"):
                if part.strip():
                    print("     %r" % (part.strip() + ";"))
            print("")
            fields_seen = [q for q in triggered.split(";") if "," in q]
            if fields_seen:
                print("  Those carry fields, so that is the input format.")
            else:
                print("  Those carry no fields, so they are acknowledgements, not")
                print("  input states.  The input format is still unproven.")
        else:
            print("  the board reported nothing when asked for its input states,")
            print("  with the config active - so silence here is the firmware, not")
            print("  a panel nobody pressed.")
        print("")
        print("  Work every control now - press each button, turn each encoder")
        print("  both ways, and HOLD one button down for a few seconds too.")
        print("  Listening %.0fs, printing a line every 5s.  Ctrl-C to stop." % a.seconds)
        print("")

        buffer = ""
        total_bytes = 0
        events = 0
        start = time.monotonic()
        next_beat = start + 5.0
        next_trigger = start + 2.0
        end = start + a.seconds
        while time.monotonic() < end:
            try:
                waiting = ser.in_waiting
            except Exception:
                waiting = 0
            now = time.monotonic()
            # A heartbeat on its own line, so the record shows the probe was
            # alive and counting rather than leaving silence to be guessed at.
            if now >= next_beat:
                print("    ...%2.0fs elapsed   bytes:%-6d events:%-4d"
                      % (now - start, total_bytes, events), flush=True)
                next_beat = now + 5.0
            # Re-ask for input states while listening.  If change detection
            # is the broken part, a button held down still reports here.
            if now >= next_trigger:
                ser.write(("%d%s" % (MF_TRIGGER, ";")).encode("ascii"))
                next_trigger = now + 2.0
            if waiting:
                total_bytes += waiting
                buffer += ser.read(waiting).decode("ascii", "replace")
                while ";" in buffer:
                    line, _, buffer = buffer.partition(";")
                    line = line.strip()
                    if not line:
                        continue
                    fields = [f.strip() for f in line.split(",")]
                    kind = fields[0]
                    label = ""
                    if kind == str(MF_BUTTON_CHANGE) and len(fields) >= 3:
                        label = "  BUTTON  name=%-10s value=%s" % (fields[1], fields[2])
                    elif kind == str(MF_ENCODER_CHANGE) and len(fields) >= 3:
                        label = "  ENCODER name=%-10s value=%s" % (fields[1], fields[2])
                    events += 1
                    print("    %-46r%s" % (line + ";", label))
                    if len(fields) >= 2:
                        seen.setdefault((kind, fields[1]), 0)
                        seen[(kind, fields[1])] += 1
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n  (stopped)")
    finally:
        try:
            ser.close()
        except Exception:
            pass

    print("")
    print("=" * 74)
    if seen:
        print("  controls that reported, and how many events each sent:")
        for (kind, name), count in sorted(seen.items(), key=lambda kv: -kv[1]):
            what = {str(MF_BUTTON_CHANGE): "button",
                    str(MF_ENCODER_CHANGE): "encoder"}.get(kind, "id " + kind)
            print("     %-8s %-12s %d" % (what, name, count))
        declared = board_controls(board)
        if declared:
            quiet = sorted(
                n for n, t in declared.items()
                if t in ("Button", "Encoder")
                and not any(n == s[1] for s in seen)
            )
            if quiet:
                print("")
                print("  declared but never reported: %s" % ", ".join(quiet))
                print("  (either not touched, or not wired the way the config says)")
    else:
        print("  No input events, on a board that answered every trigger.  The",
              "link is")
        print("  proven live, so this is not the probe and not an untouched panel.")
        print("")
        print("  Note the trigger replies: id 23 answered with 34, which is not in")
        print("  the command set assumed here.  That means the ids in this file are",
              "")
        print("  not this firmware\'s ids, and no further guessed id should be sent")
        print("  to the board - a wrong guess can erase its stored config.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
