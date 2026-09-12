"""Verified Windows USB re-enumeration for devices with a known VID/PID.

This is intentionally narrower than a generic ``pnputil`` wrapper: a caller
can only target a physical USB parent already named by the MuslimSim catalogue.
The operation refuses non-elevated sessions and reports failure if the device
never leaves the bus, preventing Windows' misleading success-without-reset
case from being shown as a working screen restart.
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import subprocess
import time
from typing import Dict, Iterable, List


class UsbResetError(RuntimeError):
    pass


_USB_IDENTITIES: Dict[str, str] = {
    "fcu_32_efis": "VID_4098&PID_BA01",
    "pdc_bb62": "VID_4098&PID_BB62",
    "pap3_mag": "VID_4098&PID_BF0F",
    "agp_bb80": "VID_4098&PID_BB80",
    "pfp3n_bb35": "VID_4098&PID_BB35",
    "mcdu32_bb36": "VID_4098&PID_BB36",
    "winctrl_throttle": "VID_4098&PID_B930",
    "ecam32": "VID_4098&PID_BB70",
    "moza_a210": "VID_346E&PID_1001",
    "moza_ab6": "VID_346E&PID_1002",
}


def is_elevated() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _usb_parents(identity: str) -> List[str]:
    """Return only USB parent instance IDs, never HID child nodes."""

    if os.name != "nt":
        raise UsbResetError("USB re-enumeration is available only on Windows")
    # Instance IDs are emitted as data, one per line, then used as a direct
    # subprocess argument.  No shell interpolation is involved.
    script = (
        "$ErrorActionPreference='Stop'; "
        f"Get-PnpDevice -PresentOnly | Where-Object {{ $_.InstanceId -like 'USB\\{identity}*' }} | "
        "ForEach-Object { $_.InstanceId }"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, timeout=8, check=False,
    )
    if completed.returncode != 0:
        raise UsbResetError(completed.stderr.strip() or "Windows could not enumerate USB device parents")
    return [line.strip() for line in completed.stdout.splitlines() if line.strip().upper().startswith("USB\\")]


def can_power_cycle(device_key: str) -> tuple[bool, str]:
    if device_key not in _USB_IDENTITIES:
        return False, "No captured USB parent identity exists for this device"
    if not is_elevated():
        return False, "Restart screen/device requires Administrator rights"
    try:
        parents = _usb_parents(_USB_IDENTITIES[device_key])
    except UsbResetError as exc:
        return False, str(exc)
    if not parents:
        return False, "Device is not currently present on the USB bus"
    return True, ""


def power_cycle(device_key: str, *, absent_timeout: float = 4.0, return_timeout: float = 15.0) -> Dict[str, object]:
    """Restart a verified USB parent and prove it left then rejoined the bus."""

    if device_key not in _USB_IDENTITIES:
        raise UsbResetError("No captured USB parent identity exists for this device")
    if not is_elevated():
        raise UsbResetError("Restart screen/device requires Administrator rights")
    identity = _USB_IDENTITIES[device_key]
    parents = _usb_parents(identity)
    if not parents:
        raise UsbResetError("Device is not currently present on the USB bus")
    for parent in parents:
        completed = subprocess.run(
            ["pnputil", "/restart-device", parent],
            capture_output=True, text=True, timeout=12, check=False,
        )
        if completed.returncode != 0:
            raise UsbResetError(completed.stderr.strip() or f"Windows could not restart {parent}")
    deadline = time.monotonic() + max(0.5, float(absent_timeout))
    went_away = False
    while time.monotonic() < deadline:
        if not _usb_parents(identity):
            went_away = True
            break
        time.sleep(0.05)
    if not went_away:
        raise UsbResetError("Windows reported success but the device never left the USB bus, so it was not restarted")
    deadline = time.monotonic() + max(1.0, float(return_timeout))
    while time.monotonic() < deadline:
        present = _usb_parents(identity)
        if present:
            return {"device": device_key, "parents": present, "power_cycled": True}
        time.sleep(0.10)
    raise UsbResetError("Device left the USB bus but did not return before the timeout")
