#!/usr/bin/env python3
"""WINCTRL FCU-32 / EFIS-32L / EFIS-32R (VID 4098 / PID BA01).

The current BA01 firmware sends a 41-byte input report ``0x01``; some HID
stacks pad that same report to the 64-byte transfer maximum. Its first twelve
payload bytes are the confirmed 96-control bitmap: FCU at indexes 0..31,
captain EFIS at 32..63 and first-officer EFIS at 64..95. Only controls whose
semantic identity is confirmed by the direct FCU/EFIS decoder are named here.
The remaining input payload is retained for diagnostics but never interpreted
as buttons.
"""

from __future__ import annotations

from dataclasses import dataclass
import threading
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

try:
    import hid
except ImportError:  # pragma: no cover - optional runtime dependency
    hid = None


FCU_EFIS_VID = 0x4098
FCU_EFIS_PID = 0xBA01
FCU_EFIS_REPORT_ID = 0x01
FCU_EFIS_REPORT_LENGTH = 64
FCU_EFIS_CONTROL_REPORT_LENGTH = 13  # report id + twelve control bytes
FCU_EFIS_INPUT_BITS = (FCU_EFIS_REPORT_LENGTH - 1) * 8
FCU_EFIS_RECONNECT_SECONDS = 1.0
FCU_EFIS_FCU_IDENTIFIER = 0x10
FCU_EFIS_EFIS_LEFT_IDENTIFIER = 0x0D
FCU_EFIS_EFIS_RIGHT_IDENTIFIER = 0x0E

# These are the exact segments and report layouts used by the documented BA01
# FCU/EFIS implementation.  The panel has no input report for its current
# display content, so the Studio mirror intentionally represents the last
# confirmed value frame *sent* to the device, rather than claiming a readback.
_SEGMENT = {
    "0": 0xFA, "1": 0x60, "2": 0xD6, "3": 0xF4, "4": 0x6C,
    "5": 0xBC, "6": 0xBE, "7": 0xE0, "8": 0xFE, "9": 0xFC,
    "S": 0xBC, "T": 0x1E, "D": 0x76, "-": 0x04,
    "#": 0x36,  # BA01's small-zero V/S glyph
    " ": 0x00,
}
_FCU_EFIS_DEFAULT_DISPLAY: Dict[str, Any] = {
    "speed": 250.0, "speed_is_mach": False, "heading": 90.0,
    "altitude": 10000.0, "vertical_speed": 0.0, "flight_path_angle": 0.0,
    "left_baro": 29.92, "right_baro": 29.92,
    "left_baro_inhg": True, "right_baro_inhg": True,
    "left_baro_std": False, "right_baro_std": False,
    "speed_visible": True, "vertical_speed_visible": True,
    # Airbus managed windows stay electrically present and draw dashes. These
    # are deliberately separate from *_visible, whose false state means a
    # genuinely blank/unavailable window for legacy aircraft profiles.
    "speed_dashed": False, "heading_dashed": False,
    "vertical_speed_dashed": False,
    "airbus_fcu_presentation": False,
    # Aircraft profiles opt in.  False preserves the exact legacy/Zibo
    # packets; ToLiss requests fixed-width 001/00001-style windows.
    "zero_pad_fcu_values": False,
    "track_fpa_mode": False,
    "speed_managed": False, "heading_managed": False, "altitude_managed": False,
    # >>> MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 >>>
    # Default physical output is dark/off.  Live/Test authority explicitly
    # enables the display/backlight only for a permitted output.
    "display_enabled": False, "display_test": False, "backlight": 0,
    # <<< MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 <<<
    "button_leds": {},
}


