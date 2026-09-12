"""Universal MuslimSim product discovery and runtime locator service.

MUSLIMSIM_PORTABLE_DEVICE_PLATFORM_V1

This layer intentionally separates *identity* from *location*:

- identity: stable product VID/PID, product strings and protocol name;
- location: COM number, HID path, SDL instance index, Windows PnP path.

A location may change after reboot or unplug/replug.  It is never persisted as
the identity of a supported device and a serial number is never required to
accept a replacement unit of the same product.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
import re
import subprocess
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .product_registry import (
    ProductSpec, PRODUCTS, product_by_key, product_for_runtime_text,
)

try:
    from serial.tools import list_ports  # type: ignore
except Exception:  # pragma: no cover - runtime dependency / frozen environment
    list_ports = None

try:
    import hid  # type: ignore
except Exception:  # pragma: no cover - runtime dependency / frozen environment
    hid = None

try:
    import pygame  # type: ignore
except Exception:  # pragma: no cover - runtime dependency / frozen environment
    pygame = None


@dataclass(frozen=True)
class SerialEndpoint:
    port: str
    vendor_id: int = 0
    product_id: int = 0
    description: str = ""
    manufacturer: str = ""
    product: str = ""
    hwid: str = ""
    pnp_id: str = ""
    source: str = "serial"

    def searchable_text(self) -> str:
        return " ".join((
            self.port, self.description, self.manufacturer, self.product,
            self.hwid, self.pnp_id,
        )).casefold()

    def snapshot(self) -> Dict[str, Any]:
        # No serial_number field by design: a replacement unit remains the
        # same supported product.
        return asdict(self)



@dataclass(frozen=True)
class HIDEndpoint:
    path: str
    vendor_id: int = 0
    product_id: int = 0
    product: str = ""
    manufacturer: str = ""
    interface_number: int = -1
    usage_page: int = 0
    usage: int = 0
    source: str = "hid-enumeration"

    def searchable_text(self) -> str:
        return " ".join((self.product, self.manufacturer)).casefold()

    def snapshot(self) -> Dict[str, Any]:
        # `path` is deliberately exposed only as a current runtime locator.
        # No serial number is stored or returned as product identity.
        return asdict(self)


@dataclass(frozen=True)
class HIDResolution:
    device_key: str
    paths: Tuple[str, ...]
    matched_by: str

    def snapshot(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SDLControllerEndpoint:
    index: int
    instance_id: int
    name: str
    guid: str = ""
    source: str = "sdl"

    def snapshot(self) -> Dict[str, Any]:
        # index / instance_id / GUID are runtime locators only. None are a
        # persisted replacement-unit identity.
        return asdict(self)


@dataclass(frozen=True)
class SDLResolution:
    device_key: str
    index: int
    instance_id: int
    matched_by: str
    candidates: Tuple[int, ...]

    def snapshot(self) -> Dict[str, Any]:
        return asdict(self)



@dataclass(frozen=True)
class SerialResolution:
    device_key: str
    port: str
    matched_by: str
    candidates: Tuple[str, ...]

    def snapshot(self) -> Dict[str, Any]:
        return asdict(self)


def _normalise_port(value: object) -> str:
    text = str(value or "").strip()
    return text.upper() if re.fullmatch(r"COM\d+", text, flags=re.IGNORECASE) else text


def _int_or_zero(value: object) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _pyserial_endpoints() -> List[SerialEndpoint]:
    if list_ports is None:
        return []
    try:
        rows = list(list_ports.comports())
    except Exception:
        return []
    result: List[SerialEndpoint] = []
    for row in rows:
        port = _normalise_port(getattr(row, "device", ""))
        if not port:
            continue
        result.append(SerialEndpoint(
            port=port,
            vendor_id=_int_or_zero(getattr(row, "vid", 0)),
            product_id=_int_or_zero(getattr(row, "pid", 0)),
            description=str(getattr(row, "description", "") or ""),
            manufacturer=str(getattr(row, "manufacturer", "") or ""),
            product=str(getattr(row, "product", "") or ""),
            hwid=str(getattr(row, "hwid", "") or ""),
            pnp_id=str(getattr(row, "pnp_id", "") or ""),
            source="pyserial",
        ))
    return result


def _extract_usb_id(text: object) -> Tuple[int, int]:
    value = str(text or "")
    match = re.search(
        r"VID[_:=]([0-9A-F]{4}).*?PID[_:=]([0-9A-F]{4})",
        value, flags=re.IGNORECASE,
    )
    if match is None:
        return (0, 0)
    return (int(match.group(1), 16), int(match.group(2), 16))


def _windows_serial_endpoints() -> List[SerialEndpoint]:
    """Read Windows COM inventory and its short PnP ancestor chain without opening it.

    Composite cockpit hardware may expose its COM child with a generic
    ``USB Serial Device`` name while the stable product VID/PID exists only on
    a parent USB interface/device. Walking up to four ancestors lets the same
    PU resolve after COM renumbering without relying on a friendly-name guess.
    """
    if os.name != "nt":
        return []
    command = r"""
