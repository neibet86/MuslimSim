"""Generic HID / SDL device driver — MUSLIMSIM_GENERIC_HID_DRIVER_V1.

Provides input reading for devices described by community JSON profiles
(``community/devices/*.json``) without any device-specific Python code.

Phase 1 scope
-------------
- Defines ``GenericSDLDevice``: reads SDL axes, buttons and hats for any
  community-profile device and routes each event through ``HardwareLab.input``.
- Defines ``GenericHIDDevice``: stub for future raw-HID community devices.
- Neither class opens hardware until ``start()`` is called by the bridge.
- No output is sent.  Community profiles that list outputs with
  ``"status": "unknown"`` are explicitly blocked here — Rule 0.1 requires a
  capture-proven OFF state before any output is enabled.

Phase 2 will wire these into the bridge's SDL event dispatch so that user
mappings created in Studio actually fire simulator commands.
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple

if TYPE_CHECKING:
    from .catalog import DeviceSpec


InputCallback = Callable[[str, str, object], None]


class GenericSDLDevice:
    """SDL input reader for a community-profile gaming peripheral.

    Parameters
    ----------
    device_spec:
        The DeviceSpec loaded from the community profile.
    sdl_index:
        The pygame joystick index resolved at runtime.
    on_input:
        Called with ``(device_key, control_key, value)`` on every input event.
        Signature matches ``HardwareLab.input(device, control, value, source=...)``.
    """

    def __init__(
        self,
        device_spec: "DeviceSpec",
        sdl_index: int,
        on_input: InputCallback,
    ) -> None:
        self._spec = device_spec
        self._sdl_index = sdl_index
        self._on_input = on_input
        self._running = False
        self._joystick: Any = None

    @property
    def device_key(self) -> str:
        return self._spec.key

    def start(self) -> None:
        """Open the SDL joystick handle.  No-op if already started."""
        if self._running:
            return
        try:
            import pygame
            joystick = pygame.joystick.Joystick(self._sdl_index)
            if not joystick.get_init():
                joystick.init()
            self._joystick = joystick
            self._running = True
        except Exception:
            pass

    def stop(self) -> None:
        """Release the SDL handle."""
        self._running = False
        self._joystick = None

    def dispatch_axis(self, sdl_axis: int, value: float) -> None:
        """Route an SDL axis event through the community profile's control map."""
        if not self._running:
            return
        raw_label = f"SDL axis {sdl_axis}"
        for control in self._spec.controls:
            if control.direction == "input" and control.raw == raw_label:
                self._on_input(self._spec.key, control.key, value)
                return

    def dispatch_button(self, sdl_button: int, pressed: bool) -> None:
        """Route an SDL button event through the community profile's control map."""
        if not self._running:
            return
        raw_label = f"SDL button {sdl_button}"
        for control in self._spec.controls:
            if control.direction == "input" and control.raw == raw_label:
                self._on_input(self._spec.key, control.key, int(pressed))
                return

    def dispatch_hat(self, sdl_hat: int, value: Tuple[int, int]) -> None:
        """Route an SDL hat event; converts (x, y) tuple to compass string."""
        if not self._running:
            return
        raw_label = f"SDL hat {sdl_hat}"
        hat_map = {
            (0, 1): "N", (1, 1): "NE", (1, 0): "E", (1, -1): "SE",
            (0, -1): "S", (-1, -1): "SW", (-1, 0): "W", (-1, 1): "NW",
            (0, 0): "CENTER",
        }
        compass = hat_map.get(tuple(value), "CENTER")
        for control in self._spec.controls:
            if control.direction == "input" and control.raw == raw_label:
                self._on_input(self._spec.key, control.key, compass)
                return

    def status(self) -> Dict[str, object]:
        return {
            "device": self._spec.key,
            "title": self._spec.title,
            "running": self._running,
            "sdl_index": self._sdl_index,
            "driver": "generic_hid",
        }


class GenericHIDDevice:
    """Raw-HID input stub for community-profile non-SDL panels.

    Phase 1 placeholder only.  Raw-HID community devices are recognised in
    discovery and show their control map in Studio, but active input reading
    is implemented in Phase 2.
    """

    def __init__(self, device_spec: "DeviceSpec") -> None:
        self._spec = device_spec

    @property
    def device_key(self) -> str:
        return self._spec.key

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def status(self) -> Dict[str, object]:
        return {
            "device": self._spec.key,
            "title": self._spec.title,
            "running": False,
            "driver": "generic_hid_stub",
            "notes": "Phase 1: raw-HID community device recognised; active input reading is Phase 2.",
        }


def make_generic_device(
    device_spec: "DeviceSpec",
    *,
    sdl_index: Optional[int] = None,
    on_input: Optional[InputCallback] = None,
) -> "GenericSDLDevice | GenericHIDDevice":
    """Factory: return the right generic driver for a community profile device."""
    if sdl_index is not None and on_input is not None:
        if any(t in ("sdl", "usb-gaming") for t in ()):
            pass
        return GenericSDLDevice(device_spec, sdl_index, on_input)
    return GenericHIDDevice(device_spec)


__all__ = [
    "GenericSDLDevice",
    "GenericHIDDevice",
    "make_generic_device",
    "InputCallback",
]

MUSLIMSIM_GENERIC_HID_DRIVER_V1 = True
