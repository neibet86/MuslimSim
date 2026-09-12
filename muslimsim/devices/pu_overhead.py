"""PU Overhead boundary: product-discovered serial/SDL/Raw Input owner."""

from __future__ import annotations

from typing import Sequence

from ..core.profiles import DeviceDescriptor, DeviceSelection


DESCRIPTOR = DeviceDescriptor(
    key="pu_overhead",
    title="PU Overhead / automatic USB serial",
    purpose="Overhead controls, starter auto-retract, gauges, and P7 annunciator lamps",
)


def apply(selection: DeviceSelection, arguments: Sequence[str]) -> list[str]:
    """Map the P7 feedback preference without ever disabling PU controls."""
    result = list(arguments)
    if not selection.pu_lights and "--no-pu-lights" not in result:
        result.append("--no-pu-lights")
    return result
