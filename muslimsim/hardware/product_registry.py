"""Stable MuslimSim physical-product identity registry.

MUSLIMSIM_PORTABLE_DEVICE_PLATFORM_V1

This module answers one question only: *what product is this?*  It does not
open a device and it never uses a unit serial number, COM number, SDL index,
HID path, Windows user path, or installation directory as product identity.

Those volatile values are runtime locators.  A replacement unit of the same
supported product must match the same ProductSpec and inherit the same Studio
profile/defaults without configuration.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ProductSpec:
    key: str
    title: str
    transports: Tuple[str, ...]
    driver: str
    usb_ids: Tuple[Tuple[int, int], ...] = ()
    product_tokens: Tuple[str, ...] = ()
    serial_protocol_names: Tuple[str, ...] = ()
    notes: str = ""
    replaceable_unit: bool = True
    # OS driver family is installation/bootstrap metadata only. It is not part
    # of product identity and does not change any existing device owner.
    driver_family: str = "windows-native"

    def matches_usb(self, vendor_id: int, product_id: int) -> bool:
        return (int(vendor_id), int(product_id)) in self.usb_ids

    def matches_text(self, *values: object) -> bool:
        haystack = " ".join(str(value or "") for value in values).casefold()
        return any(token.casefold() in haystack for token in self.product_tokens)

    def matches_protocol_name(self, value: object) -> bool:
        normalised = " ".join(str(value or "").casefold().split())
        return any(
            " ".join(name.casefold().split()) == normalised
            for name in self.serial_protocol_names
        )


# Product identity is deliberately broader than one physical unit.  Serial
# numbers are never listed here.  The two HOWALT boards share a USB-serial
# chipset and are separated by their read-only MobiFlight firmware name.
PRODUCTS: Tuple[ProductSpec, ...] = (
    ProductSpec(
        "muslimrtp_d201", "MUSLIMRTP • HOWALT D201 RTP",
        ("serial",), "muslimsim.devices.muslimrtp_v4",
        usb_ids=((0x1A86, 0x7523), (0x1A86, 0x5523), (0x1A86, 0x55D3), (0x1A86, 0x55D4)),
        product_tokens=("HOWALT D201", "HOOWALT D201", "D201 RTP"),
        serial_protocol_names=("Hoowalt D201 RTP", "Howalt D201 RTP"),
        notes="Shared WCH USB serial identity; model is resolved by read-only firmware identity.",
        driver_family="wch-ch34x",
    ),
    ProductSpec(
        "muslimatc_d203", "MUSLIMATC • HOWALT D203 ATC",
        ("serial",), "muslimsim.devices.muslimatc_v4",
        usb_ids=((0x1A86, 0x7523), (0x1A86, 0x5523), (0x1A86, 0x55D3), (0x1A86, 0x55D4)),
        product_tokens=("HOWALT D203", "HOOWALT D203", "D203 ATC", "D203 XPNDR"),
        serial_protocol_names=("Hoowalt D203 ATC", "Howalt D203 ATC"),
        notes="Shared WCH USB serial identity; model is resolved by read-only firmware identity.",
        driver_family="wch-ch34x",
    ),
    ProductSpec(
        "pu_overhead", "PU Overhead", ("hid", "serial", "sdl", "raw-input"),
        "bridge.final PU owner", usb_ids=((0x3561, 0x8561),),
        product_tokens=("PU OVHD", "PU OVERHEAD", "PU OVHD 737"),
        notes="Composite PU panel. USB identity is stable; COM number is runtime-only.",
        driver_family="pu-composite",
    ),
    ProductSpec(
        "tca_boeing", "Thrustmaster TCA Boeing Quadrant", ("sdl", "usb-gaming"),
        "bridge.final SDL TCA owner",
        usb_ids=((0x044F, 0x040A), (0x044F, 0x040B)),
        product_tokens=("TCA Q BOEING 1&2", "TCA QUADRANT BOEING 1&2", "TCA Q BOEING 3&4", "TCA QUADRANT BOEING 3&4"),
        notes="One supported product family; Windows may expose either bank identity.",
        driver_family="windows-game",
    ),
    ProductSpec("fcu_32_efis", "WINCTRL 32 FCU + 32 EFIS L/R", ("hid",), "muslimsim.devices.fcu_efis_ba01", usb_ids=((0x4098, 0xBA01),), product_tokens=("FCU", "EFIS"), driver_family="windows-hid"),
    ProductSpec("pdc_bb62", "WINCTRL 3N PDC", ("hid",), "muslimsim.devices.pdc_bb62", usb_ids=((0x4098, 0xBB62),), product_tokens=("PDC",), driver_family="windows-hid"),
    ProductSpec("pdc_bb61_left", "WINWING PDC", ("hid",), "muslimsim.devices.pdc_bb61_bb52", usb_ids=((0x4098, 0xBB61), (0x4098, 0xBB51)), product_tokens=("3N PDC L", "3M PDC L"), driver_family="windows-hid"),
    ProductSpec("pdc_bb52_right", "WINWING PDC", ("hid",), "muslimsim.devices.pdc_bb61_bb52", usb_ids=((0x4098, 0xBB52),), product_tokens=("3M PDC R",), driver_family="windows-hid"),
    # BB51 merged into pdc_bb61_left below — same 3M hardware, Captain-side config.
    ProductSpec("pap3_mag", "WINCTRL 3N PAP MCP", ("hid",), "muslimsim.devices.pap3_mcp", usb_ids=((0x4098, 0xBF0F),), product_tokens=("PAP", "MCP"), driver_family="windows-hid"),
    ProductSpec("winctrl_throttle", "WINCTRL URSA Minor throttle", ("hid", "sdl"), "bridge.final WinCtrl axis owner", usb_ids=((0x4098, 0xB930),), product_tokens=("URSA MINOR", "THROTTLE"), driver_family="windows-hid-game"),
    ProductSpec(
        "winctrl_pedals", "WINCTRL Orion Combat Rudder Pedals Metal",
        ("hid", "sdl", "usb-gaming"), "bridge.final pedal owner",
        usb_ids=((0x4098, 0xBEF0),),
        product_tokens=(
            "ORION COMBAT RUDDER PEDALS",
            "ORION COMBAT RUDDER PEDALS METAL",
            "ORION RUDDER PEDALS",
        ),
        notes=(
            "The proven control owner remains the single bridge SDL reader; "
            "HID 4098:BEF0 is stable product discovery/identity only."
        ),
        driver_family="windows-hid-game",
    ),
    ProductSpec("agp_bb80", "WINCTRL 32 AGP Metal", ("hid",), "bridge.final AGP owner", usb_ids=((0x4098, 0xBB80),), product_tokens=("AGP",), driver_family="windows-hid"),
    ProductSpec("pfp3n_bb35", "WINCTRL 3N PFP", ("hid",), "bridge.final BB35 path router",
        usb_ids=((0x4098, 0xBB35), (0x4098, 0xBB3D), (0x4098, 0xBB39)),
        product_tokens=("3N PFP", "PFP CO-PILOT", "PFP OBSERVER"),
        notes="BB35=Captain, BB3D=Co-Pilot, BB39=Observer (read-only input interface).",
        driver_family="windows-hid"),
    ProductSpec("mcdu32_bb36", "WINCTRL 32 MCDU", ("hid",), "bridge.final BB36 path router",
        usb_ids=((0x4098, 0xBB36), (0x4098, 0xBB3E), (0x4098, 0xBB3A)),
        product_tokens=("32 MCDU", "MCDU CO-PILOT", "MCDU OBSERVER"),
        notes="BB36=Captain, BB3E=Co-Pilot, BB3A=Observer (read-only input interface).",
        driver_family="windows-hid"),
    ProductSpec("ecam32", "WINCTRL 32 ECAM", ("hid",), "muslimsim.devices.ecam32", usb_ids=((0x4098, 0xBB70),), product_tokens=("ECAM",), driver_family="windows-hid"),
    ProductSpec("moza_a210", "MOZA A210 Base + detachable yoke", ("hid", "sdl"), "muslimsim.devices.moza_a210", usb_ids=((0x346E, 0x1001),), product_tokens=("MOZA A210", "MOZA AY210"), driver_family="windows-hid-game"),
    ProductSpec("moza_ab6", "MOZA AB6 FFB Base", ("hid", "sdl"), "muslimsim.devices.moza_a210", usb_ids=((0x346E, 0x1002),), product_tokens=("MOZA AB6",), driver_family="windows-hid-game"),
)

PRODUCT_BY_KEY: Dict[str, ProductSpec] = {item.key: item for item in PRODUCTS}


def product_by_key(key: str) -> Optional[ProductSpec]:
    return PRODUCT_BY_KEY.get(str(key))


def products_for_usb(vendor_id: int, product_id: int) -> Tuple[ProductSpec, ...]:
    identity = (int(vendor_id), int(product_id))
    return tuple(item for item in PRODUCTS if identity in item.usb_ids)


def product_for_usb(vendor_id: int, product_id: int) -> Optional[ProductSpec]:
    matches = products_for_usb(vendor_id, product_id)
    return matches[0] if len(matches) == 1 else None


def product_for_text(*values: object) -> Optional[ProductSpec]:
    matches = tuple(item for item in PRODUCTS if item.matches_text(*values))
    return matches[0] if len(matches) == 1 else None



def products_for_runtime_text(
    *values: object,
    transports: Sequence[str] = (),
) -> Tuple[ProductSpec, ...]:
    """Return products matching runtime-visible text, optionally by transport.

    Product strings may be used to recognise a model, but a unit serial,
    SDL index, HID path or COM number is never consulted here.
    """
    allowed = {str(item).strip().casefold() for item in transports if str(item).strip()}
    matches = []
    for item in PRODUCTS:
        if allowed and not allowed.intersection(t.casefold() for t in item.transports):
            continue
        if item.matches_text(*values):
            matches.append(item)
    return tuple(matches)


def product_for_runtime_text(
    *values: object,
    transports: Sequence[str] = (),
) -> Optional[ProductSpec]:
    """Resolve one stable product from runtime text without locator identity."""
    matches = products_for_runtime_text(*values, transports=transports)
    return matches[0] if len(matches) == 1 else None


def product_for_protocol_name(value: object) -> Optional[ProductSpec]:
    matches = tuple(item for item in PRODUCTS if item.matches_protocol_name(value))
    return matches[0] if len(matches) == 1 else None


def winctrl_pid_map() -> Dict[int, Tuple[str, str]]:
    result: Dict[int, Tuple[str, str]] = {}
    for item in PRODUCTS:
        for vid, pid in item.usb_ids:
            if vid == 0x4098:
                result[int(pid)] = (item.key, item.title)
    return result


def generic_usb_map() -> Dict[Tuple[int, int], Tuple[str, str]]:
    result: Dict[Tuple[int, int], Tuple[str, str]] = {}
    for item in PRODUCTS:
        # WINCTRL is handled by the PID map above. HOWALT is shared and must
        # not be guessed from VID/PID alone.
        for vid, pid in item.usb_ids:
            if vid in {0x4098, 0x1A86} or item.key == "tca_boeing":
                continue
            result[(int(vid), int(pid))] = (item.key, item.title)
    return result


__all__ = [
    "ProductSpec", "PRODUCTS", "PRODUCT_BY_KEY", "product_by_key",
    "products_for_usb", "product_for_usb", "product_for_text",
    "products_for_runtime_text", "product_for_runtime_text",
    "product_for_protocol_name", "winctrl_pid_map", "generic_usb_map",
]

MUSLIMSIM_PORTABLE_DEVICE_PLATFORM_V2_REGISTRY = True

MUSLIMSIM_PORTABLE_DEVICE_PLATFORM_V3_DRIVER_FAMILIES = True


def _extend_with_community() -> None:
    """Append community JSON profiles to PRODUCTS at startup.

    Uses a lazy import so there is no circular dependency: device_profiles.py
    imports ProductSpec from this module, but only after this module has
    already finished defining it.  A missing community folder or any load
    error is silently ignored so a packaged .exe without the folder works.
    """
    global PRODUCTS, PRODUCT_BY_KEY
    try:
        from muslimsim.hardware.device_profiles import load_community_products
        community = load_community_products()
        if not community:
            return
        existing_keys = {item.key for item in PRODUCTS}
        new_items = tuple(item for item in community if item.key not in existing_keys)
        if new_items:
            PRODUCTS = PRODUCTS + new_items
            PRODUCT_BY_KEY = {item.key: item for item in PRODUCTS}
    except Exception:
        pass


_extend_with_community()

MUSLIMSIM_COMMUNITY_PROFILE_SYSTEM_V1 = True
