"""Hold the PU overhead at its dimmest while nothing else owns it.

The PU has no off.  Its resting state is whatever its physical brightness knob
says, and it returns there about a second after anything stops sending it
frames - measured against the port closing, the frame contents, PU Korea's own
minimum, and the stream length.  So the only way to keep it dim once MuslimSim
exits is for something to keep talking to it.

That is this.  It streams the captured vendor minimum

    OVHD,0,1,1,0,<blank>,<blank>,0,0

at the bridge's own cadence, and does nothing else.  It is as dark as this
protocol goes; only the physical knob reaches true off.

**It holds COM5, and that is the whole cost.**  Two owners on that port is the
one thing this project refuses, so it lets go the instant anything that has a
better claim appears:

  * PU CONNECT MSFS starts   -> release immediately, that is its panel
  * the stop file appears    -> release
  * Ctrl-C / console closes  -> release

It refuses to start at all while MuslimSim Studio or the bridge is running,
because they own COM5 then.

Two things to know before relying on it.

**The handover is a race.**  PU CONNECT may reach COM5 before this notices it
started.  The scan enumerates every process, which costs about 10 ms, so the
rate is a straight trade: the default 1 s costs roughly 1% of one core and
leaves a 1 s window; `--scan 0.2` closes the window but costs 5%.  Most
applications take longer than a second to open a serial port, but if PU CONNECT
ever reports the port busy, stop this first or lower `--scan`.

**It does not yet detect MuslimSim starting.**  Studio opening COM5 while this
holds it will fail.  Until Studio is wired to stop this on startup, run
`--stop` before launching Studio.

Usage:
    python tools/pu_dim_holder.py            # hold, until something claims it
    python tools/pu_dim_holder.py --stop     # ask a running holder to release
    python tools/pu_dim_holder.py --status
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import importlib.util
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

# Anything here has a better claim on the panel than we do.
YIELD_TO = {
    "pu connect msfs.exe",
    "pu connect msfs updater.exe",
}

STOP_FILE = PROJECT / "logs" / "pu_dim_holder.stop"
PID_FILE = PROJECT / "logs" / "pu_dim_holder.pid"

TH32CS_SNAPPROCESS = 0x00000002


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wt.DWORD),
        ("szExeFile", wt.WCHAR * 260),
    ]


def running_process_names() -> set:
    """Every running image name, lowercased.

    Toolhelp is used rather than PowerShell because this runs several times a
    second for as long as the holder lives; spawning a shell that often would
    cost more than the job itself.
    """

    kernel32 = ctypes.windll.kernel32
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == -1:
        return set()
    names = set()
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        if not kernel32.Process32FirstW(snap, ctypes.byref(entry)):
            return names
        while True:
            names.add(str(entry.szExeFile).casefold())
            if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                break
    finally:
        kernel32.CloseHandle(snap)
    return names


def running_muslimsim(root: Path):
    """Studio and the bridge own COM5 whenever they are up."""

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


def claimant(names: set):
    """Return the name of whatever has a better claim, or None."""

    for wanted in YIELD_TO:
        if wanted in names:
            return wanted
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM5")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--interval", type=float, default=0.05,
                    help="frame cadence, matching the bridge")
    ap.add_argument("--scan", type=float, default=1.0,
                    help="how often to look for something with a better claim. "
                         "Each scan enumerates every process and costs about "
                         "10 ms, so 1 s is ~1%% of one core; 0.2 s would be 5%%. "
                         "Lower it if PU CONNECT ever finds the port busy.")
    ap.add_argument("--wait-for-exit", type=float, default=0.0,
                    help="seconds to wait for MuslimSim to exit before taking "
                         "the port. Studio launches this while still alive, so "
                         "it must wait rather than refuse; without it there is "
                         "a window where both would hold COM5.")
    ap.add_argument("--stop", action="store_true",
                    help="ask a running holder to release and exit")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()

    STOP_FILE.parent.mkdir(parents=True, exist_ok=True)

    if a.stop:
        STOP_FILE.write_text("stop", encoding="utf-8")
        print("Stop requested. A running holder releases COM5 within a second.")
        return 0

    if a.status:
        alive = PID_FILE.is_file()
        print("pid file : %s" % (PID_FILE if alive else "none"))
        if alive:
            print("pid      : %s" % PID_FILE.read_text(encoding="utf-8").strip())
        held = claimant(running_process_names())
        print("claimant : %s" % (held or "none"))
        return 0

    procs = running_muslimsim(PROJECT)
    if procs and a.wait_for_exit > 0.0:
        # Launched from Studio's own shutdown, so MuslimSim is necessarily
        # still alive at this moment.  Wait for it to release COM5 rather
        # than refusing, and never open the port while it still holds it.
        deadline = time.monotonic() + a.wait_for_exit
        while procs and time.monotonic() < deadline:
            time.sleep(0.25)
            procs = running_muslimsim(PROJECT)
        if procs:
            print(
                "MuslimSim did not exit within %.0fs; leaving COM5 alone."
                % a.wait_for_exit,
                file=sys.stderr,
            )
            return 1
        # It has gone, but the OS may not have finished releasing the handle.
        time.sleep(0.5)
    elif procs:
        print("MuslimSim is running and owns COM5:", file=sys.stderr)
        for p in procs:
            print("   " + p, file=sys.stderr)
        return 1

    # A stale stop file from a previous run would make this exit at once.
    try:
        STOP_FILE.unlink()
    except FileNotFoundError:
        pass

    spec = importlib.util.spec_from_file_location(
        "_pudim", PROJECT / "bridge" / "final.py"
    )
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    if bridge.serial is None:
        print("pyserial is not installed.", file=sys.stderr)
        return 1

    class _Args:
        egt_scale = 1.0
        egt_offset = 0.0
        egt_zero_threshold = 0.0
        egt_zero_raw = 0
        egt_mid_temp = 300.0
        egt_mid_raw = 128
        egt_peak_temp = 700.0
        egt_peak_raw = 255

    # The same frame the bridge sends as it exits: the captured vendor minimum.
    frame = bridge._pu_safe_dark_packet(_Args()).encode("ascii")

    early = claimant(running_process_names())
    if early:
        print("%s is already running; it owns the panel. Nothing to do." % early)
        return 0

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
        print("Could not open %s: %s" % (a.port, exc), file=sys.stderr)
        return 1

    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    releasing = ["stopped"]

    def request_stop(_signum=None, _frame=None):
        releasing[0] = "signal"
        raise KeyboardInterrupt

    try:
        signal.signal(signal.SIGINT, request_stop)
        signal.signal(signal.SIGTERM, request_stop)
    except Exception:
        pass

    print("Holding %s at the dimmest this protocol allows." % a.port)
    print("  frame   : %r" % frame.decode().strip())
    print("  releases: PU CONNECT MSFS starting, --stop, or Ctrl-C")
    print("  note    : this is dim, not off. Only the knob reaches true off.")

    next_scan = 0.0
    try:
        bridge._pu_force_serial_line_state(
            ser, bridge.PU_SERIAL_LINE_DASH_STATE
        )
        while True:
            ser.write(frame)
            now = time.monotonic()
            if now >= next_scan:
                who = claimant(running_process_names())
                if who is not None:
                    releasing[0] = who
                    break
                if STOP_FILE.is_file():
                    releasing[0] = "stop file"
                    break
                next_scan = now + max(0.05, a.scan)
            time.sleep(max(0.01, a.interval))
    except KeyboardInterrupt:
        pass
    finally:
        # Let go first, explain afterwards: whatever is waiting for this port
        # should not wait on a print.
        try:
            ser.close()
        except Exception:
            pass
        try:
            PID_FILE.unlink()
        except FileNotFoundError:
            pass
        try:
            STOP_FILE.unlink()
        except FileNotFoundError:
            pass

    print("Released %s (%s). The panel returns to its knob brightness."
          % (a.port, releasing[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
