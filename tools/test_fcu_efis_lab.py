#!/usr/bin/env python3
"""Offline verification of the BA01 semantic decoder and Zibo dispatcher."""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.devices.fcu_efis_ba01 import (
    FCU_EFIS_INPUT_BITS,
    FCU_EFIS_REPORT_ID,
    FcuRawInputEvent,
    MuslimSimFCUEFIS,
    MuslimSimFCUEFISZiboDispatcher,
    fcu_efis_backlight_packets,
    fcu_efis_display_packets,
    fcu_efis_initialize_packet,
)
from muslimsim.hardware.virtual_zibo import VirtualZiboPreview


def main() -> None:
    events: list[FcuRawInputEvent] = []
    manager = MuslimSimFCUEFIS(input_sink=events.append)
    initial = bytes((FCU_EFIS_REPORT_ID,)) + bytes(63)
    changed = bytearray(initial)
    changed[1] |= 0x01  # FCU bit 0
    changed[5] |= 0x01  # captain EFIS bit 32
    changed[9] |= 0x01  # first-officer EFIS bit 64
    changed[4] |= 0x80  # intentionally unknown bit 31
    manager._emit_changes(initial, bytes(changed))
    assert [(event.control, event.phase) for event in events] == [
        ("mach", "press"), ("unknown_bit_31", "press"),
        ("left_fd", "press"), ("right_fd", "press"),
    ]
    assert FCU_EFIS_INPUT_BITS == 504

    packets, next_sequence = fcu_efis_display_packets({
        "speed": 250, "heading": 90, "altitude": 10000,
        "vertical_speed": -700, "left_baro": 29.92, "right_baro": 1013,
        "right_baro_inhg": False, "right_baro_std": False,
    })
    assert len(packets) == 6 and all(len(packet) == 64 for packet in packets)
    assert packets[0][:6] == bytes((0xF0, 0x00, 1, 0x31, 0x10, 0xBB))
    assert packets[1][:6] == bytes((0xF0, 0x00, 1, 0x11, 0x10, 0xBB))
    assert packets[2][:6] == bytes((0xF0, 0x00, 2, 0x1A, 0x0D, 0xBF))
    assert packets[4][:6] == bytes((0xF0, 0x00, 3, 0x1A, 0x0E, 0xBF))
    assert next_sequence == 4
    assert fcu_efis_initialize_packet()[:2] == bytes((0xF0, 0x02))
    assert len(fcu_efis_backlight_packets(180)) == 6

    commands: list[str] = []
    writes: list[tuple[str, float]] = []
    values = {
        "laminar/B738/EFIS_control/capt/baro_in_hpa": 0.0,
        "laminar/B738/EFIS/baro_sel_in_hg_pilot": 29.92,
        "laminar/B738/EFIS_control/capt/vor1_off_pos": -1.0,
    }
    names: dict[int, str] = {}

    def dataref_id(_api: str, name: str) -> int:
        key = len(names) + 1
        names[key] = name
        return key

    def command_id(_api: str, name: str) -> int:
        key = len(names) + 1
        names[key] = name
        return key

    dispatcher = MuslimSimFCUEFISZiboDispatcher(
        api_version="test",
        resolve_dataref_id=dataref_id,
        read_dataref=lambda _api, ref: values.get(names[ref], 0.0),
        set_dataref=lambda _api, ref, value: writes.append((names[ref], value)),
        resolve_command_id=command_id,
        activate_command=lambda _api, command, _duration: commands.append(names[command]),
    )
    dispatcher(FcuRawInputEvent("altitude_step_1000", "press", 1, 26))
    dispatcher(FcuRawInputEvent("altitude_inc", "press", 1, 18))
    assert commands.count("sim/autopilot/altitude_up") == 10
    dispatcher(FcuRawInputEvent("left_mode_arc", "press", 1, 48))
    assert ("laminar/B738/EFIS_control/capt/map_mode_pos", 2.0) in writes
    dispatcher(FcuRawInputEvent("left_baro_inc", "press", 1, 42))
    assert any(name == "laminar/B738/EFIS/baro_sel_in_hg_pilot" and abs(value - 29.93) < 0.0001 for name, value in writes)
    dispatcher(FcuRawInputEvent("left_nav1_vor", "press", 1, 58))
    assert commands.count("laminar/B738/EFIS_control/capt/vor1_off_up") == 2

    # The simulator-free EFIS model must retain every selected switch/detent
    # so Studio can mirror a real BA01 press without requiring X-Plane.
    preview = VirtualZiboPreview()
    preview.activate("fcu_32_efis", "left_hpa")
    preview.activate("fcu_32_efis", "left_mode_arc")
    preview.activate("fcu_32_efis", "left_range_160")
    preview.activate("fcu_32_efis", "left_nav1_vor")
    preview.activate("fcu_32_efis", "left_nav2_adf")
    preview.activate("fcu_32_efis", "left_fd")
    preview.activate("fcu_32_efis", "left_std_push")
    preview_values = dict(preview.snapshot()["fcu_32_efis"]["values"])
    assert preview_values["left_baro_std"] == 1.0
    assert preview_values["left_baro_inhg"] == 0.0
    assert preview_values["left_mode"] == "arc"
    assert preview_values["left_range"] == 160.0
    assert preview_values["left_nav1"] == "vor"
    assert preview_values["left_nav2"] == "adf"
    assert preview_values["left_fd"] == 1.0
    print("FCU/EFIS BA01 semantic decoder and Zibo profile self-test passed.")


if __name__ == "__main__":
    main()
