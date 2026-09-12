"""Read-only discovery of currently attached MuslimSim / WINCTRL HID units.

The configuration studio uses this module only to identify devices.  Opening
or driving an HID report remains the bridge's responsibility.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import os
import re
import subprocess
from typing import Any, Dict, Iterable, Mapping

from .product_registry import (
    generic_usb_map, product_for_runtime_text, winctrl_pid_map,
)

try:  # Keep the studio usable on a machine where HID support is not installed.
    import hid
except ImportError:  # pragma: no cover - depends on a local optional package
    hid = None

try:  # SDL sees DirectInput/XInput gaming hardware that does not expose HID strings.
    import pygame
except ImportError:  # pragma: no cover - depends on a local optional package
    pygame = None


WINCTRL_VENDOR_ID = 0x4098


@dataclass(frozen=True)
class DetectedDevice:
    key: str
    title: str
    vendor_id: int
    product_id: int
    product: str
    manufacturer: str
    serial: str
    firmware: str
    connected: bool = True
    recognised: bool = False
    source: str = "hid"

    def snapshot(self) -> Dict[str, Any]:
        return asdict(self)


_KNOWN: Dict[int, tuple[str, str]] = winctrl_pid_map()

# Captured from the Windows controller GUID and then confirmed by its present
# HID VID/PID.  Unlike an unknown controller, this is the already-supported
# serial/SDL PU Overhead, so it is safe to open its existing catalogue page.
# >>> MUSLIMSIM PDC CLEAN DISCOVERY V1 >>>
_KNOWN = dict(_KNOWN)
_KNOWN[0xBB61] = ("pdc_bb61_left",  "WINCTRL 3N PDC")
_KNOWN[0xBB51] = ("pdc_bb61_left",  "WINCTRL 3M PDC")
_KNOWN[0xBB52] = ("pdc_bb52_right", "WINCTRL 3M PDC")
_KNOWN[0xBB3D] = ("pfp3n_bb35",     "WINCTRL 3N PFP")
_KNOWN[0xBB39] = ("pfp3n_bb35",     "WINCTRL 3N PFP")
_KNOWN[0xBB3E] = ("mcdu32_bb36",    "WINCTRL 32 MCDU")
_KNOWN[0xBB3A] = ("mcdu32_bb36",    "WINCTRL 32 MCDU")
# <<< MUSLIMSIM PDC CLEAN DISCOVERY V1 <<<

_KNOWN_GENERIC_USB: Dict[tuple[int, int], tuple[str, str]] = generic_usb_map()

_GAMING_MARKERS = (
    "game", "gaming", "controller", "joystick", "throttle", "rudder",
    "pedal", "yoke", "flight", "hotas", "virpil", "vkb", "saitek",
    "logitech", "thrustmaster", "honeycomb", "turtle beach", "winctrl",
    "winwing", "ursa", "orion", "pu overhead", "pu ovhd", "moza",
)
_PNP_BRANDED_GAMING_MARKERS = tuple(
    marker for marker in _GAMING_MARKERS if marker not in {"game", "gaming", "controller"}
)


def _known_game_controller(name: str, vendor_id: int = 0) -> tuple[str, str] | None:
    """Return a verified catalogue key from the shared product registry.

    SDL index and GUID are deliberately not consulted. This keeps discovery
    aligned with the bridge's one SDL owner and lets a replacement unit of the
    same model inherit the same MuslimSim key.
    """
    spec = product_for_runtime_text(
        name, transports=("sdl", "usb-gaming")
    )
    if spec is None:
        return None
    if vendor_id and spec.usb_ids and all(vid != vendor_id for vid, _pid in spec.usb_ids):
        return None
    return (spec.key, spec.title)


def canonical_device_key(key: str, *identity_fields: object) -> str:
    """Collapse product/driver aliases onto one real MuslimSim device key.

    USB HID, SDL and serial drivers may use different names for the same
    piece of hardware.  In particular ``PU OVHD 737`` and ``PU Overhead``
    are one physical PU panel, not two separate rows or mappings.
    """

    text = " ".join((str(key), *(str(value) for value in identity_fields))).casefold()
    if "pu ovhd" in text or "pu overhead" in text:
        return "pu_overhead"
    if "moza" in text and "ab6" in text:
        return "moza_ab6"
    if "moza" in text and ("a210" in text or "ay210" in text):
        return "moza_a210"
    return str(key)


def _canonical_device(device: DetectedDevice) -> DetectedDevice:
    key = canonical_device_key(device.key, device.title, device.product, device.manufacturer)
    labels = {
        "pu_overhead": "PU Overhead",
        "moza_a210": "MOZA A210 Base + detachable yoke",
        "moza_ab6": "MOZA AB6 FFB Base",
    }
    if key not in labels:
        return device
    return replace(device, key=key, title=labels[key], recognised=True)


def _unknown_key(vendor_id: int, product_id: int, item: Mapping[str, Any]) -> str:
    """Keep every unrecognised attached panel visible without collisions."""

    identity = str(item.get("serial_number") or item.get("path") or "attached")
    suffix = re.sub(r"[^a-z0-9]+", "-", identity.casefold()).strip("-")[:36] or "attached"
    return f"unrecognised_hid_{vendor_id:04x}_{product_id:04x}_{suffix}"


def _is_audio_or_camera(name: str) -> bool:
    return bool(re.search(r"\b(headsets?|headphones?|speakers?|microphones?|webcams?)\b", name, re.I))


def hardware_presence(state: Mapping[str, Any]) -> bool | None:
    """Physical connection evidence only; simulator/aircraft power is unrelated."""
    for field in ("usb_connected", "present"):
        if isinstance(state.get(field), bool):
            return state[field]
    # Generic service connection/state can refer to the simulator, a display
    # producer or a restarting reader. It cannot disprove a positive USB scan.
    label = str(state.get("state") or "").strip().lower()
    if label in {"unplugged", "waiting-for-usb"}:
        return False
    if state.get("connected") is True or label == "connected":
        return True
    return None


def _looks_like_gaming_hardware(item: Mapping[str, Any]) -> bool:
    """Filter the full HID inventory to likely gaming/flight hardware.

    Some WinCtrl firmware revisions advertise a different VID while retaining
    WINCTRL/WINWING in their USB strings.  The former vendor-only discovery
    silently excluded those units.  A device with a known WINCTRL product ID
    is still included even if its strings are blank.
    """

    vendor_id = int(item.get("vendor_id") or 0)
    product_id = int(item.get("product_id") or 0)
    if vendor_id == WINCTRL_VENDOR_ID or (vendor_id, product_id) in _KNOWN_GENERIC_USB:
        return True
    text = " ".join(
        str(item.get(field) or "")
        for field in ("product_string", "manufacturer_string", "serial_number")
    ).casefold()
    if _is_audio_or_camera(text):
        return False
    if int(item.get("usage_page") or 0) == 1 and int(item.get("usage") or 0) in {4, 5, 8}:
        return True
    return any(marker in text for marker in _GAMING_MARKERS)


def _controller_key(name: str, index: int, guid: str = "") -> str:
    identity = re.sub(r"[^a-z0-9]+", "-", f"{guid}-{name}".casefold()).strip("-")[:48]
    return f"game_controller_{identity or 'attached'}_{index}"


def _sdl_guid_usb_identity(guid: str) -> tuple[int, int] | None:
    """Read the USB VID/PID embedded in a Windows SDL controller GUID.

    A panel may be exposed both as HID and as a DirectInput controller.  The
    HID entry has the richer identity and known device map, so do not add a
    second, misleading “needs a definition” row for that same hardware.
    Non-USB/XInput GUIDs deliberately return ``None`` and remain visible.
    """

    compact = re.sub(r"[^0-9a-f]", "", guid.casefold())
    if len(compact) != 32:
        return None
    try:
        vendor_id = int.from_bytes(bytes.fromhex(compact[8:12]), "little")
        product_id = int.from_bytes(bytes.fromhex(compact[16:20]), "little")
    except ValueError:
        return None
    return (vendor_id, product_id) if vendor_id and product_id else None


def _windows_usb_identity(instance_id: str) -> tuple[int, int] | None:
    """Extract VID/PID from a Windows PnP HID instance identifier."""

    match = re.search(r"VID_([0-9A-F]{4}).*?PID_([0-9A-F]{4})", instance_id, flags=re.IGNORECASE)
    if match is None:
        return None
    return (int(match.group(1), 16), int(match.group(2), 16))


def _discover_windows_game_controllers() -> list[DetectedDevice]:
    """Read Windows' present HID game-controller records without opening HID.

    Some device drivers hide their input interface from hidapi/SDL while
    Windows still reports a present ``HID-compliant game controller``.  This
    gives any brand a visible safe placeholder.  The child bridge calls this
    only from its worker and the loopback server caches the result, so neither
    a device scan nor a Windows query can freeze Studio.
    """

    if os.name != "nt":
        return []
    command = (
        "Get-PnpDevice -PresentOnly -Class HIDClass | "
        "Select-Object FriendlyName,InstanceId,Status | ConvertTo-Json -Compress"
    )
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=2.5,
            check=False,
            creationflags=creationflags,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            return []
        raw_items = json.loads(completed.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []
    rows = raw_items if isinstance(raw_items, list) else [raw_items]
    found: list[DetectedDevice] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("Status") or "OK").casefold() != "ok":
            continue
        name = str(row.get("FriendlyName") or "Windows game controller")
        if _is_audio_or_camera(name):
            continue
        instance_id = str(row.get("InstanceId") or "")
        identity = _windows_usb_identity(instance_id)
        text = f"{name} {instance_id}".casefold()
        # Windows also exposes unrelated HID *system controllers*.  Keep the
        # neutral “HID-compliant game controller” class and recognised flight
        # brands, but do not clutter Studio with keyboards/media hardware.
        if "game controller" not in text and not any(marker in text for marker in _PNP_BRANDED_GAMING_MARKERS):
            continue
        vendor_id, product_id = identity or (0, 0)
        known = (
            _KNOWN.get(product_id)
            if vendor_id == WINCTRL_VENDOR_ID
            else _KNOWN_GENERIC_USB.get((vendor_id, product_id))
        )
        if known is None:
            known = _known_game_controller(f"{name} {instance_id}", vendor_id)
        label = known[1] if known else (
            f"{name} (USB {vendor_id:04X}:{product_id:04X})  —  needs a control definition"
            if identity else f"{name}  —  needs a control definition"
        )
        found.append(DetectedDevice(
            key=known[0] if known else _unknown_key(vendor_id, product_id, {"serial_number": instance_id}),
            title=label,
            vendor_id=vendor_id,
            product_id=product_id,
            product=name,
            manufacturer="Windows HID game controller",
            serial=instance_id,
            firmware="reported by Windows",
            recognised=known is not None,
            source="windows",
        ))
    return found


def _discover_game_controllers() -> list[DetectedDevice]:
    """Read SDL's Windows game-controller list without changing any input.

    HID product strings are not guaranteed for DirectInput/XInput devices.
    SDL is the already-used controller layer for pedals/throttles, so it is
    the correct second source for generic gaming devices.  This only opens
    the joystick subsystem to read names/IDs; no input is consumed or output
    report is sent.
    """

    if pygame is None:
        return []
    try:
        if not pygame.joystick.get_init():
            pygame.joystick.init()
        count = int(pygame.joystick.get_count())
    except Exception:
        return []
    found: list[DetectedDevice] = []
    for index in range(max(0, count)):
        try:
            joystick = pygame.joystick.Joystick(index)
            if not joystick.get_init():
                joystick.init()
            name = str(joystick.get_name() or f"Game controller {index + 1}")
            get_guid = getattr(joystick, "get_guid", None)
            guid = str(get_guid() or "") if callable(get_guid) else ""
            get_instance = getattr(joystick, "get_instance_id", None)
            instance = int(get_instance()) if callable(get_instance) else index
        except Exception:
            continue
        known = _known_game_controller(name)
        found.append(DetectedDevice(
            key=known[0] if known else _controller_key(name, instance, guid),
            title=known[1] if known else f"{name}  —  needs a control definition",
            vendor_id=0,
            product_id=0,
            product=name,
            manufacturer="Gaming controller",
            serial=guid or f"SDL controller {instance}",
            firmware="reported by Windows game-controller layer",
            recognised=known is not None,
            source="sdl",
        ))
    return found


def discover_hid_devices(*, include_sdl: bool = True) -> list[DetectedDevice]:
    """Return present supported and unrecognised gaming-panel devices.

    This does not open a handle or send any report.  An unknown unit is shown
    with its real USB identity so the owner can see it immediately; it does
    not receive a guessed control map or any output write.
    """

    found: list[DetectedDevice] = []
    hid_identities: set[tuple[int, int]] = set()
    if hid is not None:
        try:
            inventory = hid.enumerate()
        except Exception:
            inventory = ()
        for item in inventory:
            if not isinstance(item, Mapping) or not _looks_like_gaming_hardware(item):
                continue
            product_id = int(item.get("product_id") or 0)
            vendor_id = int(item.get("vendor_id") or 0)
            if vendor_id and product_id:
                hid_identities.add((vendor_id, product_id))
            known = (
                _KNOWN.get(product_id)
                if vendor_id == WINCTRL_VENDOR_ID
                else _KNOWN_GENERIC_USB.get((vendor_id, product_id))
            )
            if known is None:
                known = _known_game_controller(
                    " ".join(str(item.get(field) or "") for field in ("product_string", "manufacturer_string", "serial_number")), vendor_id
                )
            # >>> MUSLIMSIM WINCTRL PANEL CATCH-ALL V1 >>>
            # Any WinCtrl panel model/PID not yet in _KNOWN is immediately
            # recognised — no user ever sees "needs a control definition".
            # Recognised by product string keywords; Studio role picker sets
            # Captain/FO and the assignment persists in config/panel_roles.json.
            if known is None and vendor_id == WINCTRL_VENDOR_ID:
                pstr = str(item.get("product_string") or "").upper()
                if "PFP" in pstr:
                    known = ("pfp3n_bb35", "WinCtrl PFP panel")
                elif "MCDU" in pstr:
                    known = ("mcdu32_bb36", "WinCtrl MCDU panel")
                elif "PDC" in pstr:
                    is_right = " PDC R" in pstr or pstr.endswith("PDC R")
                    known = (
                        ("pdc_bb52_right", "WinCtrl PDC")
                        if is_right else
                        ("pdc_bb61_left",  "WinCtrl PDC")
                    )
            # <<< MUSLIMSIM WINCTRL PANEL CATCH-ALL V1 <<<
            key, fallback = known or (_unknown_key(vendor_id, product_id, item), "Unrecognised gaming HID panel")
            product = str(item.get("product_string") or fallback)
            release = int(item.get("release_number") or 0)
            found.append(DetectedDevice(
                key=key,
                title=fallback if known else f"{product}  —  needs a control definition",
                vendor_id=vendor_id,
                product_id=product_id,
                product=product,
                manufacturer=str(item.get("manufacturer_string") or "Gaming HID device"),
                serial=str(item.get("serial_number") or ""),
                firmware=f"0x{release:04X}" if release else "reported by device",
                recognised=known is not None,
            ))
    # Do not enumerate SDL joysticks from the Windows live bridge.  Creating
    # a pygame Joystick object opens a DirectInput handle; Studio's background
    # discovery refresh used to do that just before the dedicated PU/throttle
    # reader and could leave every maintained switch and B930 axis silent.
    # Windows PnP inventory below detects generic gaming devices without
    # opening their input interface.  Non-Windows builds retain the SDL-only
    # fallback because they do not share this DirectInput ownership hazard.
    sdl_devices = [] if not include_sdl else [
        device for device in _discover_game_controllers()
        if _sdl_guid_usb_identity(device.serial) not in hid_identities
    ]
    found.extend(sdl_devices)
    observed_identities = set(hid_identities)
    observed_identities.update(
        identity for device in sdl_devices
        if (identity := _sdl_guid_usb_identity(device.serial)) is not None
    )
    found.extend(
        device for device in _discover_windows_game_controllers()
        if (device.vendor_id, device.product_id) not in observed_identities
    )
    # Keep every physical device separate.  A few HID APIs can surface more
    # than one interface for one panel; retaining a unique unknown key makes
    # the duplicate diagnosable rather than disappearing in a dictionary.
    seen: set[str] = set()
    unique: list[DetectedDevice] = []
    for device in sorted((_canonical_device(item) for item in found), key=lambda value: (not value.recognised, value.title, value.serial, value.product_id)):
        if device.key in seen:
            # Known composite panels intentionally use one canonical Studio
            # page.  Unknown HID duplicates carry a serial/path key and SDL
            # controllers carry an instance key, so neither disappears.
            continue
        seen.add(device.key)
        unique.append(device)
    return unique


def discovery_snapshot(*, include_sdl: bool = True) -> Mapping[str, object]:
    snapshot: Dict[str, object] = {
        "devices": [
            device.snapshot()
            for device in discover_hid_devices(include_sdl=include_sdl)
        ]
    }
    # Additive platform information for Studio/diagnostics. Existing callers
    # that only read ``devices`` keep exactly the same contract.
    try:
        from .device_manager import product_runtime_snapshot
        from .runtime_bundle import dependency_snapshot
        snapshot["platform"] = product_runtime_snapshot()
        snapshot["runtime"] = dependency_snapshot()
    except Exception as exc:
        snapshot["platform_error"] = f"{type(exc).__name__}: {exc}"
    return snapshot

MUSLIMSIM_PORTABLE_DEVICE_PLATFORM_V2_DISCOVERY = True
