#!/usr/bin/env python3
"""Offline protocol, mapping, and startup-safety checks for PDC BB62."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.devices.pdc_bb62 import (
    PDC_CONTROLS,
    PDC_PID_BYTES,
    PDCControlEvent,
    PDCInputState,
    MuslimSimPDCZiboDispatcher,
    pdc_control_events,
    pdc_decode_input_report,
    pdc_initialize_packet,
    pdc_lcd_packets,
    pdc_led_packet,
)


class _FakeBridge:
    def __init__(self) -> None:
        self.dataref_ids = {
            "laminar/B738/EFIS_control/capt/map_mode_pos": 101,
            "laminar/B738/EFIS/capt/map_range": 102,
            "laminar/B738/EFIS_control/cpt/minimums": 103,
        }
        self.command_ids = {}
        self.values = {101: 0.0, 102: 0.0, 103: 0.0}
        self.set_calls = []
        self.command_calls = []

    def resolve_dataref(self, _api_version: str, name: str) -> int:
        return self.dataref_ids[name]

    def set_dataref(self, _api_version: str, ref_id: int, value: float) -> None:
        self.values[ref_id] = value
        self.set_calls.append((ref_id, value))

    def resolve_command(self, _api_version: str, name: str) -> int:
        if name not in self.command_ids:
            self.command_ids[name] = 1000 + len(self.command_ids)
        return self.command_ids[name]

    def activate_command(
        self,
        _api_version: str,
        command_id: int,
        _duration: float,
    ) -> None:
        self.command_calls.append(command_id)


def main() -> int:
    report = bytes((0x01, 0x01, 0x00, 0x00, 0x80, 0x00, 0x00, 0x00, 0x00,
                    0x34, 0x12, 0x78, 0x56))
    state = pdc_decode_input_report(report)
    assert state == PDCInputState(0x0000000080000001, (0x1234, 0x5678))
    assert pdc_decode_input_report(b"\x01" * 12) is None
    assert pdc_decode_input_report(bytes((0x02,)) + bytes(12)) is None

    led = pdc_led_packet(9, 999)
    assert len(led) == 14 and led[0] == 0x02
    assert led[1:3] == PDC_PID_BYTES and led[8] == 255
    init = pdc_initialize_packet(0)
    assert len(init) == 64 and init[0:4] == bytes((0xF0, 0x00, 1, 0x12))
    assert init[4:6] == PDC_PID_BYTES
    packets, next_sequence = pdc_lcd_packets(bytes(32), 254)
    assert len(packets) == 4 and next_sequence == 3
    assert packets[0][4:6] == PDC_PID_BYTES
    assert packets[3][0x1D:0x1F] == PDC_PID_BYTES

    assert PDC_CONTROLS["mode_plan"] == ("bit", 30)
    assert PDC_CONTROLS["tfc"] == ("bit", 17)
    assert PDC_CONTROLS["mins_knob_cw"] == ("bit", 41)
    assert PDC_CONTROLS["mins_knob_ccw"] == ("bit", 39)
    assert PDC_CONTROLS["baro_knob_cw"] == ("bit", 44)
    assert PDC_CONTROLS["baro_knob_ccw"] == ("bit", 42)

    previous = PDCInputState(0, (100, 200))
    current = PDCInputState(1 << 4, (103, 234))
    assert pdc_control_events(previous, current, {}) == ()
    events = pdc_control_events(
        previous,
        current,
        {"example_button": ("bit", 4), "example_axis": ("axis", 1)},
    )
    assert [(event.control, event.phase, event.value) for event in events] == [
        ("example_button", "press", 1),
        ("example_axis", "change", 234),
    ]
    rotary_events = pdc_control_events(
        PDCInputState((1 << 40) | (1 << 43), (0, 0)),
        PDCInputState((1 << 41) | (1 << 44), (0, 0)),
        {
            "mins_knob_cw": PDC_CONTROLS["mins_knob_cw"],
            "baro_knob_cw": PDC_CONTROLS["baro_knob_cw"],
        },
    )
    assert [(event.control, event.phase, event.value) for event in rotary_events] == [
        ("mins_knob_cw", "press", 1),
        ("baro_knob_cw", "press", 1),
    ]

    bridge = _FakeBridge()
    dispatcher = MuslimSimPDCZiboDispatcher(
        api_version="v3",
        resolve_dataref_id=bridge.resolve_dataref,
        set_dataref=bridge.set_dataref,
        resolve_command_id=bridge.resolve_command,
        activate_command=bridge.activate_command,
    )
    dispatcher(PDCControlEvent("mode_plan", "press", 1))
    dispatcher(PDCControlEvent("mins_mode_baro", "press", 1))
    dispatcher(PDCControlEvent("wxr", "press", 1))
    command_count = len(bridge.command_calls)
    dispatcher(PDCControlEvent("wxr", "release", 0))
    dispatcher(PDCControlEvent("mins_knob_cw", "release", 0))
    assert bridge.values[101] == 3.0
    assert bridge.values[103] == 1.0
    assert len(bridge.command_calls) == command_count
    assert bridge.command_calls == [
        bridge.command_ids[
            "laminar/B738/EFIS_control/capt/push_button/wxr_press"
        ]
    ]

    dispatcher(PDCControlEvent("mins_knob_cw", "press", 1))
    dispatcher(PDCControlEvent("mins_knob_ccw", "press", 1))
    dispatcher(PDCControlEvent("baro_knob_cw", "press", 1))
    dispatcher(PDCControlEvent("baro_knob_ccw", "press", 1))
    assert bridge.command_calls[-4:] == [
        bridge.command_ids["laminar/B738/EFIS_control/cpt/minimums_up"],
        bridge.command_ids["laminar/B738/EFIS_control/cpt/minimums_dn"],
        bridge.command_ids["laminar/B738/pilot/barometer_up"],
        bridge.command_ids["laminar/B738/pilot/barometer_down"],
    ]

    dispatcher(PDCControlEvent("vor_adf_1_vor", "press", 1))
    assert bridge.command_calls[-2:] == [
        bridge.command_ids[
            "laminar/B738/EFIS_control/capt/vor1_off_up"
        ],
        bridge.command_ids[
            "laminar/B738/EFIS_control/capt/vor1_off_up"
        ],
    ]

    dispatcher(PDCControlEvent("vor_adf_1_off", "press", 1))
    assert bridge.command_calls[-3:] == [
        bridge.command_ids[
            "laminar/B738/EFIS_control/capt/vor1_off_up"
        ],
        bridge.command_ids[
            "laminar/B738/EFIS_control/capt/vor1_off_up"
        ],
        bridge.command_ids[
            "laminar/B738/EFIS_control/capt/vor1_off_dn"
        ],
    ]

    dispatcher(PDCControlEvent("vor_adf_1_adf", "press", 1))
    assert bridge.command_calls[-2:] == [
        bridge.command_ids[
            "laminar/B738/EFIS_control/capt/vor1_off_dn"
        ],
        bridge.command_ids[
            "laminar/B738/EFIS_control/capt/vor1_off_dn"
        ],
    ]

    dispatcher(PDCControlEvent("vor_adf_2_vor", "press", 1))
    dispatcher(PDCControlEvent("vor_adf_2_off", "press", 1))
    dispatcher(PDCControlEvent("vor_adf_2_adf", "press", 1))
    assert bridge.command_calls[-7:] == [
        bridge.command_ids[
            "laminar/B738/EFIS_control/capt/vor2_off_up"
        ],
        bridge.command_ids[
            "laminar/B738/EFIS_control/capt/vor2_off_up"
        ],
        bridge.command_ids[
            "laminar/B738/EFIS_control/capt/vor2_off_up"
        ],
        bridge.command_ids[
            "laminar/B738/EFIS_control/capt/vor2_off_up"
        ],
        bridge.command_ids[
            "laminar/B738/EFIS_control/capt/vor2_off_dn"
        ],
        bridge.command_ids[
            "laminar/B738/EFIS_control/capt/vor2_off_dn"
        ],
        bridge.command_ids[
            "laminar/B738/EFIS_control/capt/vor2_off_dn"
        ],
    ]
    print("PDC BB62 protocol, mapping, and startup-safety tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
