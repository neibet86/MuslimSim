from __future__ import annotations

import importlib.metadata
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Optional

from .contracts import Capability, DeviceDriver, PlatformError, ValidationError

PLUGIN_API_VERSION = 1
ENTRY_POINT_GROUP = "muslimsim.device_plugins"


@dataclass(frozen=True)
class Lease:
    device_id: str
    owner: str
    purpose: str
    generation: int
    acquired_at: float


class DeviceLeaseBroker:
    """Prevents two MuslimSim components from opening the same physical device."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._leases: dict[str, Lease] = {}
        self._generation = 0

    def acquire(self, device_id: str, owner: str, purpose: str) -> Lease:
        key = str(device_id)
        with self._lock:
            existing = self._leases.get(key)
            if existing is not None and existing.owner != owner:
                raise PlatformError(
                    f"{key} is already owned by {existing.owner} for {existing.purpose}; "
                    "MuslimSim permits one hardware owner only"
                )
            self._generation += 1
            lease = Lease(key, str(owner), str(purpose), self._generation, time.time())
            self._leases[key] = lease
            return lease

    def release(self, lease: Lease) -> None:
        with self._lock:
            current = self._leases.get(lease.device_id)
            if current is not None and current.generation == lease.generation:
                self._leases.pop(lease.device_id, None)

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [lease.__dict__.copy() for lease in self._leases.values()]


@dataclass
class ManifestControl:
    key: str
    kind: str
    report_id: int
    byte_offset: int
    bit: int | None = None
    width: int = 1
    signed: bool = False
    little_endian: bool = True
    scale: float = 1.0
    offset: float = 0.0

    def decode(self, report: bytes) -> Any:
        if not report or report[0] != self.report_id:
            raise ValidationError(f"Report ID {self.report_id:#x} required for {self.key}")
        if self.bit is not None:
            if self.byte_offset >= len(report):
                raise ValidationError(f"Report too short for {self.key}")
            return 1 if report[self.byte_offset] & (1 << self.bit) else 0
        end = self.byte_offset + self.width
        if end > len(report):
            raise ValidationError(f"Report too short for {self.key}")
        raw = int.from_bytes(report[self.byte_offset:end], "little" if self.little_endian else "big", signed=self.signed)
        return raw * self.scale + self.offset


@dataclass
class ManifestPlugin:
    plugin_id: str
    title: str
    match: list[dict[str, Any]]
    controls: list[ManifestControl]
    capabilities: Capability
    blackout_proven: bool = False
    source_path: str = ""

    def parse(self, report: bytes) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for control in self.controls:
            if report and report[0] == control.report_id:
                values[control.key] = control.decode(report)
        return values


def load_manifest(path: str | Path) -> ManifestPlugin:
    source = Path(path)
    data = json.loads(source.read_text(encoding="utf-8"))
    if int(data.get("schema", 0)) != 1:
        raise ValidationError(f"Unsupported plug-in manifest schema in {source}")
    plugin_id = str(data.get("plugin_id") or "").strip()
    if not plugin_id:
        raise ValidationError(f"plugin_id is required in {source}")
    controls: list[ManifestControl] = []
    for item in data.get("controls") or []:
        item = dict(item)
        controls.append(ManifestControl(
            key=str(item["key"]),
            kind=str(item.get("kind") or "button"),
            report_id=int(str(item.get("report_id", 1)), 0),
            byte_offset=int(item["byte_offset"]),
            bit=None if item.get("bit") is None else int(item["bit"]),
            width=int(item.get("width", 1)),
            signed=bool(item.get("signed", False)),
            little_endian=str(item.get("endian", "little")).lower() != "big",
            scale=float(item.get("scale", 1.0)),
            offset=float(item.get("offset", 0.0)),
        ))
    capabilities = Capability.DISCOVERY | Capability.INPUT | Capability.LEARNING | Capability.HOTPLUG
    for name in data.get("capabilities") or []:
        try:
            capabilities |= Capability[str(name).upper()]
        except KeyError as exc:
            raise ValidationError(f"Unknown capability {name!r} in {source}") from exc
    blackout = bool(data.get("capture_proven_blackout", False))
    if capabilities & Capability.OUTPUT and not blackout:
        raise ValidationError(
            f"{plugin_id} declares output but has no capture-proven blackout; "
            "Rule 0.1 blocks this plug-in"
        )
    return ManifestPlugin(
        plugin_id=plugin_id,
        title=str(data.get("title") or plugin_id),
        match=[dict(value) for value in data.get("match") or []],
        controls=controls,
        capabilities=capabilities,
        blackout_proven=blackout,
        source_path=str(source),
    )


class PluginRegistry:
    """Built-in, entry-point, and JSON-manifest driver registry."""

    def __init__(self) -> None:
        self._drivers: dict[str, Any] = {}
        self._manifests: dict[str, ManifestPlugin] = {}
        self._errors: list[dict[str, str]] = []
        self.broker = DeviceLeaseBroker()

    def register(self, driver: Any, *, plugin_id: str | None = None) -> None:
        key = str(plugin_id or getattr(driver, "plugin_id", "")).strip()
        if not key:
            raise ValidationError("Device plug-in has no plugin_id")
        version = int(getattr(driver, "api_version", 0))
        if version != PLUGIN_API_VERSION:
            raise ValidationError(f"{key} uses plug-in API {version}; MuslimSim requires {PLUGIN_API_VERSION}")
        if key in self._drivers or key in self._manifests:
            raise ValidationError(f"Duplicate device plug-in {key}")
        self._drivers[key] = driver

    def discover_entry_points(self) -> None:
        try:
            points = importlib.metadata.entry_points()
            selected = points.select(group=ENTRY_POINT_GROUP) if hasattr(points, "select") else points.get(ENTRY_POINT_GROUP, ())
        except Exception as exc:
            self._errors.append({"source": "entry-points", "error": str(exc)})
            return
        for point in selected:
            try:
                loaded = point.load()
                driver = loaded() if isinstance(loaded, type) else loaded
                self.register(driver, plugin_id=point.name or None)
            except Exception as exc:
                self._errors.append({"source": f"entry-point:{getattr(point, 'name', '?')}", "error": str(exc)})

    def discover_manifests(self, directories: Iterable[str | Path]) -> None:
        for directory in directories:
            root = Path(directory)
            if not root.is_dir():
                continue
            for path in sorted(root.glob("*.muslimsim-device.json")):
                try:
                    manifest = load_manifest(path)
                    if manifest.plugin_id in self._drivers or manifest.plugin_id in self._manifests:
                        raise ValidationError(f"Duplicate device plug-in {manifest.plugin_id}")
                    self._manifests[manifest.plugin_id] = manifest
                except Exception as exc:
                    self._errors.append({"source": str(path), "error": str(exc)})

    def get(self, plugin_id: str) -> Any:
        key = str(plugin_id)
        if key in self._drivers:
            return self._drivers[key]
        if key in self._manifests:
            return self._manifests[key]
        raise KeyError(key)

    def snapshot(self) -> dict[str, Any]:
        return {
            "api_version": PLUGIN_API_VERSION,
            "entry_point_group": ENTRY_POINT_GROUP,
            "drivers": sorted(self._drivers),
            "manifests": [
                {
                    "plugin_id": item.plugin_id,
                    "title": item.title,
                    "capabilities": int(item.capabilities),
                    "controls": len(item.controls),
                    "blackout_proven": item.blackout_proven,
                    "source_path": item.source_path,
                }
                for item in sorted(self._manifests.values(), key=lambda value: value.plugin_id)
            ],
            "leases": self.broker.snapshot(),
            "errors": list(self._errors),
        }
