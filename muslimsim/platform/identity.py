from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import replace
from typing import Any, Iterable, Mapping, Sequence

from .contracts import AdoptedDevice, Capability, DeviceRole, DeviceSighting, TransportIdentity

_ROLE_WORDS = re.compile(
    r"\b(capt(?:ain)?|first[\s_-]*officer|f/?o|copilot|co[\s_-]*pilot|pilot|left|right|lhs|rhs)\b",
    re.IGNORECASE,
)
_SPACE = re.compile(r"[^a-z0-9]+")


def _clean(value: Any) -> str:
    return str(value or "").strip().lower()


def _norm_product(value: str) -> str:
    text = _ROLE_WORDS.sub(" ", _clean(value))
    return _SPACE.sub(" ", text).strip()


def _hash(parts: Iterable[Any]) -> str:
    payload = json.dumps([str(p or "").strip().lower() for p in parts], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def role_hint_from_text(*values: str) -> DeviceRole:
    text = " ".join(_clean(value) for value in values)
    if re.search(r"\b(first[\s_-]*officer|f/?o|copilot|co[\s_-]*pilot|right|rhs)\b", text):
        return DeviceRole.FIRST_OFFICER
    if re.search(r"\b(capt(?:ain)?|pilot|left|lhs)\b", text):
        return DeviceRole.CAPTAIN
    if re.search(r"\bcenter|centre\b", text):
        return DeviceRole.CENTER
    return DeviceRole.UNASSIGNED


def family_key(identity: TransportIdentity) -> str:
    """Stable hardware-family fingerprint, excluding volatile Windows paths."""

    return _hash(
        (
            _clean(identity.transport),
            f"{identity.vendor_id or 0:04x}",
            f"{identity.product_id or 0:04x}",
            identity.interface_number if identity.interface_number is not None else "",
            identity.usage_page if identity.usage_page is not None else "",
            identity.usage if identity.usage is not None else "",
            _norm_product(identity.product),
            _clean(identity.manufacturer),
            _clean(identity.descriptor_hash),
        )
    )


def portable_key(identity: TransportIdentity) -> str:
    """Cross-PC identity when the hardware exposes a real serial number."""

    serial = _clean(identity.serial_number)
    if not serial or serial in {"0", "none", "unknown", "n/a", "00000000", "0000"}:
        return ""
    return _hash((family_key(identity), serial))


def local_match_key(identity: TransportIdentity) -> str:
    """Best-effort same-PC identity; never uploaded as the portable identity."""

    local = _clean(identity.container_id) or _clean(identity.instance_id) or _clean(identity.path)
    return _hash((family_key(identity), local)) if local else ""


def sighting_from_mapping(record: Mapping[str, Any], *, source: str = "discovery") -> DeviceSighting:
    def integer(*names: str) -> int | None:
        for name in names:
            value = record.get(name)
            if value in (None, ""):
                continue
            try:
                return int(str(value), 0)
            except (TypeError, ValueError):
                try:
                    return int(value)
                except (TypeError, ValueError):
                    pass
        return None

    product = str(record.get("product") or record.get("name") or record.get("title") or "")
    manufacturer = str(record.get("manufacturer") or record.get("vendor") or "")
    identity = TransportIdentity(
        transport=str(record.get("transport") or record.get("source") or "usb").lower(),
        vendor_id=integer("vendor_id", "vid", "vendorId"),
        product_id=integer("product_id", "pid", "productId"),
        serial_number=str(record.get("serial_number") or record.get("serial") or ""),
        interface_number=integer("interface_number", "interface", "mi"),
        usage_page=integer("usage_page", "usagePage"),
        usage=integer("usage"),
        product=product,
        manufacturer=manufacturer,
        descriptor_hash=str(record.get("descriptor_hash") or record.get("descriptorHash") or ""),
        container_id=str(record.get("container_id") or record.get("containerId") or ""),
        instance_id=str(record.get("instance_id") or record.get("instanceId") or ""),
        path=str(record.get("path") or record.get("device_path") or ""),
        extra={key: value for key, value in record.items() if key not in {
            "transport", "source", "vendor_id", "vid", "vendorId", "product_id", "pid", "productId",
            "serial_number", "serial", "interface_number", "interface", "mi", "usage_page", "usagePage",
            "usage", "product", "name", "title", "manufacturer", "vendor", "descriptor_hash",
            "descriptorHash", "container_id", "containerId", "instance_id", "instanceId", "path", "device_path",
        }},
    )
    caps = record.get("capabilities", int(Capability.DISCOVERY | Capability.INPUT | Capability.LEARNING))
    try:
        capabilities = Capability(int(caps))
    except (TypeError, ValueError):
        capabilities = Capability.DISCOVERY | Capability.INPUT | Capability.LEARNING
    return DeviceSighting(
        identity=identity,
        source=source,
        observed_at=float(record.get("observed_at") or time.time()),
        legacy_key=str(record.get("key") or record.get("device_key") or record.get("legacy_key") or ""),
        capabilities=capabilities,
        vendor_role_hint=role_hint_from_text(product, str(record.get("role") or record.get("side") or "")),
        driver_id=str(record.get("driver") or record.get("driver_id") or ""),
    )


class IdentityResolver:
    """Reconciles volatile OS sightings with persistent adopted devices.

    Serial-bearing devices transfer automatically to another Windows install.
    Serial-less identical devices intentionally remain ambiguous until the user
    performs a touch-to-identify challenge.  Silently guessing would be capable
    of swapping captain and first-officer controls.
    """

    def __init__(self, records: Sequence[AdoptedDevice] = ()) -> None:
        self.records: dict[str, AdoptedDevice] = {item.adoption_id: item for item in records}

    def adopt(
        self,
        sighting: DeviceSighting,
        *,
        role: DeviceRole = DeviceRole.UNASSIGNED,
        friendly_name: str = "",
        adoption_id: str | None = None,
    ) -> AdoptedDevice:
        identity = sighting.identity
        record = AdoptedDevice(
            adoption_id=adoption_id or str(uuid.uuid4()),
            family_key=family_key(identity),
            portable_key=portable_key(identity),
            assigned_role=role,
            friendly_name=friendly_name or identity.product or sighting.legacy_key or "Adopted device",
            legacy_key=sighting.legacy_key,
            driver_id=sighting.driver_id,
            capabilities=sighting.capabilities,
            vendor_product=identity.product,
            vendor_role_hint=sighting.vendor_role_hint,
            state="online",
            last_seen=sighting.observed_at,
            local_match_key=local_match_key(identity),
            aliases=[value for value in (identity.product, sighting.legacy_key) if value],
        )
        self.records[record.adoption_id] = record
        return record

    def _candidates(self, sighting: DeviceSighting) -> list[AdoptedDevice]:
        fk = family_key(sighting.identity)
        return [record for record in self.records.values() if record.family_key == fk]

    def match(self, sighting: DeviceSighting) -> tuple[AdoptedDevice | None, str]:
        pk = portable_key(sighting.identity)
        if pk:
            exact = [record for record in self.records.values() if record.portable_key == pk]
            if len(exact) == 1:
                return exact[0], "portable-serial"

        lk = local_match_key(sighting.identity)
        if lk:
            exact = [record for record in self.records.values() if record.local_match_key == lk]
            if len(exact) == 1:
                return exact[0], "local-container"

        candidates = self._candidates(sighting)
        if not candidates:
            return None, "new"

        # A stable legacy key is useful only inside the same product family.
        legacy = [record for record in candidates if sighting.legacy_key and record.legacy_key == sighting.legacy_key]
        if len(legacy) == 1:
            return legacy[0], "legacy-key"

        hint = sighting.vendor_role_hint
        if hint != DeviceRole.UNASSIGNED:
            by_role = [
                record for record in candidates
                if record.assigned_role in {hint, DeviceRole.CAPTAIN if hint == DeviceRole.PILOT else hint}
                or record.vendor_role_hint == hint
            ]
            if len(by_role) == 1:
                return by_role[0], "family-role-hint"

        if len(candidates) == 1:
            # Safe for one device of this family, but mark it for confirmation
            # when neither a serial nor a local identity exists.
            only = candidates[0]
            if not pk and not lk and not only.portable_key and not only.local_match_key:
                only.needs_confirmation = True
                return only, "single-family-needs-confirmation"
            return only, "single-family"
        return None, "ambiguous-touch-required"

    def observe(self, sighting: DeviceSighting) -> tuple[AdoptedDevice | None, str]:
        record, reason = self.match(sighting)
        if record is None:
            return None, reason

        product = sighting.identity.product
        if product and product not in record.aliases:
            record.aliases.append(product)
        old_hint = record.vendor_role_hint
        record.vendor_product = product or record.vendor_product
        record.vendor_role_hint = sighting.vendor_role_hint
        record.role_change_detected = bool(
            old_hint != DeviceRole.UNASSIGNED
            and sighting.vendor_role_hint != DeviceRole.UNASSIGNED
            and old_hint != sighting.vendor_role_hint
        )
        record.state = "online"
        record.last_seen = sighting.observed_at
        record.local_match_key = local_match_key(sighting.identity) or record.local_match_key
        record.legacy_key = sighting.legacy_key or record.legacy_key
        record.driver_id = sighting.driver_id or record.driver_id
        record.capabilities |= sighting.capabilities
        return record, reason

    def set_role(self, adoption_id: str, role: DeviceRole) -> AdoptedDevice:
        record = self.records[adoption_id]
        record.assigned_role = role
        record.needs_confirmation = False
        record.role_change_detected = False
        return record

    def offline_unseen(self, seen_ids: set[str]) -> None:
        for adoption_id, record in self.records.items():
            if adoption_id not in seen_ids:
                record.state = "offline"

    def snapshot(self) -> list[dict[str, Any]]:
        return [record.to_dict() for record in sorted(self.records.values(), key=lambda item: (item.friendly_name, item.adoption_id))]
