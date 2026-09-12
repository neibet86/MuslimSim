"""WinCtrl pedal device boundary: rudder yaw and independent toe brakes."""

from __future__ import annotations

from typing import Sequence

from ..core.profiles import DeviceDescriptor, DeviceSelection


DESCRIPTOR = DeviceDescriptor(
    key="pedals",
    title="WinCtrl rudder pedals",
    purpose="Rudder yaw plus independent left and right toe brakes",
)


def apply(selection: DeviceSelection, arguments: Sequence[str]) -> list[str]:
    """Disable only the pedal input when this device is turned off."""
    result = list(arguments)
    if not selection.pedals and "--no-pedals" not in result:
        result.append("--no-pedals")
    return result
