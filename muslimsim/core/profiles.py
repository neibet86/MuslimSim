"""Shared models used by the MuslimSim device modules and future GUI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceDescriptor:
    key: str
    title: str
    purpose: str


@dataclass(frozen=True)
class DeviceSelection:
    """Device choices made by the launcher before the bridge starts."""

    pu_lights: bool = True
    winctrl: bool = True
    pedals: bool = True
    agp: bool = True
    pfp: bool = False
    pdc: bool = True
