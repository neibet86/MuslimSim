#!/usr/bin/env python3
"""Offline checks for MuslimSim Portable Device Platform V3 bootstrap."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muslimsim.hardware.device_manager import HIDEndpoint, SerialEndpoint
from muslimsim.hardware.product_registry import product_by_key
from muslimsim.hardware.windows_bootstrap import (
    clean_pc_readiness,
    load_driver_manifest,
    windows_pnp_usb_devices,
)


def main() -> int:
    checks = 0

    # Driver family metadata is deployment-only and does not change identity.
    d201 = product_by_key("muslimrtp_d201")
    pu = product_by_key("pu_overhead")
    bb36 = product_by_key("mcdu32_bb36")
    assert d201 is not None and d201.driver_family == "wch-ch34x"
    assert pu is not None and pu.driver_family == "pu-composite"
    assert bb36 is not None and bb36.driver_family == "windows-hid"
    assert not hasattr(d201, "serial_number")
    pedals = product_by_key("winctrl_pedals")
    assert pedals is not None
    assert pedals.driver_family == "windows-hid-game"
    assert "hid" in pedals.transports
    assert (0x4098, 0xBEF0) in pedals.usb_ids
    checks += 1

    # PnP parser treats instance ID as a diagnostic locator only.
    pnp = windows_pnp_usb_devices(({
        "InstanceId": r"USB\VID_4098&PID_BB36\replacement-unit",
        "FriendlyName": "WINCTRL 32 MCDU CAPTAIN",
        "Class": "HIDClass",
        "Status": "OK",
        "ProblemCode": 0,
        "Service": "HidUsb",
        "DriverProvider": "Microsoft",
    },))
    assert len(pnp) == 1
    assert (pnp[0].vendor_id, pnp[0].product_id) == (0x4098, 0xBB36)
    assert "serial_number" not in pnp[0].snapshot()
    checks += 1

    runtime_ok = {
        "ready": True,
        "modules": [],
        "data": [],
    }

    # A present HID product with its HID interface is ready.
    report = clean_pc_readiness(
        ROOT,
        pnp_inventory=({
            "InstanceId": r"USB\VID_4098&PID_BB36\x",
            "FriendlyName": "WINCTRL 32 MCDU CAPTAIN",
            "Class": "HIDClass",
            "Status": "OK",
            "ProblemCode": 0,
        },),
        serial_inventory=(),
        hid_inventory=(HIDEndpoint(
            path="replacement-bb36-path",
            vendor_id=0x4098,
            product_id=0xBB36,
            product="WINCTRL 32 MCDU CAPTAIN",
        ),),
        runtime_snapshot=runtime_ok,
    )
    row = next(item for item in report["products"] if item["key"] == "mcdu32_bb36")
    assert row["connected"] and row["driver_ready"]
    assert report["ready"]
    checks += 1

    # The actual live-cockpit Orion HID identity 4098:BEF0 is recognised as
    # the same logical pedal product; the control owner remains SDL.
    report = clean_pc_readiness(
        ROOT,
        pnp_inventory=({
            "InstanceId": r"HID\VID_4098&PID_BEF0&MI_00\replacement",
            "FriendlyName": "WINCTRL Orion Combat Rudder Pedals Metal",
            "Class": "HIDClass",
            "Status": "OK",
            "ProblemCode": 0,
        },),
        serial_inventory=(),
        hid_inventory=(HIDEndpoint(
            path="replacement-orion-path",
            vendor_id=0x4098,
            product_id=0xBEF0,
            product="WINCTRL Orion Combat Rudder Pedals Metal",
        ),),
        runtime_snapshot=runtime_ok,
    )
    pedals_row = next(item for item in report["products"] if item["key"] == "winctrl_pedals")
    assert pedals_row["connected"] and pedals_row["driver_ready"]
    assert pedals_row["hid_interfaces"] == 1
    checks += 1

    # HOWALT USB device present but without a COM interface is a driver issue.
    report = clean_pc_readiness(
        ROOT,
        pnp_inventory=({
            "InstanceId": r"USB\VID_1A86&PID_7523\x",
            "FriendlyName": "USB2.0-Serial",
            "Class": "USB",
            "Status": "OK",
            "ProblemCode": 0,
        },),
        serial_inventory=(),
        hid_inventory=(),
        runtime_snapshot=runtime_ok,
    )
    d201_row = next(item for item in report["products"] if item["key"] == "muslimrtp_d201")
    d203_row = next(item for item in report["products"] if item["key"] == "muslimatc_d203")
    assert d201_row["connected"] and not d201_row["driver_ready"]
    assert d203_row["connected"] and not d203_row["driver_ready"]
    assert not report["ready"]
    checks += 1

    # The same WCH replacement unit is ready as soon as Windows exposes COM.
    report = clean_pc_readiness(
        ROOT,
        pnp_inventory=({
            "InstanceId": r"USB\VID_1A86&PID_7523\another-unit",
            "FriendlyName": "USB-SERIAL CH340",
            "Class": "Ports",
            "Status": "OK",
            "ProblemCode": 0,
        },),
        serial_inventory=(SerialEndpoint(
            "COM44", 0x1A86, 0x7523, description="USB-SERIAL CH340"
        ),),
        hid_inventory=(),
        runtime_snapshot=runtime_ok,
    )
    d201_row = next(item for item in report["products"] if item["key"] == "muslimrtp_d201")
    assert d201_row["driver_ready"] and "COM44" in d201_row["serial_ports"]
    checks += 1

    # PnP problem code/status overrides an otherwise present interface.
    report = clean_pc_readiness(
        ROOT,
        pnp_inventory=({
            "InstanceId": r"USB\VID_4098&PID_BF0F\x",
            "FriendlyName": "WINCTRL 3N PAP MCP",
            "Class": "HIDClass",
            "Status": "Error",
            "ProblemCode": 28,
        },),
        hid_inventory=(HIDEndpoint(
            path="pap-path",
            vendor_id=0x4098,
            product_id=0xBF0F,
            product="WINCTRL 3N PAP MCP",
        ),),
        serial_inventory=(),
        runtime_snapshot=runtime_ok,
    )
    pap = next(item for item in report["products"] if item["key"] == "pap3_mag")
    assert pap["connected"] and not pap["driver_ready"]
    assert "PnP" in pap["reason"]
    checks += 1

    # Runtime packaging failure is fatal independently of hardware.
    report = clean_pc_readiness(
        ROOT,
        pnp_inventory=(),
        serial_inventory=(),
        hid_inventory=(),
        runtime_snapshot={"ready": False, "modules": [], "data": []},
    )
    assert not report["ready"]
    assert not report["driver_issues"]
    checks += 1

    # Current manifest intentionally embeds no unreviewed kernel driver.
    manifest = load_driver_manifest(ROOT)
    assert manifest["schema"] == 1
    assert manifest["packages"] == []
    assert "signed" in manifest["policy"].casefold()
    checks += 1

    # No-pip/no-cockpit-app policy is part of the readiness result.
    report = clean_pc_readiness(
        ROOT,
        pnp_inventory=(),
        serial_inventory=(),
        hid_inventory=(),
        runtime_snapshot=runtime_ok,
    )
    policy = report["policy"]
    assert "no end-user pip" in policy["python_dependencies"].casefold()
    assert policy["cockpit_software"] == "not required"
    assert "signed" in policy["driver_install"].casefold()
    checks += 1

    print(f"Portable device platform V3 bootstrap: {checks} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
