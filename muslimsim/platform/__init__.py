"""MuslimSim Platform V7.

This package is deliberately additive.  It wraps the proven MuslimSim hardware
owners with stable identity, telemetry, learning, profile, authority, cloud,
and update services.  It does not open hardware by itself unless a future
device plug-in explicitly owns that device through the lease broker.
"""

from .contracts import (
    Capability,
    DeviceRole,
    DeviceSighting,
    InputEvent,
    RuntimeMode,
    TransportIdentity,
)
from .runtime import PlatformRuntime

__all__ = [
    "Capability",
    "DeviceRole",
    "DeviceSighting",
    "InputEvent",
    "PlatformRuntime",
    "RuntimeMode",
    "TransportIdentity",
]

__version__ = "7.0.0"
