"""WinCtrl device boundary: throttle, reversers, and hardware input ownership."""

from __future__ import annotations

from typing import Sequence

from ..core.profiles import DeviceDescriptor, DeviceSelection


DESCRIPTOR = DeviceDescriptor(
    key="winctrl",
    title="WinCtrl flight controls",
    purpose="Boeing thrust, reversers, speedbrake, flaps, and WinCtrl hardware input",
)


def apply(selection: DeviceSelection, arguments: Sequence[str]) -> list[str]:
    result = list(arguments)
    if not selection.winctrl and "--no-winctrl" not in result:
        result.append("--no-winctrl")
    return result
