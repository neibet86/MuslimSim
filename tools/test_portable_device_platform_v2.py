#!/usr/bin/env python3
"""Offline checks for Portable Device Platform V2."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muslimsim.hardware.device_manager import (
    HIDEndpoint,
    SDLControllerEndpoint,
    hid_endpoints,
    resolve_hid_interfaces,
    resolve_sdl_controller,
    sdl_endpoint_from_metadata,
)
from muslimsim.hardware.discovery import _known_game_controller
from muslimsim.hardware.product_registry import (
    product_for_runtime_text,
    products_for_runtime_text,
)


def main() -> int:
    checks = 0

    expected_names = {
        "PU OVHD 737": "pu_overhead",
        "WINCTRL URSA MINOR 32 THROTTLE": "winctrl_throttle",
        "ORION COMBAT RUDDER PEDALS": "winctrl_pedals",
        "TCA Q Boeing 1&2": "tca_boeing",
        "TCA QUADRANT BOEING 3&4": "tca_boeing",
        "MOZA A210": "moza_a210",
        "MOZA AB6": "moza_ab6",
    }
    for name, expected in expected_names.items():
        spec = product_for_runtime_text(
            name, transports=("sdl", "usb-gaming")
        )
        assert spec is not None and spec.key == expected, (name, spec)
    checks += 1

    # SDL index/GUID changes do not change the logical product.
    first = (
        sdl_endpoint_from_metadata(
            "ORION COMBAT RUDDER PEDALS",
            index=0, instance_id=101, guid="old-unit-guid",
        ),
    )
    replacement = (
        sdl_endpoint_from_metadata(
            "ORION COMBAT RUDDER PEDALS",
            index=7, instance_id=908, guid="different-unit-guid",
        ),
    )
    a = resolve_sdl_controller("winctrl_pedals", endpoints=first)
    b = resolve_sdl_controller("winctrl_pedals", endpoints=replacement)
    assert a is not None and b is not None
    assert a.device_key == b.device_key == "winctrl_pedals"
    assert (a.index, a.instance_id) == (0, 101)
    assert (b.index, b.instance_id) == (7, 908)
    checks += 1

    # Two identical simultaneous products are not guessed by index.
    tied = (
        SDLControllerEndpoint(1, 11, "ORION COMBAT RUDDER PEDALS", "a"),
        SDLControllerEndpoint(4, 44, "ORION COMBAT RUDDER PEDALS", "b"),
    )
    assert resolve_sdl_controller("winctrl_pedals", endpoints=tied) is None
    preferred = resolve_sdl_controller(
        "winctrl_pedals", preferred_instance_id=44, endpoints=tied
    )
    assert preferred is not None and preferred.index == 4
    checks += 1

    # Replacement HID unit: path and serial-like locator can change, VID/PID
    # keeps the same product. The resolver returns all current interfaces and
    # never requires a unit serial number.
    hid_a = HIDEndpoint(
        path=r"\\?\hid#old-path", vendor_id=0x4098, product_id=0xBB36,
        product="WINCTRL 32 MCDU CAPTAIN",
    )
    hid_b = HIDEndpoint(
        path=r"\\?\hid#replacement-path", vendor_id=0x4098, product_id=0xBB36,
        product="WINCTRL 32 MCDU CAPTAIN",
    )
    ra = resolve_hid_interfaces("mcdu32_bb36", endpoints=(hid_a,))
    rb = resolve_hid_interfaces("mcdu32_bb36", endpoints=(hid_b,))
    assert ra is not None and rb is not None
    assert ra.device_key == rb.device_key == "mcdu32_bb36"
    assert ra.paths != rb.paths
    checks += 1

    # HID enumeration discards serial_number from the endpoint model.
    enumerated = hid_endpoints(inventory=({
        "vendor_id": 0x4098,
        "product_id": 0xBF0F,
        "path": b"replacement-pap3-path",
        "product_string": "WINCTRL 3N PAP MCP",
        "manufacturer_string": "WINCTRL",
        "serial_number": "SOME-OTHER-UNIT-SERIAL",
    },))
    assert len(enumerated) == 1
    snap = enumerated[0].snapshot()
    assert "serial_number" not in snap
    assert enumerated[0].path == "replacement-pap3-path"
    checks += 1

    # Shared registry now drives SDL discovery too.
    assert _known_game_controller("PU OVHD 737")[0] == "pu_overhead"
    assert _known_game_controller("TCA Q Boeing 3&4")[0] == "tca_boeing"
    assert _known_game_controller("ORION COMBAT RUDDER PEDALS")[0] == "winctrl_pedals"
    checks += 1

    # Broad HID labels are deliberately ambiguous rather than guessed.
    assert product_for_runtime_text("PDC", transports=("hid",)) is None
    assert len(products_for_runtime_text("PDC", transports=("hid",))) >= 2
    checks += 1

    # The bridge's one SDL owner must consult the shared registry and keep the
    # advanced custom pedal token override; no joystick index is product identity.
    bridge = (ROOT / "bridge" / "final.py").read_text(encoding="utf-8")
    assert "MUSLIMSIM_PORTABLE_DEVICE_PLATFORM_V2_SDL_IDENTITY" in bridge
    assert "_muslimsim_product_for_runtime_text(" in bridge
    assert 'product_key == "pu_overhead"' in bridge
    assert 'product_key == "winctrl_throttle"' in bridge
    assert 'product_key == "winctrl_pedals"' in bridge
    assert 'product_key == "tca_boeing"' in bridge
    assert "pygame.joystick.get_count() == 1" not in bridge
    checks += 1

    print(f"Portable device platform V2: {checks} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
