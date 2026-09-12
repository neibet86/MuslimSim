#!/usr/bin/env python3
"""Offline tests for MuslimSim portable product/locator platform V1."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muslimsim.hardware.device_manager import SerialEndpoint, _extract_usb_id, resolve_serial_port
from muslimsim.hardware.product_registry import (
    product_by_key,
    products_for_usb,
    winctrl_pid_map,
    generic_usb_map,
)
from muslimsim.hardware.device_lifecycle import DEVICE_SPECS, ReconnectableSerialPort


class FakeRaw:
    def __init__(self, port: str) -> None:
        self.port = port
        self.is_open = True
        self.dtr = False
        self.rts = False
        self._port_handle = None
        self.writes = []

    @property
    def in_waiting(self):
        return 0

    def write(self, data):
        self.writes.append(bytes(data))
        return len(data)

    def read(self, size=1):
        return b""

    def flush(self):
        return None

    def close(self):
        self.is_open = False


def main() -> int:
    checks = 0

    # Same product, another physical unit: no serial number is part of ProductSpec.
    pu = product_by_key("pu_overhead")
    assert pu is not None and (0x3561, 0x8561) in pu.usb_ids
    assert not hasattr(pu, "serial_number")
    checks += 1

    # HOWALT USB chipset is intentionally ambiguous until protocol identity.
    howalt = products_for_usb(0x1A86, 0x7523)
    assert {item.key for item in howalt} == {"muslimrtp_d201", "muslimatc_d203"}
    checks += 1

    # Current WinCtrl/generic discovery maps retain the established keys.
    pids = winctrl_pid_map()
    assert pids[0xBB35][0] == "pfp3n_bb35"
    assert pids[0xBB36][0] == "mcdu32_bb36"
    assert pids[0xBF0F][0] == "pap3_mag"
    assert generic_usb_map()[(0x3561, 0x8561)][0] == "pu_overhead"
    checks += 1

    # Existing lifecycle matchers remain the proven owners, but every active
    # lifecycle product is now represented in the shared registry and any
    # lifecycle VID/PID agrees with the registry. This prevents the new
    # platform layer from silently changing a working product identity.
    for key, lifecycle in DEVICE_SPECS.items():
        spec = product_by_key(key)
        assert spec is not None, key
        if "vid" in lifecycle and "pid" in lifecycle:
            assert (int(lifecycle["vid"]), int(lifecycle["pid"])) in spec.usb_ids, key
    checks += 1

    # A PU on any COM number resolves by stable VID/PID.
    endpoints = (
        SerialEndpoint("COM27", 0x3561, 0x8561, description="USB Serial"),
        SerialEndpoint("COM4", 0x1234, 0x5678, description="Other device"),
    )
    resolution = resolve_serial_port("pu_overhead", endpoints=endpoints)
    assert resolution is not None and resolution.port == "COM27"
    assert resolution.matched_by == "usb-vid-pid"
    checks += 1

    # Windows composite COM children may carry the stable product identity on
    # an ancestor rather than on the Ports-class child itself.
    assert _extract_usb_id(
        r"USB\VID_1A86&PID_7523&MI_00 | USB\VID_3561&PID_8561\ABC"
    ) == (0x1A86, 0x7523)
    assert _extract_usb_id(r"USB\VID_3561&PID_8561\PU") == (0x3561, 0x8561)
    checks += 1

    # A driver that omits structured VID/PID can still resolve by product string.
    resolution = resolve_serial_port(
        "pu_overhead",
        endpoints=(SerialEndpoint("COM41", description="PU OVHD 737 USB Serial"),),
    )
    assert resolution is not None and resolution.port == "COM41"
    assert resolution.matched_by == "product-string"
    checks += 1

    # Two identical candidates must not be guessed by enumeration order.
    ambiguous = (
        SerialEndpoint("COM11", 0x3561, 0x8561),
        SerialEndpoint("COM12", 0x3561, 0x8561),
    )
    assert resolve_serial_port("pu_overhead", endpoints=ambiguous) is None
    chosen = resolve_serial_port("pu_overhead", preferred="COM12", endpoints=ambiguous)
    assert chosen is not None and chosen.port == "COM12"
    checks += 1

    # Reconnectable PU serial proxy may move to another COM without replacing
    # the logical device owner or requiring a config change.
    opened = []
    current = {"port": "COM27"}

    def open_serial(*args, **kwargs):
        port = kwargs.get("port") if "port" in kwargs else args[0]
        opened.append(str(port))
        return FakeRaw(str(port))

    proxy = ReconnectableSerialPort(
        open_serial,
        (),
        {"port": "COM5"},
        value_state=2,
        dash_state=0,
        reset_seconds=0,
        dash_seconds=0,
        port_resolver=lambda: current["port"],
    )
    assert opened[-1] == "COM27"
    with proxy._lock:
        proxy._drop_raw_locked()
    current["port"] = "COM44"
    proxy.write(b"test")
    assert opened[-1] == "COM44"
    assert proxy.port == "COM44"
    proxy.close()
    checks += 1

    # In auto mode, a missing/unresolved product must never fall through to
    # the historical COM5 compatibility locator and open an unrelated port.
    attempted = []
    absent_proxy = ReconnectableSerialPort(
        lambda *args, **kwargs: attempted.append(
            kwargs.get("port") if "port" in kwargs else args[0]
        ) or FakeRaw("unexpected"),
        (),
        {"port": "COM5"},
        value_state=2,
        dash_state=0,
        reset_seconds=0,
        dash_seconds=0,
        port_resolver=lambda: None,
    )
    assert attempted == []
    assert absent_proxy.port == ""
    absent_proxy.close()
    checks += 1

    # The bridge may use an SDL index as a momentary event locator, but it may
    # not identify the PU merely because it is the only/index-0 joystick.
    bridge = (ROOT / "bridge" / "final.py").read_text(encoding="utf-8")
    assert "pygame.joystick.get_count() == 1" not in bridge
    checks += 1

    print(f"Portable device platform V1: {checks} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
