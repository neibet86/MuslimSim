#!/usr/bin/env python3
"""Offline guard for ToLiss's profile-scoped six-detent WinCtrl probe."""

from __future__ import annotations

import inspect
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muslimsim.hardware.profiles import HardwareProfileStore, ProfileError
from muslimsim.hardware.toliss_throttle_calibration import (
    AIRCRAFT_FAMILY,
    DEFAULT_RAW_GATES,
    DIRECT_INPUT_TARGETS,
    DETENT_BUTTONS,
    DETENT_ORDER,
    SETTLE_RAW_TOLERANCE,
    SETTLE_SECONDS,
    TolissThrottleDetentProbe,
    calibration_to_raw_anchors,
    default_calibration,
    normalise_calibration,
)
from muslimsim.gui import studio


def _bits(*one_based_buttons: int) -> int:
    value = 0
    for button in one_based_buttons:
        value |= 1 << (int(button) - 1)
    return value


def _observe_gate(
    probe: TolissThrottleDetentProbe,
    gate: str,
    *,
    at: float,
    left: bool = True,
    right: bool = True,
) -> None:
    buttons = []
    if left:
        buttons.append(DETENT_BUTTONS["left"][gate])
    if right:
        buttons.append(DETENT_BUTTONS["right"][gate])
    probe.observe(
        DEFAULT_RAW_GATES["left"][gate],
        DEFAULT_RAW_GATES["right"][gate],
        _bits(*buttons),
        now=at,
    )
    probe.observe(
        DEFAULT_RAW_GATES["left"][gate],
        DEFAULT_RAW_GATES["right"][gate],
        _bits(*buttons),
        now=at + SETTLE_SECONDS + 0.01,
    )


