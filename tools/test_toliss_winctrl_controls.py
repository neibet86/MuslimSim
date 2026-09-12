#!/usr/bin/env python3
"""Offline guard for BUG-30/50, the complete ToLiss WinCtrl/AGP path.

No simulator, HID handle, SDL reader, or output device is opened.  The test
pins the owner capture which identified the knob push, all native ToLiss
targets, pure lever conversions, profile isolation, long-press page order,
startup no-write ordering, delta updates, and the electrical blackout path.
"""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from bridge import final
from muslimsim.hardware.catalog import device_by_key


def _bits(*buttons: int) -> int:
    value = 0
    for button in buttons:
        value |= 1 << (int(button) - 1)
    return value


def main() -> None:
    checks = 0

    # The only two 37-byte B930 payloads in MODE.pcapng.  The press changes
    # report byte 3 by 0x80 and nothing else: zero-based bit 23 / button 24.
    baseline = bytes.fromhex(
        "018a4010242400000000000000c54ec54e0000000000000000000000000000000000000000"
    )
    pressed = bytes.fromhex(
        "018a4090242400000000000000c54ec54e0000000000000000000000000000000000000000"
    )
    assert len(baseline) == len(pressed) == final.WINCTRL_REPORT_LEN == 37
    changed = int.from_bytes(baseline[1:13], "little") ^ int.from_bytes(
        pressed[1:13], "little"
    )
    assert changed == 1 << 23
    assert final.TOLISS_WINCTRL_TRIM_MODE_BUTTON == 24
    assert final.TOLISS_WINCTRL_BUTTON_CONTROLS[24] == "trim_mode_cycle"
    checks += 4

    role = "STAB"
    seen = []
    for _ in range(4):
        role = final._toliss_next_trim_role(role)
        seen.append(role)
    assert seen == ["RUDDER", "STAB", "RUDDER", "STAB"]
    assert final.TOLISS_WINCTRL_ENGINE_MODE_BUTTONS == {
        7: "engine_mode_crank", 8: "engine_mode_norm", 9: "engine_mode_start",
    }
    assert "aileron_trim" not in final.TOLISS_WINCTRL_DATAREFS
    assert not any("aileron_trim" in key for key in final.TOLISS_WINCTRL_COMMANDS)
    checks += 4

    # ToLiss uses its cockpit's -0.5 ARMED range; the remaining gates remain
    # continuous and the five flap contacts land on Airbus 0/1/2/3/FULL.
    assert final._toliss_winctrl_speedbrake_output(0, _bits(38)) == 0.0
    assert final._toliss_winctrl_speedbrake_output(0, _bits(38, 39)) == 0.0
    assert final._toliss_winctrl_speedbrake_output(1000, _bits(39)) == -0.5
    assert final._toliss_winctrl_speedbrake_output(32000, _bits(37)) == 0.5
    assert final._toliss_winctrl_speedbrake_output(65535, _bits(36)) == 1.0
    for button, expected in ((35, 0.0), (34, .25), (33, .5), (32, .75), (31, 1.0)):
        assert final._toliss_winctrl_flap_output(12345, _bits(button)) == expected
        checks += 1
    assert 0.49 < final._toliss_winctrl_flap_output(32768, 0) < 0.51
    checks += 6

    expected_commands = {
        "engine_1_on": "toliss_airbus/engcommands/Master1On",
        "engine_1_off": "toliss_airbus/engcommands/Master1Off",
        "engine_2_on": "toliss_airbus/engcommands/Master2On",
        "engine_2_off": "toliss_airbus/engcommands/Master2Off",
        "engine_mode_crank": "toliss_airbus/engcommands/EngineModeSwitchToCrank",
        "engine_mode_norm": "toliss_airbus/engcommands/EngineModeSwitchToNorm",
        "engine_mode_start": "toliss_airbus/engcommands/EngineModeSwitchToStart",
        "parking_brake_set": "toliss_airbus/park_brake_set",
        "parking_brake_release": "toliss_airbus/park_brake_release",
        "autothrust_disconnect": "sim/autopilot/autothrottle_off",
    }
    for key, name in expected_commands.items():
        assert final.TOLISS_WINCTRL_COMMANDS[key] == name
        checks += 1
    assert not any(
        name.startswith("laminar/B738")
        for name in final.TOLISS_WINCTRL_COMMANDS.values()
    )
    checks += 1

    # Exact BB80 selectors published by the maintained WINCTRL AGP driver.
    # ON and DECEL are separate lamps; HOT belongs to the brake-fan switch.
    assert final.AGP_BRAKE_FAN_HOT_LED == 6
    assert final.AGP_AUTOBRAKE_DECEL_LED_BY_POSITION == {
        2: 11, 3: 12, 5: 13,
    }
    class _FakeAgp:
        def __init__(self) -> None:
            self.writes: list[list[int]] = []

        def write(self, report: list[int]) -> None:
            self.writes.append(list(report))

    fake_agp = _FakeAgp()
    final._agp_blackout(fake_agp)
    dark_selectors = {
        report[7] for report in fake_agp.writes
        if len(report) > 8 and report[8] == 0
    }
    assert {6, 11, 12, 13, 14, 15, 16}.issubset(dark_selectors)
    checks += 3

    pages = []
    page = "clock"
    for _ in range(4):
        page = final._toliss_agp_next_page(page)
        pages.append(page)
    assert pages == ["radio", "ctl", "clock", "radio"]
    assert final.AGP_NAV_PAGE not in final.TOLISS_AGP_PAGE_ORDER
    assert final.AGP_PAGE_ORDER == ("radio", "ctl", "nav")  # Zibo unchanged.
    checks += 3

    # One captured RST count remains one native fine command. A batched host
    # read is expanded losslessly and later paced through the LCD one step at
    # a time; neither division nor dropped turns may hide intermediate values.
    assert final._toliss_agp_radio_fine_steps(0) == ()
    assert final._toliss_agp_radio_fine_steps(4) == (1, 1, 1, 1)
    assert final._toliss_agp_radio_fine_steps(-3) == (-1, -1, -1)
    checks += 3

    throttle = device_by_key("winctrl_throttle")
    assert throttle is not None
    mode_push = next(c for c in throttle.controls if c.key == "trim_mode_cycle")
    assert mode_push.raw == "B930 HID bit 24"
    checks += 2

    source = (PROJECT / "bridge" / "final.py").read_text(encoding="utf-8")
    start = source.index("def _run_toliss_agp_profile(")
    end = source.index("def _run_pfp_pfd_self_test", start)
    toliss = source[start:end]
    baseline_guard = toliss.index("if not toliss_winctrl_baseline_ready:")
    native_dispatch = toliss.index("_toliss_dispatch_winctrl_button(", baseline_guard)
    assert baseline_guard < native_dispatch
    assert 'source="physical", route=False' in toliss[baseline_guard:native_dispatch]
    assert 'winctrl_evt[0] == "winctrl_flap_axis"' in toliss
    assert '_toliss_apply_surface_axis(' in toliss
    assert 'desired_output_power = _toliss_output_powered()' in toliss
    assert '_toliss_winctrl_blackout()' in toliss
    assert '_agp_blackout(device, packet_number)' in toliss
    assert 'TOLISS_AGP_MODE_LONG_PRESS_SECONDS' in toliss
    assert 'press_command("rmp_swap")' in toliss
    assert 'press_command("nav1_flip")' not in toliss
    assert '_toliss_rotate_fcu_knob("fcu_speed_knob"' in toliss
    assert 'toliss_agp_radio_fine_queue.extend(' in toliss
    assert 'toliss_agp_radio_fine_queue.popleft()' in toliss
    assert 'now + TOLISS_AGP_RADIO_FINE_STEP_INTERVAL' in toliss
    assert 'if first_winctrl_axes:' in toliss
    assert 'speedbrake_state["target"] = numeric("speedbrake", math.nan)' in toliss
    assert 'if not toliss_winctrl_flap_baseline_ready:' in toliss
    assert 'flap_state["target"] = numeric("flaps", math.nan)' in toliss
    park_start = toliss.index("if button_no in (29, 30):")
    park_end = toliss.index("if button_no in TOLISS_WINCTRL_FLAP_DETENTS", park_start)
    park_dispatch = toliss[park_start:park_end]
    assert 'target = 0.0 if button_no == 29 else 1.0' in park_dispatch
    assert 'write_ref("parking_brake", target)' in park_dispatch
    assert 'if "parking_brake" in datarefs:' in park_dispatch
    assert '"brake_panel_lights": "AirbusFBW/OHPLightsATA32_Raw"' in toliss
    assert "read_dataref_index(api_version, ref_id, int(index))" in toliss
    assert "ABrkLoButtonAnim" not in toliss
    assert "ABrkMedButtonAnim" not in toliss
    assert "ABrkMaxButtonAnim" not in toliss
    for index in (11, 12, 14, 16):
        assert f'numeric_element("brake_panel_lights", {index}, 0.0)' in toliss
        checks += 1
    assert "((2, 13), (3, 15), (5, 17))" in toliss
    assert "AGP_BRAKE_FAN_HOT_LED" in toliss
    assert "AGP_AUTOBRAKE_DECEL_LED_BY_POSITION" in toliss
    blackout = toliss[toliss.index("def _toliss_winctrl_blackout"):toliss.index(
        "def _toliss_rotate_fcu_knob"
    )]
    assert "toliss_winctrl_output_started or" not in blackout
    assert 'winctrl_throttle_lab_output("__blackout__", 0)' in blackout
    cold_start = toliss[toliss.index("agp_output_powered = _toliss_output_powered()"):toliss.index(
        "if control_server is not None", toliss.index("agp_output_powered = _toliss_output_powered()")
    )]
    assert "_toliss_winctrl_blackout()" in cold_start
    powered_start = cold_start[cold_start.index("if agp_output_powered:"):]
    assert "_toliss_winctrl_set_backlights(True)" in powered_start
    assert "if toliss_winctrl_output_started" not in toliss
    owner_start = source.index("def _muslimsim_set_winctrl_throttle_lab_output")
    owner_end = source.index("def _muslimsim_select_winctrl_trim_role", owner_start)
    owner = source[owner_start:owner_end]
    assert 'blackout_request = key == "__blackout__"' in owner
    assert "_winctrl_write_trim_text_display(" in owner
    assert "_winctrl_throttle_blackout(winctrl_trim_display_device)" in owner
    studio = (PROJECT / "muslimsim" / "gui" / "studio.py").read_text(
        encoding="utf-8"
    )
    for snippet in (
        '"PUSH KNOB • NEXT TRIM"',
        '("CRANK", "trim_mode_crank")',
        '("NORM", "trim_mode_norm")',
        '("IGN/START", "trim_mode_ign_start")',
        'roles = ("STAB", "RUDDER")',
    ):
        assert snippet in studio
        checks += 1
    checks += 38

    print(
        f"ToLiss WinCtrl/AGP BUG-30/50 guard passed: {checks} checks; "
        "button 24, absolute parking brake, latched ATA32 autobrake/HOT lamps, "
        "all quadrant controls, pickup, two Airbus trim roles, "
        "CLOCK/RADIO/CTRL, lossless paced RST tuning, profile isolation and "
        "output blackout pinned."
    )


if __name__ == "__main__":
    main()
