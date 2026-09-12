"""Simulator-independent hardware-laboratory models.

This package deliberately contains no HID, serial, pygame, or Tk imports.
It is safe to use for profile editing and virtual-panel tests when neither
X-Plane nor any cockpit hardware is present.
"""

from .catalog import ALL_HARDWARE, DeviceSpec, ControlSpec, device_by_key
from .lab import HardwareLab, LabError
from .profiles import HardwareProfileStore, MappingBinding, ProfileError

__all__ = (
    "ALL_HARDWARE",
    "ControlSpec",
    "DeviceSpec",
    "HardwareLab",
    "HardwareProfileStore",
    "LabError",
    "MappingBinding",
    "ProfileError",
    "device_by_key",
)
