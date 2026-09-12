"""WinCtrl PDC BB62 launcher boundary with capture-verified controls."""

from __future__ import annotations

from typing import Sequence

from ..core.profiles import DeviceDescriptor, DeviceSelection


DESCRIPTOR = DeviceDescriptor(
    key="pdc",
    title="WinCtrl PDC / EFIS (BB62)",
    purpose="CAPT EFIS buttons, selectors, MINS, and BARO controls",
)


def apply(selection: DeviceSelection, arguments: Sequence[str]) -> list[str]:
    result = list(arguments)
    if not selection.pdc and "--no-pdc" not in result:
        result.append("--no-pdc")
    return result
