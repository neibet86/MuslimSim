#!/usr/bin/env python3
"""Offline build-recipe checks for a self-contained MuslimSim end-user EXE."""
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    spec = (ROOT / "MuslimSim.spec").read_text(encoding="utf-8")
    required_tokens = (
        '"websocket"',
        '"serial.tools.list_ports"',
        '"hid"',
        '"pygame"',
        'collect_submodules("muslimsim.devices")',
        'collect_submodules("muslimsim.hardware")',
        'collect_submodules("muslimsim.simulator")',
        'collect_submodules("muslimsim.control")',
        '"pu_physical_authority.py"',
        '"xplane_command_catalog.json"',
        '"msfs24_command_catalog.json"',
        '"pfp_bank_line_plan.json"',
        '"driver_bundles.json"',
        '"muslimsim.hardware.windows_bootstrap"',
        '"muslimsim.simulator.xplane_telemetry"',
    )
    missing = [token for token in required_tokens if token not in spec]
    if missing:
        raise AssertionError("MuslimSim.spec missing portable runtime items: " + ", ".join(missing))

    required_files = (
        ROOT / "bridge" / "final.py",
        ROOT / "bridge" / "pu_physical_authority.py",
        ROOT / "muslimsim" / "hardware" / "xplane_command_catalog.json",
        ROOT / "muslimsim" / "hardware" / "msfs24_command_catalog.json",
        ROOT / "muslimsim" / "devices" / "pfp_bank_line_plan.json",
        ROOT / "muslimsim" / "hardware" / "product_registry.py",
        ROOT / "muslimsim" / "hardware" / "device_manager.py",
        ROOT / "muslimsim" / "hardware" / "runtime_bundle.py",
        ROOT / "muslimsim" / "hardware" / "windows_bootstrap.py",
        ROOT / "muslimsim" / "hardware" / "driver_bundles.json",
        ROOT / "muslimsim" / "simulator" / "xplane_telemetry.py",
    )
    absent = [str(path.relative_to(ROOT)) for path in required_files if not path.is_file()]
    if absent:
        raise AssertionError("portable runtime source/data files absent: " + ", ".join(absent))

    print("Portable runtime bundle recipe: 15 recipe checks + 11 file checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
