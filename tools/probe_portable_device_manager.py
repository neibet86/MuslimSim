#!/usr/bin/env python3
"""Read-only MuslimSim product/locator inventory for portability checks.

Default mode does not open serial/HID handles or SDL joystick objects.
Use --include-sdl only with Studio closed; pygame may create controller
metadata objects, but this probe still sends no input/output reports.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muslimsim.hardware.device_manager import (
    product_runtime_snapshot,
    resolve_serial_port,
)
from muslimsim.hardware.discovery import discovery_snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-sdl", action="store_true",
        help="Enumerate SDL controller metadata; run only with Studio closed.",
    )
    args = parser.parse_args()

    print("=" * 78)
    print("MUSLIMSIM PORTABLE DEVICE MANAGER V2 - READ ONLY")
    print("=" * 78)
    platform = product_runtime_snapshot(
        include_hid=True,
        include_sdl=bool(args.include_sdl),
    )
    print(platform["identity_policy"])

    print("\nSerial endpoints:")
    for endpoint in platform["serial_endpoints"]:
        print(
            f"  {endpoint['port']:>7}  "
            f"VID:PID={endpoint['vendor_id']:04X}:{endpoint['product_id']:04X}  "
            f"{endpoint['description']}  [{endpoint['source']}]"
        )
    if not platform["serial_endpoints"]:
        print("  (none detected)")

    print("\nPU resolution:")
    pu = resolve_serial_port("pu_overhead")
    if pu is None:
        print("  not uniquely resolved (absent, driver missing, or ambiguous)")
    else:
        print(f"  {pu.port} via {pu.matched_by}; candidates={list(pu.candidates)}")

    print("\nSupported HID runtime locators (enumeration only; no open_path):")
    for row in platform["products"]:
        paths = row.get("hid_paths") or []
        if paths:
            print(f"  {row['key']}: {len(paths)} current HID interface(s)")
    if not any(row.get("hid_paths") for row in platform["products"]):
        print("  (none detected)")

    if args.include_sdl:
        print("\nSDL runtime locators (Studio must be closed):")
        any_sdl = False
        for row in platform["products"]:
            candidates = row.get("sdl_candidates") or []
            for candidate in candidates:
                any_sdl = True
                print(
                    f"  {row['key']}: index={candidate['index']} "
                    f"instance={candidate['instance_id']} "
                    f"name={candidate['name']!r}"
                )
        if not any_sdl:
            print("  (none detected)")
    else:
        print("\nSDL: skipped by default to avoid competing with Studio's one SDL owner.")

    print("\nStudio discovery (SDL disabled):")
    snapshot = discovery_snapshot(include_sdl=False)
    for device in snapshot.get("devices", []):
        status = "supported" if device.get("recognised") else "unrecognised"
        print(
            f"  {device.get('key')}: {device.get('title')}  "
            f"[{status}; {device.get('source')}]"
        )

    print("\nIdentity is never saved from COM/HID path/SDL index/GUID/serial number.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
