#!/usr/bin/env python3
"""Offline regression guard for BUG-22/23/24/34/36/37/50 ToLiss BA01 FCU/EFIS parity.

This test never opens X-Plane or a HID device. It pins the captured 41-byte
input contract, every FCU/EFIS lamp selector, writable ToLiss knob inputs,
selected heading/V/S/FPA sources, and the native Airbus mode presentations
while preserving the working speed/altitude and legacy Zibo display paths.
"""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.devices.fcu_efis_ba01 import (
    FCU_EFIS_CONTROL_REPORT_LENGTH,
    FcuRawInputEvent,
    MuslimSimFCUEFIS,
    fcu_efis_button_led_packet,
    fcu_efis_display_packets,
)
from muslimsim.devices.fcu_efis_ba01_toliss import (
    FCU_EFIS_TOLISS_ALTITUDE_STEP_DATAREF,
    FCU_EFIS_TOLISS_NAV_SOURCE,
    FCU_EFIS_TOLISS_ROTARY_DATAREFS,
    FCU_EFIS_TOLISS_UNDRIVEN,
    MuslimSimFCUEFISTolissDispatcher,
)


FINAL_PATH = PROJECT / "bridge" / "final.py"


def _event(control: str, bit: int = 0, phase: str = "press") -> FcuRawInputEvent:
    return FcuRawInputEvent(control, phase, 1 if phase == "press" else 0, bit)


