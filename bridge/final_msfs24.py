#!/usr/bin/env python3
"""MSFS 2024 configuration bridge for MuslimSim Studio.

This is intentionally separate from ``final.py``.  It owns only MSFS 2024
profile/catalogue work today—no SimConnect, FSUIPC, LVAR, HID, or serial write
is attempted until a connector and its protocol are verified.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import sys
import threading
from typing import Any, Mapping, Sequence

# Studio starts this file through ``launch_msfs24.py``.  Keep the bridge
# independently runnable for diagnostics as well, matching the established
# X-Plane bridge behaviour.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from muslimsim.control.server import ControlServer
from muslimsim.hardware.discovery import discover_hid_devices
from muslimsim.hardware.lab import HardwareLab
from muslimsim.hardware.msfs24_library import catalogue_summary, offline_msfs24_functions, search_msfs24_functions
from muslimsim.hardware.profiles import HardwareProfileStore, MappingBinding
from muslimsim.platform.msfs_connector import (
    MsfsTransport, NullMsfsTransport, dispatch_msfs_binding,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MuslimSim MSFS 2024 configuration bridge")
    parser.add_argument("--control-port", type=int, default=0)
    parser.add_argument("--control-token", default="")
    parser.add_argument("--lab-profile", default="")
    parser.add_argument("--test-hardware-lab", action="store_true")
    return parser


def _default_profile_path() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / "MuslimSim" / "hardware_profiles_msfs24.json"


def _hardware_inventory() -> Mapping[str, Any]:
    return {"devices": [device.snapshot() for device in discover_hid_devices()], "source": "msfs24-bridge"}


def _function_catalogue(query: str, limit: int, _aircraft: str = "") -> Mapping[str, Any]:
    functions = offline_msfs24_functions(include_axes=True)
    summary = catalogue_summary()
    return {
        "functions": search_msfs24_functions(functions, query, limit=limit),
        "source": "catalogue-msfs24",
        "total": int(summary["total"]),
        "detail": "Imported MSFS 2024 catalogue. Aircraft dispatch remains safely disabled until the MSFS connector is implemented.",
        "aircraft": list(summary["aircraft"]),
    }


def _binding_sink(
    lab: HardwareLab, device: str, control: str, binding: MappingBinding,
    value: float, phase: str, *,
    transport: MsfsTransport | None = None,
    selected_aircraft: str = "",
    loaded_title: str = "",
    loaded_path: str = "",
) -> None:
    """Route one saved MSFS mapping through the connector seam.

    ``transport`` defaults to :class:`NullMsfsTransport`, which accepts nothing
    and explains why, so a mapping can never look delivered when no execution
    surface exists.  Installing a proven transport here is the single change
    that turns MSFS dispatch on - nothing else in this file moves.
    """

    if lab.mode == "test":
        lab.record_diagnostic(device, "msfs24-test-binding", {
            "control": control, "target": binding.target, "protocol": binding.protocol,
            "value": value, "phase": phase,
        })
        return

    outcome = dispatch_msfs_binding(
        transport or NullMsfsTransport(),
        protocol=binding.protocol,
        target=binding.target,
        value=value,
        phase=phase,
        selected_aircraft=selected_aircraft,
        loaded_title=loaded_title,
        loaded_path=loaded_path,
    )
    lab.record_diagnostic(device, "msfs24-dispatch", {
        "control": control, "target": binding.target,
        "protocol": binding.protocol, **outcome,
    })


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    profiles = HardwareProfileStore(Path(args.lab_profile).expanduser() if args.lab_profile else _default_profile_path())
    profiles.load()
    lab = HardwareLab(profiles)
    lab.binding_sink = lambda device, control, binding, value, phase: _binding_sink(
        lab, device, control, binding, value, phase,
    )
    if args.test_hardware_lab:
        result = lab.self_test()
        print("MSFS24 hardware-lab self-test: " + ("PASS" if result["ok"] else "FAIL"), flush=True)
        return 0 if result["ok"] else 2

    stop_requested = threading.Event()
    server = ControlServer(
        lab,
        port=args.control_port,
        token=args.control_token or None,
        shutdown=stop_requested.set,
        function_catalog=_function_catalogue,
        hardware_discovery=_hardware_inventory,
    )
    port = server.start()
    print(f"CONTROL CHANNEL PORT {port}", flush=True)
    print("MSFS 2024 configuration bridge ready — simulator dispatch is disabled.", flush=True)

    def stop_signal(_signum: int, _frame: object) -> None:
        stop_requested.set()

    try:
        signal.signal(signal.SIGINT, stop_signal)
        signal.signal(signal.SIGTERM, stop_signal)
    except (AttributeError, ValueError):
        pass
    try:
        stop_requested.wait()
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
