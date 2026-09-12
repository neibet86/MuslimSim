"""Listen to the Hoowalt boards without sending them anything at all.

A USB capture of the D203 ATC panel (d203atc.pcapng, 54s, device 1.61) settled
what the boards actually do:

    7,XPNDR,1;      button   - 0 released, 1 pressed
    6,BMQ2-1,2;     encoder  - 0 left, 1 left fast, 2 right, 3 right fast

every message terminated with `;` then CRLF.  All 9 buttons and all 4 encoders
of the ATC config reported.

The part that matters is what the capture does NOT contain: in 54 seconds there
is not one byte from host to board.  Only enumeration, then the board streams on
its own.  MobiFlight firmware activates its stored config during setup(), so a
powered board is already reporting before anything asks it to.

That makes every command the earlier probe sent unnecessary, and one of them is
the likely reason it saw silence.  Those ids were guesses: 23 came back as 34,
which is not in the command set they were taken from, so the mapping cannot be
trusted and a wrong id can erase a board's stored config.  This tool therefore
writes nothing.  It opens the port, reads, and prints.

It listens on several ports at once, so which panel is on which port is answered
by working the controls rather than assumed from a name in EEPROM.

MobiFlight Connector must be CLOSED - it owns these ports when running.

Usage:
    python tools/probe_mobiflight_listen.py
    python tools/probe_mobiflight_listen.py --ports COM8 --seconds 90
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except Exception:
    serial = None
    list_ports = None

# Confirmed from the capture, not from a header file.
MF_ENCODER_CHANGE = "6"
MF_BUTTON_CHANGE = "7"

BUTTON_STATE = {"0": "released", "1": "pressed"}
ENCODER_DIR = {"0": "left", "1": "left fast", "2": "right", "3": "right fast"}


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


def ch340_ports():
    found = []
    if list_ports is None:
        return found
    for port in list_ports.comports():
        text = " ".join(str(x) for x in (port.description, port.hwid))
        if "1A86" in text.upper() or "CH340" in text.upper():
            found.append(port.device)
    return found


def describe(fields):
    """Decode one message, using only what the capture established."""

    if len(fields) < 3:
        return ""
    kind, name, value = fields[0], fields[1], fields[2]
    if kind == MF_BUTTON_CHANGE:
        return "  BUTTON   %-10s %s" % (name, BUTTON_STATE.get(value, value))
    if kind == MF_ENCODER_CHANGE:
        return "  ENCODER  %-10s %s" % (name, ENCODER_DIR.get(value, value))
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ports", default="", help="comma separated; default every CH340")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--settle", type=float, default=3.0)
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--wake", action="store_true",
                    help="send 18,0; once - power saving off, which the capture "
                         "shows is what makes a board report its inputs")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    if serial is None:
        print("pyserial is not installed.", file=sys.stderr)
        return 1
    if connector_running() and not a.force:
        print("MobiFlight Connector is running and owns these ports.", file=sys.stderr)
        return 1

    ports = [p.strip() for p in a.ports.split(",") if p.strip()] or ch340_ports()
    if not ports:
        print("No CH340 serial ports found.", file=sys.stderr)
        return 1

    open_ports = {}
    for name in ports:
        try:
            open_ports[name] = serial.Serial(port=name, baudrate=a.baud, timeout=0)
        except Exception as exc:
            print("  %-6s could not open: %s" % (name, exc))
    if not open_ports:
        return 1

    print("")
    print("=" * 74)
    print("  %s" % ("LISTEN, AFTER TURNING POWER SAVING OFF" if a.wake
                    else "LISTENING ONLY - nothing is sent to any board"))
    print("=" * 74)
    print("  ports: %s" % ", ".join(sorted(open_ports)))
    print("  Opening a port resets the board; waiting %.0fs for it to boot." % a.settle)
    print("")

    buffers = {name: "" for name in open_ports}
    counts = {name: 0 for name in open_ports}
    stray = {}
    seen = {}
    time.sleep(a.settle)

    # Taken verbatim from D201RTP.pcapng, not from a guessed enum.  In that
    # capture `18,1` was sent 39 times and not one input event followed any of
    # them; `18,0` was sent once and every input event in the file follows it.
    # So id 18 is the power saving mode and a board saving power reports
    # nothing.  This is the only byte this tool ever writes.
    if a.wake:
        for name, ser in open_ports.items():
            try:
                ser.write(b"18,0;")
            except Exception as exc:
                print("  %-6s could not wake: %s" % (name, exc))
        print("  sent 18,0; (power saving off) to each port")
        print("")

    print("  Work the controls now - press buttons, turn encoders both ways.")
    print("  Listening %.0fs, a line every 5s.  Ctrl-C to stop." % a.seconds)
    print("")

    start = time.monotonic()
    next_beat = start + 5.0
    end = start + a.seconds
    try:
        while time.monotonic() < end:
            now = time.monotonic()
            if now >= next_beat:
                print("    ...%2.0fs   %s" % (
                    now - start,
                    "  ".join("%s:%d" % (p, counts[p]) for p in sorted(counts))))
                next_beat = now + 5.0
            for name, ser in open_ports.items():
                try:
                    waiting = ser.in_waiting
                except Exception:
                    continue
                if not waiting:
                    continue
                counts[name] += waiting
                buffers[name] += ser.read(waiting).decode("ascii", "replace")
                while ";" in buffers[name]:
                    line, _, buffers[name] = buffers[name].partition(";")
                    line = line.strip()
                    if not line:
                        continue
                    fields = [f.strip() for f in line.split(",")]
                    print("    %-6s %-28r%s" % (name, line + ";", describe(fields)))
                    if len(fields) >= 2:
                        key = (name, fields[0], fields[1])
                        seen[key] = seen.get(key, 0) + 1
                # Anything left unterminated is still evidence.  A port that
                # speaks a different protocol shows up here, not as silence.
                if len(buffers[name]) >= 40 or (buffers[name] and waiting == 0):
                    stray[name] = stray.get(name, "") + buffers[name]
                    buffers[name] = ""
            time.sleep(0.005)
    except KeyboardInterrupt:
        print("\n  (stopped)")
    finally:
        for ser in open_ports.values():
            try:
                ser.close()
            except Exception:
                pass

    for name in sorted(open_ports):
        text = stray.get(name, "") + buffers.get(name, "")
        if not text.strip():
            continue
        print("")
        print("  %s sent %d bytes that never formed a terminated message:"
              % (name, len(text)))
        printable = "".join(c if 32 <= ord(c) < 127 or c in "\r\n" else "."
                            for c in text)
        for chunk in printable.splitlines():
            if chunk.strip():
                print("     %s" % chunk[:120])
        print("     hex: %s" % text.encode("ascii", "replace")[:60].hex())

    print("")
    print("=" * 74)
    if seen:
        print("  what reported, and on which port:")
        for (port, kind, name), count in sorted(seen.items(), key=lambda kv: -kv[1]):
            what = {MF_BUTTON_CHANGE: "button", MF_ENCODER_CHANGE: "encoder"}.get(
                kind, "id " + kind)
            print("     %-6s %-8s %-12s %d" % (port, what, name, count))
        print("")
        print("  That is the panel wiring confirmed from the hardware, and the")
        print("  format a driver parses.")
    else:
        print("  Nothing arrived on any port, with nothing sent to provoke it.")
        print("  The capture shows a powered board streaming unprompted, so a board")
        print("  silent here is either not the one wired to the panel, or was left")
        print("  in a state that stopped its reporting - which a power cycle clears.")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
