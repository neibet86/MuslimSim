"""Read-only adapters for the shared PDC canvas; never change hardware mappings."""
from typing import Any, Mapping

BB62_CHOICES = {
    'mins_mode': ('mins_mode_radio', 'mins_mode_baro'),
    'baro_unit': ('baro_mode_in', 'baro_mode_hpa'),
    'vor1': ('vor_adf_1_vor', 'vor_adf_1_off', 'vor_adf_1_adf'),
    'vor2': ('vor_adf_2_vor', 'vor_adf_2_off', 'vor_adf_2_adf'),
    'map_mode': ('mode_app', 'mode_vor', 'mode_map', 'mode_plan'),
    'map_range': ('range_5', 'range_10', 'range_20', 'range_40', 'range_80', 'range_160', 'range_320', 'range_640'),
}
BB62_ALIASES = {
    'mins_rst': 'mins_reset', 'mins_dec': 'mins_knob_ccw', 'mins_inc': 'mins_knob_cw',
    'baro_dec': 'baro_knob_ccw', 'baro_inc': 'baro_knob_cw',
}
# These locations exist in the requested design but have no confirmed named
# source in the current BB62 capture. Only explicit user assignment supplies it.
BB62_UNCAPTURED = {'ctr': 'CTR', 'range_640': 'RANGE 640'}


def control_keys(device: str, key: str) -> tuple[str, ...]:
    if device != 'pdc_bb62':
        return (key,)
    return BB62_CHOICES.get(key, (BB62_ALIASES.get(key, key),))


def selector_value(device: str, mirror: Mapping, key: str, default: int, learned: Mapping) -> int:
    values = mirror.get('input_values') or {}
    records = mirror.get('lab_inputs') or {}
    choices = control_keys(device, key)
    if device == 'pdc_bb62' and key in BB62_CHOICES:
        candidates = []
        for index, control in enumerate(choices):
            source = learned.get(control, control)
            record = records.get(source) or {}
            value = values.get(source, record.get('value', 0))
            try:
                if record.get('phase') != 'release' and float(value) > 0.5:
                    candidates.append((float(record.get('updated', 0)), index))
            except (ValueError, TypeError):
                pass
        return max(candidates)[1] if candidates else default
    source = learned.get(key, key)
    try:
        return int(round(float(values.get(source, mirror.get(key, default)))))
    except (ValueError, TypeError):
        return default


def recent_input(mirror: Mapping, source: str, now: float) -> bool:
    """A fast tap is still visible when press and release fall between polls."""
    record = (mirror.get('lab_inputs') or {}).get(source) or {}
    if record.get('phase') not in {'press', 'release', 'change'}:
        return False
    try:
        age = now - float(record.get('updated', 0))
        return 0 <= age < 0.25
    except (ValueError, TypeError):
        return False


def rotary_angle(state: dict, mirror: Mapping, dec: str, inc: str) -> float:
    """Animate observed detents, retaining motion after a quick release.

    First paint adopts the current snapshot without replaying historic presses.
    Release after an observed press is not a second step. A press/release pair
    completed between polls still produces one visible step.
    """
    first = 'seen' not in state
    seen = state.setdefault('seen', {})
    angle = state.setdefault('angle', 0.0)
    records = mirror.get('lab_inputs') or {}
    for key, sign in ((dec, -1), (inc, 1)):
        record = records.get(key) or {}
        mark = record.get('sequence', record.get('updated'))
        phase = record.get('phase')
        previous = seen.get(key)
        seen[key] = (mark, phase)
        if first or mark is None or (previous and previous[0] == mark):
            continue
        if phase == 'press' or (phase == 'release' and (not previous or previous[1] != 'press')):
            angle += sign * 24.0
    state['angle'] = angle % 360.0
    return state['angle']


def cyclic_range_angle(state: dict, position: int) -> float:
    """Unwrap BB51's existing 0..7 pose feed for unlimited visual rotation.

    Adopts the first position without startup motion. Crossings 7->0 and 0->7
    continue in the same direction rather than jumping between hard stops.
    This changes no input records, profile bindings or simulator range values.
    """
    angle = state.setdefault('angle', 0.0)
    if position not in range(8):
        return angle
    previous = state.get('position')
    state['position'] = position
    if previous is not None:
        delta = position - previous
        if delta > 4:
            delta -= 8
        elif delta < -4:
            delta += 8
        angle += delta * 45.0
    state['angle'] = angle
    return angle
