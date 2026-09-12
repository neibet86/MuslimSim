"""Community device profile loader — MUSLIMSIM_COMMUNITY_PROFILE_SYSTEM_V1.

Reads JSON profiles from the ``community/devices/`` folder beside the project
root and converts them into the same ProductSpec / DeviceSpec / ControlSpec
objects used by the built-in Python registry and catalog.

This module:
- Never opens hardware.
- Never modifies any built-in constant in product_registry or catalog.
- Fails silently when the community folder is absent (packaged .exe builds).
- Caches results for the process lifetime so JSON is read exactly once.
"""
from __future__ import annotations

import json
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple

from .product_registry import ProductSpec
from .catalog import ControlSpec, DeviceSpec

_SCHEMA = "muslimsim-device-v1"


def _community_dir() -> Path:
    return Path(__file__).parent.parent.parent / "community" / "devices"


def _control_from_dict(d: object, direction: str) -> Optional[ControlSpec]:
    if not isinstance(d, dict):
        return None
    key = str(d.get("key", "")).strip()
    if not key:
        return None
    status = str(d.get("status", "implemented"))
    return ControlSpec(
        key=key,
        label=str(d.get("label", key)),
        kind=str(d.get("kind", "button")),
        direction=direction,
        raw=str(d.get("raw", "community profile")),
        status=status,
        remappable=bool(d.get("remappable", direction == "input" and status == "implemented")),
        testable=bool(d.get("testable", direction == "input" and status == "implemented")),
        choices=tuple(str(c) for c in d.get("choices", ())),
        notes=str(d.get("notes", "")),
    )


def _load_one(path: Path) -> Tuple[Optional[ProductSpec], Optional[DeviceSpec], Dict[str, str]]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        warnings.warn(f"MuslimSim community profile {path.name}: load error — {exc}")
        return None, None, {}

    if not isinstance(data, dict) or data.get("schema") != _SCHEMA:
        warnings.warn(f"MuslimSim community profile {path.name}: unknown schema")
        return None, None, {}

    key = str(data.get("key", "")).strip()
    if not key:
        return None, None, {}

    usb_ids: Tuple[Tuple[int, int], ...] = ()
    for pair in data.get("usb_ids", []):
        try:
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                usb_ids += ((int(str(pair[0]), 0), int(str(pair[1]), 0)),)
        except (ValueError, TypeError):
            pass

    product = ProductSpec(
        key=key,
        title=str(data.get("title", key)),
        transports=tuple(str(t) for t in data.get("transports", ["hid"])),
        driver=str(data.get("driver", "muslimsim.hardware.generic_hid")),
        usb_ids=usb_ids,
        product_tokens=tuple(str(t) for t in data.get("product_tokens", [])),
        serial_protocol_names=tuple(str(n) for n in data.get("serial_protocol_names", [])),
        notes=str(data.get("notes", "")),
        replaceable_unit=bool(data.get("replaceable_unit", True)),
        driver_family=str(data.get("driver_family", "windows-hid-game")),
    )

    controls: Tuple[ControlSpec, ...] = ()
    for item in data.get("inputs", []):
        c = _control_from_dict(item, "input")
        if c is not None:
            controls += (c,)
    for item in data.get("outputs", []):
        c = _control_from_dict(item, "output")
        if c is not None:
            controls += (c,)

    transport_label = " / ".join(t.upper() for t in data.get("transports", ["HID"]))
    identity = " • ".join(
        f"VID {vid:04X} / PID {pid:04X}" for vid, pid in usb_ids
    ) or "Community profile"

    device = DeviceSpec(
        key=key,
        title=str(data.get("title", key)),
        transport=transport_label,
        identity=identity,
        driver=str(data.get("driver", "muslimsim.hardware.generic_hid")),
        status="implemented",
        notes=str(data.get("notes", "")),
        controls=controls,
        aliases=tuple(str(a) for a in data.get("aliases", [])),
    )

    default_roles: Dict[str, str] = {
        str(k): str(v) for k, v in data.get("default_roles", {}).items()
    }

    return product, device, default_roles


@lru_cache(maxsize=1)
def _load_all() -> Tuple[
    Tuple[ProductSpec, ...],
    Tuple[DeviceSpec, ...],
    Dict[str, Dict[str, str]],
]:
    """Load all community profiles exactly once per process."""
    products: Tuple[ProductSpec, ...] = ()
    devices: Tuple[DeviceSpec, ...] = ()
    roles: Dict[str, Dict[str, str]] = {}

    cdir = _community_dir()
    if not cdir.is_dir():
        return products, devices, roles

    for path in sorted(cdir.glob("*.json")):
        product, device, default_roles = _load_one(path)
        if product is None or device is None:
            continue
        # Skip if a key already exists in built-in registry — built-ins win.
        products += (product,)
        devices += (device,)
        if default_roles:
            roles[device.key] = default_roles

    return products, devices, roles


def load_community_products() -> Tuple[ProductSpec, ...]:
    return _load_all()[0]


def load_community_hardware() -> Tuple[DeviceSpec, ...]:
    return _load_all()[1]


def community_default_roles() -> Dict[str, Dict[str, str]]:
    return _load_all()[2]


def community_device_by_key(key: str) -> Optional[DeviceSpec]:
    wanted = str(key).strip().lower()
    for device in load_community_hardware():
        if wanted == device.key or wanted in device.aliases:
            return device
    return None


def reload_community_profiles() -> None:
    """Clear the cache so the next call re-reads disk (useful in tests)."""
    _load_all.cache_clear()


__all__ = [
    "load_community_products",
    "load_community_hardware",
    "community_default_roles",
    "community_device_by_key",
    "reload_community_profiles",
]

MUSLIMSIM_COMMUNITY_PROFILE_SYSTEM_V1 = True
