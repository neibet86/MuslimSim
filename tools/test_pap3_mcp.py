#!/usr/bin/env python3
"""Offline PAP3 MCP speed, annunciator-power, and socket-message checks."""

from __future__ import annotations

import json
from pathlib import Path
import queue
import sys
import threading


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.devices.pap3_mcp import (
    MuslimSimPAP3MCP,
    PAP3_LED_AT_ARM,
    PAP3_LED_LVL_CHG,
    PAP3_LED_SPEED,
    PAP3_OVERALL_LED_BRIGHTNESS,
    pap3_compose_lcd_payload,
    pap3_next_speed_value,
)


class _FakeSocket:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    def send(self, payload: str) -> None:
        self.messages.append(json.loads(payload))


def main() -> int:
    assert pap3_next_speed_value(100, False, -1) == 100.0
    assert pap3_next_speed_value(100, False, 1) == 101.0
    assert pap3_next_speed_value(399, False, 1) == 400.0
    assert pap3_next_speed_value(0.78, True, 1) == 0.79
    assert pap3_next_speed_value(78, True, -1) == 77.0

    manager = MuslimSimPAP3MCP(api_version="v3", startup_delay=0.0)
    _payload, outputs, solenoid = manager._desired_outputs({
        "_transport_connected": 1.0,
        "avionics": 1.0,
        # The affected Zibo value is intentionally zero; it must not black
        # out valid PAP3 annunciators.
        "main_bus": 0.0,
        "panel_brightness": 0.5,
        "display_test": 0.0,
        "led_lvl_chg": 1.0,
        "led_at_arm": 1.0,
        "at_arm": 1.0,
    })
    assert outputs[PAP3_OVERALL_LED_BRIGHTNESS] == 180
    assert outputs[PAP3_LED_LVL_CHG] == 1
    assert outputs[PAP3_LED_AT_ARM] == 1
    assert solenoid == 1

    practice_values = {
        "avionics": 1.0, "speed": 250.0, "speed_visible": 1.0,
        "heading": 90.0, "altitude": 10000.0, "vertical_speed": 0.0,
        "vertical_speed_visible": 1.0, "course_capt": 0.0, "course_fo": 0.0,
        "led_speed": 1.0,
    }
    assert any(pap3_compose_lcd_payload(practice_values))
    manager.set_lab_output("lcd", practice_values)
    _payload, outputs, _solenoid = manager._desired_outputs({
        "_transport_connected": 1.0, "avionics": 1.0,
    })
    assert outputs[PAP3_LED_SPEED] == 1
    assert outputs[PAP3_LED_LVL_CHG] == 0

    socket = _FakeSocket()
    counter = [7000]
    events: "queue.Queue[tuple[str, int]]" = queue.Queue()
    events.put(("press", 20))
    speed_state = {"speed": 250.0, "speed_is_mach": 0.0}
    manager._drain_input_events(
        socket,
        events,
        {"speed": 1234, "speed_control_kts": 5678},
        {},
        speed_state,
        threading.Lock(),
        counter,
    )
    assert speed_state["speed"] == 251.0
    assert socket.messages == [{
        "req_id": 7001,
        "type": "dataref_set_values",
        "params": {"datarefs": [{"id": 5678, "value": 251.0}]},
    }]

    print("PAP3 MCP speed, annunciator-power, and socket-message tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
