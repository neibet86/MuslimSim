"""Identify the Hoowalt MobiFlight boards on their serial ports.

Three CH340 boards are connected (COM7, COM8, COM9) and two board configs have
been supplied - `Hoowalt D201 RTP.mfmc` and `Hoowalt D203 ATC.mfmc`.  Nothing in
MuslimSim has ever spoken to them, so before any driver is written the first
question is simply which port is which panel, and whether they answer at all.

These run MobiFlight firmware, which speaks CmdMessenger: plain ASCII commands
terminated by `;`, fields separated by `,`.  `10;` is its identify request and
the board answers with its type, name and serial - the same serial the .mcc
refers to as `Hoowalt D203 ATC/ SN-4F6-017`.  That is the claim this tool
tests rather than assumes: if the answer matches the supplied configs, the
protocol is confirmed from the hardware and a driver can be built on it.  If it
does not, nothing has been guessed and we look again.

This only asks.  It sends the identify request and reads the reply; it writes
no output, drives no pin, and changes no board configuration.

MobiFlight Connector must be CLOSED - it owns these ports when running, and two
owners on one port is the thing this project refuses.

Usage:
    python tools/probe_mobiflight_boards.py
    python tools/probe_mobiflight_boards.py --ports COM7,COM8,COM9
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

try:
    import serial
    from serial.tools import list_ports
except Exception:
    serial = None
    list_ports = None

# CmdMessenger ids used by the MobiFlight firmware.  Only the identify pair is
# used here; nothing that sets a pin or writes a config is sent.
#
# 9 is the request and 10 is the reply, which is worth stating because getting
# it backwards is exactly what happened first: sending 10 made the boards
# answer `5,n/a;` - kStatus, unknown command.  That reply was still useful, as
# it proved these are CmdMessenger boards at this baud, parsing our input.
MF_GET_INFO = 9
MF_INFO_REPLY = 10
MF_STATUS = 5
MF_TERMINATOR = ";"


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
    """Serial ports that look like the Hoowalt boards."""

    found = []
    if list_ports is None:
        return found
    for port in list_ports.comports():
        text = " ".join(str(x) for x in (port.description, port.hwid))
        if "1A86" in text.upper() or "CH340" in text.upper():
            found.append(port.device)
    return found


def identify(port: str, baud: int, settle: float, listen: float):
    """Ask one board who it is, and return whatever it says."""

    try:
        ser = serial.Serial(
            port=port, baudrate=baud, timeout=0,
            bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )
    except Exception as exc:
        return {"port": port, "error": str(exc)}

    try:
        # Opening a CH340 resets the Arduino.  Let the sketch boot before it is
        # asked anything, or the request lands in a firmware that is not
        # listening yet and the port looks dead.
        time.sleep(settle)
        try:
            ser.reset_input_buffer()
        except Exception:
            pass

        ser.write(("%d%s" % (MF_GET_INFO, MF_TERMINATOR)).encode("ascii"))

        end = time.monotonic() + listen
        chunks = []
        while time.monotonic() < end:
            waiting = 0
            try:
                waiting = ser.in_waiting
            except Exception:
                pass
            if waiting:
                chunks.append(ser.read(waiting))
                # A complete CmdMessenger reply ends with the terminator.
                if MF_TERMINATOR.encode() in b"".join(chunks):
                    time.sleep(0.05)
                    try:
                        if ser.in_waiting:
                            chunks.append(ser.read(ser.in_waiting))
                    except Exception:
                        pass
                    break
            time.sleep(0.02)

        raw = b"".join(chunks)
        return {
            "port": port,
            "raw": raw.decode("ascii", "replace").strip(),
            "bytes": len(raw),
        }
    finally:
        try:
            ser.close()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ports", default="",
                    help="comma separated, e.g. COM7,COM8,COM9. "
                         "Default: every CH340 port found.")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--settle", type=float, default=4.0,
                    help="seconds to let the board reboot after the port opens. "
                         "A board that stays silent may simply need longer.")
    ap.add_argument("--listen", type=float, default=3.0)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    if serial is None:
        print("pyserial is not installed.", file=sys.stderr)
        return 1

    if connector_running() and not a.force:
        print("MobiFlight Connector is running and owns these ports.",
              file=sys.stderr)
        print("Close it first; two owners on one port is not allowed here.",
              file=sys.stderr)
        return 1

    ports = [p.strip() for p in a.ports.split(",") if p.strip()] or ch340_ports()
    if not ports:
        print("No CH340 serial ports found.", file=sys.stderr)
        return 1

    print("")
    print("=" * 72)
    print("  HOOWALT MOBIFLIGHT BOARD IDENTIFY")
    print("=" * 72)
    print("  asking %s" % ", ".join(ports))
    print("  request: %d%s   (identify only - nothing is written to any pin)"
          % (MF_GET_INFO, MF_TERMINATOR))
    print("")

    answered = 0
    for port in ports:
        print("  %s" % port)
        result = identify(port, a.baud, a.settle, a.listen)
        if result.get("error"):
            print("     could not open: %s" % result["error"])
            continue
        raw = result["raw"]
        if not raw:
            print("     no reply in %.1fs (%d bytes)" % (a.listen, result["bytes"]))
            continue
        answered += 1
        print("     replied: %r" % raw)
        head = raw.split(",")[0].strip()
        if head == str(MF_STATUS):
            print("     -> kStatus: the firmware did not accept that request id.")
        elif head == str(MF_INFO_REPLY):
            print("     -> kInfo: this is the identify reply.")
        # A MobiFlight identify reply is comma separated; the board name and
        # serial are the parts worth reading back to the supplied configs.
        for field in raw.replace(";", ",").split(","):
            field = field.strip()
            if "Hoowalt" in field or field.startswith("SN-"):
                print("        -> %s" % field)
        print("")

    print("=" * 72)
    if answered:
        print("  %d board(s) answered.  Compare the names above with the two" % answered)
        print("  supplied configs to fix which port is which panel:")
        print("     Hoowalt D201 RTP   - radio panel, 4 displays, 5 encoders")
        print("     Hoowalt D203 ATC   - transponder, 1 display, 4 encoders")
        print("  A third board is connected; if it answers with a name we have")
        print("  no config for, that panel needs its own .mfmc before it can be")
        print("  driven.")
    else:
        print("  Nothing answered.  Either the identify id is wrong for this")
        print("  firmware, the baud differs, or something else holds the ports.")
        print("  Nothing was written to any board, so nothing is in a bad state.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
