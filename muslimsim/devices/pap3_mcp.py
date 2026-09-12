#!/usr/bin/env python3
"""WinCtrl PAP3 Boeing 737 MCP support for the unified MuslimSim bridge.

Target hardware
---------------
WINCTRL 3N PAP MCP / PAP3
VID 0x4098, PID 0xBF0F

Design rules
------------
* One standalone MuslimSim process still owns every cockpit device.
* PAP3 has its own HID handle and worker threads, so a missing or failed MCP
  cannot block the PU overhead, throttle, PFD, MCDU, AGP, or pedals.
* The first valid HID report is only a baseline.  Starting the bridge never
  changes the aircraft merely to match a physical switch.
* All live simulator traffic uses one persistent X-Plane Web API WebSocket.
  REST is used only while resolving stable runtime IDs.
* Physical output is dirty-only: six MCP windows, annunciators, panel/LCD
  brightness, and the optional magnetic A/T solenoid are written only when
  their state changes.

This is an original Python implementation of the PAP3 HID wire protocol and
the Zibo 737 MCP dataref/command interface.
"""

from __future__ import annotations

import json
import math
import queue
import threading
import time
from typing import Any, Callable, Dict, Iterable, Mapping, MutableMapping, Optional, Tuple
import urllib.parse
import urllib.request

try:
    import hid
except ImportError:  # pragma: no cover - exercised only on installations without hidapi
    hid = None

try:
    from .winctrl_output_bus import output_transaction, wrap_hid_device
except ImportError:  # pragma: no cover - standalone source/probe fallback
    from winctrl_output_bus import output_transaction, wrap_hid_device

try:
    import websocket
except ImportError:  # pragma: no cover - exercised only on installations without websocket-client
    websocket = None


PAP3_VID = 0x4098
PAP3_PID = 0xBF0F
PAP3_PRODUCT_LABEL = "WINCTRL 3N PAP MCP"
PAP3_REPORT_ID_INPUT = 0x01
PAP3_INPUT_MIN_LENGTH = 32
PAP3_BUTTON_COUNT = 48
PAP3_PACKET_SIZE = 64
PAP3_RECONNECT_SECONDS = 1.0
PAP3_WS_RECV_TIMEOUT = 0.025
PAP3_QUEUE_LIMIT = 512
PAP3_DEFAULT_REFRESH_SECONDS = 0.12
PAP3_DEFAULT_STARTUP_DELAY_SECONDS = 3.0
PAP3_LCD_PACKET_GAP_SECONDS = 0.001
# The PAP3 accepts its native segment transaction shortly after its wake
# frame.  Practice mode does not have a simulator stream to make a later
# value change inevitable, so it deliberately sends the last confirmed
# numeric frame again at a modest cadence until Live mode owns the panel.
PAP3_PRACTICE_INITIAL_SETTLE_SECONDS = 0.08
PAP3_PRACTICE_LCD_RESYNC_SECONDS = 0.75

# Output selectors.
PAP3_BACKLIGHT = 0
PAP3_LCD_BACKLIGHT = 1
PAP3_OVERALL_LED_BRIGHTNESS = 2
PAP3_LED_N1 = 3
PAP3_LED_SPEED = 4
PAP3_LED_VNAV = 5
PAP3_LED_LVL_CHG = 6
PAP3_LED_HDG_SEL = 7
PAP3_LED_LNAV = 8
PAP3_LED_VORLOC = 9
PAP3_LED_APP = 10
PAP3_LED_ALT_HLD = 11
PAP3_LED_VS = 12
PAP3_LED_CMD_A = 13
PAP3_LED_CWS_A = 14
PAP3_LED_CMD_B = 15
PAP3_LED_CWS_B = 16
PAP3_LED_AT_ARM = 17
PAP3_LED_MA_CAPT = 18
PAP3_LED_MA_FO = 19
PAP3_SOLENOID_SELECTOR = 0x1E

PAP3_INDIVIDUAL_LED_SELECTORS = tuple(range(PAP3_LED_N1, PAP3_LED_MA_FO + 1))

# Regular momentary buttons and encoder directions.  The hardware exposes
# every rotary detent as a short button edge pair.
PAP3_BUTTONS: Dict[int, Tuple[str, str]] = {
    0: ("N1", "laminar/B738/autopilot/n1_press"),
    1: ("SPEED", "laminar/B738/autopilot/speed_press"),
    2: ("VNAV", "laminar/B738/autopilot/vnav_press"),
    3: ("LVL CHG", "laminar/B738/autopilot/lvl_chg_press"),
    4: ("HDG SEL", "laminar/B738/autopilot/hdg_sel_press"),
    5: ("LNAV", "laminar/B738/autopilot/lnav_press"),
    6: ("VOR LOC", "laminar/B738/autopilot/vorloc_press"),
    7: ("APP", "laminar/B738/autopilot/app_press"),
    8: ("ALT HLD", "laminar/B738/autopilot/alt_hld_press"),
    9: ("V/S", "laminar/B738/autopilot/vs_press"),
    10: ("CMD A", "laminar/B738/autopilot/cmd_a_press"),
    11: ("CWS A", "laminar/B738/autopilot/cws_a_press"),
    12: ("CMD B", "laminar/B738/autopilot/cmd_b_press"),
    13: ("CWS B", "laminar/B738/autopilot/cws_b_press"),
    14: ("C/O", "laminar/B738/autopilot/change_over_press"),
    15: ("SPD INTV", "laminar/B738/autopilot/spd_interv"),
    16: ("ALT INTV", "laminar/B738/autopilot/alt_interv"),
    17: ("CRS CAPT DEC", "laminar/B738/autopilot/course_pilot_dn"),
    18: ("CRS CAPT INC", "laminar/B738/autopilot/course_pilot_up"),
    # Generic heading commands deliberately avoid Zibo's accelerated/coasting
    # knob behavior and give one degree per physical detent.
    21: ("HDG DEC", "sim/autopilot/heading_down"),
    22: ("HDG INC", "sim/autopilot/heading_up"),
    23: ("ALT DEC", "laminar/B738/autopilot/altitude_dn"),
    24: ("ALT INC", "laminar/B738/autopilot/altitude_up"),
    25: ("CRS FO DEC", "laminar/B738/autopilot/course_copilot_dn"),
    26: ("CRS FO INC", "laminar/B738/autopilot/course_copilot_up"),
    38: ("V/S DEC", "sim/autopilot/vertical_speed_down"),
    39: ("V/S INC", "sim/autopilot/vertical_speed_up"),
}

# Zibo owns its MCP IAS/Mach dial and immediately overwrites X-Plane's generic
# airspeed dial. The PAP3 SPEED rotary therefore writes this verified, writable
# Zibo MCP dataref through the manager's already-open Web API WebSocket.
PAP3_SPEED_BUTTONS = {
    19: ("SPD DEC", -1),
    20: ("SPD INC", 1),
}
PAP3_SPEED_KTS_MIN = 100.0
PAP3_SPEED_KTS_MAX = 400.0
PAP3_SPEED_MACH_MIN = 0.40
PAP3_SPEED_MACH_MAX = 0.99
PAP3_SPEED_MACH_STEP = 0.01

# Maintained and multi-position controls.
PAP3_FD_CAPT_INDEX = 27
PAP3_FD_FO_INDEX = 29
PAP3_AP_DISC_DOWN_INDEX = 31
PAP3_AP_DISC_UP_INDEX = 32
PAP3_BANK_ANGLE_TARGETS = {
    33: 0,  # 10 degrees
    34: 1,  # 15 degrees
    35: 2,  # 20 degrees
    36: 3,  # 25 degrees
    37: 4,  # 30 degrees
}
PAP3_AT_ARMED_INDEX = 40
PAP3_AT_DISARMED_INDEX = 41

PAP3_TOGGLE_COMMANDS = {
    "fd_capt": "laminar/B738/autopilot/flight_director_toggle",
    "fd_fo": "laminar/B738/autopilot/flight_director_fo_toggle",
    "ap_disconnect": "laminar/B738/autopilot/disconnect_toggle",
    "at_arm": "laminar/B738/autopilot/autothrottle_arm_toggle",
}
PAP3_BANK_COMMANDS = {
    "up": "laminar/B738/autopilot/bank_angle_up",
    "down": "laminar/B738/autopilot/bank_angle_dn",
}

# All values needed for the six windows, annunciators, brightness, magnetic
# switch, and state-aware maintained-switch handling.
PAP3_DATAREFS: Dict[str, str] = {
    "avionics": "sim/cockpit/electrical/avionics_on",
    "panel_brightness": "laminar/B738/electric/panel_brightness",
    # Actual panel illumination after X-Plane electrical power/failures.
    "panel_brightness_actual": "sim/cockpit2/electrical/panel_brightness_ratio",
    "speed": "laminar/B738/autopilot/mcp_speed_dial_kts_mach",
    # Zibo's underlying IAS selector. The combined ``speed`` value is a
    # display mirror while in knots and is refreshed from this one each frame.
    "speed_control_kts": "laminar/B738/autopilot/mcp_speed_dial_kts",
    "speed_is_mach": "sim/cockpit/autopilot/airspeed_is_mach",
    "heading": "laminar/B738/autopilot/mcp_hdg_dial",
    "altitude": "laminar/B738/autopilot/mcp_alt_dial",
    "vertical_speed": "sim/cockpit2/autopilot/vvi_dial_fpm",
    "vertical_speed_visible": "laminar/B738/autopilot/vvi_dial_show",
    "speed_visible": "laminar/B738/autopilot/show_ias",
    "course_capt": "laminar/B738/autopilot/course_pilot",
    "course_fo": "laminar/B738/autopilot/course_copilot",
    "digit_a": "laminar/B738/mcp/digit_A",
    "digit_8": "laminar/B738/mcp/digit_8",
    "display_test": "laminar/B738/dspl_light_test",
    "fd_capt": "laminar/B738/autopilot/flight_director_pos",
    "fd_fo": "laminar/B738/autopilot/flight_director_fo_pos",
    "ap_disconnect": "laminar/B738/autopilot/disconnect_pos",
    "at_arm": "laminar/B738/autopilot/autothrottle_arm_pos",
    "bank_angle": "laminar/B738/autopilot/bank_angle_pos",
    "led_n1": "laminar/B738/autopilot/n1_status1",
    "led_speed": "laminar/B738/autopilot/speed_status1",
    "led_vnav": "laminar/B738/autopilot/vnav_status1",
    "led_lvl_chg": "laminar/B738/autopilot/lvl_chg_status",
    "led_hdg_sel": "laminar/B738/autopilot/hdg_sel_status",
    "led_lnav": "laminar/B738/autopilot/lnav_status",
    "led_vorloc": "laminar/B738/autopilot/vorloc_status",
    "led_app": "laminar/B738/autopilot/app_status",
    "led_alt_hld": "laminar/B738/autopilot/alt_hld_status",
    "led_vs": "laminar/B738/autopilot/vs_status",
    "led_cmd_a": "laminar/B738/autopilot/cmd_a_status",
    "led_cws_a": "laminar/B738/autopilot/cws_a_status",
    "led_cmd_b": "laminar/B738/autopilot/cmd_b_status",
    "led_cws_b": "laminar/B738/autopilot/cws_b_status",
    "led_at_arm": "laminar/B738/autopilot/autothrottle_status1",
    "led_ma_capt": "laminar/B738/autopilot/master_capt_status",
    "led_ma_fo": "laminar/B738/autopilot/master_fo_status",
}