$rows = Get-PnpDevice -PresentOnly -Class Ports -ErrorAction SilentlyContinue | ForEach-Object {
    $ancestors = @()
    $current = $_.InstanceId
    for ($depth = 0; $depth -lt 4; $depth++) {
        try {
            $parent = (Get-PnpDeviceProperty -InstanceId $current -KeyName 'DEVPKEY_Device_Parent' -ErrorAction Stop).Data
            if ([string]::IsNullOrWhiteSpace($parent)) { break }
            $ancestors += $parent
            $current = $parent
        } catch { break }
    }
    [PSCustomObject]@{
        FriendlyName = $_.FriendlyName
        InstanceId = $_.InstanceId
        Ancestors = ($ancestors -join ' | ')
        Status = $_.Status
    }
}
$rows | ConvertTo-Json -Compress
"""
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=3.0, check=False,
            creationflags=creationflags,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            return []
        raw = json.loads(completed.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []
    rows = raw if isinstance(raw, list) else [raw]
    result: List[SerialEndpoint] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        friendly = str(row.get("FriendlyName") or "")
        match = re.search(r"\((COM\d+)\)", friendly, flags=re.IGNORECASE)
        if match is None:
            continue
        port = _normalise_port(match.group(1))
        instance = str(row.get("InstanceId") or "")
        ancestors = str(row.get("Ancestors") or "")
        vid, pid = _extract_usb_id(instance + " " + ancestors)
        result.append(SerialEndpoint(
            port=port,
            vendor_id=vid,
            product_id=pid,
            description=friendly,
            manufacturer="Windows Ports class",
            product=friendly,
            pnp_id=(instance + " | ancestors=" + ancestors).strip(),
            source="windows-pnp-ancestors",
        ))
    return result


def serial_endpoints() -> Tuple[SerialEndpoint, ...]:
    """Return present serial endpoints, deduplicated by runtime COM locator."""
    combined = _pyserial_endpoints() + _windows_serial_endpoints()
    merged: Dict[str, SerialEndpoint] = {}
    for endpoint in combined:
        key = endpoint.port.upper()
        old = merged.get(key)
        if old is None:
            merged[key] = endpoint
            continue
        # Prefer the record carrying a structured USB VID/PID. Keep the
        # pyserial description when it is richer than Windows' generic name.
        if not old.vendor_id and endpoint.vendor_id:
            merged[key] = endpoint
    return tuple(sorted(merged.values(), key=lambda item: item.port))


def _serial_score(endpoint: SerialEndpoint, spec: ProductSpec) -> Tuple[int, str]:
    identity = (int(endpoint.vendor_id), int(endpoint.product_id))
    if identity in spec.usb_ids:
        return (100, "usb-vid-pid")
    text = endpoint.searchable_text()
    for token in spec.product_tokens:
        if token.casefold() in text:
            return (80, "product-string")
    # Some Windows PnP strings expose VID/PID text while pyserial leaves
    # structured vid/pid unset.
    for vid, pid in spec.usb_ids:
        probes = (
            f"vid_{vid:04x}&pid_{pid:04x}",
            f"vid:pid={vid:04x}:{pid:04x}",
            f"vid_{vid:04x}+pid_{pid:04x}",
        )
        if any(probe in text for probe in probes):
            return (95, "usb-pnp-id")
    return (0, "")


def resolve_serial_port(
    device_key: str,
    *,
    preferred: object = None,
    endpoints: Optional[Sequence[SerialEndpoint]] = None,
) -> Optional[SerialResolution]:
    """Resolve a product to its *current* COM port without serial-number lock.

    If more than one equally strong candidate exists, the resolver refuses to
    guess unless the caller's previous/preferred runtime port is one of those
    tied candidates. This prevents opening a different cockpit panel merely
    because Windows changed enumeration order.
    """
    spec = product_by_key(device_key)
    if spec is None or "serial" not in spec.transports:
        return None
    inventory = tuple(endpoints) if endpoints is not None else serial_endpoints()
    scored: List[Tuple[int, str, SerialEndpoint]] = []
    for endpoint in inventory:
        score, reason = _serial_score(endpoint, spec)
        if score:
            scored.append((score, reason, endpoint))
    if not scored:
        return None
    highest = max(item[0] for item in scored)
    finalists = [item for item in scored if item[0] == highest]
    preferred_port = _normalise_port(preferred)
    if preferred_port:
        for score, reason, endpoint in finalists:
            if endpoint.port.upper() == preferred_port.upper():
                return SerialResolution(
                    device_key=spec.key, port=endpoint.port,
                    matched_by=reason + "+preferred-runtime-port",
                    candidates=tuple(item[2].port for item in finalists),
                )
    if len(finalists) != 1:
        return None
    score, reason, endpoint = finalists[0]
    return SerialResolution(
        device_key=spec.key, port=endpoint.port, matched_by=reason,
        candidates=tuple(item[2].port for item in finalists),
    )


def resolve_serial_port_name(
    device_key: str,
    *,
    preferred: object = None,
) -> Optional[str]:
    resolution = resolve_serial_port(device_key, preferred=preferred)
    return resolution.port if resolution is not None else None



def _path_text(value: object) -> str:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return value.hex()
    return str(value or "")


def hid_endpoints(
    inventory: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Tuple[HIDEndpoint, ...]:
    """Enumerate current HID locators without opening a HID handle."""
    if inventory is None:
        if hid is None:
            rows: Sequence[Mapping[str, Any]] = ()
        else:
            try:
                enumerated = hid.enumerate()
            except Exception:
                enumerated = ()
            rows = tuple(item for item in enumerated if isinstance(item, Mapping))
    else:
        rows = tuple(item for item in inventory if isinstance(item, Mapping))

    result: List[HIDEndpoint] = []
    for row in rows:
        vid = _int_or_zero(row.get("vendor_id"))
        pid = _int_or_zero(row.get("product_id"))
        product = str(row.get("product_string") or "")
        manufacturer = str(row.get("manufacturer_string") or "")

        # Keep only devices that can map to a supported HID product. Shared
        # HOWALT WCH serial interfaces are intentionally not treated as HID.
        spec = None
        if vid and pid:
            candidates = [
                item for item in PRODUCTS
                if "hid" in item.transports and (vid, pid) in item.usb_ids
            ]
            if len(candidates) == 1:
                spec = candidates[0]
        if spec is None:
            spec = product_for_runtime_text(
                product, manufacturer, transports=("hid",)
            )
        if spec is None:
            continue

        path = _path_text(row.get("path")).strip()
        if not path:
            continue
        result.append(HIDEndpoint(
            path=path,
            vendor_id=vid,
            product_id=pid,
            product=product,
            manufacturer=manufacturer,
            interface_number=_int_or_zero(row.get("interface_number", -1)),
            usage_page=_int_or_zero(row.get("usage_page")),
            usage=_int_or_zero(row.get("usage")),
        ))
    return tuple(result)


def resolve_hid_interfaces(
    device_key: str,
    *,
    endpoints: Optional[Sequence[HIDEndpoint]] = None,
) -> Optional[HIDResolution]:
    """Resolve a stable product to all of its current HID interface paths.

    Multiple interfaces are returned together instead of guessing which HID
    interface a device-specific driver needs. Existing proven drivers remain
    free to choose the interface/usage they already understand.
    """
    spec = product_by_key(device_key)
    if spec is None or "hid" not in spec.transports:
        return None
    inventory = tuple(endpoints) if endpoints is not None else hid_endpoints()
    matched: List[HIDEndpoint] = []
    reasons = set()
    for endpoint in inventory:
        identity = (endpoint.vendor_id, endpoint.product_id)
        if identity in spec.usb_ids:
            matched.append(endpoint)
            reasons.add("usb-vid-pid")
            continue
        if spec.matches_text(endpoint.product, endpoint.manufacturer):
            matched.append(endpoint)
            reasons.add("product-string")
    if not matched:
        return None
    return HIDResolution(
        device_key=spec.key,
        paths=tuple(item.path for item in matched),
        matched_by="+".join(sorted(reasons)),
    )


def sdl_endpoint_from_metadata(
    name: object,
    *,
    index: int,
    instance_id: Optional[int] = None,
    guid: object = "",
) -> SDLControllerEndpoint:
    """Create an SDL runtime locator; no field here is stable identity."""
    idx = int(index)
    return SDLControllerEndpoint(
        index=idx,
        instance_id=idx if instance_id is None else int(instance_id),
        name=str(name or ""),
        guid=str(guid or ""),
    )


def sdl_endpoints() -> Tuple[SDLControllerEndpoint, ...]:
    """Enumerate SDL controller metadata.

    This may instantiate pygame joystick metadata objects, so it is intended
    for the one bridge SDL owner or for an explicit diagnostic run with Studio
    closed. Background Studio discovery must continue using include_sdl=False.
    """
    if pygame is None:
        return ()
    try:
        if not pygame.joystick.get_init():
            pygame.joystick.init()
        count = int(pygame.joystick.get_count())
    except Exception:
        return ()

    found: List[SDLControllerEndpoint] = []
    for index in range(max(0, count)):
        try:
            joystick = pygame.joystick.Joystick(index)
            name = str(joystick.get_name() or "")
            get_instance = getattr(joystick, "get_instance_id", None)
            instance_id = int(get_instance()) if callable(get_instance) else index
            get_guid = getattr(joystick, "get_guid", None)
            guid = str(get_guid() or "") if callable(get_guid) else ""
        except Exception:
            continue
        found.append(sdl_endpoint_from_metadata(
            name, index=index, instance_id=instance_id, guid=guid
        ))
    return tuple(found)


def resolve_sdl_controller(
    device_key: str,
    *,
    preferred_instance_id: Optional[int] = None,
    endpoints: Optional[Sequence[SDLControllerEndpoint]] = None,
) -> Optional[SDLResolution]:
    """Resolve a stable product to its current SDL locator.

    Replacement hardware is accepted because matching uses only the product
    name tokens from ProductSpec. SDL index, instance ID and GUID may change.
    If two identical products are simultaneously present, enumeration order is
    not used to guess a role; a still-valid prior runtime instance may be used.
    """
    spec = product_by_key(device_key)
    if spec is None or not {"sdl", "usb-gaming"}.intersection(spec.transports):
        return None
    inventory = tuple(endpoints) if endpoints is not None else sdl_endpoints()
    matched = [
        item for item in inventory
        if spec.matches_text(item.name)
    ]
    if not matched:
        return None
    if preferred_instance_id is not None:
        for item in matched:
            if item.instance_id == int(preferred_instance_id):
                return SDLResolution(
                    device_key=spec.key,
                    index=item.index,
                    instance_id=item.instance_id,
                    matched_by="product-string+preferred-runtime-instance",
                    candidates=tuple(candidate.instance_id for candidate in matched),
                )
    if len(matched) != 1:
        return None
    item = matched[0]
    return SDLResolution(
        device_key=spec.key,
        index=item.index,
        instance_id=item.instance_id,
        matched_by="product-string",
        candidates=(item.instance_id,),
    )



def product_runtime_snapshot(
    *,
    include_hid: bool = True,
    include_sdl: bool = False,
) -> Dict[str, Any]:
    serial_inventory = serial_endpoints()
    hid_inventory = hid_endpoints() if include_hid else ()
    sdl_inventory = sdl_endpoints() if include_sdl else ()

    products = []
    for spec in PRODUCTS:
        row: Dict[str, Any] = {
            "key": spec.key,
            "title": spec.title,
            "transports": list(spec.transports),
            "driver": spec.driver,
            "replaceable_unit": bool(spec.replaceable_unit),
            "identity_policy": "product/protocol; never serial-number/COM/index/path",
        }

        if "serial" in spec.transports:
            candidates = []
            for endpoint in serial_inventory:
                score, reason = _serial_score(endpoint, spec)
                if score:
                    candidates.append({
                        "port": endpoint.port,
                        "match": reason,
                        "score": score,
                    })
            row["serial_candidates"] = candidates

        if "hid" in spec.transports:
            resolution = resolve_hid_interfaces(spec.key, endpoints=hid_inventory)
            row["hid_paths"] = (
                list(resolution.paths) if resolution is not None else []
            )

        if {"sdl", "usb-gaming"}.intersection(spec.transports):
            candidates = [
                {
                    "index": endpoint.index,
                    "instance_id": endpoint.instance_id,
                    "name": endpoint.name,
                }
                for endpoint in sdl_inventory
                if spec.matches_text(endpoint.name)
            ]
            row["sdl_candidates"] = candidates

        products.append(row)

    return {
        "identity_policy": (
            "Supported replacement units match stable product/protocol identity; "
            "serial numbers, COM numbers, HID paths, SDL GUIDs and SDL indices "
            "are runtime-only locators."
        ),
        "serial_endpoints": [item.snapshot() for item in serial_inventory],
        "hid_endpoints": [item.snapshot() for item in hid_inventory],
        "sdl_endpoints": [item.snapshot() for item in sdl_inventory],
        "products": products,
    }


__all__ = [
    "SerialEndpoint", "SerialResolution", "serial_endpoints",
    "HIDEndpoint", "HIDResolution", "hid_endpoints", "resolve_hid_interfaces",
    "SDLControllerEndpoint", "SDLResolution", "sdl_endpoint_from_metadata",
    "sdl_endpoints", "resolve_sdl_controller",
    "resolve_serial_port", "resolve_serial_port_name",
    "product_runtime_snapshot",
]

MUSLIMSIM_PORTABLE_DEVICE_PLATFORM_V2_LOCATORS = True
