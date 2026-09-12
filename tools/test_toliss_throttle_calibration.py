#!/usr/bin/env python3
"""Offline guard for BUG-25: ToLiss must not inherit Boeing calibration.

No simulator or hardware is opened. The bridge module is imported only to
exercise its pure throttle conversion helpers and inspect the established
safe-pickup ordering.
"""

from __future__ import annotations

import importlib.util
import inspect
import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
FINAL_PATH = ROOT / "bridge" / "final.py"


def _load_bridge():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(
        "_muslimsim_toliss_throttle_guard", FINAL_PATH,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("bridge/final.py could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bits(*one_based_buttons: int) -> int:
    value = 0
    for button in one_based_buttons:
        value |= 1 << (int(button) - 1)
    return value


def _near(actual: float, expected: float, label: str) -> None:
    assert math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-9), (
        f"{label}: got {actual:.12f}, expected {expected:.12f}"
    )


def main() -> None:
    bridge = _load_bridge()
    checks = 0

    # Pin the pre-existing Boeing constants and pure mapping. A ToLiss repair
    # must not tune any of these values behind Zibo/LevelUp's back.
    assert bridge.WINCTRL_LEFT_IDLE_RAW == 19308
    assert bridge.WINCTRL_RIGHT_IDLE_RAW == 20165
    assert bridge.WINCTRL_LEFT_REV_IDLE_RAW == 13976
    assert bridge.WINCTRL_RIGHT_REV_IDLE_RAW == 14115
    _near(bridge.WINCTRL_REV_IDLE_VALUE, 0.0600001, "Boeing REV IDLE")
    checks += 5
    for idle_raw, rev_idle_raw in (
        (bridge.WINCTRL_LEFT_IDLE_RAW, bridge.WINCTRL_LEFT_REV_IDLE_RAW),
        (bridge.WINCTRL_RIGHT_IDLE_RAW, bridge.WINCTRL_RIGHT_REV_IDLE_RAW),
    ):
        _near(
            bridge._winctrl_throttle_values(
                idle_raw, idle_raw, rev_idle_raw, False, True,
            )[0],
            0.0,
            "Boeing idle",
        )
        _near(
            bridge._winctrl_throttle_values(
                65535, idle_raw, rev_idle_raw, False, False,
            )[0],
            1.0,
            "Boeing TOGA",
        )
        _near(
            bridge._winctrl_throttle_values(
                rev_idle_raw, idle_raw, rev_idle_raw, True, False,
            )[1],
            0.0600001,
            "Boeing reverse idle",
        )
        checks += 3

    toliss_source = "\n".join((
        inspect.getsource(bridge._toliss_build_winctrl_throttle_profile),
        inspect.getsource(bridge._toliss_winctrl_engine_throttle_output),
        inspect.getsource(bridge._toliss_winctrl_throttle_output),
    ))
    for forbidden in (
        "_winctrl_throttle_values",
        "WINCTRL_LEFT_IDLE_RAW",
        "WINCTRL_RIGHT_IDLE_RAW",
        "WINCTRL_LEFT_REV_IDLE_RAW",
        "WINCTRL_RIGHT_REV_IDLE_RAW",
        "WINCTRL_REV_IDLE_VALUE",
    ):
        assert forbidden not in toliss_source, (
            f"ToLiss throttle path has reintroduced Boeing calibration: {forbidden}"
        )
        checks += 1

    ratios = bridge._toliss_throttle_detent_ratios()
    profile = bridge._toliss_build_winctrl_throttle_profile(ratios)
    assert profile["name"] == "toliss-a320-a321-winctrl-v2"
    assert profile["direct_input_targets"] == (
        bridge.TOLISS_THROTTLE_DIRECT_INPUT_TARGETS
    )
    checks += 2

    expected_by_name = {
        "full_reverse": -1.0,
        "reverse_idle": -0.10,
        "idle": 0.0,
        "climb": 0.70,
        "flex_mct": 0.875,
        "toga": 1.0,
    }
    assert bridge.TOLISS_THROTTLE_DIRECT_INPUT_TARGETS == expected_by_name
    # Pin the direct-input windows proven by the installed ToLiss aircraft's
    # own FMOD conditions.  A value derived from the ISCS raw joystick ratios
    # (the former bug) falls below both the CL and FLEX windows.
    assert 0.68 < expected_by_name["climb"] < 0.72
    assert 0.86 < expected_by_name["flex_mct"] < 0.90
    assert expected_by_name["toga"] > 0.98
    assert expected_by_name["idle"] < 0.02
    assert expected_by_name["reverse_idle"] < -0.06
    checks += 6
    engine_cases = {
        "engine1": (0, ((17, 40), (16, 40), (15,), (14,), (13,), (12,))),
        "engine2": (1, ((23, 41), (22, 41), (21,), (20,), (19,), (18,))),
    }
    for engine_key, (engine_index, button_sets) in engine_cases.items():
        anchors = profile["engines"][engine_key]["anchors"]
        assert tuple(anchor[0] for anchor in anchors) == tuple(expected_by_name)
        checks += 1
        for anchor, buttons in zip(anchors, button_sets):
            name, raw, _value, _button = anchor
            # Offset the ADC on purpose: the physical contact must still nail
            # the exact detent output rather than pass jitter through.
            jittered_raw = max(0, min(65535, int(raw) + (37 if raw < 65535 else -37)))
            raw_pair = [20165, 20165]
            raw_pair[engine_index] = jittered_raw
            outputs = bridge._toliss_winctrl_throttle_output(
                raw_pair[0], raw_pair[1], _bits(*buttons), profile=profile,
            )
            _near(outputs[engine_key], expected_by_name[name], f"{engine_key} {name}")
            checks += 1

    # Below idle cannot create reverse unless the matching lift handle is up.
    outputs = bridge._toliss_winctrl_throttle_output(0, 0, 0, profile=profile)
    _near(outputs["engine1"], 0.0, "engine1 reverse gate")
    _near(outputs["engine2"], 0.0, "engine2 reverse gate")
    checks += 2

    # Returning from reverse can briefly overlap REV IDLE and IDLE contacts.
    # IDLE must win immediately even when the raw axis is still nearer the
    # reverse-idle anchor, otherwise ToLiss remains latched in IDLE REV.
    outputs = bridge._toliss_winctrl_throttle_output(
        14500, 14500,
        _bits(15, 16, 21, 22, 40, 41),
        profile=profile,
    )
    _near(outputs["engine1"], 0.0, "engine1 overlapping IDLE contact")
    _near(outputs["engine2"], 0.0, "engine2 overlapping IDLE contact")
    checks += 2

    # If ToLiss says reverse is not on the same axis, negative output stays
    # blocked even with the physical handles raised.
    no_reverse_profile = bridge._toliss_build_winctrl_throttle_profile({
        **ratios,
        "rev_on_same_axis": 0.0,
    })
    outputs = bridge._toliss_winctrl_throttle_output(
        0, 0, _bits(17, 23, 40, 41), profile=no_reverse_profile,
    )
    _near(outputs["engine1"], 0.0, "engine1 same-axis setting")
    _near(outputs["engine2"], 0.0, "engine2 same-axis setting")
    checks += 2

    # ISCS idle/CL/MCT sliders calibrate a native 0..1 joystick axis before
    # ToLiss creates throttle_input. MuslimSim writes throttle_input directly,
    # so changing those raw-axis ratios must never move the canonical direct
    # CL/FLEX targets again. revOnSameAxis remains the one live safety setting.
    different_native_axis = bridge._toliss_build_winctrl_throttle_profile({
        "idle_detent": 0.15,
        "cl_detent": 0.52,
        "mct_detent": 0.76,
        "rev_on_same_axis": 1.0,
    })
    for engine_key in ("engine1", "engine2"):
        outputs_by_name = {
            name: value
            for name, _raw, value, _button in
            different_native_axis["engines"][engine_key]["anchors"]
        }
        assert outputs_by_name == expected_by_name
        checks += 1

    # Engines are calibrated independently. Deliberately move only engine 2's
    # IDLE/REV anchors and prove the same raw count no longer means the same
    # output on both sides.
    custom_raw = {
        "engine1": bridge.TOLISS_A320_A321_THROTTLE_RAW_ANCHORS["engine1"],
        "engine2": (
            ("full_reverse", 0, 23),
            ("reverse_idle", 15000, 22),
            ("idle", 21000, 21),
            ("climb", 46000, 20),
            ("flex_mct", 56000, 19),
            ("toga", 65535, 18),
        ),
    }
    custom_profile = bridge._toliss_build_winctrl_throttle_profile(
        ratios, custom_raw,
    )
    outputs = bridge._toliss_winctrl_throttle_output(
        20500, 20500, 0, profile=custom_profile,
    )
    assert outputs["engine1"] > 0.0
    _near(outputs["engine2"], 0.0, "independent engine2 idle")
    checks += 2

    # Interpolation must stay monotonic from FULL REV through TOGA.
    engine1 = profile["engines"]["engine1"]
    samples = (0, 7000, 14115, 17000, 20165, 30000, 45371, 50000, 55453, 61000, 65535)
    values = [
        bridge._toliss_winctrl_engine_throttle_output(
            raw, _bits(40), engine1,
        )
        for raw in samples
    ]
    assert all(left <= right for left, right in zip(values, values[1:])), values
    checks += 1

    # Startup pickup remains between current-simulator readback and writes.
    run_source = inspect.getsource(bridge._run_toliss_agp_profile)
    queue_at = run_source.index("# WinCtrl throttle -> real ToLiss thrust levers")
    pickup_at = run_source.index("_winctrl_axis_pickup_reached", queue_at)
    read_at = run_source.index("read_dataref_index", queue_at)
    write_at = run_source.index("set_dataref_index", queue_at)
    assert read_at < pickup_at < write_at
    assert "profile=active_toliss_throttle_profile" in run_source[queue_at:write_at]
    assert "calibration_probe_owns_event" in run_source[queue_at:write_at]
    checks += 3

    # The ToLiss reader replaces the preflight WinCtrl consumer. It must keep
    # publishing raw physical axes to Studio even when the simulator dataref
    # is temporarily unavailable during an aircraft reload.
    axis_unpack_at = run_source.index(
        "_, left_raw, right_raw, _speed_raw, button_bits = winctrl_evt",
        queue_at,
    )
    dataref_gate_at = run_source.index(
        "if toliss_throttle_input_id is None:", axis_unpack_at,
    )
    telemetry_block = run_source[axis_unpack_at:dataref_gate_at]
    assert axis_unpack_at < dataref_gate_at
    assert "hardware_lab is not None" in telemetry_block
    assert '"left_thrust"' in telemetry_block
    assert '"right_thrust"' in telemetry_block
    assert "route=False" in telemetry_block
    checks += 5

    print(
        f"ToLiss A320/A321 throttle calibration guard passed: {checks} checks; "
        "six canonical direct detents per engine, handle-gated reverse, independent engines, "
        "Boeing constants unchanged, startup pickup and Studio sliders preserved."
    )


if __name__ == "__main__":
    main()
