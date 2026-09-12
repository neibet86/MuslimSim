"""Read-only composition of bridge state for MuslimSim Studio faceplates.

The private bridge already owns the authoritative physical-input state in
``HardwareLab.snapshot()['inputs']`` and many device managers publish a richer
``status()['mirror']`` model.  Historically Studio treated those as two
unrelated channels: device-specific renderers could see the latter, while most
common buttons/knobs depended on a short diagnostic-event flash.  A dropped or
unconsumed diagnostic therefore made a real panel look frozen in Studio even
though its input still reached X-Plane.

This module joins those *read-only* views.  It never opens hardware and never
writes to the simulator or a device.
"""
from __future__ import annotations

# MUSLIMSIM_PRACTICE_DATA_PLANE_V4

import math
import time
from typing import Any, Dict, Mapping, Optional


# Fields that are useful as a faceplate model when a device manager published
# them at the top level or under diagnostics instead of under ``mirror``.
# Existing mirror values always win.
_MIRROR_FALLBACK_FIELDS = (
    "state",
    "detail",
    "live",
    "connected",
    "mode",
    "page",
    "values",
    "lines",
    "pfd",
    "axes",
    "buttons",
    "displays",
    "rotary_raw",
    "controls",
    "light_mask",
    "last_event",
    "standby",
    "frames",
)


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _finite_number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _lab_device_items(
    lab: Mapping[str, Any],
    section: str,
    device_key: str,
) -> Dict[str, Dict[str, Any]]:
    values = lab.get(section)
    if not isinstance(values, Mapping):
        return {}
    device = values.get(str(device_key))
    if not isinstance(device, Mapping):
        return {}
    return {
        str(key): dict(item)
        for key, item in device.items()
        if isinstance(item, Mapping)
    }