PAP3_DATAREF_INDICES = {
    "panel_brightness": 0,
    "panel_brightness_actual": 0,
    "display_test": 0,
}

PAP3_REQUIRED_DATAREF_KEYS = frozenset({
    "avionics",
    "speed",
    "speed_is_mach",
    "heading",
    "altitude",
    "vertical_speed",
    "course_capt",
    "course_fo",
})

PAP3_LED_DATAREFS = {
    PAP3_LED_N1: "led_n1",
    PAP3_LED_SPEED: "led_speed",
    PAP3_LED_VNAV: "led_vnav",
    PAP3_LED_LVL_CHG: "led_lvl_chg",
    PAP3_LED_HDG_SEL: "led_hdg_sel",
    PAP3_LED_LNAV: "led_lnav",
    PAP3_LED_VORLOC: "led_vorloc",
    PAP3_LED_APP: "led_app",
    PAP3_LED_ALT_HLD: "led_alt_hld",
    PAP3_LED_VS: "led_vs",
    PAP3_LED_CMD_A: "led_cmd_a",
    PAP3_LED_CWS_A: "led_cws_a",
    PAP3_LED_CMD_B: "led_cmd_b",
    PAP3_LED_CWS_B: "led_cws_b",
    PAP3_LED_AT_ARM: "led_at_arm",
    PAP3_LED_MA_CAPT: "led_ma_capt",
    PAP3_LED_MA_FO: "led_ma_fo",
}

# LCD payload is the 32 bytes corresponding to absolute device offsets 0x19
# through 0x38.
PAP3_LCD_PAYLOAD_SIZE = 32

# Segment-group absolute offsets ordered as:
# middle, top-left, bottom-left, bottom, bottom-right, top-right, top.
PAP3_G0 = (0x1D, 0x21, 0x25, 0x29, 0x2D, 0x31, 0x35)
PAP3_G1 = (0x1E, 0x22, 0x26, 0x2A, 0x2E, 0x32, 0x36)
PAP3_G2 = (0x1F, 0x23, 0x27, 0x2B, 0x2F, 0x33, 0x37)
PAP3_G3 = (0x20, 0x24, 0x28, 0x2C, 0x30, 0x34, 0x38)

# Digit-position bits in each group.
SPD_UNITS = 0x01
SPD_TENS = 0x02
SPD_HUNDREDS = 0x04
SPD_KILO = 0x08
CPT_CRS_UNITS = 0x20
CPT_CRS_TENS = 0x40
CPT_CRS_HUNDREDS = 0x80

ALT_HUNDREDS = 0x01
ALT_KILO = 0x02
ALT_TENS_KILO = 0x04
HDG_UNITS = 0x10
HDG_TENS = 0x20
HDG_HUNDREDS = 0x40

VSPD_UNITS = 0x01
VSPD_TENS = 0x02
VSPD_HUNDREDS = 0x04
VSPD_KILO = 0x08
ALT_UNITS = 0x40
ALT_TENS = 0x80

FO_CRS_UNITS = 0x10
FO_CRS_TENS = 0x20
FO_CRS_HUNDREDS = 0x40

# Special segment flags used by the Zibo profile.
OFF_19 = 0x19
OFF_1A = 0x1A
OFF_1B = 0x1B
OFF_1E = 0x1E
OFF_1F = 0x1F
OFF_22 = 0x22
OFF_28 = 0x28
OFF_2C = 0x2C

DOT_SPD = 0x04
DOT_ALT = 0x01
DOT_VSPD = 0x04
SPD_BAR_BOTTOM = 0x80
SPD_BAR_TOP = 0x80
VSPD_MINUS = 0x10
VSPD_PLUS_BOT = 0x80
VSPD_PLUS_TOP = 0x80

# Seven-segment mask bits A..G.
SEG_A = 1 << 0
SEG_B = 1 << 1
SEG_C = 1 << 2
SEG_D = 1 << 3
SEG_E = 1 << 4
SEG_F = 1 << 5
SEG_G = 1 << 6

PAP3_DIGIT_MASKS = (
    SEG_A | SEG_B | SEG_C | SEG_D | SEG_E | SEG_F,
    SEG_B | SEG_C,
    SEG_A | SEG_B | SEG_G | SEG_E | SEG_D,
    SEG_A | SEG_B | SEG_C | SEG_D | SEG_G,
    SEG_F | SEG_G | SEG_B | SEG_C,
    SEG_A | SEG_F | SEG_G | SEG_C | SEG_D,
    SEG_A | SEG_F | SEG_E | SEG_D | SEG_C | SEG_G,
    SEG_A | SEG_B | SEG_C,
    SEG_A | SEG_B | SEG_C | SEG_D | SEG_E | SEG_F | SEG_G,
    SEG_A | SEG_B | SEG_C | SEG_D | SEG_F | SEG_G,
)
PAP3_LETTER_A_MASK = SEG_A | SEG_B | SEG_C | SEG_E | SEG_F | SEG_G


def _finite(value: Any, fallback: float = 0.0) -> float:
    """Return one finite float, accepting WebSocket scalar wrappers."""
    candidate = value

    for _ in range(4):
        if isinstance(candidate, dict):
            if "value" in candidate:
                candidate = candidate["value"]
                continue
            if "data" in candidate:
                candidate = candidate["data"]
                continue
            if len(candidate) == 1:
                candidate = next(iter(candidate.values()))
                continue
            return float(fallback)

        if isinstance(candidate, (list, tuple)):
            if not candidate:
                return float(fallback)
            candidate = candidate[0]
            continue

        break

    try:
        numeric = float(candidate)
    except (TypeError, ValueError):
        return float(fallback)

    return numeric if math.isfinite(numeric) else float(fallback)


def _logical(value: Any, fallback: bool = False) -> bool:
    return _finite(value, 1.0 if fallback else 0.0) >= 0.5


def _display_test_mode(value: Any) -> int:
    return max(0, min(255, int(round(_finite(value, 0.0)))))


def pap3_next_speed_value(
    current: Any,
    speed_is_mach: Any,
    direction: int,
) -> float:
    """Return the next valid Zibo MCP speed without touching the simulator.

    Zibo normally stores Mach as 0.xx. Some cockpit variants expose the same
    value as xx, so preserve the observed representation in Mach mode. IAS is
    always a one-knot integer step.
    """
    current_value = _finite(current, math.nan)
    step = -1 if int(direction) < 0 else 1
    if not math.isfinite(current_value):
        raise ValueError("PAP3 speed target is not available")

    if _logical(speed_is_mach):
        if current_value >= 1.0:
            return float(max(40, min(99, int(round(current_value)) + step)))
        return max(
            PAP3_SPEED_MACH_MIN,
            min(
                PAP3_SPEED_MACH_MAX,
                round(current_value + PAP3_SPEED_MACH_STEP * step, 2),
            ),
        )

    return float(
        max(
            int(PAP3_SPEED_KTS_MIN),
            min(int(PAP3_SPEED_KTS_MAX), int(round(current_value)) + step),
        )
    )


def _payload_index(absolute_offset: int) -> int:
    return int(absolute_offset) - 0x19


def _set_payload_flag(
    payload: bytearray,
    absolute_offset: int,
    bit_mask: int,
    enabled: bool = True,
) -> None:
    if not enabled:
        return
    index = _payload_index(absolute_offset)
    if 0 <= index < len(payload):
        payload[index] |= int(bit_mask) & 0xFF


def _draw_segment_mask(
    payload: bytearray,
    group_offsets: Tuple[int, int, int, int, int, int, int],
    position_flag: int,
    segment_mask: int,
) -> None:
    # Group order is middle(G), top-left(F), bottom-left(E), bottom(D),
    # bottom-right(C), top-right(B), top(A).
    checks = (
        SEG_G,
        SEG_F,
        SEG_E,
        SEG_D,
        SEG_C,
        SEG_B,
        SEG_A,
    )
    for absolute_offset, segment in zip(group_offsets, checks):
        _set_payload_flag(
            payload,
            absolute_offset,
            position_flag,
            bool(segment_mask & segment),
        )


def _draw_digit(
    payload: bytearray,
    group_offsets: Tuple[int, int, int, int, int, int, int],
    position_flag: int,
    digit: int,
) -> None:
    safe_digit = max(0, min(9, int(digit)))
    _draw_segment_mask(
        payload,
        group_offsets,
        position_flag,
        PAP3_DIGIT_MASKS[safe_digit],
    )