def main() -> None:
    checks = 0
    default = default_calibration()
    assert normalise_calibration(default) == default
    assert default["aircraft_family"] == AIRCRAFT_FAMILY
    assert default["version"] == 2
    assert SETTLE_SECONDS >= 0.25
    assert SETTLE_RAW_TOLERANCE == 40
    assert DIRECT_INPUT_TARGETS == {
        "full_reverse": -1.0,
        "reverse_idle": -0.10,
        "idle": 0.0,
        "climb": 0.70,
        "flex_mct": 0.875,
        "toga": 1.0,
    }
    checks += 6

    anchors = calibration_to_raw_anchors(default)
    assert tuple(item[0] for item in anchors["engine1"]) == DETENT_ORDER
    assert tuple(item[0] for item in anchors["engine2"]) == DETENT_ORDER
    assert tuple(item[2] for item in anchors["engine1"]) == tuple(
        DETENT_BUTTONS["left"][gate] for gate in DETENT_ORDER
    )
    assert tuple(item[2] for item in anchors["engine2"]) == tuple(
        DETENT_BUTTONS["right"][gate] for gate in DETENT_ORDER
    )
    checks += 4

    for broken in (
        {**default, "aircraft_family": "zibo-737"},
        {**default, "left": {**default["left"], "climb": default["left"]["idle"]}},
        {**default, "version": 1},
        {**default, "version": 99},
    ):
        try:
            normalise_calibration(broken)
        except ValueError:
            checks += 1
        else:
            raise AssertionError(f"invalid calibration was accepted: {broken}")

    # The first contact edge is only a candidate. Follow the raw axis as it
    # travels another few thousand counts into the mechanical notch, then
    # commit the final resting value only after the complete stable dwell.
    probe = TolissThrottleDetentProbe()
    probe.start()
    full_reverse_bits = _bits(
        DETENT_BUTTONS["left"]["full_reverse"],
        DETENT_BUTTONS["right"]["full_reverse"],
    )
    first = probe.observe(1000, 1200, full_reverse_bits, now=0.0)
    assert first["progress"] == {"left": 0, "right": 0}
    assert first["settling"]["left"]["raw"] == 1000
    probe.observe(3000, 3200, full_reverse_bits, now=0.10)
    probe.observe(5000, 5200, full_reverse_bits, now=0.20)
    not_yet = probe.observe(
        5000, 5200, full_reverse_bits,
        now=0.20 + SETTLE_SECONDS - 0.01,
    )
    assert not_yet["progress"] == {"left": 0, "right": 0}
    settled = probe.observe(
        5000, 5200, full_reverse_bits,
        now=0.20 + SETTLE_SECONDS + 0.01,
    )
    assert settled["captured"]["left"]["full_reverse"] == 5000
    assert settled["captured"]["right"]["full_reverse"] == 5200
    checks += 5

    # Releasing the contact before the dwell completes cancels the candidate;
    # elapsed wall time while outside the notch can never save it later.
    probe = TolissThrottleDetentProbe()
    probe.start()
    probe.observe(100, 100, full_reverse_bits, now=0.0)
    released = probe.observe(200, 200, 0, now=SETTLE_SECONDS + 1.0)
    assert released["settling"] == {"left": None, "right": None}
    restarted = probe.observe(
        400, 400, full_reverse_bits, now=SETTLE_SECONDS + 1.1,
    )
    assert restarted["progress"] == {"left": 0, "right": 0}
    assert restarted["settling"]["left"]["raw"] == 400
    checks += 3

    # Both levers may be swept together. An unrelated contact cannot advance
    # the expected FULL REV gate, and completion is consumable exactly once.
    probe = TolissThrottleDetentProbe()
    probe.start()
    probe.observe(1234, 1234, _bits(1, 2), now=0.0)
    assert probe.snapshot()["progress"] == {"left": 0, "right": 0}
    checks += 1
    for index, gate in enumerate(DETENT_ORDER, 1):
        _observe_gate(probe, gate, at=float(index))
        assert probe.snapshot()["progress"] == {"left": index, "right": index}
        checks += 1
    completed = probe.consume_completed()
    assert completed == default
    assert probe.consume_completed() is None
    probe.mark_saved()
    assert probe.snapshot()["saved"] is True
    checks += 3

    # Sides are independent: engine 1 may finish before engine 2 without
    # copying either side's values or skipping the right-side contact order.
    probe = TolissThrottleDetentProbe()
    probe.start()
    for index, gate in enumerate(DETENT_ORDER):
        _observe_gate(probe, gate, at=float(index), right=False)
    assert probe.snapshot()["progress"] == {"left": 6, "right": 0}
    for index, gate in enumerate(DETENT_ORDER, 10):
        _observe_gate(probe, gate, at=float(index), left=False)
    assert probe.consume_completed() == default
    checks += 2

    # A gate that is too close remains uncaptured and reports a useful error;
    # a later valid contact can recover without restarting the whole probe.
    probe = TolissThrottleDetentProbe()
    probe.start()
    _observe_gate(probe, "full_reverse", at=0.0)
    probe.observe(50, 50, _bits(16, 22), now=1.0)
    probe.observe(50, 50, _bits(16, 22), now=1.0 + SETTLE_SECONDS + 0.01)
    failed = probe.snapshot()
    assert failed["progress"] == {"left": 1, "right": 1}
    assert "too close" in failed["error"]
    _observe_gate(probe, "reverse_idle", at=2.0)
    assert probe.snapshot()["progress"] == {"left": 2, "right": 2}
    checks += 3

    # HardwareProfileStore accepts only the marked ToLiss schema for this
    # device, keeps exact unit-specific counts, and preserves them through a
    # real save/reload rather than only in the running Studio process.
    settled_profile = {
        **default,
        "left": {
            "full_reverse": 3,
            "reverse_idle": 14115,
            "idle": 20165,
            "climb": 45370,
            "flex_mct": 55452,
            "toga": 65534,
        },
        "right": {
            "full_reverse": 4,
            "reverse_idle": 14116,
            "idle": 20166,
            "climb": 45371,
            "flex_mct": 55453,
            "toga": 65535,
        },
    }
    with tempfile.TemporaryDirectory() as directory:
        profile_path = Path(directory) / "hardware_profiles_toliss.json"
        store = HardwareProfileStore(profile_path)
        store.load()
        store.set_calibration("winctrl_throttle", settled_profile)
        assert store.calibration("winctrl_throttle") == settled_profile
        store.save()
        reopened = HardwareProfileStore(profile_path)
        reopened.load()
        assert reopened.calibration("winctrl_throttle") == settled_profile
        try:
            reopened.set_calibration(
                "winctrl_throttle",
                {**default, "aircraft_family": "zibo-737"},
            )
        except ProfileError:
            checks += 1
        else:
            raise AssertionError("foreign-aircraft throttle calibration was accepted")
    checks += 2

    studio_source = inspect.getsource(studio.MuslimSimStudio)
    assert "toliss_throttle_calibration_start" in studio_source
    assert "normalise_toliss_throttle_calibration" in studio_source
    assert "RAW {int(round(fraction * TOLISS_THROTTLE_RAW_AXIS_MAX)):05d}" in studio_source
    assert 'f"{short_labels[gate]}\\n{int(gates[gate]):05d}"' in studio_source
    assert "HOLD {label} STEADY" in studio_source
    faceplate_source = inspect.getsource(studio.MuslimSimStudio._draw_winctrl_throttle)
    assert "detent_font_size=8 if is_toliss else 7" in faceplate_source
    assert "CAPTURED OUTPUT TESTS" not in faceplate_source
    assert "NEW CAPTURED AUXILIARY BUTTONS" not in faceplate_source
    assert "LIVE HARDWARE OVERRIDES STUDIO PRACTICE CONTROLS" in faceplate_source
    click_source = inspect.getsource(studio.MuslimSimStudio._faceplate_click)
    assert '"toliss_throttle_calibration_"' in click_source
    checks += 10

    final_source = (ROOT / "bridge" / "final.py").read_text(encoding="utf-8")
    assert "tuple(range(12, 24))" in final_source
    assert 'calibration=lambda values: _toliss_apply_raw_throttle_calibration(' in final_source
    assert "if calibration_probe_owns_event:" in final_source
    assert "latest_probe_snapshot" in final_source
    assert "if toliss_throttle_probe.is_active():" in final_source
    assert "toliss_throttle_previous[engine_key] = math.nan" in final_source
    command_source = final_source[
        final_source.index("def _toliss_winctrl_throttle_command"):
        final_source.index("    try:", final_source.index("def _toliss_winctrl_throttle_command"))
    ]
    assert command_source.index("toliss_throttle_probe.start()") < command_source.index(
        "_toliss_rearm_throttle_pickup()"
    )
    checks += 7

    print(
        f"ToLiss throttle probe guard passed: {checks} checks; six settled "
        "contact gates, independent engines, profile persistence/validation, "
        "readable Studio ruler, and suspended live writes preserved."
    )


if __name__ == "__main__":
    main()
