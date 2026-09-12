from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum, IntFlag, auto
from typing import Any, Mapping, Optional, Protocol, Sequence


class DeviceRole(str, Enum):
    UNASSIGNED = "unassigned"
    CAPTAIN = "captain"
    FIRST_OFFICER = "first_officer"
    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"
    PILOT = "pilot"
    COPILOT = "copilot"
    OBSERVER = "observer"


class RuntimeMode(str, Enum):
    LIVE = "live"
    PRACTICE = "practice"


class Capability(IntFlag):
    NONE = 0
    DISCOVERY = auto()
    INPUT = auto()
    OUTPUT = auto()
    DISPLAY = auto()
    LIGHTING = auto()
    ACTUATOR = auto()
    CALIBRATION = auto()
    LEARNING = auto()
    HOTPLUG = auto()


@dataclass(frozen=True)
class TransportIdentity:
    """One operating-system sighting of a physical device.

    ``path`` and ``instance_id`` are local hints only.  They are intentionally
    excluded from the portable identity because Windows may change both after a
    USB-port move, driver reinstall, or migration to another PC.
    """

    transport: str
    vendor_id: Optional[int] = None
    product_id: Optional[int] = None
    serial_number: Optional[str] = None
    interface_number: Optional[int] = None
    usage_page: Optional[int] = None
    usage: Optional[int] = None
    product: str = ""
    manufacturer: str = ""
    descriptor_hash: str = ""
    container_id: str = ""
    instance_id: str = ""
    path: str = ""
    extra: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["extra"] = dict(self.extra)
        return data


@dataclass(frozen=True)
class DeviceSighting:
    identity: TransportIdentity
    source: str
    observed_at: float
    legacy_key: str = ""
    capabilities: Capability = Capability.DISCOVERY | Capability.INPUT | Capability.LEARNING
    vendor_role_hint: DeviceRole = DeviceRole.UNASSIGNED
    driver_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["identity"] = self.identity.to_dict()
        data["capabilities"] = int(self.capabilities)
        data["vendor_role_hint"] = self.vendor_role_hint.value
        return data


@dataclass(frozen=True)
class InputEvent:
    device_key: str
    control_key: str
    value: Any
    phase: str = "change"
    source: str = "physical"
    timestamp: float = 0.0
    raw_signature: str = ""
    kind: str = ""


@dataclass
class AdoptedDevice:
    adoption_id: str
    family_key: str
    portable_key: str = ""
    assigned_role: DeviceRole = DeviceRole.UNASSIGNED
    friendly_name: str = ""
    legacy_key: str = ""
    driver_id: str = ""
    capabilities: Capability = Capability.NONE
    vendor_product: str = ""
    vendor_role_hint: DeviceRole = DeviceRole.UNASSIGNED
    state: str = "offline"
    last_seen: float = 0.0
    local_match_key: str = ""
    aliases: list[str] = field(default_factory=list)
    needs_confirmation: bool = False
    role_change_detected: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["assigned_role"] = self.assigned_role.value
        data["vendor_role_hint"] = self.vendor_role_hint.value
        data["capabilities"] = int(self.capabilities)
        return data


@dataclass(frozen=True)
class DriverProbeResult:
    sighting: DeviceSighting
    confidence: int
    reason: str = ""


class DeviceDriver(Protocol):
    """Contract for future MuslimSim device plug-ins.

    Input-only drivers may omit output methods.  Output-capable drivers must
    provide an explicit, capture-proven ``blackout`` implementation before the
    platform will grant an output lease.
    """

    plugin_id: str
    api_version: int

    def probe(self) -> Sequence[DriverProbeResult]: ...
    def start(self, event_sink: Any) -> None: ...
    def stop(self) -> None: ...
    def snapshot(self) -> Mapping[str, Any]: ...
    def set_output(self, control_key: str, value: Any) -> None: ...
    def blackout(self) -> None: ...


class PlatformError(RuntimeError):
    pass


class AuthenticationError(PlatformError):
    pass


class ConflictError(PlatformError):
    pass


class ValidationError(PlatformError):
    pass