def _simple_values(items: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, item in items.items():
        if "value" in item:
            result[str(key)] = item.get("value")
    return result


def _merge_missing_mapping(
    current: Any,
    fallback: Mapping[str, Any],
) -> Dict[str, Any]:
    merged = dict(current) if isinstance(current, Mapping) else {}
    for key, value in fallback.items():
        merged.setdefault(str(key), value)
    return merged


def _input_is_asserted(item: Mapping[str, Any]) -> bool:
    phase = str(item.get("phase") or "").strip().casefold()
    if phase == "release":
        return False
    value = _finite_number(item.get("value"))
    return bool(value is not None and abs(value) > 0.5)


def _latest_asserted_choice(
    items: Mapping[str, Mapping[str, Any]],
    keys: tuple[str, ...],
) -> Optional[str]:
    candidates = []
    for key in keys:
        item = items.get(key)
        if not isinstance(item, Mapping) or not _input_is_asserted(item):
            continue
        updated = _finite_number(item.get("updated")) or 0.0
        candidates.append((updated, key))
    return max(candidates)[1] if candidates else None


def _agp_control_fallback(
    inputs: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    """Derive only the AGP mechanical poses the authored faceplate expects.

    The source contacts are already capture-proven HardwareLab controls.  This
    helper does not infer any simulator behavior; it merely translates the
    asserted on/off contact into the label the existing drawing already uses.
    """

    controls: Dict[str, Any] = {}

    gear = _latest_asserted_choice(inputs, ("gear_up", "gear_down"))
    if gear == "gear_up":
        controls["gear"] = "UP"
    elif gear == "gear_down":
        controls["gear"] = "DOWN"

    fan = _latest_asserted_choice(inputs, ("brake_fan_on", "brake_fan_off"))
    if fan == "brake_fan_on":
        controls["brake_fan"] = True
    elif fan == "brake_fan_off":
        controls["brake_fan"] = False

    skid = _latest_asserted_choice(inputs, ("anti_skid_on", "anti_skid_off"))
    if skid == "anti_skid_on":
        controls["anti_skid"] = True
    elif skid == "anti_skid_off":
        controls["anti_skid"] = False

    brake = _latest_asserted_choice(
        inputs,
        ("autobrake_low", "autobrake_med", "autobrake_max"),
    )
    if brake:
        controls["autobrake"] = brake.removeprefix("autobrake_").upper()

    return controls


def _copy_visual(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _copy_visual(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_visual(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_copy_visual(item) for item in value)
    return value


def _overlay_mapping(base: Any, overlay: Any) -> Dict[str, Any]:
    """Deep-overlay one declarative visual model without mutating either side."""

    result = _mapping(base)
    if not isinstance(overlay, Mapping):
        return result
    for raw_key, value in overlay.items():
        key = str(raw_key)
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _overlay_mapping(result.get(key), value)
        else:
            result[key] = _copy_visual(value)
    return result


def _visual_scalar_like(current: Any, value: Any) -> Any:
    """Preserve the faceplate's existing bool/int/float convention where possible."""

    if isinstance(current, bool):
        number = _finite_number(value)
        return bool(number is not None and abs(number) > 0.5)
    if isinstance(current, int) and not isinstance(current, bool):
        number = _finite_number(value)
        return int(round(number)) if number is not None else value
    if isinstance(current, float):
        number = _finite_number(value)
        return float(number) if number is not None else value
    return value


def _apply_physical_visual_overlay(
    result: Dict[str, Any],
    inputs: Mapping[str, Mapping[str, Any]],
) -> None:
    """Put persistent real control positions above Practice/display pictures.

    Only a control that already has the same authored field is overlaid.  This
    makes the operation visual-only: it cannot invent a device semantic or turn
    an anonymous contact into a named switch.  Baseline records are accepted for
    maintained poses, while later ``physical`` records take over naturally.
    """

    for control_key, item in inputs.items():
        source = str(item.get("source") or "").strip().casefold()
        if source not in {"physical", "baseline"} or "value" not in item:
            continue
        value = item.get("value")
        if control_key in result and not isinstance(result.get(control_key), Mapping):
            result[control_key] = _visual_scalar_like(result.get(control_key), value)
        for namespace in ("values", "controls", "buttons"):
            current = result.get(namespace)
            if isinstance(current, Mapping) and control_key in current:
                merged = dict(current)
                merged[control_key] = _visual_scalar_like(current.get(control_key), value)
                result[namespace] = merged


def _apply_output_visual_overlay(
    key: str,
    result: Dict[str, Any],
    outputs: Mapping[str, Mapping[str, Any]],
) -> None:
    """Reflect only high-level outputs already recorded by HardwareLab.

    These are the same declarative values sent through registered device output
    adapters; no raw HID packet is decoded or guessed here.
    """

    values = _simple_values(outputs)
    if key == "fcu_32_efis":
        windows = values.get("fcu_windows")
        if isinstance(windows, Mapping):
            result["values"] = _overlay_mapping(result.get("values"), windows)
    elif key == "pap3_mag":
        lcd = values.get("lcd")
        if isinstance(lcd, Mapping):
            result["values"] = _overlay_mapping(result.get("values"), lcd)
    elif key == "agp_bb80":
        if all(name in values for name in ("chr", "utc", "et")):
            result["values"] = tuple(str(values[name]) for name in ("chr", "utc", "et"))
    elif key in {"pfp3n_bb35", "mcdu32_bb36"}:
        screen = values.get("screen")
        if isinstance(screen, Mapping) and isinstance(screen.get("lines"), (list, tuple)):
            result["lines"] = [str(line) for line in screen.get("lines")]


def compose_live_mirror(
    device_key: str,
    device_state: Any,
    lab_snapshot: Any,
    *,
    practice_preview: Any = None,
) -> Dict[str, Any]:
    """Return one non-destructive physical + Practice faceplate view.

    The three sources deliberately remain independent:

    1. established device mirror = driver/service truth;
    2. Practice preview = virtual display/output picture only;
    3. HardwareLab inputs/outputs = persistent real physical truth.

    Practice overlays the live mirror, then current physical controls are
    re-applied above that picture.  Thus a virtual LCD can change while the
    real knob/switch/axis remains exactly where the hardware says it is.
    """

    key = str(device_key)
    state = _mapping(device_state)
    diagnostics = _mapping(state.get("diagnostics"))
    lab = _mapping(lab_snapshot)

    result = _mapping(state.get("mirror"))
    if isinstance(practice_preview, Mapping):
        result = _overlay_mapping(result, practice_preview)

    # Some managers publish useful read-only status beside ``mirror``. Promote
    # only missing fields; explicit mirror/Practice content keeps precedence.
    for source in (state, diagnostics):
        for field in _MIRROR_FALLBACK_FIELDS:
            if field not in result and field in source:
                result[field] = _copy_visual(source[field])

    inputs = _lab_device_items(lab, "inputs", key)
    outputs = _lab_device_items(lab, "outputs", key)

    # Current physical pose always wins over a virtual picture for fields the
    # authored faceplate already knows. This is read-only visual composition.
    if inputs:
        _apply_physical_visual_overlay(result, inputs)

    # Actual high-level Practice output records may be newer than the preview
    # snapshot. Reflect them only through known declarative adapter fields.
    if outputs:
        _apply_output_visual_overlay(key, result, outputs)

    result["lab_inputs"] = inputs
    result["lab_outputs"] = outputs
    result["input_values"] = _simple_values(inputs)
    result["output_values"] = _simple_values(outputs)

    if inputs:
        result["inputs"] = _merge_missing_mapping(result.get("inputs"), inputs)
    if outputs:
        result["outputs"] = _merge_missing_mapping(result.get("outputs"), outputs)

    if key == "agp_bb80" and inputs:
        # Mechanical contact truth must be last so Practice cannot move the
        # authored gear/fan/skid/autobrake picture away from the real hardware.
        physical_controls = _agp_control_fallback(inputs)
        current_controls = dict(result.get("controls") or {})
        current_controls.update(physical_controls)
        result["controls"] = current_controls

    if "state" in state:
        result.setdefault("service_state", state.get("state"))
    if "detail" in state:
        result.setdefault("service_detail", state.get("detail"))

    return result


def physical_input_item(
    lab_snapshot: Any,
    device_key: str,
    control_key: str,
) -> Dict[str, Any]:
    lab = _mapping(lab_snapshot)
    return _lab_device_items(lab, "inputs", str(device_key)).get(
        str(control_key), {}
    )


def physical_input_active(
    lab_snapshot: Any,
    device_key: str,
    control_key: str,
    *,
    kind: str = "",
    now_wall: Optional[float] = None,
    rotary_recent_seconds: float = 0.80,
) -> bool:
    """Whether one real physical input should be visibly active in Studio.

    Maintained buttons/toggles/selectors follow their latest asserted state.
    Relative rotaries are pulses rather than positions, so they illuminate only
    for a short interval after the bridge saw a physical change.  Axes are
    rendered by their device-specific geometry and are never treated as a
    pressed button here.
    """

    item = physical_input_item(lab_snapshot, device_key, control_key)
    if not item or str(item.get("source") or "").casefold() != "physical":
        return False

    phase = str(item.get("phase") or "").strip().casefold()
    kind = str(kind or "").strip().casefold()

    if kind == "axis":
        return False
    if kind in {"rotary", "knob"}:
        updated = _finite_number(item.get("updated"))
        if updated is None:
            return phase in {"change", "press"}
        if now_wall is None:
            now_wall = time.time()
        return (
            phase in {"change", "press"}
            and 0.0 <= float(now_wall) - updated <= max(0.05, rotary_recent_seconds)
        )

    return _input_is_asserted(item)


__all__ = (
    "compose_live_mirror",
    "physical_input_active",
    "physical_input_item",
)
