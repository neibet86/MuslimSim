"""Verified Studio calibration profiles distilled from owner-supplied Moza presets.

The supplied ``.preset`` files are settings files for the Moza application.
They establish the names, value ranges, and selected values below, but do not
contain a USB report protocol.  These profiles are consequently safe Studio
calibration records: they can be selected, inspected, tuned and saved per
MuslimSim profile without pretending that Studio can write an unknown Moza
force-feedback protocol to hardware.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping, Tuple


# Every editable number below is in the 0..100 range used by the supplied
# preset.  The toggle names are retained verbatim where possible so the
# on-screen setting remains recognisable in Moza's own software.
_COMMON_AXIS: Dict[str, Any] = {
    "axis_range_x_reversal": 0,
    "axis_range_y_reversal": 0,
    "axis_range_z_reversal": 0,
    "axis_x_deadzone": 0,
    "axis_y_deadzone": 0,
    "axis_z_deadzone": 0,
}


MOZA_UI_PRESETS: Dict[str, Dict[str, Any]] = {
    "ab6_a320_msfs2024": {
        "device": "moza_ab6",
        "title": "A320 Family",
        "source_file": "ab6-a320-msfs2024.preset",
        "simulator": "microsoft_flight_simulator_2024",
        "vehicle": "microsoft-a320neo",
        "source_device_parameters": 234,
        "source_telemetry_parameters": 186,
        "values": {
            **_COMMON_AXIS,
            "overall_strength": 70,
            "max_torque": 100,
            "damper": 30,
            "friction": 10,
            "inertia": 10,
            "spring": 50,
            "game_force_feedback": 100,
            "advanced_force": 0,
            "g_force_enabled": False,
            "g_force_strength": 100,
            "stall_buffet_enabled": True,
            "stall_buffet_strength": 10,
            "runway_rumble_enabled": False,
            "runway_rumble_strength": 100,
            "gear_motion_enabled": True,
            "gear_motion_strength": 4,
            "flaps_motion_enabled": True,
            "flaps_motion_strength": 22,
            "jet_rumble_enabled": True,
            "jet_rumble_strength": 4,
            "turbulence_enabled": False,
            "turbulence_strength": 11,
            "speedbrake_buffet_enabled": False,
            "speedbrake_buffet_strength": 21,
        },
    },
    "a210_ifly_b737max_msfs2024": {
        "device": "moza_a210",
        "title": "iFly B737 MAX tony v1.2",
        "source_file": "iFly B737MAX tony v1.2.preset",
        "simulator": "microsoft_flight_simulator_2024",
        "vehicle": "",
        "source_device_parameters": 232,
        "source_telemetry_parameters": 223,
        "values": {
            **_COMMON_AXIS,
            "overall_strength": 100,
            "max_torque": 100,
            "damper": 100,
            "friction": 0,
            "inertia": 100,
            "spring": 50,
            "game_force_feedback": 100,
            "advanced_force": 1,
            "background_led_brightness": 15,
            "gear_led_brightness": 15,
            "g_force_enabled": True,
            "g_force_strength": 100,
            "stall_buffet_enabled": True,
            "stall_buffet_strength": 20,
            "runway_rumble_enabled": True,
            "runway_rumble_strength": 100,
            "gear_motion_enabled": True,
            "gear_motion_strength": 10,
            "flaps_motion_enabled": True,
            "flaps_motion_strength": 10,
            "jet_rumble_enabled": True,
            "jet_rumble_strength": 10,
            "turbulence_enabled": False,
            "turbulence_strength": 5,
            "speedbrake_buffet_enabled": False,
            "speedbrake_buffet_strength": 50,
        },
    },
    "a210_pmdg_b777_msfs2024": {
        "device": "moza_a210",
        "title": "PMDG B777 tony v1.2",
        "source_file": "PMDG B777 tony v1.2.preset",
        "simulator": "microsoft_flight_simulator_2024",
        "vehicle": "",
        "source_device_parameters": 232,
        "source_telemetry_parameters": 223,
        "values": {
            **_COMMON_AXIS,
            "overall_strength": 100,
            "max_torque": 100,
            "damper": 100,
            "friction": 0,
            "inertia": 100,
            "spring": 50,
            "game_force_feedback": 100,
            "advanced_force": 1,
            "background_led_brightness": 15,
            "gear_led_brightness": 15,
            "g_force_enabled": True,
            "g_force_strength": 100,
            "stall_buffet_enabled": True,
            "stall_buffet_strength": 100,
            "runway_rumble_enabled": True,
            "runway_rumble_strength": 100,
            "gear_motion_enabled": True,
            "gear_motion_strength": 10,
            "flaps_motion_enabled": True,
            "flaps_motion_strength": 10,
            "jet_rumble_enabled": True,
            "jet_rumble_strength": 10,
            "turbulence_enabled": False,
            "turbulence_strength": 5,
            "speedbrake_buffet_enabled": False,
            "speedbrake_buffet_strength": 100,
        },
    },
}


_DEVICE_PRESETS: Dict[str, Tuple[str, ...]] = {
    "moza_ab6": ("ab6_a320_msfs2024",),
    "moza_a210": ("a210_ifly_b737max_msfs2024", "a210_pmdg_b777_msfs2024"),
}

# The Studio panel deliberately limits editable fields to settings whose
# names/values appear in the supplied preset.  This does not expose an
# arbitrary Moza configuration dictionary or an undocumented motor command.
MOZA_EDITABLE_KEYS = frozenset(
    key for preset in MOZA_UI_PRESETS.values() for key in dict(preset["values"]).keys()
)
MOZA_BOOLEAN_KEYS = frozenset(
    key for key in MOZA_EDITABLE_KEYS
    if isinstance(next(
        value for preset in MOZA_UI_PRESETS.values()
        if key in dict(preset["values"])
        for value in (dict(preset["values"])[key],)
    ), bool)
)


def presets_for_device(device_key: str) -> Tuple[Mapping[str, Any], ...]:
    """Return UI-safe metadata for the captured presets of one Moza base."""

    return tuple(MOZA_UI_PRESETS[item] for item in _DEVICE_PRESETS.get(device_key, ()))


def default_preset_id(device_key: str) -> str:
    presets = _DEVICE_PRESETS.get(device_key, ())
    if not presets:
        raise ValueError(f"Unknown Moza device {device_key!r}")
    return presets[0]


def normalise_calibration(device_key: str, settings: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate and complete a saved Studio calibration document.

    ``preset_id`` chooses one owner-supplied baseline.  The other values are
    deliberate local adjustments and stay bounded by the ranges observed in
    the files (booleans or 0..100 integers).  No hardware write is performed
    here or by this module.
    """

    preset_id = str(settings.get("preset_id") or default_preset_id(device_key))
    preset = MOZA_UI_PRESETS.get(preset_id)
    if preset is None or str(preset.get("device")) != device_key:
        raise ValueError("Choose a captured preset for the selected Moza base")
    values = deepcopy(dict(preset["values"]))
    unknown = set(settings) - (set(MOZA_EDITABLE_KEYS) | {"preset_id"})
    if unknown:
        raise ValueError("Unsupported Moza calibration setting: " + ", ".join(sorted(unknown)))
    for key, value in settings.items():
        if key == "preset_id":
            continue
        if key not in values:
            # A value that belongs to the other physical base must not leak
            # across a profile; such as the A210-only LED brightness fields.
            raise ValueError(f"{key} is not available on the selected Moza preset")
        if key in MOZA_BOOLEAN_KEYS:
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be on or off")
            values[key] = value
        else:
            try:
                number = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be a whole number") from exc
            if not 0 <= number <= 100:
                raise ValueError(f"{key} must be between 0 and 100")
            values[key] = number
    return {"preset_id": preset_id, **values}


def effective_calibration(device_key: str, settings: Mapping[str, Any] | None) -> Dict[str, Any]:
    """Return valid, complete values even for an older blank profile."""

    try:
        return normalise_calibration(device_key, settings or {})
    except ValueError:
        return normalise_calibration(device_key, {"preset_id": default_preset_id(device_key)})
