"""AGP device boundary: landing gear, autobrake, and clock/electrical display."""

from __future__ import annotations

from typing import Sequence

from ..core.profiles import DeviceDescriptor, DeviceSelection


DESCRIPTOR = DeviceDescriptor(
    key="agp",
    title="WinCtrl AGP panel",
    purpose="Landing gear, smart autobrake, indicator lamps, CHR/UTC/ET displays",
)


def apply(selection: DeviceSelection, arguments: Sequence[str]) -> list[str]:
    result = list(arguments)
    if not selection.agp and "--no-agp-display" not in result:
        result.append("--no-agp-display")
    return result
