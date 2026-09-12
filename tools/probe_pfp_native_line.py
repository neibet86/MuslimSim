"""Probe one undocumented BB35/BB36 LCD command, display-only.

This deliberately sends exactly one candidate command after the same proven
F2/F0 display reinitialization used by MuslimSim Studio.  It then performs a
dark clear and a proven LCD refresh.  It never reads or writes X-Plane and
never opens any other WinCtrl device.  Studio must be stopped so two processes
do not write the same display.

Examples (run one at a time and photograph the screen):

    python tools/probe_pfp_native_line.py --panel bb36 --function 0x115 --layout endpoints16 --confirm-studio-stopped
    python tools/probe_pfp_native_line.py --panel bb36 --restore --confirm-studio-stopped
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import time


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

BACKGROUND = (6, 7, 13)


def _load_bridge():
    path = PROJECT / "bridge" / "final.py"
    spec = importlib.util.spec_from_file_location("final", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _active_studio_processes() -> list[str]:
    """Return MuslimSim process rows using Windows' read-only process query."""
    command = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -in @('python.exe','pythonw.exe') -and "
        "$_.CommandLine -match "
        "'MuslimSim Studio|MuslimSim\\\\launch\\.py|D:\\\\MuslimSim\\\\launch\\.py' } | "
        "ForEach-Object { \"$($_.ProcessId) $($_.Name) $($_.CommandLine)\" }"
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", command],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _payload(layout: str) -> bytes:
    # A long 45-degree segment, far from the screen edges.  The known colour
    # state is set to white before this is sent.
    x0, y0, x1, y1 = 120, 100, 420, 400
    if layout == "endpoints16":
        return struct.pack("<HHHH", x0, y0, x1, y1)
    if layout == "endpoints16-thickness16":
        return struct.pack("<HHHHH", x0, y0, x1, y1, 2)
    if layout == "endpoints16-thickness32":
        return struct.pack("<HHHHI", x0, y0, x1, y1, 2)
    if layout == "endpoints32":
        return struct.pack("<IIII", x0, y0, x1, y1)
    if layout == "xywh16":
        return struct.pack("<HHHH", x0, y0, x1 - x0, y1 - y0)
    raise ValueError(f"Unknown layout: {layout}")


def _collect_acks(device, seconds: float = 0.8) -> list[int]:
    counters: list[int] = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        report = device.read(64)
        if not report:
            time.sleep(0.002)
            continue
        if report[0] == 0xF0 and len(report) > 2:
            counters.append(int(report[2]))
    return counters


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", choices=("bb35", "bb36"), default="bb36")
    parser.add_argument("--function", type=lambda value: int(value, 0), default=0x115)
    parser.add_argument(
        "--layout",
        choices=(
            "endpoints16",
            "endpoints16-thickness16",
            "endpoints16-thickness32",
            "endpoints32",
            "xywh16",
        ),
        default="endpoints16",
    )
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--confirm-studio-stopped", action="store_true")
    args = parser.parse_args()

    if not args.confirm_studio_stopped:
        parser.error("--confirm-studio-stopped is required")
    active = _active_studio_processes()
    if active:
        print("REFUSED: MuslimSim Studio/launch.py still owns display output:")
        for row in active:
            print(f"  {row}")
        print("Stop Studio, then run this probe again.")
        return 3

    bridge = _load_bridge()
    if bridge.hid is None:
        print("hidapi unavailable")
        return 2

    if args.panel == "bb35":
        pid = bridge.PFP_PFD_PID
        identifier = bridge.PFP_PFD_IDENTIFIER
        label = "BB35 PFP"
    else:
        pid = bridge.MCDU_PFD_PID
        identifier = bridge.MCDU_PFD_IDENTIFIER
        label = "BB36 MCDU"

    devices = list(bridge.hid.enumerate(bridge.PFP_PFD_VID, pid))
    if not devices:
        print(f"{label} not found")
        return 2
    device_info = devices[0]
    path = device_info.get("path")
    if not path:
        print(f"{label} has no HID path")
        return 2

    # Reinitialize both persistent display planes before every candidate.  It
    # is the exact safe F2/F0 sequence used by Studio at startup and replaces
    # the user's manual unplug/replug for ordinary protocol experiments.  A
    # true Windows USB restart remains available only to an Administrator and
    # is intentionally not imitated or falsely reported here.
    config_packets = (
        (
            bridge._pfp_black_background_packet(),
            bridge._pfp_text_grid_packet(),
        )
        if args.panel == "bb35"
        else ()
    )
    print(f"{label}: reinitializing F2/F0 display planes before candidate...")
    if not bridge._force_refresh_one_winctrl_display(
        device_info,
        identifier,
        label,
        config_packets,
    ):
        print(f"{label}: display reinitialization failed; candidate was not sent.")
        return 2
    time.sleep(0.20)

    # Re-enumerate after the handle-close reset so the probe never reuses a
    # stale HID path.  This also establishes a fresh F0 sequence/session.
    devices = list(bridge.hid.enumerate(bridge.PFP_PFD_VID, pid))
    if not devices:
        print(f"{label} did not return after display reinitialization")
        return 2
    path = devices[0].get("path")
    if not path:
        print(f"{label} returned without a HID path")
        return 2

    device = bridge.hid.device()
    device.open_path(path)
    try:
        device.set_nonblocking(1)
        _collect_acks(device, 0.15)
        canvas = bridge._PfpNativeCanvas(device, identifier=identifier)

        # The reset deliberately releases the panel dark/off.  Test authority
        # is explicit here, so wake only this selected display at the same
        # proven levels used by Studio's live path.
        bridge._winctrl_display_set_brightness(device, identifier, 0, 128)
        bridge._winctrl_display_set_brightness(device, identifier, 1, 220)

        # Known dark clear and four small corner witnesses prove that the
        # graphics plane accepted the card even when the candidate is ignored.
        canvas.colour(*BACKGROUND)
        canvas.fill(0, 0, 640, 480)
        if args.restore:
            canvas.command(0x103)
            print(f"{label} restored to the normal dark background.")
            return 0

        canvas.colour(0, 180, 255)
        for x, y in ((90, 70), (530, 70), (90, 390), (530, 390)):
            canvas.fill(x, y, 20, 20)

        candidate = _payload(args.layout)
        canvas.colour(255, 255, 255)
        canvas.command(args.function, candidate)
        canvas.command(0x103)

        acks = _collect_acks(device)
        print(f"{label}: function=0x{args.function:03X}, layout={args.layout}")
        print("Reset: proven F2 blank + F0 clear + HID reopen")
        print(f"payload: {candidate.hex(' ')}")
        print(f"F0 acknowledgements: {len(acks)}")
        print("Four cyan corner blocks only -> candidate was ignored or has another layout.")
        print("White diagonal present       -> native line command confirmed.")
        print("Run with --restore afterwards, or restart Studio normally.")
    finally:
        try:
            device.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
