#!/usr/bin/env python3
"""Offline end-to-end checks for Studio live hardware feedback V1.

No simulator, HID, serial or SDL device is opened.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muslimsim.control.client import ControlClient
from muslimsim.control.server import ControlServer, DeviceRegistration
from muslimsim.gui.live_feedback import (
    compose_live_mirror,
    physical_input_active,
)
from muslimsim.gui.studio import MuslimSimStudio
from muslimsim.hardware.lab import HardwareLab


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class BoolValue:
    def __init__(self, value: bool) -> None:
        self.value = bool(value)

    def get(self) -> bool:
        return self.value


class StudioHarness:
    _device_mirror = MuslimSimStudio._device_mirror
    _live_control_active = MuslimSimStudio._live_control_active
    _control_color = MuslimSimStudio._control_color
    _control_fill = MuslimSimStudio._control_fill

    def __init__(self, *, selected: str, states, lab, kinds) -> None:
        self._selected_device = selected
        self._device_states = states
        self._lab = lab
        self._control_kinds = kinds
        self._selected_visual = None
        self._flash_until = {}
        self.practice_mode = BoolValue(False)
        self._preview_snapshot = {}

    def _learned_source(self, _key: str):
        return ""


def main() -> int:
    checks = 0

    # ------------------------------------------------------------------
    # Root-cause proof: HardwareLab latest state survives diagnostics loss.
    # ------------------------------------------------------------------
    lab = HardwareLab()
    lab.input(
        "mcdu32_bb36", "key_12", 1.0,
        phase="press", source="physical", route=False,
    )
    # Flood the intentionally bounded diagnostic ring so the original key_12
    # event is no longer a reliable event-transport source.
    for index in range(150):
        key = f"key_{index % 74}"
        lab.input(
            "mcdu32_bb36", key, float(index & 1),
            phase="change", source="physical", route=False,
        )
    snapshot = lab.snapshot()
    check(len(snapshot["diagnostics"]) == 100, "diagnostic ring is not bounded as expected")
    check("key_12" in snapshot["inputs"]["mcdu32_bb36"], "latest physical state was lost with diagnostics")
    checks += 2

    # Restore a definite pressed state after the flood.
    lab.input(
        "mcdu32_bb36", "key_12", 1.0,
        phase="press", source="physical", route=False,
    )
    snapshot = lab.snapshot()

    # ------------------------------------------------------------------
    # Composition preserves a real device mirror while adding physical state.
    # ------------------------------------------------------------------
    state = {
        "state": "running",
        "detail": "healthy",
        "mirror": {
            "state": "fmc",
            "lines": ["MCDU LIVE", "123.45"],
            "values": {"existing": 7},
        },
        "diagnostics": {
            "values": {"diagnostic_only": 9},
            "buttons": [True, False],
        },
    }
    mirror = compose_live_mirror("mcdu32_bb36", state, snapshot)
    check(mirror["state"] == "fmc", "service state overwrote established FMC mirror state")
    check(mirror["lines"] == ["MCDU LIVE", "123.45"], "live LCD lines were not preserved")
    check(mirror["values"] == {"existing": 7}, "device mirror values were overwritten")
    check(mirror["buttons"] == [True, False], "missing diagnostic live field was not recovered")
    check(mirror["input_values"]["key_12"] == 1.0, "physical input value did not enter composed mirror")
    check(mirror["lab_inputs"]["key_12"]["source"] == "physical", "input source metadata was lost")
    check(mirror["service_state"] == "running", "service state is not namespaced")
    checks += 7

    # Device with no mirror (the BB62 pattern) still exposes its live
    # diagnostics + HardwareLab state rather than returning {} to Studio.
    pdc_lab = HardwareLab()
    pdc_lab.input(
        "pdc_bb62", "mode_map", 1.0,
        phase="press", source="physical", route=False,
    )
    pdc_state = {
        "state": "connected",
        "diagnostics": {"buttons": [1, 0, 0], "axes": [12, 34]},
    }
    pdc_mirror = compose_live_mirror("pdc_bb62", pdc_state, pdc_lab.snapshot())
    check(pdc_mirror["buttons"] == [1, 0, 0], "PDC diagnostics did not become mirror fallback")
    check(pdc_mirror["axes"] == [12, 34], "PDC axes did not become mirror fallback")
    check(pdc_mirror["input_values"]["mode_map"] == 1.0, "PDC physical selector missing from mirror")
    checks += 3

    # ------------------------------------------------------------------
    # Common faceplate controls now read latest physical state directly.
    # ------------------------------------------------------------------
    harness = StudioHarness(
        selected="mcdu32_bb36",
        states={"mcdu32_bb36": state},
        lab=snapshot,
        kinds={"mcdu32_bb36": {"key_12": "button"}},
    )
    check(harness._device_mirror("mcdu32_bb36")["lines"][0] == "MCDU LIVE", "Studio _device_mirror lost LCD data")
    check(harness._live_control_active("key_12"), "pressed physical MCDU key is not live-active")
    check(harness._control_fill("key_12") == "#0a655e", "common key face did not show physical press")
    check(harness._control_color("key_12") == "#35e7cf", "common key outline did not show physical press")
    checks += 4

    # A release clears persistent button state.
    lab.input(
        "mcdu32_bb36", "key_12", 0.0,
        phase="release", source="physical", route=False,
    )
    released = lab.snapshot()
    check(
        not physical_input_active(released, "mcdu32_bb36", "key_12", kind="button"),
        "released physical button stayed active",
    )
    checks += 1

    # Rotary pulses are visible briefly but do not pretend to have an absolute
    # maintained shaft position.
    rotary_lab = HardwareLab()
    rotary_lab.input(
        "pdc_bb62", "mins_knob_cw", 1.0,
        phase="change", source="physical", route=False,
    )
    rotary_snapshot = rotary_lab.snapshot()
    updated = rotary_snapshot["inputs"]["pdc_bb62"]["mins_knob_cw"]["updated"]
    check(
        physical_input_active(
            rotary_snapshot, "pdc_bb62", "mins_knob_cw",
            kind="rotary", now_wall=updated + 0.20,
        ),
        "recent physical rotary pulse is not visible",
    )
    check(
        not physical_input_active(
            rotary_snapshot, "pdc_bb62", "mins_knob_cw",
            kind="rotary", now_wall=updated + 2.0,
        ),
        "relative rotary incorrectly became a maintained position",
    )
    checks += 2

    # ------------------------------------------------------------------
    # AGP authored faceplate gets its mechanical poses from the same physical
    # input state without changing any AGP simulator behavior.
    # ------------------------------------------------------------------
    agp_lab = HardwareLab()
    for key, value in (
        ("gear_up", 1.0),
        ("brake_fan_on", 1.0),
        ("anti_skid_off", 1.0),
        ("autobrake_med", 1.0),
    ):
        agp_lab.input(
            "agp_bb80", key, value,
            phase="change", source="physical", route=False,
        )
    agp_mirror = compose_live_mirror(
        "agp_bb80",
        {"state": "running", "mirror": {"values": ["U1", "120900", "1200"]}},
        agp_lab.snapshot(),
    )
    controls = agp_mirror["controls"]
    check(controls["gear"] == "UP", "AGP gear pose did not follow physical contact")
    check(controls["brake_fan"] is True, "AGP brake-fan pose did not follow physical contact")
    check(controls["anti_skid"] is False, "AGP anti-skid pose did not follow physical contact")
    check(controls["autobrake"] == "MED", "AGP autobrake pose did not follow physical contact")
    check(agp_mirror["values"] == ["U1", "120900", "1200"], "AGP LCD mirror was overwritten")
    checks += 5

    # ------------------------------------------------------------------
    # Actual loopback control-channel round trip. This proves the bridge-side
    # transport already carried both device mirror and physical state; the
    # defect was Studio's consumption of it, not simulator/device routing.
    # ------------------------------------------------------------------
    server_lab = HardwareLab()
    server_lab.input(
        "pap3_mag", "speed_inc", 1.0,
        phase="change", source="physical", route=False,
    )
    server = ControlServer(server_lab, port=0, token="studio-feedback-test")
    server.register(DeviceRegistration(
        "pap3_mag",
        status=lambda: {
            "state": "connected",
            "mirror": {"values": {"speed": 271, "heading": 123}},
        },
    ))
    port = server.start()
    try:
        response = ControlClient(port, "studio-feedback-test", timeout=1.0).request("status")
    finally:
        server.stop()
    check(response["devices"]["pap3_mag"]["mirror"]["values"]["speed"] == 271,
          "control channel dropped device LCD/value mirror")
    check(response["lab"]["inputs"]["pap3_mag"]["speed_inc"]["source"] == "physical",
          "control channel dropped physical HardwareLab input")
    composed = compose_live_mirror(
        "pap3_mag", response["devices"]["pap3_mag"], response["lab"]
    )
    check(composed["values"]["speed"] == 271, "round-trip LCD value not consumable")
    check(composed["input_values"]["speed_inc"] == 1.0, "round-trip knob input not consumable")
    encoded_size = len(json.dumps(response, separators=(",", ":")).encode("utf-8"))
    check(encoded_size < 1024 * 1024, "status round trip exceeded protocol limit")
    checks += 5

    # ------------------------------------------------------------------
    # Safety/ownership boundary: this fix is Studio/read-only only.
    # ------------------------------------------------------------------
    source = (ROOT / "muslimsim" / "gui" / "live_feedback.py").read_text(encoding="utf-8")
    for forbidden in (
        "set_dataref(", "activate_command(", "import hid", "import pygame",
        "serial.Serial", ".write(",
    ):
        check(forbidden not in source, f"live-feedback layer crossed write/owner boundary: {forbidden}")
        checks += 1

    studio_source = (ROOT / "muslimsim" / "gui" / "studio.py").read_text(encoding="utf-8")
    for token in (
        "compose_live_mirror(",
        "physical_input_active(",
        "self._sync_live_selector_poses(lab)",
        "MUSLIMSIM_STUDIO_LIVE_FEEDBACK_V1",
    ):
        check(token in studio_source, f"Studio feedback integration missing: {token}")
        checks += 1

    print(f"Studio live feedback V1: {checks} checks passed")


if __name__ == "__main__":
    main()