def main() -> None:
    checks = 0

    # Exact endpoint 0x81 BA01 report observed in the owner's ToLiss capture.
    captured = bytes.fromhex(
        "01000000020088081200100a2200000000000000000000000000000000030021013c0087ff0100edff"
    )
    assert len(captured) == 41
    assert FCU_EFIS_CONTROL_REPORT_LENGTH == 13
    assert MuslimSimFCUEFIS._report(captured) == captured
    assert MuslimSimFCUEFIS._report(bytes(12)) is None
    assert MuslimSimFCUEFIS._report(bytes((2,)) + bytes(40)) is None
    checks += 5

    events: list[FcuRawInputEvent] = []
    manager = MuslimSimFCUEFIS(input_sink=events.append)
    before = bytes(41)
    after = bytearray(before)
    after[2] |= 0x04  # bit 10: speed clockwise
    after[20] |= 0x80  # outside the confirmed twelve-byte control bitmap
    manager._emit_changes(before, bytes(after))
    assert [(event.control, event.phase) for event in events] == [("speed_inc", "press")]
    checks += 1

    for key, selector in {
        "loc": 3, "ap1": 5, "ap2": 7, "athr": 9, "exped": 11, "appr": 13,
    }.items():
        packet = fcu_efis_button_led_packet(key, True)
        assert packet[:3] == bytes((0x02, 0x10, 0xBB))
        assert packet[7:9] == bytes((selector, 1))
        checks += 2

    # Physical right-side presses at 61.624..63.074 seconds in EFIS L.R.pcapng
    # pair one-for-one with selectors 5..9. The two EFIS units are symmetric.
    efis_filter_selectors = {
        "cstr": 5, "wpt": 6, "vord": 7, "ndb": 8, "arpt": 9,
    }
    for side, identifier in (("left", 0x0D), ("right", 0x0E)):
        for control, selector in efis_filter_selectors.items():
            lit = fcu_efis_button_led_packet(f"{side}_{control}", True)
            dark = fcu_efis_button_led_packet(f"{side}_{control}", False)
            assert lit == bytes(
                (0x02, identifier, 0xBF, 0, 0, 0x03, 0x49, selector, 1, 0, 0, 0, 0, 0)
            )
            assert dark == bytes(
                (0x02, identifier, 0xBF, 0, 0, 0x03, 0x49, selector, 0, 0, 0, 0, 0, 0)
            )
            checks += 2

    display_values = {
        "display_enabled": True,
        "speed": 250,
        "heading": 90,
        "altitude": 10000,
        "vertical_speed": -4800,
    }
    legacy_packet = fcu_efis_display_packets(display_values)[0][0]
    assert legacy_packet[32:43] == bytes.fromhex("04b6afafafcfe6afaf4f00")

    legacy_mach_packet = fcu_efis_display_packets({
        "display_enabled": True,
        "speed_is_mach": True,
        "speed": 0.77,
        "heading": 357,
        "altitude": 4300,
        "vertical_speed": -1200,
    })[0][0]
    assert legacy_mach_packet[25:43] == bytes.fromhex(
        "00e1e044cf0b8e04d046afaf0f66adaf4f00"
    )

    airbus_values = dict(display_values, airbus_fcu_presentation=True)
    airbus_descent_packet = fcu_efis_display_packets(airbus_values)[0][0]
    assert airbus_descent_packet[32:43] == bytes.fromhex("0cb6bfbfbfdfe66f634300")

    airbus_values["vertical_speed"] = 4800
    airbus_climb_packet = fcu_efis_display_packets(airbus_values)[0][0]
    assert airbus_climb_packet[32:43] == bytes.fromhex("0cb6bfbfbfdfe67f634300")

    # Exact dynamic bytes for the owner's four reference-screen states.
    ias_hdg_vs = fcu_efis_display_packets({
        "display_enabled": True,
        "airbus_fcu_presentation": True,
        "speed": 113,
        "heading": 0,
        "altitude": 4300,
        "vertical_speed": 0,
    })[0][0]
    assert ias_hdg_vs[25:43] == bytes.fromhex(
        "6060f40800a0af0cd056bfbfbfaf7f634300"
    )

    # ToLiss opts into fixed-width numeric windows.  One knot/degree/foot must
    # be 001/001/00001; the default remains space-padded for legacy/Zibo.
    padded_minimums = fcu_efis_display_packets({
        "display_enabled": True,
        "airbus_fcu_presentation": True,
        "zero_pad_fcu_values": True,
        "speed": 1,
        "heading": 1,
        "altitude": 1,
        "vertical_speed": 0,
    })[0][0]
    assert padded_minimums[25:43] == bytes.fromhex(
        "fafa60a8af0fa6acbfbfbf1fb6af7f634300"
    )
    legacy_minimums = fcu_efis_display_packets({
        "display_enabled": True,
        "airbus_fcu_presentation": True,
        "speed": 1,
        "heading": 1,
        "altitude": 1,
        "vertical_speed": 0,
    })[0][0]
    assert legacy_minimums[25:43] == bytes.fromhex(
        "000060080000a60c10101010b6af7f634300"
    )
    checks += 2

    mach_trk_fpa = fcu_efis_display_packets({
        "display_enabled": True,
        "airbus_fcu_presentation": True,
        "speed_is_mach": True,
        "speed": 0.77,
        "heading": 357,
        "altitude": 4300,
        "vertical_speed": 0,
        "flight_path_angle": 0.0,
        "track_fpa_mode": True,
    })[0][0]
    assert mach_trk_fpa[25:43] == bytes.fromhex(
        "fae1e044cf0b6e03d056bfbfbfbf1f008000"
    )

    # Managed Airbus windows are electrically lit. ToLiss's dashed flags mean
    # three dashes plus the large managed dot for SPD/MACH and HDG, and five
    # dashes (sign stroke + four cells) for V/S; they never mean blank bytes.
    managed_base = {
        "display_enabled": True,
        "airbus_fcu_presentation": True,
        "zero_pad_fcu_values": True,
        "speed_dashed": True,
        "speed_managed": True,
        "heading": 283,
        "heading_dashed": True,
        "heading_managed": True,
        "altitude": 36000,
        "vertical_speed": 0,
        "vertical_speed_dashed": True,
    }
    managed_ias = fcu_efis_display_packets(dict(
        managed_base, speed=250, speed_is_mach=False,
    ))[0][0]
    assert managed_ias[25:43] == bytes.fromhex(
        "0404044a4040b04cffbbbfbf5f4040404000"
    )
    managed_mach = fcu_efis_display_packets(dict(
        managed_base, speed=0.778, speed_is_mach=True,
    ))[0][0]
    assert managed_mach[25:43] == bytes.fromhex(
        "040404464040b04cffbbbfbf5f4040404000"
    )
    checks += 2

    # At cruise the PFD can keep its Mach caption visible while the FCU has
    # been switched back to selected knots.  The FCU unit flag must win: 257
    # is SPD 257, never a Mach value clipped to .99.  Switching back to MACH
    # must immediately restore the real .77 target.
    cruise_knots = fcu_efis_display_packets({
        "display_enabled": True,
        "airbus_fcu_presentation": True,
        "zero_pad_fcu_values": True,
        "speed": 257,
        "speed_is_mach": False,
        "heading": 283,
        "altitude": 36000,
        "vertical_speed": 0,
    })[0][0]
    assert cruise_knots[25:43] == bytes.fromhex(
        "d6bce068ed4faf4cffbbbfbfbfaf7f634300"
    )
    cruise_mach = fcu_efis_display_packets({
        "display_enabled": True,
        "airbus_fcu_presentation": True,
        "zero_pad_fcu_values": True,
        "speed": 0.77,
        "speed_is_mach": True,
        "heading": 283,
        "altitude": 36000,
        "vertical_speed": 0,
    })[0][0]
    assert cruise_mach[25:43] == bytes.fromhex(
        "fae1e064ed4faf4cffbbbfbfbfaf7f634300"
    )
    checks += 2

    fpa_descent = fcu_efis_display_packets({
        "display_enabled": True,
        "airbus_fcu_presentation": True,
        "speed": 250,
        "heading": 90,
        "altitude": 10000,
        "vertical_speed": 0,
        "flight_path_angle": -3.2,
        "track_fpa_mode": True,
    })[0][0]
    assert fpa_descent[25:43] == bytes.fromhex(
        "d6bcfa08c0af6f03b6bfbfbf5f7f0d008000"
    )

    unpowered = fcu_efis_display_packets({
        "display_enabled": False,
        "airbus_fcu_presentation": True,
        "speed_is_mach": True,
        "track_fpa_mode": True,
        "flight_path_angle": 3.2,
    })[0][0]
    assert unpowered[25:43] == bytes(18)
    checks += 8

    names_by_id: dict[int, str] = {}
    ids_by_name: dict[str, int] = {}
    values: dict[str, float] = {}
    writes: list[tuple[str, float]] = []

    def dataref_id(_api: str, name: str) -> int:
        if name not in ids_by_name:
            identifier = len(ids_by_name) + 1
            ids_by_name[name] = identifier
            names_by_id[identifier] = name
        return ids_by_name[name]

    def read_dataref(_api: str, identifier: int) -> float:
        return values.get(names_by_id[identifier], 0.0)

    def set_dataref(_api: str, identifier: int, value: float) -> None:
        name = names_by_id[identifier]
        values[name] = float(value)
        writes.append((name, float(value)))

    dispatcher = MuslimSimFCUEFISTolissDispatcher(
        api_version="test",
        resolve_dataref_id=dataref_id,
        read_dataref=read_dataref,
        set_dataref=set_dataref,
        resolve_command_id=lambda _api, _name: 1,
        activate_command=lambda _api, _command, _duration: None,
    )

    rotary_cases = (
        ("speed_inc", 0, 1),
        ("speed_dec", 0, -1),
        ("heading_inc", 29, -10),
        ("heading_dec", -10, 29),
        ("altitude_inc", 0, 1),
        ("altitude_dec", 0, -1),
        ("vs_inc", 0, 1),
        ("vs_dec", 0, -1),
    )
    for control, initial, expected in rotary_cases:
        dataref, _delta = FCU_EFIS_TOLISS_ROTARY_DATAREFS[control]
        values[dataref] = float(initial)
        writes.clear()
        dispatcher(_event(control))
        assert writes[-1] == (dataref, float(expected))
        checks += 1

    writes.clear()
    dispatcher(_event("altitude_step_100"))
    dispatcher(_event("altitude_step_1000"))
    assert writes[-2:] == [
        (FCU_EFIS_TOLISS_ALTITUDE_STEP_DATAREF, 0.0),
        (FCU_EFIS_TOLISS_ALTITUDE_STEP_DATAREF, 1.0),
    ]
    checks += 2

    writes.clear()
    dispatcher(_event("speed_inc", phase="release"))
    assert not writes
    checks += 1

    expected_sources = {
        "left_nav1_adf": ("ckpt/fcu/adf1Left/anim", 0),
        "left_nav1_off": ("ckpt/fcu/adf1Left/anim", 1),
        "left_nav1_vor": ("ckpt/fcu/adf1Left/anim", 2),
        "left_nav2_adf": ("ckpt/fcu/adf2Left/anim", 0),
        "left_nav2_off": ("ckpt/fcu/adf2Left/anim", 1),
        "left_nav2_vor": ("ckpt/fcu/adf2Left/anim", 2),
        "right_nav1_adf": ("ckpt/fcu/adf1Right/anim", 0),
        "right_nav1_off": ("ckpt/fcu/adf1Right/anim", 1),
        "right_nav1_vor": ("ckpt/fcu/adf1Right/anim", 2),
        "right_nav2_adf": ("ckpt/fcu/adf2Right/anim", 0),
        "right_nav2_off": ("ckpt/fcu/adf2Right/anim", 1),
        "right_nav2_vor": ("ckpt/fcu/adf2Right/anim", 2),
    }
    assert FCU_EFIS_TOLISS_NAV_SOURCE == expected_sources
    assert not FCU_EFIS_TOLISS_UNDRIVEN
    checks += 2
    for control, (dataref, position) in expected_sources.items():
        writes.clear()
        dispatcher(_event(control))
        assert writes == [(dataref, float(position))]
        checks += 1

    source = FINAL_PATH.read_text(encoding="utf-8")
    start = source.index("fcu_efis_dataref_names = {")
    end = source.index("next_fcu_efis_display_read = 0.0", start)
    display_setup = source[start:end]
    assert '"speed": "sim/cockpit/autopilot/airspeed"' in display_setup
    assert '"speed": "toliss_airbus/pfdoutputs/general/ap_speed_value"' not in display_setup
    assert '"speed_is_mach_raw": "sim/cockpit/autopilot/airspeed_is_mach"' in display_setup
    assert '"speed_is_mach_raw": "AirbusFBW/ShowMachCapt"' not in display_setup
    assert '"altitude": "sim/cockpit2/autopilot/altitude_dial_ft"' in display_setup
    assert '"altitude": "toliss_airbus/pfdoutputs/general/ap_alt_target_value"' not in display_setup
    assert '"heading": "sim/cockpit/autopilot/heading_mag"' in display_setup
    assert '"vertical_speed": "sim/cockpit/autopilot/vertical_velocity"' in display_setup
    assert '"flight_path_angle": "sim/cockpit2/autopilot/fpa"' in display_setup
    assert '"track_fpa_mode_raw": "AirbusFBW/HDGTRKmode"' in display_setup
    assert '"heading": "AirbusFBW/HDGCapt"' not in display_setup
    assert '"vertical_speed": "AirbusFBW/VS"' not in display_setup
    for dataref in (
        "AirbusFBW/LOCilluminated", "AirbusFBW/AP1Engage",
        "AirbusFBW/AP2Engage", "AirbusFBW/ATHRmode",
        "AirbusFBW/APVerticalMode", "AirbusFBW/APPRilluminated",
        "AirbusFBW/FD1Engage", "AirbusFBW/FD2Engage",
        "AirbusFBW/ILSonCapt", "AirbusFBW/ILSonFO",
    ):
        assert dataref in display_setup
        checks += 1
    checks += 8

    update_start = source.index("# FCU/EFIS BA01 display windows:", end)
    update_end = source.index("# LOW/MED/MAX each light", update_start)
    update = source[update_start:update_end]
    assert 'fcu_efis_values["button_leds"] = button_leds' in update
    assert 'fcu_efis_values["airbus_fcu_presentation"] = True' in update
    assert 'fcu_efis_values["zero_pad_fcu_values"] = True' in update
    assert 'fcu_efis_values["track_fpa_mode"] = _toliss_fcu_efis_flag(' in update
    assert 'fcu_efis_values["speed_dashed"] = _toliss_fcu_efis_flag(' in update
    assert 'fcu_efis_values["vertical_speed_dashed"] = _toliss_fcu_efis_flag(' in update
    assert 'fcu_efis_values["heading_dashed"] = fcu_efis_values[' in update
    assert 'fcu_efis_values["speed_visible"] = True' in update
    assert 'fcu_efis_values["vertical_speed_visible"] = True' in update
    assert 'fcu_efis_values["speed_visible"] = not _toliss_fcu_efis_flag(' not in update
    assert 'fcu_efis_values["vertical_speed_visible"] = not _toliss_fcu_efis_flag(' not in update
    assert "if not powered:" in update
    assert 'button_leds = {key: False for key in button_leds}' in update
    assert '"fcu_speed": "sim/cockpit/autopilot/airspeed"' in source
    assert '"fcu_speed_is_mach": "sim/cockpit/autopilot/airspeed_is_mach"' in source
    assert '"fcu_speed_is_mach": "AirbusFBW/ShowMachCapt"' not in source
    assert '"fcu_altitude": "sim/cockpit2/autopilot/altitude_dial_ft"' in source
    checks += 21

    print(
        f"ToLiss FCU/EFIS BUG-22/23/24/34/36/37 guard passed: {checks} checks; "
        "41-byte input, all four rotaries, all VOR/ADF selectors, selected LCD targets, SPD/MACH, "
        "HDG/V/S, TRK/FPA, managed dashes/dots, unit-aware Mach, selected altitude, fixed-width ToLiss digits, legacy display bytes, "
        "cruise SPD/MACH transitions and captured LEDs pinned."
    )


if __name__ == "__main__":
    main()