def _draw_letter_a(
    payload: bytearray,
    group_offsets: Tuple[int, int, int, int, int, int, int],
    position_flag: int,
) -> None:
    _draw_segment_mask(
        payload,
        group_offsets,
        position_flag,
        PAP3_LETTER_A_MASK,
    )


def _digits3(value: int) -> Tuple[int, int, int]:
    value = max(0, min(999, int(value)))
    return (value // 100) % 10, (value // 10) % 10, value % 10


def _digits4(value: int) -> Tuple[int, int, int, int]:
    value = max(0, min(9999, int(value)))
    return (
        (value // 1000) % 10,
        (value // 100) % 10,
        (value // 10) % 10,
        value % 10,
    )


def _digits5(value: int) -> Tuple[int, int, int, int, int]:
    value = max(0, min(99999, int(value)))
    return (
        (value // 10000) % 10,
        (value // 1000) % 10,
        (value // 100) % 10,
        (value // 10) % 10,
        value % 10,
    )


def pap3_compose_lcd_payload(
    values: Mapping[str, Any],
    *,
    transport_connected: bool = True,
) -> bytes:
    """Compose the PAP3's native 32-byte MCP LCD segment payload.

    This pure function is intentionally exported so the protocol can be tested
    without a connected panel or a running simulator.
    """
    payload = bytearray(PAP3_LCD_PAYLOAD_SIZE)
    test_mode = _display_test_mode(values.get("display_test", 0.0))
    avionics = _logical(values.get("avionics", 0.0))

    display_enabled = bool(
        transport_connected
        and avionics
        and test_mode != 2
    )

    if not display_enabled:
        return bytes(payload)

    if test_mode >= 1:
        return bytes([0xFF] * PAP3_LCD_PAYLOAD_SIZE)

    speed = _finite(values.get("speed", 0.0))
    speed_is_mach = _logical(values.get("speed_is_mach", 0.0))
    speed_visible = _logical(values.get("speed_visible", 1.0), True)

    if speed_visible and speed_is_mach:
        mach = max(0.0, min(0.9999, speed if speed < 1.0 else speed / 100.0))
        two_digits = max(0, min(99, int(math.floor(mach * 100.0 + 0.5))))
        _draw_digit(payload, PAP3_G0, SPD_TENS, (two_digits // 10) % 10)
        _draw_digit(payload, PAP3_G0, SPD_UNITS, two_digits % 10)
        _set_payload_flag(payload, OFF_19, DOT_SPD, True)
        digit_a = _logical(values.get("digit_a", 0.0))
        _set_payload_flag(payload, OFF_22, SPD_BAR_TOP, digit_a)
        _set_payload_flag(payload, OFF_1E, SPD_BAR_BOTTOM, digit_a)

    elif speed_visible:
        ias = max(0, int(math.floor(speed + 0.5)))
        kilo, hundreds, tens, units = _digits4(ias)
        show_kilo = kilo != 0
        show_hundreds = show_kilo or hundreds != 0

        if show_kilo:
            _draw_digit(payload, PAP3_G0, SPD_KILO, kilo)
        if show_hundreds:
            _draw_digit(payload, PAP3_G0, SPD_HUNDREDS, hundreds)
        _draw_digit(payload, PAP3_G0, SPD_TENS, tens)
        _draw_digit(payload, PAP3_G0, SPD_UNITS, units)

        digit_a = _logical(values.get("digit_a", 0.0))
        digit_8 = _logical(values.get("digit_8", 0.0))
        _set_payload_flag(payload, OFF_22, SPD_BAR_TOP, digit_a)
        _set_payload_flag(payload, OFF_1E, SPD_BAR_BOTTOM, digit_a)

        if not show_kilo:
            if digit_a:
                _draw_letter_a(payload, PAP3_G0, SPD_KILO)
            if digit_8:
                _draw_digit(payload, PAP3_G0, SPD_KILO, 8)

    # Captain course.
    crs_capt = max(0, int(round(_finite(values.get("course_capt", 0.0)))))
    c_h, c_t, c_u = _digits3(crs_capt)
    _draw_digit(payload, PAP3_G0, CPT_CRS_HUNDREDS, c_h)
    _draw_digit(payload, PAP3_G0, CPT_CRS_TENS, c_t)
    _draw_digit(payload, PAP3_G0, CPT_CRS_UNITS, c_u)

    # Heading.
    heading_raw = int(round(_finite(values.get("heading", 0.0))))
    heading = 360 if heading_raw >= 360 else max(0, min(359, heading_raw))
    h_h, h_t, h_u = _digits3(heading)
    _draw_digit(payload, PAP3_G1, HDG_HUNDREDS, h_h)
    _draw_digit(payload, PAP3_G1, HDG_TENS, h_t)
    _draw_digit(payload, PAP3_G1, HDG_UNITS, h_u)

    # Altitude.
    altitude = max(0, int(round(_finite(values.get("altitude", 0.0)))))
    a_10k, a_k, a_h, a_t, a_u = _digits5(altitude)
    if a_10k:
        _draw_digit(payload, PAP3_G1, ALT_TENS_KILO, a_10k)
    _draw_digit(payload, PAP3_G1, ALT_KILO, a_k)
    _draw_digit(payload, PAP3_G1, ALT_HUNDREDS, a_h)
    _draw_digit(payload, PAP3_G2, ALT_TENS, a_t)
    _draw_digit(payload, PAP3_G2, ALT_UNITS, a_u)
    _set_payload_flag(payload, OFF_1A, DOT_ALT, False)

    # Vertical speed.  Zibo intentionally blanks this window when the selector
    # is not shown.
    if _logical(values.get("vertical_speed_visible", 1.0)):
        vertical_speed = int(_finite(values.get("vertical_speed", 0.0)))
        absolute = max(0, min(9999, abs(vertical_speed)))
        v_k, v_h, v_t, v_u = _digits4(absolute)

        if absolute >= 1000:
            _draw_digit(payload, PAP3_G2, VSPD_KILO, v_k)
        if absolute >= 100:
            _draw_digit(payload, PAP3_G2, VSPD_HUNDREDS, v_h)
        if absolute >= 10 or absolute == 0:
            _draw_digit(payload, PAP3_G2, VSPD_TENS, v_t)
        _draw_digit(payload, PAP3_G2, VSPD_UNITS, v_u)

        negative = vertical_speed < 0
        positive = vertical_speed > 0
        _set_payload_flag(payload, OFF_1F, VSPD_MINUS, negative or positive)
        _set_payload_flag(payload, OFF_2C, VSPD_PLUS_TOP, positive)
        _set_payload_flag(payload, OFF_28, VSPD_PLUS_BOT, positive)
        _set_payload_flag(payload, OFF_1B, DOT_VSPD, False)

    # First-officer course.
    crs_fo = max(0, int(round(_finite(values.get("course_fo", 0.0)))))
    f_h, f_t, f_u = _digits3(crs_fo)
    _draw_digit(payload, PAP3_G3, FO_CRS_HUNDREDS, f_h)
    _draw_digit(payload, PAP3_G3, FO_CRS_TENS, f_t)
    _draw_digit(payload, PAP3_G3, FO_CRS_UNITS, f_u)

    return bytes(payload)


def pap3_decode_button_bits(report: bytes) -> Optional[int]:
    """Return the 48 PAP3 input bits from one report-ID 1 packet."""
    raw = bytes(report)
    if len(raw) < PAP3_INPUT_MIN_LENGTH:
        return None
    if raw[0] != PAP3_REPORT_ID_INPUT:
        return None
    return int.from_bytes(raw[1:7], byteorder="little", signed=False)


def pap3_led_packet(selector: int, value: int) -> bytes:
    """Build one full PAP3 HID dimming/annunciator output report.

    The native command occupies the first 14 bytes, but Windows HID expects
    the write to use the device's full output-report length.  PAP3's captured
    output frames are 64 bytes, so preserve the command bytes and zero-pad the
    remainder exactly like the known-good WinCtrl Windows driver.
    """
    packet = bytearray(PAP3_PACKET_SIZE)
    packet[:14] = bytes((
        0x02,
        0x0F,
        0xBF,
        0x00,
        0x00,
        0x03,
        0x49,
        int(selector) & 0xFF,
        max(0, min(255, int(value))),
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
    ))
    return bytes(packet)


def pap3_initialize_packet(sequence: int) -> bytes:
    sequence = _normalize_sequence(sequence)
    packet = bytearray(PAP3_PACKET_SIZE)
    packet[0:4] = bytes((0xF0, 0x00, sequence, 0x12))
    packet[4:24] = bytes((
        0x0F, 0xBF, 0x00, 0x00,
        0x04, 0x01, 0x00, 0x00,
        0x26, 0xCC, 0x00, 0x00,
        0x00, 0x01, 0x00, 0x00,
        0x00, 0x03, 0x00, 0x00,
    ))
    return bytes(packet)


def pap3_lcd_packets(
    payload: bytes,
    sequence: int,
) -> Tuple[Tuple[bytes, bytes, bytes, bytes], int]:
    """Build one complete dirty-only LCD transaction and next sequence."""
    if len(payload) != PAP3_LCD_PAYLOAD_SIZE:
        raise ValueError(
            f"PAP3 LCD payload must be {PAP3_LCD_PAYLOAD_SIZE} bytes"
        )

    seq = _normalize_sequence(sequence)
    frames = []

    data_frame = bytearray(PAP3_PACKET_SIZE)
    data_frame[0:4] = bytes((0xF0, 0x00, seq, 0x38))
    data_frame[4:18] = bytes((
        0x0F, 0xBF, 0x00, 0x00,
        0x02, 0x01, 0x00, 0x00,
        0xDF, 0xA2, 0x50, 0x00,
        0x00, 0xB0,
    ))
    data_frame[25:57] = payload
    frames.append(bytes(data_frame))
    seq = _next_sequence(seq)

    for _ in range(2):
        empty_frame = bytearray(PAP3_PACKET_SIZE)
        empty_frame[0:4] = bytes((0xF0, 0x00, seq, 0x38))
        frames.append(bytes(empty_frame))
        seq = _next_sequence(seq)

    commit = bytearray(PAP3_PACKET_SIZE)
    commit[0:4] = bytes((0xF0, 0x00, seq, 0x2A))
    commit[0x1D] = 0x0F
    commit[0x1E] = 0xBF
    commit[0x21] = 0x03
    commit[0x22] = 0x01
    commit[0x25] = 0xDF
    commit[0x26] = 0xA2
    commit[0x27] = 0x50
    frames.append(bytes(commit))
    seq = _next_sequence(seq)

    return (frames[0], frames[1], frames[2], frames[3]), seq


def _normalize_sequence(value: int) -> int:
    sequence = int(value) & 0xFF
    return sequence if sequence else 1


def _next_sequence(value: int) -> int:
    sequence = (int(value) + 1) & 0xFF
    return sequence if sequence else 1


def _http_json(url: str, timeout: float = 2.0) -> Any:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_collection(payload: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("data", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return ()


def _resolve_named_id(
    api_root: str,
    api_version: str,
    collection: str,
    name: str,
) -> int:
    query = urllib.parse.urlencode({"filter[name]": name})
    url = (
        f"{api_root.rstrip('/')}/api/{api_version}/"
        f"{collection}?{query}"
    )
    payload = _http_json(url)

    exact = None
    first = None
    for item in _extract_collection(payload):
        if first is None:
            first = item
        if str(item.get("name", "")) == name:
            exact = item
            break

    selected = exact or first
    if not selected or "id" not in selected:
        raise KeyError(f"{collection} unavailable: {name}")

    return int(selected["id"])


def _resolve_dataref_id(api_root: str, api_version: str, name: str) -> int:
    return _resolve_named_id(api_root, api_version, "datarefs", name)


def _resolve_command_id(api_root: str, api_version: str, name: str) -> int:
    return _resolve_named_id(api_root, api_version, "commands", name)


def _ws_url(api_root: str, api_version: str) -> str:
    parsed = urllib.parse.urlsplit(api_root.rstrip("/"))
    if not parsed.netloc:
        raise ValueError(f"invalid X-Plane API root: {api_root!r}")
    scheme = "wss" if parsed.scheme == "https" else "ws"
    prefix = parsed.path.rstrip("/")
    return f"{scheme}://{parsed.netloc}{prefix}/api/{api_version}"


def _queue_clear(event_queue: "queue.Queue[Tuple[str, int]]") -> None:
    while True:
        try:
            event_queue.get_nowait()
        except queue.Empty:
            return


def _queue_edge(
    event_queue: "queue.Queue[Tuple[str, int]]",
    edge: Tuple[str, int],
) -> None:
    try:
        event_queue.put_nowait(edge)
        return
    except queue.Full:
        pass

    try:
        event_queue.get_nowait()
    except queue.Empty:
        pass

    try:
        event_queue.put_nowait(edge)
    except queue.Full:
        pass


def _state_value(
    state: Mapping[str, Any],
    key: str,
) -> Optional[float]:
    if key not in state:
        return None
    value = _finite(state.get(key), math.nan)
    return value if math.isfinite(value) else None


def _values_equivalent(left: Any, right: Any) -> bool:
    left_value = _finite(left, math.nan)
    right_value = _finite(right, math.nan)
    if math.isfinite(left_value) and math.isfinite(right_value):
        return abs(left_value - right_value) <= 1e-7
    return left == right


class MuslimSimPAP3MCP:
    """Independent PAP3 manager owned by the unified MuslimSim process."""

    def __init__(
        self,
        *,
        api_version: str,
        api_root: str = "http://127.0.0.1:8086",
        refresh_interval: float = PAP3_DEFAULT_REFRESH_SECONDS,
        startup_delay: float = PAP3_DEFAULT_STARTUP_DELAY_SECONDS,
        at_switch_type: str = "magnetic",
        diagnose: bool = False,
        input_router: Optional[Callable[[int, str], bool]] = None,
    ) -> None:
        switch_type = str(at_switch_type).strip().lower()
        if switch_type not in {"magnetic", "standard"}:
            raise ValueError(
                "PAP3 A/T switch type must be 'magnetic' or 'standard'"
            )

        self.api_version = str(api_version)
        self.api_root = str(api_root).rstrip("/")
        self.refresh_interval = max(0.08, float(refresh_interval))
        self.startup_delay = max(0.0, float(startup_delay))
        self.at_switch_type = switch_type
        self.diagnose = bool(diagnose)
        # The router is optional and receives post-baseline physical edges.
        # It may return True only when a saved Hardware Lab mapping consumed
        # the event; the established PAP3 WebSocket route remains the default.
        self.input_router = input_router

        self.stop_event = threading.Event()
        self._manager_thread: Optional[threading.Thread] = None
        self._current_session_stop: Optional[threading.Event] = None
        self._status = "stopped"
        self._status_detail = ""
        self._status_lock = threading.Lock()
        self._packet_sequence = 1
        self._warned_commands: set[str] = set()
        self._lab_outputs: Dict[str, Any] = {}
        self._lab_outputs_lock = threading.Lock()
        self._lab_output_dirty = threading.Event()
        self._live_snapshot: Dict[str, Any] = {"state": "starting"}
        self._live_snapshot_lock = threading.Lock()

    @property
    def status(self) -> str:
        with self._status_lock:
            return self._status

    @property
    def status_detail(self) -> str:
        with self._status_lock:
            return self._status_detail

    def _set_status(self, value: str, detail: str = "") -> None:
        with self._status_lock:
            self._status = str(value)
            self._status_detail = str(detail)

    def set_lab_output(self, control: str, value: Any) -> None:
        """Set a confirmed PAP3 test output without exposing raw HID writes.

        The driver accepts only its documented aggregate outputs.  In
        particular, the native segment LCD can show all-segments/on or blank
        patterns, but it has no arbitrary-text protocol and no solenoid-force
        setting.
        """

        if control not in {"lcd", "annunciators", "backlight", "at_arm_solenoid"}:
            raise ValueError(f"PAP3 output is not exposed for laboratory testing: {control}")
        with self._lab_outputs_lock:
            self._lab_outputs[control] = value
        self._lab_output_dirty.set()

    def clear_lab_outputs(self) -> None:
        with self._lab_outputs_lock:
            self._lab_outputs.clear()
        self._lab_output_dirty.set()

    def _lab_output_snapshot(self) -> Dict[str, Any]:
        with self._lab_outputs_lock:
            return dict(self._lab_outputs)

    def live_snapshot(self) -> Dict[str, Any]:
        """Read-only values already used for the physical MCP windows."""

        with self._live_snapshot_lock:
            return dict(self._live_snapshot)

    def _remember_live_snapshot(self, state: Mapping[str, Any]) -> None:
        # The UI needs the panel model, not raw HID output bytes.  These are
        # the same simulator values that feed the six native numeric windows
        # and annunciators, copied under a short lock for the loopback status
        # call.  No control path reads this back into the simulator.
        keys = (
            "speed", "speed_is_mach", "heading", "altitude", "vertical_speed",
            "vertical_speed_visible", "speed_visible", "course_capt", "course_fo",
            "fd_capt", "fd_fo", "ap_disconnect", "at_arm", "bank_angle",
            "led_n1", "led_speed", "led_vnav", "led_lvl_chg", "led_hdg_sel",
            "led_lnav", "led_vorloc", "led_app", "led_alt_hld", "led_vs",
            "led_cmd_a", "led_cws_a", "led_cmd_b", "led_cws_b", "led_at_arm",
            "led_ma_capt", "led_ma_fo",
        )
        snapshot = {
            "state": "connected" if _logical(state.get("_transport_connected", 0.0)) else "offline",
            "values": {key: state.get(key) for key in keys if key in state},
        }
        with self._live_snapshot_lock:
            self._live_snapshot = snapshot

    def start(self) -> None:
        if self._manager_thread and self._manager_thread.is_alive():
            return

        self.stop_event.clear()
        self._manager_thread = threading.Thread(
            target=self._manager,
            name="MuslimSim-PAP3-Manager",
            daemon=True,
        )
        self._manager_thread.start()

    def stop(self) -> None:
        self.stop_event.set()

        if self._current_session_stop is not None:
            self._current_session_stop.set()

        if self._manager_thread is not None:
            self._manager_thread.join(timeout=4.0)

        self._set_status("stopped")

    def _manager(self) -> None:
        if hid is None:
            print(
                "WARNING: PAP3 MCP disabled: install hidapi with "
                "py -m pip install hidapi"
            )
            self._set_status("dependency-missing")
            return

        if websocket is None:
            print(
                "WARNING: PAP3 MCP disabled: install websocket-client with "
                "py -m pip install websocket-client"
            )
            self._set_status("dependency-missing")
            return

        if self.startup_delay > 0.0:
            if self.diagnose:
                print(
                    "PAP3 startup delayed "
                    f"{self.startup_delay:.2f}s so BB35/BB36 display "
                    "sessions finish their font/plane initialization first."
                )
            if self.stop_event.wait(self.startup_delay):
                self._set_status("stopped")
                return

        absent_reported = False

        while not self.stop_event.is_set():
            device = None
            session_stop = threading.Event()
            self._current_session_stop = session_stop

            try:
                # Zibo can become transport-ready just before every display
                # DataRef is published. Resolve that API state before touching
                # the panel, so an early retry cannot clear the six windows.
                dataref_ids, command_ids = self._resolve_runtime_ids()

                device = self._open_device()
                absent_reported = False
                self._packet_sequence = 1
                self._warned_commands.clear()

                hid_io_lock = threading.Lock()
                self._initialize_device(device, hid_io_lock)

                event_queue: "queue.Queue[Tuple[str, int]]" = queue.Queue(
                    maxsize=PAP3_QUEUE_LIMIT
                )
                state: Dict[str, Any] = {"_transport_connected": 0.0}
                state_lock = threading.Lock()
                dirty_event = threading.Event()
                transport_ready = threading.Event()

                input_thread = threading.Thread(
                    target=self._input_worker,
                    args=(
                        device,
                        event_queue,
                        transport_ready,
                        hid_io_lock,
                        session_stop,
                    ),
                    name="MuslimSim-PAP3-Input",
                    daemon=True,
                )
                websocket_thread = threading.Thread(
                    target=self._websocket_worker,
                    args=(
                        event_queue,
                        dataref_ids,
                        command_ids,
                        state,
                        state_lock,
                        dirty_event,
                        transport_ready,
                        session_stop,
                    ),
                    name="MuslimSim-PAP3-WebSocket",
                    daemon=True,
                )
                output_thread = threading.Thread(
                    target=self._output_worker,
                    args=(
                        device,
                        state,
                        state_lock,
                        dirty_event,
                        hid_io_lock,
                        session_stop,
                    ),
                    name="MuslimSim-PAP3-Output",
                    daemon=True,
                )

                input_thread.start()
                websocket_thread.start()
                output_thread.start()

                self._set_status("connected")
                print(
                    "PAP3 MCP CONNECTED: WINCTRL 4098:BF0F, "
                    "Zibo WebSocket controls, six native displays, "
                    "annunciators, brightness, "
                    f"A/T={self.at_switch_type}."
                )

                while (
                    not self.stop_event.is_set()
                    and not session_stop.wait(0.10)
                ):
                    if (
                        not input_thread.is_alive()
                        or not websocket_thread.is_alive()
                        or not output_thread.is_alive()
                    ):
                        session_stop.set()
                        break

                session_stop.set()
                transport_ready.clear()
                input_thread.join(timeout=1.0)
                websocket_thread.join(timeout=1.5)
                output_thread.join(timeout=1.5)

            except FileNotFoundError:
                self._set_status("waiting-for-pap3", "WINCTRL 3N PAP MCP is not connected")
                if not absent_reported:
                    print(
                        "PAP3 MCP: waiting for WINCTRL 3N PAP MCP "
                        "(4098:BF0F)."
                    )
                    absent_reported = True

            except Exception as exc:
                self._set_status("reconnecting", f"{type(exc).__name__}: {exc}")
                if not self.stop_event.is_set():
                    print(f"PAP3 MCP reconnecting after error: {exc}")

            finally:
                session_stop.set()
                if device is not None:
                    # Preserve the last valid frame through a short reconnect.
                    # Repeated blackouts were perceived as PAP3 flashing.
                    if self.stop_event.is_set():
                        try:
                            self._blackout(device)
                        except Exception:
                            pass
                    try:
                        device.close()
                    except Exception:
                        pass
                self._current_session_stop = None

            if not self.stop_event.is_set():
                self.stop_event.wait(PAP3_RECONNECT_SECONDS)

        self._set_status("stopped")

    @staticmethod
    def _open_device() -> Any:
        devices = hid.enumerate(PAP3_VID, PAP3_PID)
        if not devices:
            raise FileNotFoundError(
                f"{PAP3_PRODUCT_LABEL} ({PAP3_VID:04X}:{PAP3_PID:04X}) "
                "not connected"
            )

        # Prefer a record whose product string names PAP/MCP, while retaining a
        # deterministic fallback for firmware that omits the string.
        chosen = None
        for info in devices:
            name = str(info.get("product_string") or "").upper()
            if "PAP" in name or "MCP" in name:
                chosen = info
                break
        if chosen is None:
            chosen = devices[0]

        path = chosen.get("path")
        if not path:
            raise RuntimeError("PAP3 HID path unavailable")

        device = hid.device()
        device.open_path(path)
        try:
            device.set_nonblocking(1)
        except Exception:
            pass
        return wrap_hid_device(
            device,
            label="PAP3-BF0F",
            product_id=PAP3_PID,
        )

    def _resolve_runtime_ids(self) -> Tuple[Dict[str, int], Dict[str, int]]:
        dataref_ids: Dict[str, int] = {}
        missing_required = []

        for key, name in PAP3_DATAREFS.items():
            try:
                dataref_ids[key] = _resolve_dataref_id(
                    self.api_root,
                    self.api_version,
                    name,
                )
            except Exception:
                if key in PAP3_REQUIRED_DATAREF_KEYS:
                    missing_required.append(name)
                elif self.diagnose:
                    print(f"PAP3 optional DataRef unavailable: {name}")

        if missing_required:
            raise RuntimeError(
                "required Zibo PAP3 DataRefs unavailable: "
                + ", ".join(missing_required[:4])
                + (" ..." if len(missing_required) > 4 else "")
            )

        command_names = {
            command_name
            for _label, command_name in PAP3_BUTTONS.values()
        }
        command_names.update(PAP3_TOGGLE_COMMANDS.values())
        command_names.update(PAP3_BANK_COMMANDS.values())

        command_ids: Dict[str, int] = {}
        for name in sorted(command_names):
            try:
                command_ids[name] = _resolve_command_id(
                    self.api_root,
                    self.api_version,
                    name,
                )
            except Exception:
                if self.diagnose:
                    print(f"PAP3 Zibo command unavailable: {name}")

        return dataref_ids, command_ids

    def _initialize_device(
        self,
        device: Any,
        hid_io_lock: threading.Lock,
    ) -> None:
        # Keep this short and atomic.  Overall LED brightness remains zero
        # while the first live output pass programs every individual LED, so
        # stale firmware state cannot flash on the panel.
        # Take the process-wide display bus before this panel's HID lock.
        # Otherwise a long frame on another WinCtrl screen can leave PAP3's
        # output worker holding ``hid_io_lock`` while it waits for the bus,
        # which also pauses PAP3 input reads and makes Studio look frozen.
        with output_transaction(
            "PAP3-initialize",
            settle_after=0.004,
        ), hid_io_lock:
            self._write_packet(
                device,
                pap3_initialize_packet(self._packet_sequence),
            )
            self._packet_sequence = _next_sequence(self._packet_sequence)

            for selector in (
                PAP3_BACKLIGHT,
                PAP3_LCD_BACKLIGHT,
                PAP3_OVERALL_LED_BRIGHTNESS,
            ):
                self._write_packet(device, pap3_led_packet(selector, 0))

            self._write_packet(
                device,
                pap3_led_packet(PAP3_SOLENOID_SELECTOR, 0),
            )
            self._write_lcd_payload_locked(
                device,
                bytes(PAP3_LCD_PAYLOAD_SIZE),
            )

    def _blackout(self, device: Any) -> None:
        # Brightness-off hides every individual LED immediately; there is no
        # reason to send seventeen extra LED reports during disconnect/shutdown.
        with output_transaction(
            "PAP3-blackout",
            settle_after=0.003,
        ):
            for selector in (
                PAP3_OVERALL_LED_BRIGHTNESS,
                PAP3_LCD_BACKLIGHT,
                PAP3_BACKLIGHT,
            ):
                self._write_packet(device, pap3_led_packet(selector, 0))

            self._write_packet(
                device,
                pap3_led_packet(PAP3_SOLENOID_SELECTOR, 0),
            )
            self._write_lcd_payload_locked(
                device,
                bytes(PAP3_LCD_PAYLOAD_SIZE),
            )

    @staticmethod
    def _write_packet(device: Any, packet: bytes) -> None:
        result = device.write(list(packet))
        if isinstance(result, int) and result < 0:
            raise OSError(f"PAP3 HID write failed ({result})")

    def _write_lcd_payload_locked(
        self,
        device: Any,
        payload: bytes,
    ) -> None:
        packets, next_sequence = pap3_lcd_packets(
            payload,
            self._packet_sequence,
        )
        # A PAP3 LCD update is one four-report transaction.  Keep the data,
        # two required empty frames, and commit together.
        with output_transaction("PAP3-LCD"):
            for index, packet in enumerate(packets):
                self._write_packet(device, packet)
                if index + 1 < len(packets):
                    time.sleep(PAP3_LCD_PACKET_GAP_SECONDS)
        self._packet_sequence = next_sequence

    def _input_worker(
        self,
        device: Any,
        event_queue: "queue.Queue[Tuple[str, int]]",
        transport_ready: threading.Event,
        hid_io_lock: threading.Lock,
        session_stop: threading.Event,
    ) -> None:
        previous_bits: Optional[int] = None
        read_errors = 0
        unexpected_report_seen = False

        while (
            not self.stop_event.is_set()
            and not session_stop.is_set()
        ):
            try:
                with hid_io_lock:
                    report = device.read(64)
                read_errors = 0
            except Exception as exc:
                read_errors += 1
                if read_errors >= 3:
                    print(f"PAP3 HID disconnected: {exc}")
                    session_stop.set()
                    return
                session_stop.wait(0.01)
                continue

            if not report:
                session_stop.wait(0.001)
                continue

            raw = bytes(report)
            current_bits = pap3_decode_button_bits(raw)

            if current_bits is None:
                if self.diagnose and not unexpected_report_seen:
                    report_id = raw[0] if raw else -1
                    print(
                        f"PAP3 ignored HID report len={len(raw)} "
                        f"id=0x{report_id & 0xFF:02X}"
                    )
                    unexpected_report_seen = True
                continue

            if previous_bits is None:
                # Startup safety: capture only.  Do not force the aircraft to
                # the physical panel's current maintained-switch positions.
                previous_bits = current_bits
                if self.diagnose:
                    print(
                        "PAP3 startup baseline captured; aircraft unchanged "
                        f"(buttons=0x{current_bits:012X})."
                    )
                continue

            changed = current_bits ^ previous_bits
            if changed:
                for hardware_index in range(PAP3_BUTTON_COUNT):
                    mask = 1 << hardware_index
                    if not (changed & mask):
                        continue

                    edge = (
                        "press"
                        if current_bits & mask
                        else "release"
                    )

                    routed = False
                    if self.input_router is not None:
                        try:
                            routed = bool(self.input_router(hardware_index, edge))
                        except Exception as exc:
                            # A panel/profile fault must never kill the PAP3
                            # HID worker or prevent the established default
                            # binding from being considered.
                            print(f"PAP3 hardware-lab input observer failed: {exc}")

                    # Movements while X-Plane is disconnected are deliberately
                    # not replayed later.
                    if transport_ready.is_set() and not routed:
                        _queue_edge(
                            event_queue,
                            (edge, hardware_index),
                        )

                    if self.diagnose:
                        print(
                            f"PAP3 HID index={hardware_index:02d} "
                            f"{edge.upper()}"
                        )

            previous_bits = current_bits

    @staticmethod
    def _ws_send(ws: Any, payload: Mapping[str, Any]) -> None:
        ws.send(json.dumps(payload, separators=(",", ":")))

    @staticmethod
    def _next_request(counter: list[int]) -> int:
        counter[0] += 1
        return counter[0]

    def _command_phase(
        self,
        ws: Any,
        request_counter: list[int],
        command_id: int,
        active: bool,
    ) -> None:
        self._ws_send(
            ws,
            {
                "req_id": self._next_request(request_counter),
                "type": "command_set_is_active",
                "params": {
                    "commands": [{
                        "id": int(command_id),
                        "is_active": bool(active),
                    }]
                },
            },
        )

    def _set_dataref_value(
        self,
        ws: Any,
        request_counter: list[int],
        dataref_id: int,
        value: float,
    ) -> None:
        """Set one writable DataRef through this manager's existing socket."""
        self._ws_send(
            ws,
            {
                "req_id": self._next_request(request_counter),
                "type": "dataref_set_values",
                "params": {
                    "datarefs": [{
                        "id": int(dataref_id),
                        "value": float(value),
                    }]
                },
            },
        )

    def _pulse_command(
        self,
        ws: Any,
        request_counter: list[int],
        command_id: int,
        count: int = 1,
    ) -> None:
        for _ in range(max(0, int(count))):
            self._command_phase(
                ws,
                request_counter,
                command_id,
                True,
            )
            self._command_phase(
                ws,
                request_counter,
                command_id,
                False,
            )

    def _warn_command(
        self,
        label: str,
        command_name: str,
    ) -> None:
        token = f"{label}:{command_name}"
        if token in self._warned_commands:
            return
        self._warned_commands.add(token)
        print(
            f"PAP3 {label}: Zibo command unavailable "
            f"({command_name})"
        )

    def _maybe_toggle_to(
        self,
        ws: Any,
        request_counter: list[int],
        command_ids: Mapping[str, int],
        state: Mapping[str, Any],
        *,
        state_key: str,
        target: bool,
        command_name: str,
        label: str,
    ) -> None:
        current_numeric = _state_value(state, state_key)
        if current_numeric is None:
            if self.diagnose:
                print(
                    f"PAP3 {label}: waiting for simulator state; "
                    "no startup/guess write made."
                )
            return

        current = current_numeric >= 0.5
        if current == bool(target):
            return

        command_id = command_ids.get(command_name)
        if command_id is None:
            self._warn_command(label, command_name)
            return

        self._pulse_command(
            ws,
            request_counter,
            command_id,
        )

        if self.diagnose:
            print(
                f"PAP3 {label} -> {'ON' if target else 'OFF'}"
            )

    def _drain_input_events(
        self,
        ws: Any,
        event_queue: "queue.Queue[Tuple[str, int]]",
        dataref_ids: Mapping[str, int],
        command_ids: Mapping[str, int],
        state: MutableMapping[str, Any],
        state_lock: threading.Lock,
        request_counter: list[int],
    ) -> None:
        processed = 0

        while processed < 128:
            try:
                edge, hardware_index = event_queue.get_nowait()
            except queue.Empty:
                return

            processed += 1
            hardware_index = int(hardware_index)
            pressed = edge == "press"

            speed_control = PAP3_SPEED_BUTTONS.get(hardware_index)
            if speed_control is not None:
                if not pressed:
                    continue
                label, direction = speed_control
                with state_lock:
                    snapshot = dict(state)
                speed = _state_value(snapshot, "speed")
                speed_is_mach = _logical(
                    snapshot.get("speed_is_mach", 0.0)
                )
                # In IAS mode, write the authoritative Zibo knots dial, not
                # the combined display mirror which Zibo restores each frame.
                speed_ref_id = dataref_ids.get(
                    "speed" if speed_is_mach else "speed_control_kts"
                )
                if speed is None or speed_ref_id is None:
                    if self.diagnose:
                        print(
                            f"PAP3 {label}: waiting for Zibo MCP speed; "
                            "no guessed write made."
                        )
                    continue
                target = pap3_next_speed_value(
                    speed,
                    speed_is_mach,
                    direction,
                )
                if _values_equivalent(speed, target):
                    continue
                self._set_dataref_value(
                    ws,
                    request_counter,
                    speed_ref_id,
                    target,
                )
                # Keep successive physical detents responsive while waiting
                # for the authoritative Web API subscription update.
                with state_lock:
                    state["speed"] = target
                if self.diagnose:
                    print(f"PAP3 {label} -> Zibo MCP speed {target:g}")
                continue

            regular = PAP3_BUTTONS.get(hardware_index)
            if regular is not None:
                label, command_name = regular
                command_id = command_ids.get(command_name)
                if command_id is None:
                    if pressed:
                        self._warn_command(label, command_name)
                    continue

                self._command_phase(
                    ws,
                    request_counter,
                    command_id,
                    pressed,
                )
                if pressed and self.diagnose:
                    print(
                        f"PAP3 key {hardware_index:02d} {label} -> Zibo"
                    )
                continue

            with state_lock:
                snapshot = dict(state)

            if hardware_index == PAP3_FD_CAPT_INDEX:
                self._maybe_toggle_to(
                    ws,
                    request_counter,
                    command_ids,
                    snapshot,
                    state_key="fd_capt",
                    target=pressed,
                    command_name=PAP3_TOGGLE_COMMANDS["fd_capt"],
                    label="FD CAPT",
                )
                continue

            if hardware_index == PAP3_FD_FO_INDEX:
                self._maybe_toggle_to(
                    ws,
                    request_counter,
                    command_ids,
                    snapshot,
                    state_key="fd_fo",
                    target=pressed,
                    command_name=PAP3_TOGGLE_COMMANDS["fd_fo"],
                    label="FD FO",
                )
                continue

            if hardware_index in (
                PAP3_AP_DISC_DOWN_INDEX,
                PAP3_AP_DISC_UP_INDEX,
            ):
                if not pressed:
                    continue
                target = hardware_index == PAP3_AP_DISC_UP_INDEX
                self._maybe_toggle_to(
                    ws,
                    request_counter,
                    command_ids,
                    snapshot,
                    state_key="ap_disconnect",
                    target=target,
                    command_name=PAP3_TOGGLE_COMMANDS["ap_disconnect"],
                    label="AP DISCONNECT",
                )
                continue

            if hardware_index in PAP3_BANK_ANGLE_TARGETS:
                if not pressed:
                    continue
                target = PAP3_BANK_ANGLE_TARGETS[hardware_index]
                current_value = _state_value(snapshot, "bank_angle")
                if current_value is None:
                    if self.diagnose:
                        print(
                            "PAP3 BANK ANGLE: waiting for simulator state; "
                            "selector movement not guessed."
                        )
                    continue

                current = max(0, min(4, int(round(current_value))))
                delta = target - current
                if delta == 0:
                    continue

                command_name = PAP3_BANK_COMMANDS[
                    "up" if delta > 0 else "down"
                ]
                command_id = command_ids.get(command_name)
                if command_id is None:
                    self._warn_command("BANK ANGLE", command_name)
                    continue

                self._pulse_command(
                    ws,
                    request_counter,
                    command_id,
                    abs(delta),
                )
                if self.diagnose:
                    print(
                        "PAP3 BANK ANGLE -> "
                        f"{(10, 15, 20, 25, 30)[target]} degrees"
                    )
                continue

            if hardware_index in (
                PAP3_AT_ARMED_INDEX,
                PAP3_AT_DISARMED_INDEX,
            ):
                if self.at_switch_type == "standard":
                    # A standard PAP3 switch springs back.  Only its ARMED
                    # rising edge is a momentary toggle; the return line must
                    # never disarm it.
                    if (
                        hardware_index != PAP3_AT_ARMED_INDEX
                        or not pressed
                    ):
                        continue

                    command_name = PAP3_TOGGLE_COMMANDS["at_arm"]
                    command_id = command_ids.get(command_name)
                    if command_id is None:
                        self._warn_command("A/T ARM", command_name)
                        continue
                    self._pulse_command(
                        ws,
                        request_counter,
                        command_id,
                    )
                    if self.diagnose:
                        print("PAP3 A/T momentary toggle")
                    continue

                # Magnetic switch: each physical line is an absolute target.
                if not pressed:
                    continue
                target = hardware_index == PAP3_AT_ARMED_INDEX
                self._maybe_toggle_to(
                    ws,
                    request_counter,
                    command_ids,
                    snapshot,
                    state_key="at_arm",
                    target=target,
                    command_name=PAP3_TOGGLE_COMMANDS["at_arm"],
                    label="A/T ARM",
                )
                continue

    def _websocket_worker(
        self,
        event_queue: "queue.Queue[Tuple[str, int]]",
        dataref_ids: Mapping[str, int],
        command_ids: Mapping[str, int],
        state: MutableMapping[str, Any],
        state_lock: threading.Lock,
        dirty_event: threading.Event,
        transport_ready: threading.Event,
        session_stop: threading.Event,
    ) -> None:
        id_to_key = {
            str(int(reference_id)): key
            for key, reference_id in dataref_ids.items()
        }
        request_counter = [7000]
        websocket_url = _ws_url(
            self.api_root,
            self.api_version,
        )
        connection_reported = False

        while (
            not self.stop_event.is_set()
            and not session_stop.is_set()
        ):
            ws = None
            try:
                transport_ready.clear()
                _queue_clear(event_queue)

                ws = websocket.create_connection(
                    websocket_url,
                    timeout=1.0,
                    enable_multithread=True,
                )
                ws.settimeout(PAP3_WS_RECV_TIMEOUT)

                subscriptions = []
                for key, reference_id in dataref_ids.items():
                    subscription: Dict[str, Any] = {
                        "id": int(reference_id)
                    }
                    if key in PAP3_DATAREF_INDICES:
                        subscription["index"] = int(
                            PAP3_DATAREF_INDICES[key]
                        )
                    subscriptions.append(subscription)

                self._ws_send(
                    ws,
                    {
                        "req_id": self._next_request(request_counter),
                        "type": "dataref_subscribe_values",
                        "params": {"datarefs": subscriptions},
                    },
                )

                with state_lock:
                    state["_transport_connected"] = 1.0
                dirty_event.set()
                transport_ready.set()

                if not connection_reported or self.diagnose:
                    print(
                        "PAP3 X-Plane WebSocket CONNECTED: "
                        f"{len(subscriptions)} DataRefs subscribed, "
                        f"{len(command_ids)} commands resolved."
                    )
                    connection_reported = True

                while (
                    not self.stop_event.is_set()
                    and not session_stop.is_set()
                ):
                    self._drain_input_events(
                        ws,
                        event_queue,
                        dataref_ids,
                        command_ids,
                        state,
                        state_lock,
                        request_counter,
                    )

                    try:
                        raw_message = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue

                    if not raw_message:
                        raise ConnectionError(
                            "X-Plane WebSocket closed"
                        )

                    message = json.loads(raw_message)

                    if message.get("type") == "result":
                        if (
                            not message.get("success", False)
                            and self.diagnose
                        ):
                            print(
                                "PAP3 WebSocket request error: "
                                f"{message.get('error_code')} "
                                f"{message.get('error_message')}"
                            )
                        continue

                    if message.get("type") != "dataref_update_values":
                        continue

                    updates = message.get("data", {})
                    if not isinstance(updates, dict):
                        continue

                    changed = False
                    with state_lock:
                        for raw_id, value in updates.items():
                            key = id_to_key.get(str(raw_id).strip())
                            if key is None:
                                continue

                            scalar = _finite(value, math.nan)
                            if not math.isfinite(scalar):
                                continue

                            if (
                                key not in state
                                or not _values_equivalent(
                                    state.get(key),
                                    scalar,
                                )
                            ):
                                state[key] = scalar
                                changed = True

                    if changed:
                        dirty_event.set()

            except Exception as exc:
                if (
                    not self.stop_event.is_set()
                    and not session_stop.is_set()
                    and self.diagnose
                ):
                    print(
                        f"PAP3 X-Plane WebSocket reconnecting: {exc}"
                    )

            finally:
                transport_ready.clear()
                _queue_clear(event_queue)
                with state_lock:
                    state["_transport_connected"] = 0.0
                dirty_event.set()

                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass

            if (
                not self.stop_event.is_set()
                and not session_stop.is_set()
            ):
                session_stop.wait(PAP3_RECONNECT_SECONDS)

    def _desired_outputs(
        self,
        state: Mapping[str, Any],
    ) -> Tuple[bytes, Dict[int, int], int]:
        connected = _logical(
            state.get("_transport_connected", 0.0)
        )
        avionics = connected and _logical(
            state.get("avionics", 0.0)
        )
        test_mode = _display_test_mode(
            state.get("display_test", 0.0)
        )
        display_test = connected and test_mode >= 1

        panel_ratio = max(
            0.0,
            min(
                1.0,
                _finite(
                    state.get("panel_brightness", 0.5),
                    0.5,
                ),
            ),
        )

        # PAP3 selector 0 is the illumination behind the button legends
        # (LNAV/VNAV/APP/CMD/etc.), not the green mode annunciators.
        #
        # Use X-Plane's ACTUAL panel brightness here.  Unlike Zibo's rheostat
        # position, this value reflects electrical power/failures, so a saved
        # non-zero dimmer position cannot leave the physical PAP3 lit while the
        # aircraft is cold-and-dark.
        actual_panel_ratio = _finite(
            state.get("panel_brightness_actual", math.nan),
            math.nan,
        )
        if math.isfinite(actual_panel_ratio):
            backlight_ratio = max(0.0, min(1.0, actual_panel_ratio))
        else:
            # Compatibility fallback if this optional dataref is unavailable.
            backlight_ratio = panel_ratio if avionics else 0.0

        # Ignore tiny residual values that some aircraft leave near zero.
        backlight = (
            int(round(backlight_ratio * 255.0))
            if connected and backlight_ratio >= 0.02
            else 0
        )
        lcd_backlight = 180 if avionics else 0
        overall_led = (
            255
            if display_test
            # ``electric/main_bus`` is zero in the current Zibo even with
            # powered avionics and active MCP statuses. It must not black out
            # PAP3 annunciators; avionics state is the valid power gate.
            else (180 if avionics else 0)
        )

        outputs: Dict[int, int] = {
            PAP3_BACKLIGHT: backlight,
            PAP3_LCD_BACKLIGHT: lcd_backlight,
            PAP3_OVERALL_LED_BRIGHTNESS: overall_led,
        }

        for selector, key in PAP3_LED_DATAREFS.items():
            # Never leave stale mode lights illuminated while X-Plane is
            # disconnected. The retained state cache becomes visible again
            # only after a fresh transport subscription is active.
            outputs[selector] = int(
                display_test
                or (
                    connected
                    and _logical(state.get(key, 0.0))
                )
            )

        solenoid = 0
        if self.at_switch_type == "magnetic" and connected:
            solenoid = int(_logical(state.get("at_arm", 0.0)))

        lcd_payload = pap3_compose_lcd_payload(
            state,
            transport_connected=connected,
        )
        lab_outputs = self._lab_output_snapshot()
        if "annunciators" in lab_outputs:
            forced = 255 if _logical(lab_outputs["annunciators"]) else 0
            for selector in PAP3_LED_DATAREFS:
                outputs[selector] = forced
            outputs[PAP3_OVERALL_LED_BRIGHTNESS] = 255 if forced else 0
        if "backlight" in lab_outputs:
            forced = 255 if _logical(lab_outputs["backlight"]) else 0
            outputs[PAP3_BACKLIGHT] = forced
            outputs[PAP3_LCD_BACKLIGHT] = 180 if forced else 0
            outputs[PAP3_OVERALL_LED_BRIGHTNESS] = max(outputs[PAP3_OVERALL_LED_BRIGHTNESS], forced)
        if "at_arm_solenoid" in lab_outputs:
            # The only captured PAP3 actuator control is a binary selector.
            solenoid = int(_logical(lab_outputs["at_arm_solenoid"]))
        if "lcd" in lab_outputs:
            requested_value = lab_outputs["lcd"]
            if isinstance(requested_value, Mapping):
                # The LCD protocol already has a captured numeric composer.
                # A practice cockpit may therefore drive the same six fields
                # as the live MCP without accepting arbitrary display bytes.
                lcd_payload = pap3_compose_lcd_payload(
                    requested_value,
                    transport_connected=True,
                )
                # Practice mode carries individual, verified annunciator
                # states beside its six numerical windows.  It never lights
                # every button merely because the virtual panel is powered.
                if "annunciators" not in lab_outputs:
                    for selector, key in PAP3_LED_DATAREFS.items():
                        outputs[selector] = int(_logical(requested_value.get(key, 0.0)))
            else:
                requested = str(requested_value).strip().upper()
                if requested in {"888888", "CHECKER", "ALL_ON", "1", "TRUE"}:
                    lcd_payload = bytes([0xFF] * PAP3_LCD_PAYLOAD_SIZE)
                elif requested in {"", "0", "FALSE", "ALL_OFF"}:
                    lcd_payload = bytes(PAP3_LCD_PAYLOAD_SIZE)
        return lcd_payload, outputs, solenoid

    def _output_worker(
        self,
        device: Any,
        state: Mapping[str, Any],
        state_lock: threading.Lock,
        dirty_event: threading.Event,
        hid_io_lock: threading.Lock,
        session_stop: threading.Event,
    ) -> None:
        # Initialization already established a fully dark/blank baseline.
        previous_lcd: Optional[bytes] = bytes(PAP3_LCD_PAYLOAD_SIZE)
        previous_outputs: Dict[int, int] = {
            PAP3_BACKLIGHT: 0,
            PAP3_LCD_BACKLIGHT: 0,
            PAP3_OVERALL_LED_BRIGHTNESS: 0,
        }
        previous_solenoid: Optional[int] = 0
        last_lcd_write = 0.0
        dirty_event.set()

        while (
            not self.stop_event.is_set()
            and not session_stop.is_set()
        ):
            dirty_event.wait(0.10)
            if self._lab_output_dirty.is_set():
                self._lab_output_dirty.clear()
                dirty_event.set()
            if not dirty_event.is_set():
                continue
            dirty_event.clear()

            with state_lock:
                snapshot = dict(state)

            self._remember_live_snapshot(snapshot)

            lcd_payload, outputs, solenoid = self._desired_outputs(
                snapshot
            )

            now = time.monotonic()
            lcd_due = (
                previous_lcd != lcd_payload
                and now - last_lcd_write >= self.refresh_interval
            )

            try:
                # Preserve the same global-then-local lock order as startup.
                # Input never needs the global display bus, so it remains
                # free to report a real button press while another screen is
                # completing an atomic output burst.
                with output_transaction("PAP3-live-output"), hid_io_lock:
                    # Program individual annunciators while overall brightness
                    # is still dark on first sync.  This prevents a one-frame
                    # flash of stale LED state left by another application.
                    for selector in sorted(outputs):
                        if selector in (
                            PAP3_BACKLIGHT,
                            PAP3_LCD_BACKLIGHT,
                            PAP3_OVERALL_LED_BRIGHTNESS,
                        ):
                            continue
                        value = outputs[selector]
                        if previous_outputs.get(selector) == value:
                            continue
                        self._write_packet(
                            device,
                            pap3_led_packet(selector, value),
                        )
                        previous_outputs[selector] = value

                    if previous_solenoid != solenoid:
                        self._write_packet(
                            device,
                            pap3_led_packet(
                                PAP3_SOLENOID_SELECTOR,
                                solenoid,
                            ),
                        )
                        previous_solenoid = solenoid

                    if lcd_due:
                        self._write_lcd_payload_locked(
                            device,
                            lcd_payload,
                        )
                        previous_lcd = lcd_payload
                        last_lcd_write = time.monotonic()

                    # Reveal the already-programmed LEDs/LCD last.
                    for selector in (
                        PAP3_BACKLIGHT,
                        PAP3_LCD_BACKLIGHT,
                        PAP3_OVERALL_LED_BRIGHTNESS,
                    ):
                        value = outputs[selector]
                        if previous_outputs.get(selector) == value:
                            continue
                        self._write_packet(
                            device,
                            pap3_led_packet(selector, value),
                        )
                        previous_outputs[selector] = value

                if previous_lcd != lcd_payload:
                    wait_for = max(
                        0.0,
                        self.refresh_interval
                        - (time.monotonic() - last_lcd_write),
                    )
                    if wait_for > 0.0:
                        session_stop.wait(wait_for)
                    if session_stop.is_set():
                        return
                    dirty_event.set()

            except Exception as exc:
                print(f"PAP3 output disconnected: {exc}")
                session_stop.set()
                return

class MuslimSimPAP3Preview:
    """Minimal HID-only PAP3 preview used while X-Plane is unavailable.

    It shares the proven MCP LCD/LED packet builders with the live manager but
    deliberately has no simulator transport and no input route. The bridge
    stops it before the normal PAP3 manager claims the device handle.
    """

    def __init__(self, input_sink: Optional[Callable[[int, str], None]] = None) -> None:
        self.stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._state_lock = threading.Lock()
        self._outputs: Dict[str, Any] = {
            "lcd": {
                "speed": 250, "speed_is_mach": 0, "heading": 90,
                "altitude": 10000, "vertical_speed": 0,
                "course_capt": 0, "course_fo": 0,
                "speed_visible": 1, "vertical_speed_visible": 1,
                "avionics": 1,
            },
            "backlight": 1,
        }
        self._status = "stopped"
        self._status_detail = ""
        self._status_lock = threading.Lock()
        self._lcd_transactions = 0
        self._last_lcd_payload = bytes(PAP3_LCD_PAYLOAD_SIZE)
        self._last_lcd_write_at = 0.0
        self.input_sink = input_sink
        # Reuse initialization, packet sequencing and HID transaction guards.
        self._writer = MuslimSimPAP3MCP(api_version="preview", startup_delay=0.0)

    @property
    def status(self) -> str:
        with self._status_lock:
            return self._status

    @property
    def status_detail(self) -> str:
        with self._status_lock:
            return self._status_detail

    def _set_status(self, value: str, detail: str = "") -> None:
        with self._status_lock:
            self._status = value
            self._status_detail = str(detail)

    def live_snapshot(self) -> Dict[str, Any]:
        """Return the native six-window state being sent by the preview."""

        with self._state_lock:
            outputs = dict(self._outputs)
            lcd = dict(outputs.get("lcd") or {})
        return {
            "state": self.status,
            "values": lcd,
            "outputs": {
                "annunciators": outputs.get("annunciators", 0),
                "backlight": outputs.get("backlight", 0),
                "at_arm_solenoid": outputs.get("at_arm_solenoid", 0),
            },
            "display_mirror": "last-sent-output",
            "physical_output": {
                "lcd_transactions": self._lcd_transactions,
                "lcd_nonzero": bool(any(self._last_lcd_payload)),
                "last_lcd_write_age_ms": int(max(0.0, time.monotonic() - self._last_lcd_write_at) * 1000)
                if self._last_lcd_write_at else None,
            },
        }

    def set_lab_output(self, control: str, value: Any) -> None:
        if control not in {"lcd", "annunciators", "backlight", "at_arm_solenoid"}:
            raise ValueError(f"PAP3 preview does not expose {control}")
        if control == "lcd" and not isinstance(value, Mapping):
            raise ValueError("PAP3 practice LCD requires captured numeric fields")
        with self._state_lock:
            self._outputs[control] = dict(value) if isinstance(value, Mapping) else value

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self.stop_event.clear()
        self._thread = threading.Thread(
            target=self._manager, name="MuslimSim-PAP3-Preview", daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None
        self._set_status("stopped")

    def _manager(self) -> None:
        """Keep the simulator-down display owner alive across USB replugging."""

        while not self.stop_event.is_set():
            self._run_session()
            if not self.stop_event.is_set():
                self._set_status("reconnecting", "Waiting to reclaim the reconnected PAP3")
                self.stop_event.wait(PAP3_RECONNECT_SECONDS)
        self._set_status("stopped")

    def _run_session(self) -> None:
        if hid is None:
            self._set_status("dependency-missing")
            return
        device = None
        reader: Optional[threading.Thread] = None
        try:
            device = self._writer._open_device()
            io_lock = threading.Lock()
            self._writer._initialize_device(device, io_lock)
            # Do not trust the first segment commit while the panel is still
            # changing out of its cleared start state.  This is a passive
            # wait, after which the normal captured packet is resent.
            if self.stop_event.wait(PAP3_PRACTICE_INITIAL_SETTLE_SECONDS):
                return
            self._set_status("practice-preview")
            reader = threading.Thread(
                target=self._input_worker,
                args=(device, io_lock),
                name="MuslimSim-PAP3-Preview-Input",
                daemon=True,
            )
            reader.start()
            previous_payload: Optional[bytes] = None
            previous_leds: Dict[int, int] = {}
            previous_solenoid: Optional[int] = None
            while not self.stop_event.is_set():
                with self._state_lock:
                    outputs = dict(self._outputs)
                lcd_state = dict(outputs.get("lcd") or {})
                payload = pap3_compose_lcd_payload(lcd_state, transport_connected=True)
                panel_on = 255 if _logical(outputs.get("backlight", 1)) else 0
                explicit_annunciators = outputs.get("annunciators")
                if explicit_annunciators is None:
                    individual_leds = {
                        selector: int(_logical(lcd_state.get(key, 0.0)))
                        for selector, key in PAP3_LED_DATAREFS.items()
                    }
                else:
                    forced = int(bool(_logical(explicit_annunciators)))
                    individual_leds = {selector: forced for selector in PAP3_INDIVIDUAL_LED_SELECTORS}
                leds = {
                    PAP3_BACKLIGHT: panel_on,
                    PAP3_LCD_BACKLIGHT: 180 if panel_on else 0,
                    PAP3_OVERALL_LED_BRIGHTNESS: 180 if panel_on else 0,
                    **individual_leds,
                }
                solenoid = int(_logical(outputs.get("at_arm_solenoid", 0)))
                now = time.monotonic()
                lcd_due = (
                    previous_payload != payload
                    or now - self._last_lcd_write_at >= PAP3_PRACTICE_LCD_RESYNC_SECONDS
                )
                # Do not hold this panel's input lock while waiting for an
                # unrelated WinCtrl display transaction.
                with output_transaction("PAP3-practice-preview"), io_lock:
                    for selector, value in sorted(leds.items()):
                        if previous_leds.get(selector) != value:
                            self._writer._write_packet(device, pap3_led_packet(selector, value))
                    if previous_solenoid != solenoid:
                        self._writer._write_packet(device, pap3_led_packet(PAP3_SOLENOID_SELECTOR, solenoid))
                    if lcd_due:
                        self._writer._write_lcd_payload_locked(device, payload)
                previous_leds = leds
                previous_solenoid = solenoid
                previous_payload = payload
                if lcd_due:
                    with self._status_lock:
                        self._lcd_transactions += 1
                        self._last_lcd_payload = bytes(payload)
                        self._last_lcd_write_at = now
                self.stop_event.wait(0.08)
        except FileNotFoundError:
            self._set_status("waiting-for-pap3", "WINCTRL 3N PAP MCP is not connected")
        except Exception as exc:
            self._set_status("preview-error", f"{type(exc).__name__}: {exc}")
        finally:
            if reader is not None:
                reader.join(timeout=1.0)
            if device is not None:
                try:
                    self._writer._blackout(device)
                except Exception:
                    pass
                try:
                    device.close()
                except Exception:
                    pass

    def _input_worker(self, device: Any, io_lock: threading.Lock) -> None:
        previous_bits: Optional[int] = None
        while not self.stop_event.is_set():
            try:
                with io_lock:
                    report = device.read(64)
            except Exception:
                return
            if not report:
                self.stop_event.wait(0.002)
                continue
            bits = pap3_decode_button_bits(bytes(report))
            if bits is None:
                continue
            if previous_bits is None:
                previous_bits = bits
                continue
            changed = bits ^ previous_bits
            for index in range(PAP3_BUTTON_COUNT):
                if not changed & (1 << index):
                    continue
                if self.input_sink is not None:
                    try:
                        self.input_sink(index, "press" if bits & (1 << index) else "release")
                    except Exception:
                        pass
            previous_bits = bits


__all__ = [
    "MuslimSimPAP3MCP",
    "MuslimSimPAP3Preview",
    "PAP3_VID",
    "PAP3_PID",
    "PAP3_BUTTONS",
    "PAP3_SPEED_BUTTONS",
    "PAP3_LED_DATAREFS",
    "PAP3_DEFAULT_REFRESH_SECONDS",
    "PAP3_DEFAULT_STARTUP_DELAY_SECONDS",
    "pap3_compose_lcd_payload",
    "pap3_decode_button_bits",
    "pap3_next_speed_value",
    "pap3_initialize_packet",
    "pap3_lcd_packets",
    "pap3_led_packet",
]
