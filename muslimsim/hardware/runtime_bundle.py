"""MuslimSim frozen-runtime dependency/readiness checks.

End users should run MuslimSim.exe, not pip.  This module exists so the build
and diagnostics can prove that the packaged runtime contains the Python-side
hardware dependencies used by the bridge.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any, Dict, Tuple


RUNTIME_MODULES: Tuple[Tuple[str, str], ...] = (
    ("serial", "USB serial / PU / HOWALT"),
    ("serial.tools.list_ports", "automatic COM discovery"),
    ("hid", "WinCtrl/WinWing HID panels"),
    ("pygame", "shared SDL controller owner"),
    ("websocket", "X-Plane/BB35/BB36 live feeds"),
    ("PIL.Image", "Studio/rendering assets"),
    ("muslimsim.hardware.windows_bootstrap", "clean-PC / signed-driver bootstrap"),
    ("muslimsim.simulator.xplane_telemetry", "shared X-Plane telemetry distribution"),
)

RUNTIME_DATA = (
    ("bridge/pu_physical_authority.py", "PU maintained-state authority helper"),
    ("muslimsim/hardware/xplane_command_catalog.json", "X-Plane mapping catalogue"),
    ("muslimsim/hardware/msfs24_command_catalog.json", "MSFS mapping catalogue"),
    ("muslimsim/devices/pfp_bank_line_plan.json", "PFP font/layout plan"),
    ("muslimsim/hardware/driver_bundles.json", "signed Windows driver bundle manifest"),
)


def dependency_snapshot(project_root: object = None) -> Dict[str, Any]:
    modules = []
    for module_name, purpose in RUNTIME_MODULES:
        try:
            importlib.import_module(module_name)
            available = True
            error = ""
        except Exception as exc:
            available = False
            error = f"{type(exc).__name__}: {exc}"
        modules.append({
            "module": module_name,
            "purpose": purpose,
            "available": available,
            "error": error,
        })

    root = Path(project_root) if project_root else None
    data = []
    for relative, purpose in RUNTIME_DATA:
        present = None if root is None else (root / relative).is_file()
        data.append({
            "path": relative,
            "purpose": purpose,
            "present": present,
        })

    return {
        "frozen": bool(getattr(sys, "frozen", False)),
        "python": sys.version.split()[0],
        "end_user_install_policy": "MuslimSim.exe bundles Python runtime dependencies; no pip required",
        "modules": modules,
        "data": data,
        "ready": all(item["available"] for item in modules),
    }


__all__ = ["RUNTIME_MODULES", "RUNTIME_DATA", "dependency_snapshot"]

MUSLIMSIM_PORTABLE_DEVICE_PLATFORM_V3_RUNTIME = True

MUSLIMSIM_SHARED_XPLANE_TELEMETRY_V1_RUNTIME = True