def _number(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(fallback)


def _text(value: str, width: int) -> str:
    return str(value).upper()[-width:].rjust(width)


def _encoded_segments(width: int, text: str) -> list[int]:
    data = [0] * width
    for index, char in enumerate(_text(text, width)):
        data[width - 1 - index] = _SEGMENT.get(char, 0)
    return data


def _encoded_segments_swapped(width: int, text: str) -> list[int]:
    data = _encoded_segments(width, text) + [0]
    data = [((value & 0x0F) << 4) | ((value & 0xF0) >> 4) for value in data]
    for index in range(width):
        data[width - index] = (data[width - index] & 0x0F) | (data[width - 1 - index] & 0xF0)
        data[width - 1 - index] &= 0x0F
    return data


def _encoded_efis_segments(width: int, text: str) -> list[int]:
    result: list[int] = []
    for value in _encoded_segments(width, text):
        converted = 0
        converted |= 0x01 if value & 0x08 else 0
        converted |= 0x02 if value & 0x04 else 0
        converted |= 0x04 if value & 0x02 else 0
        converted |= 0x08 if value & 0x10 else 0
        converted |= 0x10 if value & 0x80 else 0
        converted |= 0x20 if value & 0x40 else 0
        converted |= 0x40 if value & 0x20 else 0
        converted |= 0x80 if value & 0x01 else 0
        result.append(converted)
    return result


def _packet(values: list[int], length: int = 64) -> bytes:
    return bytes(values[:length] + [0] * max(0, length - len(values)))


def fcu_efis_initialize_packet() -> bytes:
    """Return the BA01 display-engine initialization report."""

    return _packet([0xF0, 0x02])


def fcu_efis_backlight_packets(brightness: Any) -> Tuple[bytes, ...]:
    """Return only the six documented panel/screen backlight reports."""

    level = max(0, min(255, int(round(_number(brightness, 180)))))
    selectors = (
        (FCU_EFIS_FCU_IDENTIFIER, 0xBB, 0), (FCU_EFIS_FCU_IDENTIFIER, 0xBB, 1),
        (FCU_EFIS_EFIS_RIGHT_IDENTIFIER, 0xBF, 0), (FCU_EFIS_EFIS_RIGHT_IDENTIFIER, 0xBF, 1),
        (FCU_EFIS_EFIS_LEFT_IDENTIFIER, 0xBF, 0), (FCU_EFIS_EFIS_LEFT_IDENTIFIER, 0xBF, 1),
    )
    return tuple(
        bytes((0x02, identifier, family, 0, 0, 0x03, 0x49, selector, level, 0, 0, 0, 0, 0))
        for identifier, family, selector in selectors
    )


# Individual button integral lights - same 14-byte report family as the
# backlight above (0x02 <identifier> <family> 00 00 03 49 <selector>
# <level> 00 00 00 00 00), just with selectors 3-9 instead of the
# backlight's 0/1. Captured live from "EFIS L.R .pcapng": each selector's
# on/off write landed within ~50-150ms of its matching physical press, one
# button at a time. The ordered physical right-side presses in that trace are
# raw bits 66/67/68/69/70 at 61.624/61.934/62.204/62.494/63.074 seconds; the
# corresponding light-on reports are selectors 5/6/7/8/9 at
# 61.987/62.210/62.515/62.792/63.410 seconds. This pins the real sequence as
# CSTR=5, WPT=6, VOR.D=7, NDB=8, ARPT=9 on both symmetric EFIS components.
# A later FCU/EFIS lamp-and-knob capture
# exercised the FCU lamp test plus every alternating individual channel.
# With A/THR's already-confirmed selector 9 as the anchor, it confirms the
# six odd FCU selectors in physical left-to-right order: LOC=3, AP1=5,
# AP2=7, A/THR=9, EXPED=11, APPR=13.
_FCU_EFIS_BUTTON_LED_SELECTORS: Dict[str, Tuple[int, int, int]] = {
    "left_fd": (FCU_EFIS_EFIS_LEFT_IDENTIFIER, 0xBF, 3),
    "left_ls": (FCU_EFIS_EFIS_LEFT_IDENTIFIER, 0xBF, 4),
    "left_cstr": (FCU_EFIS_EFIS_LEFT_IDENTIFIER, 0xBF, 5),
    "left_wpt": (FCU_EFIS_EFIS_LEFT_IDENTIFIER, 0xBF, 6),
    "left_vord": (FCU_EFIS_EFIS_LEFT_IDENTIFIER, 0xBF, 7),
    "left_ndb": (FCU_EFIS_EFIS_LEFT_IDENTIFIER, 0xBF, 8),
    "left_arpt": (FCU_EFIS_EFIS_LEFT_IDENTIFIER, 0xBF, 9),
    "right_fd": (FCU_EFIS_EFIS_RIGHT_IDENTIFIER, 0xBF, 3),
    "right_ls": (FCU_EFIS_EFIS_RIGHT_IDENTIFIER, 0xBF, 4),
    "right_cstr": (FCU_EFIS_EFIS_RIGHT_IDENTIFIER, 0xBF, 5),
    "right_wpt": (FCU_EFIS_EFIS_RIGHT_IDENTIFIER, 0xBF, 6),
    "right_vord": (FCU_EFIS_EFIS_RIGHT_IDENTIFIER, 0xBF, 7),
    "right_ndb": (FCU_EFIS_EFIS_RIGHT_IDENTIFIER, 0xBF, 8),
    "right_arpt": (FCU_EFIS_EFIS_RIGHT_IDENTIFIER, 0xBF, 9),
    "loc": (FCU_EFIS_FCU_IDENTIFIER, 0xBB, 3),
    "ap1": (FCU_EFIS_FCU_IDENTIFIER, 0xBB, 5),
    "ap2": (FCU_EFIS_FCU_IDENTIFIER, 0xBB, 7),
    "athr": (FCU_EFIS_FCU_IDENTIFIER, 0xBB, 9),
    "exped": (FCU_EFIS_FCU_IDENTIFIER, 0xBB, 11),
    "appr": (FCU_EFIS_FCU_IDENTIFIER, 0xBB, 13),
}


def fcu_efis_button_led_packet(key: str, lit: Any) -> bytes:
    """Return the captured 14-byte report that sets one button's own light."""

    identifier, family, selector = _FCU_EFIS_BUTTON_LED_SELECTORS[key]
    level = 1 if lit else 0
    return bytes((0x02, identifier, family, 0, 0, 0x03, 0x49, selector, level, 0, 0, 0, 0, 0))


def _fcu_display_packet(values: Mapping[str, Any], sequence: int) -> bytes:
    enabled, test = bool(values.get("display_enabled", True)), bool(values.get("display_test", False))
    airbus_fcu_presentation = bool(values.get("airbus_fcu_presentation", False))
    zero_pad_fcu_values = bool(values.get("zero_pad_fcu_values", False))
    track_fpa_mode = airbus_fcu_presentation and bool(values.get("track_fpa_mode", False))
    speed_is_mach = bool(values.get("speed_is_mach", False))
    speed_dashed = airbus_fcu_presentation and bool(values.get("speed_dashed", False))
    heading_dashed = airbus_fcu_presentation and bool(values.get("heading_dashed", False))
    vertical_speed_dashed = airbus_fcu_presentation and bool(
        values.get("vertical_speed_dashed", False)
    )
    speed = _number(values.get("speed"), 250)
    if speed_is_mach:
        mach_hundredths = max(
            0, min(99, int(round((speed if speed < 2 else speed / 100) * 100)))
        )
        # The Airbus FCU's decimal point is a separate flag. Its three digit
        # cells must therefore receive 077, not ".77", to display 0.77.
        speed_text = f"{mach_hundredths:03d}" if airbus_fcu_presentation else f".{mach_hundredths:02d}"
    else:
        speed_value = max(0, min(999, int(round(speed))))
        speed_text = (
            f"{speed_value:03d}" if zero_pad_fcu_values
            else _text(str(speed_value), 3)
        )
    if speed_dashed:
        speed_text = "---"
    heading_value = int(round(_number(values.get("heading"), 90))) % 360
    heading = (
        f"{heading_value:03d}" if zero_pad_fcu_values
        else _text(str(heading_value), 3)
    )
    if heading_dashed:
        heading = "---"
    altitude_value = max(
        0, min(99999, int(round(_number(values.get("altitude"), 10000))))
    )
    altitude = (
        f"{altitude_value:05d}" if zero_pad_fcu_values
        else _text(str(altitude_value), 5)
    )
    vertical_speed = _number(values.get("vertical_speed"), 0)
    flight_path_angle = _number(values.get("flight_path_angle"), 0)
    vertical_target = flight_path_angle if track_fpa_mode else vertical_speed
    if track_fpa_mode:
        # FPA uses two full-size digits with the decimal annunciator between
        # them; the two unused V/S cells stay blank. 3.2 degrees -> "32  ".
        fpa_tenths = max(0, min(99, int(round(abs(flight_path_angle) * 10.0))))
        vs = f"{fpa_tenths:02d}  "
    elif airbus_fcu_presentation:
        # Airbus shows two hundreds digits followed by two physically smaller
        # zero glyphs: 4800 is encoded as "48##", with sign strokes separate.
        vs = f"{max(0, min(99, int(round(abs(vertical_speed) / 100.0)))):02d}##"
    else:
        vs = _text(str(max(0, min(9999, int(round(abs(vertical_speed)))))), 4)
    if vertical_speed_dashed:
        # The four digit cells plus the separate sign stroke form the five
        # dashes shown by the real Airbus V/S/FPA managed window.
        vs = "----"
    speed_data, heading_data = _encoded_segments(3, speed_text), _encoded_segments_swapped(3, heading)
    altitude_data, vs_data = _encoded_segments_swapped(5, altitude), _encoded_segments_swapped(4, vs)
    # Byte indexes are named in the BA01 display descriptor.  Keep this
    # explicit: these flags share bytes with the segment planes.
    H0, H3, A0, A1, A2, A3, A4, A5, V2, V3, V0, V1, S1 = range(13)
    flags = [0] * 17
    flags[H3] |= 0x04 if speed_is_mach else 0x08  # MACH/SPD header
    if bool(values.get("speed_managed", False)):
        flags[H3] |= 0x02
    if speed_is_mach and not speed_dashed:
        flags[S1] |= 0x01  # documented MACH decimal marker
    if airbus_fcu_presentation:
        flags[H0] |= 0x20  # LAT header
        flags[H0] |= 0x40 if track_fpa_mode else 0x80  # TRK / HDG header
    else:
        flags[H0] |= 0x80  # legacy HDG header
    if bool(values.get("heading_managed", False)):
        flags[H0] |= 0x10
    flags[A4] |= 0x10  # ALT header
    if airbus_fcu_presentation:
        # The two mode pairs appear together: HDG with V/S, or TRK with FPA.
        flags[A5] |= 0x03 if track_fpa_mode else 0x0C
        flags[V0] |= 0x80 if track_fpa_mode else 0x40
        if track_fpa_mode:
            flags[V3] |= 0x10  # decimal between the two FPA digits
        # Real FCU: ALT <- LVL/CH -> V/S/FPA, plus the horizontal stroke shared
        # by both signs. Positive values add the vertical stroke below.
        flags[A3] |= 0x10  # LVL/CH left arrow
        flags[A2] |= 0x10  # LVL/CH legend
        flags[A1] |= 0x10  # LVL/CH right arrow
        flags[A0] |= 0x10  # V/S plus/minus horizontal stroke
    else:
        flags[A5] |= 0x04  # legacy V/S header over the vertical-speed area
        flags[V0] |= 0x40  # legacy V/S header
    if bool(values.get("altitude_managed", False)):
        flags[V1] |= 0x10
    if vertical_target >= 0 and not vertical_speed_dashed:
        flags[V2] |= 0x10  # positive V/S or FPA indication
    if not bool(values.get("speed_visible", True)):
        speed_data = [0, 0, 0]
        flags[H3] = flags[S1] = 0
    if not bool(values.get("vertical_speed_visible", True)):
        vs_data = [0, 0, 0, 0, 0]
        for index in (A0, A1, A2, A3, A5, V0, V1, V2, V3):
            flags[index] = 0
    if not enabled or test:
        fill = 0xFF if test else 0
        speed_data, heading_data, altitude_data, vs_data, flags = (
            [fill] * 3, [fill] * 4, [fill] * 6, [fill] * 5, [fill] * 17,
        )
    data = [
        0xF0, 0x00, sequence, 0x31, FCU_EFIS_FCU_IDENTIFIER, 0xBB, 0, 0,
        0x02, 0x01, 0, 0, 0xFF, 0xFF, 0x02, 0, 0, 0x20, 0, 0, 0, 0, 0, 0, 0,
        speed_data[2], speed_data[1] | flags[S1], speed_data[0],
        heading_data[3] | flags[H3], heading_data[2], heading_data[1], heading_data[0] | flags[H0],
        altitude_data[5] | flags[A5], altitude_data[4] | flags[A4], altitude_data[3] | flags[A3],
        altitude_data[2] | flags[A2], altitude_data[1] | flags[A1], altitude_data[0] | vs_data[4] | flags[A0],
        vs_data[3] | flags[V3], vs_data[2] | flags[V2], vs_data[1] | flags[V1], vs_data[0] | flags[V0],
    ]
    return _packet(data)


def _efis_display_packet(values: Mapping[str, Any], sequence: int, side: str) -> bytes:
    prefix = "left" if side == "left" else "right"
    identifier = FCU_EFIS_EFIS_LEFT_IDENTIFIER if prefix == "left" else FCU_EFIS_EFIS_RIGHT_IDENTIFIER
    enabled, test = bool(values.get("display_enabled", True)), bool(values.get("display_test", False))
    std, inhg = bool(values.get(f"{prefix}_baro_std", False)), bool(values.get(f"{prefix}_baro_inhg", True))
    baro = _number(values.get(f"{prefix}_baro"), 29.92)
    number = int(round(baro * (100 if inhg else 33.8639)))
    baro_text = "STD " if std else _text(str(max(0, min(9999, number))), 4)
    encoded = _encoded_efis_segments(4, baro_text)
    if not enabled:
        window = [0] * 5
    elif test:
        window = [0x7F, 0xFF, 0x7F, 0x7F, 0xFF]
    else:
        window = [encoded[3], encoded[2] | (0x80 if inhg else 0), encoded[1], encoded[0], 0 if std else 0x02]
    return _packet([
        0xF0, 0x00, sequence, 0x1A, identifier, 0xBF, 0, 0, 0x02, 0x01,
        0, 0, 0xFF, 0xFF, 0x1D, 0, 0, 0x09, 0, 0, 0, 0, 0, 0, 0, *window,
    ])


def fcu_efis_display_packets(values: Mapping[str, Any], sequence: int = 1) -> Tuple[Tuple[bytes, ...], int]:
    """Build the FCU, captain EFIS and first-officer EFIS value frames.

    The return value includes the next non-zero BA01 sequence number.  It is
    side-effect free so the packet contract can be verified without hardware.
    """

    current = max(1, min(255, int(sequence)))
    packets: list[bytes] = []
    for payload, identifier, family in (
        (_fcu_display_packet(values, current), FCU_EFIS_FCU_IDENTIFIER, 0xBB),
        (_efis_display_packet(values, (current + 1) if current < 255 else 1, "left"), FCU_EFIS_EFIS_LEFT_IDENTIFIER, 0xBF),
        (_efis_display_packet(values, (current + 2) if current < 254 else (current + 2) % 255 or 1, "right"), FCU_EFIS_EFIS_RIGHT_IDENTIFIER, 0xBF),
    ):
        packets.append(payload)
        packets.append(_packet([0xF0, 0x00, payload[2], 0x11, identifier, family, 0, 0, 0x03, 0x01, 0, 0, 0xFF if identifier == FCU_EFIS_FCU_IDENTIFIER else 0x4C, 0xFF if identifier == FCU_EFIS_FCU_IDENTIFIER else 0x0C, 0x02 if identifier == FCU_EFIS_FCU_IDENTIFIER else 0x1D, 0]))
    next_sequence = (current + 3) % 256 or 1
    return tuple(packets), next_sequence


@dataclass(frozen=True)
class FcuControlDefinition:
    """One verified BA01 bitmap position used by the FCU/EFIS device."""

    bit: int
    key: str
    label: str
    kind: str = "button"


# The direct FCU/EFIS decoder and its Zibo profile agree on these bit values.
# Deliberately unused control bits 27..31, 62..63 and 94..95 stay unknown;
# report bytes after bit 95 are retained as device state and never decoded.
FCU_EFIS_CONTROL_DEFINITIONS: Tuple[FcuControlDefinition, ...] = (
    FcuControlDefinition(0, "mach", "SPD/MACH"),
    FcuControlDefinition(1, "loc", "LOC"),
    FcuControlDefinition(2, "trk", "TRK/FPA"),
    FcuControlDefinition(3, "ap1", "AP 1"),
    FcuControlDefinition(4, "ap2", "AP 2"),
    FcuControlDefinition(5, "athr", "A/THR"),
    FcuControlDefinition(6, "exped", "EXPED"),
    FcuControlDefinition(7, "metric", "METRIC"),
    FcuControlDefinition(8, "appr", "APPR"),
    FcuControlDefinition(9, "speed_dec", "Speed rotary counter-clockwise", "rotary"),
    FcuControlDefinition(10, "speed_inc", "Speed rotary clockwise", "rotary"),
    FcuControlDefinition(11, "speed_push", "Speed knob push"),
    FcuControlDefinition(12, "speed_pull", "Speed knob pull"),
    FcuControlDefinition(13, "heading_dec", "Heading rotary counter-clockwise", "rotary"),
    FcuControlDefinition(14, "heading_inc", "Heading rotary clockwise", "rotary"),
    FcuControlDefinition(15, "heading_push", "Heading knob push"),
    FcuControlDefinition(16, "heading_pull", "Heading knob pull"),
    FcuControlDefinition(17, "altitude_dec", "Altitude rotary counter-clockwise", "rotary"),
    FcuControlDefinition(18, "altitude_inc", "Altitude rotary clockwise", "rotary"),
    FcuControlDefinition(19, "altitude_push", "Altitude knob push"),
    FcuControlDefinition(20, "altitude_pull", "Altitude knob pull"),
    FcuControlDefinition(21, "vs_dec", "Vertical-speed rotary counter-clockwise", "rotary"),
    FcuControlDefinition(22, "vs_inc", "Vertical-speed rotary clockwise", "rotary"),
    FcuControlDefinition(23, "vs_push", "Vertical-speed knob push"),
    FcuControlDefinition(24, "vs_pull", "Vertical-speed knob pull"),
    FcuControlDefinition(25, "altitude_step_100", "Altitude step 100", "selector"),
    FcuControlDefinition(26, "altitude_step_1000", "Altitude step 1000", "selector"),
    FcuControlDefinition(32, "left_fd", "Captain EFIS FD"),
    FcuControlDefinition(33, "left_ls", "Captain EFIS LS"),
    FcuControlDefinition(34, "left_cstr", "Captain EFIS CSTR"),
    FcuControlDefinition(35, "left_wpt", "Captain EFIS WPT"),
    FcuControlDefinition(36, "left_vord", "Captain EFIS VOR.D"),
    FcuControlDefinition(37, "left_ndb", "Captain EFIS NDB"),
    FcuControlDefinition(38, "left_arpt", "Captain EFIS ARPT"),
    FcuControlDefinition(39, "left_std_push", "Captain BARO STD push"),
    FcuControlDefinition(40, "left_std_pull", "Captain BARO STD pull"),
    FcuControlDefinition(41, "left_baro_dec", "Captain BARO rotary counter-clockwise", "rotary"),
    FcuControlDefinition(42, "left_baro_inc", "Captain BARO rotary clockwise", "rotary"),
    FcuControlDefinition(43, "left_inhg", "Captain BARO inHg", "selector"),
    FcuControlDefinition(44, "left_hpa", "Captain BARO hPa", "selector"),
    FcuControlDefinition(45, "left_mode_ls", "Captain ND mode LS", "selector"),
    FcuControlDefinition(46, "left_mode_vor", "Captain ND mode VOR", "selector"),
    FcuControlDefinition(47, "left_mode_nav", "Captain ND mode NAV", "selector"),
    FcuControlDefinition(48, "left_mode_arc", "Captain ND mode ARC", "selector"),
    FcuControlDefinition(49, "left_mode_plan", "Captain ND mode PLAN", "selector"),
    FcuControlDefinition(50, "left_range_10", "Captain ND range 10", "selector"),
    FcuControlDefinition(51, "left_range_20", "Captain ND range 20", "selector"),
    FcuControlDefinition(52, "left_range_40", "Captain ND range 40", "selector"),
    FcuControlDefinition(53, "left_range_80", "Captain ND range 80", "selector"),
    FcuControlDefinition(54, "left_range_160", "Captain ND range 160", "selector"),
    FcuControlDefinition(55, "left_range_320", "Captain ND range 320", "selector"),
    FcuControlDefinition(56, "left_nav1_adf", "Captain NAV 1 ADF", "selector"),
    FcuControlDefinition(57, "left_nav1_off", "Captain NAV 1 OFF", "selector"),
    FcuControlDefinition(58, "left_nav1_vor", "Captain NAV 1 VOR", "selector"),
    FcuControlDefinition(59, "left_nav2_adf", "Captain NAV 2 ADF", "selector"),
    FcuControlDefinition(60, "left_nav2_off", "Captain NAV 2 OFF", "selector"),
    FcuControlDefinition(61, "left_nav2_vor", "Captain NAV 2 VOR", "selector"),
    FcuControlDefinition(64, "right_fd", "First-officer EFIS FD"),
    FcuControlDefinition(65, "right_ls", "First-officer EFIS LS"),
    FcuControlDefinition(66, "right_cstr", "First-officer EFIS CSTR"),
    FcuControlDefinition(67, "right_wpt", "First-officer EFIS WPT"),
    FcuControlDefinition(68, "right_vord", "First-officer EFIS VOR.D"),
    FcuControlDefinition(69, "right_ndb", "First-officer EFIS NDB"),
    FcuControlDefinition(70, "right_arpt", "First-officer EFIS ARPT"),
    FcuControlDefinition(71, "right_std_push", "First-officer BARO STD push"),
    FcuControlDefinition(72, "right_std_pull", "First-officer BARO STD pull"),
    FcuControlDefinition(73, "right_baro_dec", "First-officer BARO rotary counter-clockwise", "rotary"),
    FcuControlDefinition(74, "right_baro_inc", "First-officer BARO rotary clockwise", "rotary"),
    FcuControlDefinition(75, "right_inhg", "First-officer BARO inHg", "selector"),
    FcuControlDefinition(76, "right_hpa", "First-officer BARO hPa", "selector"),
    FcuControlDefinition(77, "right_mode_ls", "First-officer ND mode LS", "selector"),
    FcuControlDefinition(78, "right_mode_vor", "First-officer ND mode VOR", "selector"),
    FcuControlDefinition(79, "right_mode_nav", "First-officer ND mode NAV", "selector"),
    FcuControlDefinition(80, "right_mode_arc", "First-officer ND mode ARC", "selector"),
    FcuControlDefinition(81, "right_mode_plan", "First-officer ND mode PLAN", "selector"),
    FcuControlDefinition(82, "right_range_10", "First-officer ND range 10", "selector"),
    FcuControlDefinition(83, "right_range_20", "First-officer ND range 20", "selector"),
    FcuControlDefinition(84, "right_range_40", "First-officer ND range 40", "selector"),
    FcuControlDefinition(85, "right_range_80", "First-officer ND range 80", "selector"),
    FcuControlDefinition(86, "right_range_160", "First-officer ND range 160", "selector"),
    FcuControlDefinition(87, "right_range_320", "First-officer ND range 320", "selector"),
    FcuControlDefinition(88, "right_nav1_vor", "First-officer NAV 1 VOR", "selector"),
    FcuControlDefinition(89, "right_nav1_off", "First-officer NAV 1 OFF", "selector"),
    FcuControlDefinition(90, "right_nav1_adf", "First-officer NAV 1 ADF", "selector"),
    FcuControlDefinition(91, "right_nav2_vor", "First-officer NAV 2 VOR", "selector"),
    FcuControlDefinition(92, "right_nav2_off", "First-officer NAV 2 OFF", "selector"),
    FcuControlDefinition(93, "right_nav2_adf", "First-officer NAV 2 ADF", "selector"),
)
FCU_EFIS_CONTROL_BY_BIT: Dict[int, FcuControlDefinition] = {
    item.bit: item for item in FCU_EFIS_CONTROL_DEFINITIONS
}
FCU_EFIS_ZIBO_DEFAULT_ROLES: Dict[str, str] = {
    item.key: f"Zibo default: {item.label}" for item in FCU_EFIS_CONTROL_DEFINITIONS
}


def control_for_bit(bit: int) -> str:
    """Return a verified semantic key or an explicit unknown-bit key."""

    definition = FCU_EFIS_CONTROL_BY_BIT.get(int(bit))
    return definition.key if definition is not None else f"unknown_bit_{int(bit)}"


@dataclass(frozen=True)
class FcuRawInputEvent:
    control: str
    phase: str
    value: int
    bit: int


InputSink = Callable[[FcuRawInputEvent], None]


# Default roles are only used for Zibo/B738-compatible aircraft and only when
# a control has no saved user override in the active MuslimSim profile.
FCU_EFIS_ZIBO_COMMANDS: Dict[str, str] = {
    "mach": "sim/autopilot/knots_mach_toggle", "loc": "laminar/B738/autopilot/vorloc_press",
    "trk": "sim/autopilot/trkfpa", "ap1": "laminar/B738/autopilot/cmd_a_press",
    "ap2": "laminar/B738/autopilot/cmd_b_press", "athr": "laminar/B738/autopilot/autothrottle_arm_toggle",
    "exped": "laminar/B738/autopilot/vnav_press", "metric": "laminar/B738/autopilot/alt_hld_press",
    "appr": "laminar/B738/autopilot/app_press", "speed_dec": "sim/autopilot/airspeed_down",
    "speed_inc": "sim/autopilot/airspeed_up", "speed_push": "sim/autopilot/autothrottle_toggle",
    "speed_pull": "sim/autopilot/level_change", "heading_dec": "sim/autopilot/heading_down",
    "heading_inc": "sim/autopilot/heading_up", "heading_push": "laminar/B738/autopilot/lnav_press",
    "heading_pull": "laminar/B738/autopilot/hdg_sel_press", "altitude_push": "laminar/B738/autopilot/vnav_press",
    "altitude_pull": "laminar/B738/autopilot/lvl_chg_press", "vs_dec": "sim/autopilot/vertical_speed_down",
    "vs_inc": "sim/autopilot/vertical_speed_up", "vs_push": "sim/autopilot/vertical_speed_sync",
    "vs_pull": "laminar/B738/autopilot/vs_press", "left_fd": "laminar/B738/autopilot/flight_director_toggle",
    "left_ls": "sim/instruments/EFIS_mode_up", "left_cstr": "sim/instruments/EFIS_fix",
    "left_wpt": "sim/instruments/EFIS_fix", "left_vord": "sim/instruments/EFIS_vor",
    "left_ndb": "sim/instruments/EFIS_ndb", "left_arpt": "sim/instruments/EFIS_apt",
    "left_std_push": "laminar/B738/EFIS_control/capt/push_button/std_press",
    "left_std_pull": "laminar/B738/EFIS_control/capt/push_button/std_pull",
    "left_inhg": "laminar/B738/EFIS_control/capt/baro_in_hpa_dn",
    "left_hpa": "laminar/B738/EFIS_control/capt/baro_in_hpa_up",
    "right_fd": "laminar/B738/autopilot/flight_director_fo_toggle",
    "right_ls": "sim/instruments/EFIS_copilot_mode_up", "right_cstr": "sim/instruments/EFIS_copilot_fix",
    "right_wpt": "sim/instruments/EFIS_copilot_fix", "right_vord": "sim/instruments/EFIS_copilot_vor",
    "right_ndb": "sim/instruments/EFIS_copilot_ndb", "right_arpt": "sim/instruments/EFIS_copilot_apt",
    "right_std_push": "laminar/B738/EFIS_control/fo/push_button/std_press",
    "right_std_pull": "laminar/B738/EFIS_control/fo/push_button/std_pull",
    "right_inhg": "laminar/B738/EFIS_control/fo/baro_in_hpa_dn",
    "right_hpa": "laminar/B738/EFIS_control/fo/baro_in_hpa_up",
}
FCU_EFIS_ZIBO_DATAREFS: Dict[str, Tuple[str, float]] = {
    "left_mode_ls": ("laminar/B738/EFIS_control/capt/map_mode_pos", 0.0), "left_mode_vor": ("laminar/B738/EFIS_control/capt/map_mode_pos", 0.0),
    "left_mode_nav": ("laminar/B738/EFIS_control/capt/map_mode_pos", 1.0), "left_mode_arc": ("laminar/B738/EFIS_control/capt/map_mode_pos", 2.0),
    "left_mode_plan": ("laminar/B738/EFIS_control/capt/map_mode_pos", 3.0), "left_range_10": ("laminar/B738/EFIS/capt/map_range", 1.0),
    "left_range_20": ("laminar/B738/EFIS/capt/map_range", 2.0), "left_range_40": ("laminar/B738/EFIS/capt/map_range", 3.0),
    "left_range_80": ("laminar/B738/EFIS/capt/map_range", 4.0), "left_range_160": ("laminar/B738/EFIS/capt/map_range", 5.0),
    "left_range_320": ("laminar/B738/EFIS/capt/map_range", 6.0), "right_mode_ls": ("laminar/B738/EFIS_control/fo/map_mode_pos", 0.0),
    "right_mode_vor": ("laminar/B738/EFIS_control/fo/map_mode_pos", 0.0), "right_mode_nav": ("laminar/B738/EFIS_control/fo/map_mode_pos", 1.0),
    "right_mode_arc": ("laminar/B738/EFIS_control/fo/map_mode_pos", 2.0), "right_mode_plan": ("laminar/B738/EFIS_control/fo/map_mode_pos", 3.0),
    "right_range_10": ("laminar/B738/EFIS/fo/map_range", 1.0), "right_range_20": ("laminar/B738/EFIS/fo/map_range", 2.0),
    "right_range_40": ("laminar/B738/EFIS/fo/map_range", 3.0), "right_range_80": ("laminar/B738/EFIS/fo/map_range", 4.0),
    "right_range_160": ("laminar/B738/EFIS/fo/map_range", 5.0), "right_range_320": ("laminar/B738/EFIS/fo/map_range", 6.0),
}


class MuslimSimFCUEFISZiboDispatcher:
    """Apply the source-verified BA01 Zibo profile through bridge callbacks."""

    def __init__(self, *, api_version: str, resolve_dataref_id: Callable[[str, str], int],
                 read_dataref: Callable[[str, int], float], set_dataref: Callable[[str, int, float], None],
                 resolve_command_id: Callable[[str, str], int], activate_command: Callable[[str, int, float], None],
                 diagnose: bool = False) -> None:
        self.api_version = str(api_version)
        self._resolve_dataref_id, self._read_dataref, self._set_dataref = resolve_dataref_id, read_dataref, set_dataref
        self._resolve_command_id, self._activate_command = resolve_command_id, activate_command
        self.diagnose = bool(diagnose)
        self._dataref_ids: Dict[str, int] = {}
        self._command_ids: Dict[str, int] = {}
        self._altitude_step = 100
        self._lock = threading.Lock()

    @staticmethod
    def _is_stale_id(error: Exception) -> bool:
        return getattr(error, "code", None) == 404

    def _command_id(self, command: str, *, refresh: bool = False) -> int:
        if refresh or command not in self._command_ids:
            self._command_ids[command] = self._resolve_command_id(self.api_version, command)
        return self._command_ids[command]

    def _dataref_id(self, dataref: str, *, refresh: bool = False) -> int:
        if refresh or dataref not in self._dataref_ids:
            self._dataref_ids[dataref] = self._resolve_dataref_id(self.api_version, dataref)
        return self._dataref_ids[dataref]

    def _activate(self, command: str, count: int = 1) -> None:
        for _ in range(max(1, int(count))):
            try:
                self._activate_command(self.api_version, self._command_id(command), 0.0)
            except Exception as exc:
                if not self._is_stale_id(exc):
                    raise
                self._activate_command(self.api_version, self._command_id(command, refresh=True), 0.0)

    def _set(self, dataref: str, value: float) -> None:
        try:
            self._set_dataref(self.api_version, self._dataref_id(dataref), float(value))
        except Exception as exc:
            if not self._is_stale_id(exc):
                raise
            self._set_dataref(self.api_version, self._dataref_id(dataref, refresh=True), float(value))

    def _read(self, dataref: str) -> float:
        try:
            return float(self._read_dataref(self.api_version, self._dataref_id(dataref)))
        except Exception as exc:
            if not self._is_stale_id(exc):
                raise
            return float(self._read_dataref(self.api_version, self._dataref_id(dataref, refresh=True)))

    def _set_nav_source(self, key: str) -> bool:
        values = {"adf": -1, "off": 0, "vor": 1}
        parts = key.split("_")
        if len(parts) != 3 or parts[0] not in {"left", "right"} or parts[1] not in {"nav1", "nav2"} or parts[2] not in values:
            return False
        crew, nav_number, target = ("capt" if parts[0] == "left" else "fo"), parts[1][-1], values[parts[2]]
        prefix = f"laminar/B738/EFIS_control/{crew}/vor{nav_number}_off"
        current = int(round(self._read(f"{prefix}_pos")))
        if current < target:
            self._activate(f"{prefix}_up", target - current)
        elif current > target:
            self._activate(f"{prefix}_dn", current - target)
        return True

    def _change_baro(self, crew: str, increase: bool) -> None:
        value_ref = "laminar/B738/EFIS/baro_sel_in_hg_pilot" if crew == "capt" else "laminar/B738/EFIS/baro_sel_in_hg_copilot"
        unit_ref = "laminar/B738/EFIS_control/capt/baro_in_hpa" if crew == "capt" else "laminar/B738/EFIS_control/fo/baro_in_hpa"
        increment = 0.02953 if self._read(unit_ref) > 0.5 else 0.01
        self._set(value_ref, self._read(value_ref) + (increment if increase else -increment))

    def __call__(self, event: FcuRawInputEvent) -> None:
        if event.phase != "press":
            return
        key = event.control
        with self._lock:
            if key == "altitude_step_100": self._altitude_step = 100
            elif key == "altitude_step_1000": self._altitude_step = 1000
            elif key == "altitude_inc": self._activate("sim/autopilot/altitude_up", self._altitude_step // 100)
            elif key == "altitude_dec": self._activate("sim/autopilot/altitude_down", self._altitude_step // 100)
            elif key == "left_baro_inc": self._change_baro("capt", True)
            elif key == "left_baro_dec": self._change_baro("capt", False)
            elif key == "right_baro_inc": self._change_baro("fo", True)
            elif key == "right_baro_dec": self._change_baro("fo", False)
            elif self._set_nav_source(key): pass
            elif key in FCU_EFIS_ZIBO_DATAREFS:
                dataref, value = FCU_EFIS_ZIBO_DATAREFS[key]; self._set(dataref, value)
            elif key in FCU_EFIS_ZIBO_COMMANDS: self._activate(FCU_EFIS_ZIBO_COMMANDS[key])
            else: return
        if self.diagnose:
            print(f"FCU/EFIS BA01 {key} -> Zibo default")


class MuslimSimFCUEFIS:
    """Own the BA01 HID handle and its documented value-display protocol."""

    def __init__(self, *, input_sink: Optional[InputSink] = None, diagnose: bool = False) -> None:
        self.input_sink, self.diagnose = input_sink, bool(diagnose)
        self.stop_event, self._thread, self._state_lock = threading.Event(), None, threading.Lock()
        self._status, self._last_report = "stopped", None
        self._display_values: Dict[str, Any] = dict(_FCU_EFIS_DEFAULT_DISPLAY)
        self._display_sequence = 1
        self._last_display_signature: Optional[Tuple[Tuple[str, str], ...]] = None
        self._last_backlight: Optional[int] = None
        self._last_button_leds: Dict[str, int] = {}

    @property
    def status(self) -> str:
        with self._state_lock: return self._status

    @property
    def last_report(self) -> Optional[bytes]:
        with self._state_lock: return self._last_report

    def _set_status(self, status: str) -> None:
        with self._state_lock: self._status = str(status)

    def live_snapshot(self) -> Dict[str, Any]:
        """Return the exact logical values most recently queued to BA01."""

        with self._state_lock:
            return {
                "state": self._status,
                "values": dict(self._display_values),
                "display_mirror": "last-sent-output",
            }

    def set_display_values(self, values: Mapping[str, Any], *, source: str = "lab") -> None:
        """Queue only supported BA01 display fields without taking HID ownership."""

        if not isinstance(values, Mapping):
            raise ValueError("FCU/EFIS display values must be a mapping")
        allowed = set(_FCU_EFIS_DEFAULT_DISPLAY)
        with self._state_lock:
            for key, value in values.items():
                if key in allowed:
                    self._display_values[key] = value
            self._display_values["source"] = str(source)

    def set_lab_output(self, control: str, value: Any) -> None:
        """Expose the verified value windows through the existing lab channel."""

        if control == "fcu_windows":
            if isinstance(value, Mapping):
                self.set_display_values(value, source="lab")
            else:
                token = str(value).strip().upper()
                if token in {"888888", "CHECKER", "TEST"}:
                    self.set_display_values({"display_enabled": True, "display_test": True}, source="lab-test")
                elif not token:
                    self.set_display_values({"display_enabled": False, "display_test": False}, source="lab-test")
                else:
                    raise ValueError("FCU/EFIS windows accept numeric field values or the supported blank/all-segments test")
            return
        if control == "backlight":
            level = _number(value, 0)
            self.set_display_values({"backlight": 180 if 0 < level <= 1 else level}, source="lab")
            return
        if control == "button_leds":
            if not isinstance(value, Mapping):
                raise ValueError("FCU/EFIS button_leds accepts a mapping of key -> 0/1")
            unknown = set(value) - set(_FCU_EFIS_BUTTON_LED_SELECTORS)
            if unknown:
                raise ValueError(f"FCU/EFIS has no captured light for {sorted(unknown)}")
            self.set_display_values({"button_leds": dict(value)}, source="lab")
            return
        if control in {"captain_baro", "first_officer_baro"}:
            prefix = "left" if control == "captain_baro" else "right"
            if isinstance(value, Mapping):
                translated = {
                    f"{prefix}_baro": value.get("value", value.get("baro", 29.92)),
                    f"{prefix}_baro_inhg": value.get("inhg", True),
                    f"{prefix}_baro_std": value.get("std", False),
                }
            elif str(value).strip().upper() == "STD":
                translated = {f"{prefix}_baro_std": True}
            else:
                translated = {f"{prefix}_baro": value, f"{prefix}_baro_std": False}
            self.set_display_values(translated, source="lab")
            return
        raise ValueError(f"FCU/EFIS does not expose output {control}")

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive(): return
        self.stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="MuslimSim-FCU-EFIS", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        # >>> MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 >>>
        # Request the already-captured dark state before the owner thread exits.
        self.set_display_values(
            {"display_enabled": False, "display_test": False, "backlight": 0},
            source="shutdown-blackout",
        )
        # <<< MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 <<<
        self.stop_event.set()
        if self._thread is not None: self._thread.join(timeout=2.0)
        self._set_status("stopped")

    @staticmethod
    def _open() -> Any:
        if hid is None: raise RuntimeError("hidapi is not installed")
        devices = hid.enumerate(FCU_EFIS_VID, FCU_EFIS_PID)
        if not devices: raise FileNotFoundError("WINCTRL 32 FCU + 32 EFIS L + 32 EFIS R (4098:BA01) is not connected")
        path = devices[0].get("path")
        if not path: raise RuntimeError("FCU/EFIS HID path is unavailable")
        device = hid.device(); device.open_path(path)
        try: device.set_nonblocking(1)
        except Exception: pass
        return device

    @staticmethod
    def _report(raw: Any) -> Optional[bytes]:
        report = bytes(raw)
        return report[:FCU_EFIS_REPORT_LENGTH] if len(report) >= FCU_EFIS_CONTROL_REPORT_LENGTH and report[0] == FCU_EFIS_REPORT_ID else None

    def _emit_changes(self, previous: bytes, current: bytes) -> None:
        # Bytes after the twelve-byte control bitmap are device state, not
        # buttons. Comparing only the confirmed bitmap also makes captured
        # 41-byte reports and HID-padded 64-byte reports semantically equal.
        for byte_index, (before, after) in enumerate(zip(
            previous[1:FCU_EFIS_CONTROL_REPORT_LENGTH],
            current[1:FCU_EFIS_CONTROL_REPORT_LENGTH],
        )):
            changed = before ^ after
            for offset in range(8):
                mask = 1 << offset
                if not changed & mask: continue
                bit = byte_index * 8 + offset
                event = FcuRawInputEvent(control_for_bit(bit), "press" if after & mask else "release", 1 if after & mask else 0, bit)
                if self.diagnose: print(f"FCU/EFIS {event.control} (bit {bit}) {event.phase}")
                if self.input_sink is not None: self.input_sink(event)

    @staticmethod
    def _write(device: Any, packet: bytes) -> None:
        device.write(list(packet))

    def _flush_outputs(self, device: Any, *, force: bool = False) -> None:
        with self._state_lock:
            values = dict(self._display_values)
        signature = tuple(sorted((str(key), repr(value)) for key, value in values.items()))
        brightness = max(0, min(255, int(round(_number(values.get("backlight"), 0)))))
        if force or self._last_backlight != brightness:
            for packet in fcu_efis_backlight_packets(brightness):
                self._write(device, packet)
            self._last_backlight = brightness
        button_leds = values.get("button_leds")
        if isinstance(button_leds, Mapping):
            for key, lit in button_leds.items():
                if key not in _FCU_EFIS_BUTTON_LED_SELECTORS:
                    continue
                lit = 1 if lit else 0
                if force or self._last_button_leds.get(key) != lit:
                    self._write(device, fcu_efis_button_led_packet(key, lit))
                    self._last_button_leds[key] = lit
        if not force and signature == self._last_display_signature:
            return
        packets, self._display_sequence = fcu_efis_display_packets(values, self._display_sequence)
        for packet in packets:
            self._write(device, packet)
        self._last_display_signature = signature

    def _write_blackout(self, device: Any) -> None:
        values = dict(_FCU_EFIS_DEFAULT_DISPLAY)
        values.update({
            "display_enabled": False,
            "display_test": False,
            "backlight": 0,
            "source": "shutdown-blackout",
        })
        for packet in fcu_efis_backlight_packets(0):
            self._write(device, packet)
        for key in _FCU_EFIS_BUTTON_LED_SELECTORS:
            self._write(device, fcu_efis_button_led_packet(key, 0))
        packets, self._display_sequence = fcu_efis_display_packets(
            values, self._display_sequence
        )
        for packet in packets:
            self._write(device, packet)
        self._last_backlight = 0
        self._last_button_leds = {}
        self._last_display_signature = tuple(
            sorted((str(key), repr(value)) for key, value in values.items())
        )

    def _run(self) -> None:
        if hid is None:
            self._set_status("dependency-missing"); return
        while not self.stop_event.is_set():
            device = None
            try:
                device = self._open()
                self._last_display_signature, self._last_backlight = None, None
                self._last_button_leds = {}
                self._write(device, fcu_efis_initialize_packet())
                self._flush_outputs(device, force=True)
                self._set_status("connected"); previous: Optional[bytes] = None
                while not self.stop_event.is_set():
                    self._flush_outputs(device)
                    report = self._report(device.read(FCU_EFIS_REPORT_LENGTH))
                    if report is None:
                        self.stop_event.wait(0.002); continue
                    with self._state_lock: self._last_report = report
                    if previous is not None: self._emit_changes(previous, report)
                    previous = report
            except FileNotFoundError: self._set_status("waiting-for-fcu-efis")
            except Exception as exc: self._set_status(f"reconnecting: {exc}")
            finally:
                if device is not None:
                    try: self._write_blackout(device)
                    except Exception: pass
                    try: device.close()
                    except Exception: pass
            self.stop_event.wait(FCU_EFIS_RECONNECT_SECONDS)
        self._set_status("stopped")


__all__ = (
    "FCU_EFIS_CONTROL_BY_BIT", "FCU_EFIS_CONTROL_DEFINITIONS", "FCU_EFIS_CONTROL_REPORT_LENGTH",
    "FCU_EFIS_INPUT_BITS", "FCU_EFIS_PID",
    "FCU_EFIS_REPORT_ID", "FCU_EFIS_REPORT_LENGTH", "FCU_EFIS_VID", "FCU_EFIS_ZIBO_DEFAULT_ROLES",
    "FcuControlDefinition", "FcuRawInputEvent", "MuslimSimFCUEFIS", "MuslimSimFCUEFISZiboDispatcher", "control_for_bit",
    "fcu_efis_backlight_packets", "fcu_efis_display_packets", "fcu_efis_initialize_packet",
)
