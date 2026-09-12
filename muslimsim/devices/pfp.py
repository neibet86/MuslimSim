"""PFP device boundary: optional live captain PFD and offline standby page."""

from __future__ import annotations

from typing import Sequence

from ..core.profiles import DeviceDescriptor, DeviceSelection


DESCRIPTOR = DeviceDescriptor(
    key="pfp",
    title="WinCtrl PFP display",
    purpose="Optional captain PFD page, MuslimSim boot stamp, and offline standby page",
)


def apply(selection: DeviceSelection, arguments: Sequence[str]) -> list[str]:
    result = [argument for argument in arguments if argument != "--pfp-pfd"]
    if selection.pfp:
        result.append("--pfp-pfd")
    return result
