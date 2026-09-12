#!/usr/bin/env python3
"""
MuslimSim - WINCTRL 32 MCDU CAPTAIN BB36 WebSocket FMC v4

Purpose
-------
1) Open ONLY WINCTRL 32 MCDU CAPTAIN, VID 4098 / PID BB36.
2) Upload the original WinCtrl MCDU .xpwwf font/config UNMODIFIED.
3) Render the Zibo captain FMC (fmc1) to the native 24x14 BB36 display.
4) Stream Zibo FMC changes through X-Plane WebSocket at its native 10-Hz
   push cadence and send real command press/release phases over WebSocket.

It does NOT open BB35 PFP and does NOT touch PU OVHD / throttle / AGP / pedals.

Requirements:
    py -m pip install hidapi

Example:
    py .\winctrl_mcdu_bb36_zibo_live.py ^
      --font ".\winctrl-pfp-b737-cockpit-compact17-font6.xpwwf"
"""

from __future__ import annotations

import argparse
import queue
import threading
import base64
import binascii
import json
import math
from pathlib import Path
import time
import urllib.parse
import urllib.request

try:
    import hid
except ImportError:
    hid = None

try:
    import websocket
except ImportError:
    websocket = None


VID = 0x4098
PID = 0xBB36

MCDU_IDENTIFIER = 0x32
MCDU_FAMILY = 0xBB

COLUMNS = 24
ROWS = 14
PACKET_SIZE = 64
F2_REPORT_ID = 0xF2
F2_PAYLOAD_SIZE = 63

GRID_X = 0x34
GRID_Y = 0x25

API_ROOT = "http://127.0.0.1:8086"

COLOR_BLACK = 0x0000
COLOR_AMBER = 0x0021
COLOR_WHITE = 0x0042
COLOR_CYAN = 0x0063
COLOR_GREEN = 0x0084
COLOR_MAGENTA = 0x00A5
COLOR_RED = 0x00C6
COLOR_YELLOW = 0x00E7
COLOR_GREY = 0x0129


# ---------------------------------------------------------------------------
# BB36 MCDU keypad
# ---------------------------------------------------------------------------
# HID report format used by the WinCtrl plugin:
#   report[0] = report ID 1
#   report[1:9]  = hardware button indexes 0..63, little-endian bit order
#   report[9:13] = hardware button indexes 64..95
#
# The mapping below is the exact HARDWARE_MCDU index map from the WinCtrl
# X-Plane plugin, translated to the Zibo CAPTAIN FMC1 profile.
#
# None means that Airbus-labelled MCDU key has no assignment in the plugin's
# Zibo profile.  We deliberately leave those keys unassigned instead of
# inventing a Boeing function.
BB36_KEY_MAP = {
    0:  ("LSK1L", "laminar/B738/button/fmc1_1L"),
    1:  ("LSK2L", "laminar/B738/button/fmc1_2L"),
    2:  ("LSK3L", "laminar/B738/button/fmc1_3L"),
    3:  ("LSK4L", "laminar/B738/button/fmc1_4L"),
    4:  ("LSK5L", "laminar/B738/button/fmc1_5L"),
    5:  ("LSK6L", "laminar/B738/button/fmc1_6L"),
    6:  ("LSK1R", "laminar/B738/button/fmc1_1R"),
    7:  ("LSK2R", "laminar/B738/button/fmc1_2R"),
    8:  ("LSK3R", "laminar/B738/button/fmc1_3R"),
    9:  ("LSK4R", "laminar/B738/button/fmc1_4R"),
    10: ("LSK5R", "laminar/B738/button/fmc1_5R"),
    11: ("LSK6R", "laminar/B738/button/fmc1_6R"),

    # Airbus-labelled function keys translated exactly as the public
    # WinCtrl Zibo profile does.
    12: ("DIR -> LEGS", "laminar/B738/button/fmc1_legs"),
    13: ("PROG", "laminar/B738/button/fmc1_prog"),
    14: ("PERF -> N1 LIMIT", "laminar/B738/button/fmc1_n1_lim"),
    15: ("INIT -> INIT REF", "laminar/B738/button/fmc1_init_ref"),
    16: ("DATA", None),
    17: ("EMPTY TOP RIGHT -> EXEC", "laminar/B738/button/fmc1_exec"),
    18: ("BRIGHTNESS UP", "__brightness_up__"),
    19: ("F-PLN -> LEGS", "laminar/B738/button/fmc1_legs"),
    20: ("RAD NAV", None),
    21: ("FUEL PRED", None),
    22: ("SEC F-PLN -> RTE", "laminar/B738/button/fmc1_rte"),
    23: ("ATC COMM", None),
    24: ("MENU", "laminar/B738/button/fmc1_menu"),
    25: ("BRIGHTNESS DOWN", "__brightness_down__"),
    26: ("AIRPORT -> DEP/ARR", "laminar/B738/button/fmc1_dep_app"),
    27: ("EMPTY BOTTOM LEFT -> FIX", "laminar/B738/button/fmc1_fix"),
    28: ("PREV PAGE", "laminar/B738/button/fmc1_prev_page"),
    29: ("PAGE UP", None),
    30: ("NEXT PAGE", "laminar/B738/button/fmc1_next_page"),
    31: ("PAGE DOWN", None),

    32: ("1", "laminar/B738/button/fmc1_1"),
    33: ("2", "laminar/B738/button/fmc1_2"),
    34: ("3", "laminar/B738/button/fmc1_3"),
    35: ("4", "laminar/B738/button/fmc1_4"),
    36: ("5", "laminar/B738/button/fmc1_5"),
    37: ("6", "laminar/B738/button/fmc1_6"),
    38: ("7", "laminar/B738/button/fmc1_7"),
    39: ("8", "laminar/B738/button/fmc1_8"),
    40: ("9", "laminar/B738/button/fmc1_9"),
    41: (".", "laminar/B738/button/fmc1_period"),
    42: ("0", "laminar/B738/button/fmc1_0"),
    43: ("+/-", "laminar/B738/button/fmc1_minus"),

    44: ("A", "laminar/B738/button/fmc1_A"),
    45: ("B", "laminar/B738/button/fmc1_B"),
    46: ("C", "laminar/B738/button/fmc1_C"),
    47: ("D", "laminar/B738/button/fmc1_D"),
    48: ("E", "laminar/B738/button/fmc1_E"),
    49: ("F", "laminar/B738/button/fmc1_F"),
    50: ("G", "laminar/B738/button/fmc1_G"),
    51: ("H", "laminar/B738/button/fmc1_H"),
    52: ("I", "laminar/B738/button/fmc1_I"),
    53: ("J", "laminar/B738/button/fmc1_J"),
    54: ("K", "laminar/B738/button/fmc1_K"),
    55: ("L", "laminar/B738/button/fmc1_L"),
    56: ("M", "laminar/B738/button/fmc1_M"),
    57: ("N", "laminar/B738/button/fmc1_N"),
    58: ("O", "laminar/B738/button/fmc1_O"),
    59: ("P", "laminar/B738/button/fmc1_P"),
    60: ("Q", "laminar/B738/button/fmc1_Q"),
    61: ("R", "laminar/B738/button/fmc1_R"),
    62: ("S", "laminar/B738/button/fmc1_S"),
    63: ("T", "laminar/B738/button/fmc1_T"),
    64: ("U", "laminar/B738/button/fmc1_U"),
    65: ("V", "laminar/B738/button/fmc1_V"),
    66: ("W", "laminar/B738/button/fmc1_W"),
    67: ("X", "laminar/B738/button/fmc1_X"),
    68: ("Y", "laminar/B738/button/fmc1_Y"),
    69: ("Z", "laminar/B738/button/fmc1_Z"),

    70: ("/", "laminar/B738/button/fmc1_slash"),
    71: ("SPACE", "laminar/B738/button/fmc1_SP"),
    72: ("OVERFLY -> DEL", "laminar/B738/button/fmc1_del"),
    73: ("CLR", "laminar/B738/button/fmc1_clr"),
}

MCDU_BRIGHTNESS_DATAREF = "laminar/B738/electric/instrument_brightness"
MCDU_BRIGHTNESS_INDEX = 10
MCDU_KEY_PRESS_SECONDS = 0.08

MCDU_WS_RECV_TIMEOUT = 0.01
MCDU_WS_RECONNECT_SECONDS = 0.50
MCDU_DISPLAY_MIN_INTERVAL = 0.045



# Zibo captain FMC display.  The 6 FMC rows naturally expand to a 14-row CDU:
#   row 0        page title
#   rows 1..12   small label / large content alternating
#   row 13       scratchpad
#
# The custom FMC pages are 24 characters per line.
FMC_TEXT_DATAREFS = {
    "line00_l": "laminar/B738/fmc1/Line00_L",
    "line00_s": "laminar/B738/fmc1/Line00_S",
    "entry": "laminar/B738/fmc1/Line_entry",
    "entry_i": "laminar/B738/fmc1/Line_entry_I",
}

for _line in range(1, 7):
    FMC_TEXT_DATAREFS[f"line{_line:02d}_x"] = (
        f"laminar/B738/fmc1/Line{_line:02d}_X"
    )
    for _layer in ("L", "S", "I", "M"):
        FMC_TEXT_DATAREFS[f"line{_line:02d}_{_layer.lower()}"] = (
            f"laminar/B738/fmc1/Line{_line:02d}_{_layer}"
        )


def http_json(url: str, timeout: float = 1.0):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "MuslimSim-BB36-MCDU/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def detect_api_version():
    caps = http_json(f"{API_ROOT}/api/capabilities")
    versions = caps.get("api", {}).get("versions", [])

    for preferred in ("v3", "v2", "v1"):
        if preferred in versions:
            return preferred

    raise RuntimeError(
        f"No supported X-Plane Web API version: {versions!r}"
    )


def resolve_command_id(api_version: str, name: str) -> int:
    query = urllib.parse.urlencode(
        {"filter[name]": name, "limit": 100}
    )
    payload = http_json(
        f"{API_ROOT}/api/{api_version}/commands?{query}"
    )

    items = payload.get("data", [])
    if isinstance(items, dict):
        items = [items]

    for item in items:
        if isinstance(item, dict) and item.get("name") == name:
            return int(item["id"])

    raise RuntimeError(f"Command not found: {name}")


def activate_command(
    api_version: str,
    command_id: int,
    duration: float = MCDU_KEY_PRESS_SECONDS,
):
    body = json.dumps(
        {"duration": float(duration)}
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{API_ROOT}/api/{api_version}/command/"
        f"{int(command_id)}/activate",
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "MuslimSim-BB36-MCDU/2.0",
        },
    )

    with urllib.request.urlopen(req, timeout=1.0) as response:
        if response.status != 200:
            raise RuntimeError(
                f"Command activation HTTP {response.status}"
            )


def read_dataref_index(
    api_version: str,
    dataref_id: int,
    index: int,
) -> float:
    payload = http_json(
        f"{API_ROOT}/api/{api_version}/datarefs/"
        f"{int(dataref_id)}/value",
        timeout=0.8,
    )

    data = payload.get("data") if isinstance(payload, dict) else payload

    if isinstance(data, list):
        return float(data[int(index)])

    if isinstance(data, dict):
        for key in ("value", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return float(value[int(index)])

    raise ValueError(
        f"Unsupported array DataRef payload: {payload!r}"
    )


def set_dataref_index(
    api_version: str,
    dataref_id: int,
    index: int,
    value: float,
):
    body = json.dumps(
        {"data": float(value)}
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{API_ROOT}/api/{api_version}/datarefs/"
        f"{int(dataref_id)}/value?index={int(index)}",
        data=body,
        method="PATCH",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "MuslimSim-BB36-MCDU/2.0",
        },
    )

    with urllib.request.urlopen(req, timeout=1.0) as response:
        if response.status != 200:
            raise RuntimeError(
                f"Indexed PATCH HTTP {response.status}"
            )


def resolve_dataref_id(api_version: str, name: str) -> int:
    query = urllib.parse.urlencode(
        {"filter[name]": name, "limit": 100}
    )
    payload = http_json(
        f"{API_ROOT}/api/{api_version}/datarefs?{query}"
    )

    items = payload.get("data", [])

    if isinstance(items, dict):
        items = [items]

    for item in items:
        if isinstance(item, dict) and item.get("name") == name:
            return int(item["id"])

    raise RuntimeError(f"DataRef not found: {name}")


def _decode_possible_base64_text(text: str) -> str:
    """
    Some X-Plane Web API string values can arrive as base64 encoded bytes.
    Accept a decode only when it results in mostly printable text.
    """
    stripped = text.rstrip("\x00")

    if not stripped:
        return ""

    try:
        raw = base64.b64decode(
            stripped.encode("ascii"),
            validate=True,
        )
        decoded = raw.split(b"\x00", 1)[0].decode(
            "utf-8",
            errors="strict",
        )
    except (
        UnicodeEncodeError,
        UnicodeDecodeError,
        ValueError,
        binascii.Error,
    ):
        return stripped

    if not decoded:
        return ""

    printable = sum(
        1 for char in decoded
        if char.isprintable() or char == " "
    )

    if printable / max(1, len(decoded)) >= 0.90:
        return decoded

    return stripped


def unwrap_text_value(payload) -> str:
    data = payload.get("data") if isinstance(payload, dict) else payload

    def decode(value):
        if isinstance(value, str):
            return _decode_possible_base64_text(value)

        if isinstance(value, bytes):
            return value.split(b"\x00", 1)[0].decode(
                "utf-8",
                errors="replace",
            )

        if isinstance(value, bytearray):
            return bytes(value).split(b"\x00", 1)[0].decode(
                "utf-8",
                errors="replace",
            )

        if isinstance(value, list):
            if value and all(isinstance(item, int) for item in value):
                raw = bytes(
                    max(0, min(255, int(item)))
                    for item in value
                )
                return raw.split(b"\x00", 1)[0].decode(
                    "utf-8",
                    errors="replace",
                )

            if len(value) == 1:
                return decode(value[0])

        if isinstance(value, dict):
            for key in ("value", "data"):
                if key in value:
                    result = decode(value[key])
                    if result is not None:
                        return result

        return None

    text = decode(data)

    if text is None:
        raise ValueError(
            f"Unsupported X-Plane text payload: {payload!r}"
        )

    return text


def read_text_dataref(
    api_version: str,
    dataref_id: int,
    timeout: float = 0.5,
) -> str:
    payload = http_json(
        f"{API_ROOT}/api/{api_version}/datarefs/"
        f"{dataref_id}/value",
        timeout=timeout,
    )

    return unwrap_text_value(payload)


def normalize_24(value: str) -> str:
    """
    Keep display text strictly inside one native MCDU row.
    """
    value = str(value or "")
    value = value.replace("\r", " ").replace("\n", " ")

    # The WinCtrl test glyph set is primarily ASCII. Keep useful printable
    # characters and substitute unsupported symbols conservatively.
    cleaned = []

    for char in value:
        code = ord(char)

        if 0x20 <= code <= 0x7E:
            cleaned.append(char)
        elif char == "\u00b0":
            cleaned.append("o")
        else:
            cleaned.append(" ")

    return "".join(cleaned)[:COLUMNS].ljust(COLUMNS)


def overlay_text(
    base: str,
    overlay: str,
):
    base = list(normalize_24(base))
    overlay = normalize_24(overlay)

    for index, char in enumerate(overlay):
        if char != " ":
            base[index] = char

    return "".join(base)


def overlay_coloured(
    base_text: str,
    base_colors,
    overlay: str,
    color: int,
):
    chars = list(normalize_24(base_text))
    colors = list(base_colors)
    overlay = normalize_24(overlay)

    for index, char in enumerate(overlay):
        if char != " ":
            chars[index] = char
            colors[index] = color

    return "".join(chars), tuple(colors)


def compose_zibo_page(values):
    lines = [" " * COLUMNS for _ in range(ROWS)]
    colors = [
        tuple([COLOR_WHITE] * COLUMNS)
        for _ in range(ROWS)
    ]

    # Page title.  Large/small title layers are overlaid.
    title = overlay_text(
        values.get("line00_l", ""),
        values.get("line00_s", ""),
    )
    lines[0] = title
    colors[0] = tuple([COLOR_WHITE] * COLUMNS)

    for number in range(1, 7):
        label_row = 1 + (number - 1) * 2
        content_row = label_row + 1

        # Small label row.
        lines[label_row] = normalize_24(
            values.get(f"line{number:02d}_x", "")
        )
        colors[label_row] = tuple(
            [COLOR_CYAN] * COLUMNS
        )

        # Content row starts with the large-font layer.
        text = normalize_24(
            values.get(f"line{number:02d}_l", "")
        )
        row_colors = tuple(
            [COLOR_WHITE] * COLUMNS
        )

        # The Zibo S layer is usually additional small-font text.  The BB36
        # smoke renderer currently preserves the text/color even though the
        # first pass uses one uploaded glyph set for the entire row.
        text, row_colors = overlay_coloured(
            text,
            row_colors,
            values.get(f"line{number:02d}_s", ""),
            COLOR_CYAN,
        )

        # Inverse layer is kept visible in amber in this first native pass.
        text, row_colors = overlay_coloured(
            text,
            row_colors,
            values.get(f"line{number:02d}_i", ""),
            COLOR_AMBER,
        )

        # Magenta FMC entries are exposed through LineXX_M in current Zibo.
        text, row_colors = overlay_coloured(
            text,
            row_colors,
            values.get(f"line{number:02d}_m", ""),
            COLOR_MAGENTA,
        )

        lines[content_row] = text
        colors[content_row] = row_colors

    # Scratchpad / entry.
    scratch = normalize_24(
        values.get("entry", "")
    )
    scratch_colors = tuple(
        [COLOR_WHITE] * COLUMNS
    )

    scratch, scratch_colors = overlay_coloured(
        scratch,
        scratch_colors,
        values.get("entry_i", ""),
        COLOR_AMBER,
    )

    lines[13] = scratch
    colors[13] = scratch_colors

    return tuple(lines), tuple(colors)


def read_font_packets(font_path: Path):
    raw = font_path.read_bytes()
    packets = []
    offset = 0

    while offset < len(raw):
        length = raw[offset]
        offset += 1

        if length == 0:
            break

        end = offset + length

        if end > len(raw):
            raise ValueError(
                "Font resource ends inside a packet."
            )

        packet = bytes(raw[offset:end])
        offset = end

        packet += b"\x00" * (PACKET_SIZE - len(packet))
        packets.append(packet[:PACKET_SIZE])

    if not packets or offset != len(raw):
        raise ValueError(
            "Font resource is malformed or has trailing data."
        )

    return tuple(packets)


def validate_font(packets):
    combined = b"".join(packets)

    signature = bytes((
        0x08, 0x00, 0x00, 0x00,
        GRID_X, 0x00,
        GRID_Y, 0x00,
        ROWS, 0x00,
        COLUMNS, 0x00,
    ))

    if b"\x32\xBB" not in combined:
        raise ValueError(
            "Font is not an original MCDU 32/BB resource."
        )

    if signature not in combined:
        raise ValueError(
            "Native 24x14 MCDU grid was not found."
        )


def black_background_packet():
    packet = bytearray(PACKET_SIZE)

    packet[:16] = bytes((
        0xF0, 0x00, 0x03, 0x12,
        MCDU_IDENTIFIER, MCDU_FAMILY,
        0x00, 0x00,
        0x04, 0x01, 0x00, 0x00,
        0xFD, 0x24,
        0x07, 0x00,
    ))

    packet[16:22] = bytes((
        0x00, 0x01, 0x00, 0x00, 0x00, 0x0E
    ))

    return bytes(packet)


def text_grid_packet():
    packet = bytearray(PACKET_SIZE)
    packet[:4] = bytes((0xF0, 0x00, 0x00, 0x2A))

    p = 4
    packet[p:p + 25] = bytes((
        MCDU_IDENTIFIER, MCDU_FAMILY, 0x00, 0x00,
        0x18, 0x01, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
        0x00,
        0x08, 0x00, 0x00, 0x00,
        GRID_X, 0x00,
        GRID_Y, 0x00,
        ROWS, 0x00,
        COLUMNS, 0x00,
    ))

    c = 29
    packet[c:c + 17] = bytes((
        MCDU_IDENTIFIER, MCDU_FAMILY, 0x00, 0x00,
        0x05, 0x01, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
        0x01, 0x00, 0x00, 0x00, 0x00,
    ))

    return bytes(packet)


def set_brightness(device, channel: int, brightness: int):
    device.write([
        0x02,
        MCDU_IDENTIFIER,
        MCDU_FAMILY,
        0x00, 0x00,
        0x03, 0x49,
        int(channel) & 0xFF,
        max(0, min(255, int(brightness))),
        0x00, 0x00, 0x00, 0x00, 0x00,
    ])


def page_packets(lines, colors):
    payload = bytearray()

    for row_index, line in enumerate(lines):
        text = normalize_24(line)
        row_colors = colors[row_index]

        for index, char in enumerate(text):
            color = int(row_colors[index])
            payload.extend((
                color & 0xFF,
                (color >> 8) & 0xFF,
                ord(char),
            ))

    packets = []

    while payload:
        chunk = payload[:F2_PAYLOAD_SIZE]
        del payload[:F2_PAYLOAD_SIZE]

        packet = bytearray((F2_REPORT_ID,))
        packet.extend(chunk)
        packet.extend(
            b"\x00" * (PACKET_SIZE - len(packet))
        )

        packets.append(bytes(packet))

    return tuple(packets)


def open_bb36():
    devices = hid.enumerate(VID, PID)

    if not devices:
        raise RuntimeError(
            "WINCTRL 32 MCDU CAPTAIN BB36 not found."
        )

    # User's machine currently reports one interface:
    # interface 0, Generic Desktop / Joystick.
    info = devices[0]
    path = info.get("path")

    if not path:
        raise RuntimeError(
            "BB36 did not provide a HID path."
        )

    print(
        "BB36 interface: "
        f"interface={info.get('interface_number')!r}, "
        f"usage_page={info.get('usage_page')!r}, "
        f"usage={info.get('usage')!r}"
    )

    device = hid.device()
    device.open_path(path)

    try:
        device.set_nonblocking(1)
    except Exception:
        pass

    return device


def initialize_display(device, font_packets, brightness):
    print(
        f"Uploading {len(font_packets)} original MCDU font/config packets..."
    )

    for packet in font_packets:
        device.write(list(packet))

    time.sleep(0.20)

    device.write(list(black_background_packet()))
    device.write(list(text_grid_packet()))

    set_brightness(device, 0, 128)
    set_brightness(device, 1, brightness)


def resolve_bb36_commands(api_version):
    command_ids = {}
    names = sorted({
        command
        for _index, (_label, command) in BB36_KEY_MAP.items()
        if command is not None and not command.startswith("__")
    })

    print("Resolving BB36 -> Zibo FMC1 key commands...")

    for name in names:
        try:
            command_ids[name] = resolve_command_id(
                api_version,
                name,
            )
        except Exception as exc:
            print(
                f"OPTIONAL BB36 key command unavailable "
                f"{name}: {exc}"
            )

    print(
        f"BB36 key commands resolved: "
        f"{len(command_ids)}/{len(names)}"
    )
    return command_ids


def resolve_fmc_ids(api_version):
    ids = {}

    for key, name in FMC_TEXT_DATAREFS.items():
        try:
            ids[key] = resolve_dataref_id(
                api_version,
                name,
            )
            print(f"FMC {key:12s} -> {name}")
        except Exception as exc:
            # Some Zibo builds do not expose every optional display layer.
            print(
                f"OPTIONAL FMC layer unavailable {name}: {exc}"
            )

    required = {
        "line00_l",
        "entry",
    }

    if not required.issubset(ids):
        raise RuntimeError(
            "Required Zibo captain FMC text DataRefs were not resolved."
        )

    return ids


def read_fmc_values(api_version, ids):
    result = {}

    for key, ref_id in ids.items():
        try:
            result[key] = read_text_dataref(
                api_version,
                ref_id,
            )
        except Exception:
            result[key] = ""

    return result


def _bb36_button_bits(report: bytes):
    """
    Decode the exact WinCtrl FMC report structure used by the public plugin:
      bytes 1..8  -> indexes 0..63
      bytes 9..12 -> indexes 64..95
    """
    if not report or len(report) < 13 or report[0] != 0x01:
        return None

    low = int.from_bytes(
        report[1:9],
        "little",
    )
    high = int.from_bytes(
        report[9:13],
        "little",
    )

    return low | (high << 64)


def _adjust_mcdu_brightness(
    device,
    api_version,
    brightness_ref_id,
    delta,
):
    if brightness_ref_id is None:
        print("BB36 brightness: Zibo DataRef unavailable")
        return

    try:
        current = read_dataref_index(
            api_version,
            brightness_ref_id,
            MCDU_BRIGHTNESS_INDEX,
        )
        target = max(
            0.0,
            min(1.0, float(current) + float(delta)),
        )
        set_dataref_index(
            api_version,
            brightness_ref_id,
            MCDU_BRIGHTNESS_INDEX,
            target,
        )

        # Keep the physical screen visually synchronized immediately.
        set_brightness(
            device,
            1,
            round(target * 255),
        )

        print(
            f"BB36 SCREEN BRIGHTNESS -> {target:.2f}"
        )

    except Exception as exc:
        print(f"BB36 brightness error: {exc}")


def _execute_bb36_key(
    device,
    api_version,
    command_ids,
    brightness_ref_id,
    hardware_index,
):
    mapping = BB36_KEY_MAP.get(
        int(hardware_index)
    )

    if mapping is None:
        print(
            f"BB36 KEY index={hardware_index}: UNKNOWN"
        )
        return

    label, action = mapping

    if action is None:
        print(
            f"BB36 KEY index={hardware_index:02d} "
            f"{label}: no Zibo assignment "
            "(matches WinCtrl Zibo profile)"
        )
        return

    if action == "__brightness_up__":
        _adjust_mcdu_brightness(
            device,
            api_version,
            brightness_ref_id,
            +0.1,
        )
        return

    if action == "__brightness_down__":
        _adjust_mcdu_brightness(
            device,
            api_version,
            brightness_ref_id,
            -0.1,
        )
        return

    command_id = command_ids.get(action)

    if command_id is None:
        print(
            f"BB36 KEY {label}: command not resolved "
            f"({action})"
        )
        return

    try:
        activate_command(
            api_version,
            command_id,
            MCDU_KEY_PRESS_SECONDS,
        )
        print(
            f"BB36 KEY index={hardware_index:02d} "
            f"{label} -> ZIBO"
        )
    except Exception as exc:
        print(
            f"BB36 KEY {label} command error: {exc}"
        )



def _ws_decode_text(value):
    """
    Decode X-Plane WebSocket data-type values.

    String/data DataRefs are transported as base64 just like their REST
    representation.  Plain text is retained if it is not valid base64.
    """
    if value is None:
        return ""

    if isinstance(value, str):
        return _decode_possible_base64_text(value)

    if isinstance(value, (bytes, bytearray)):
        return bytes(value).split(b"\x00", 1)[0].decode(
            "utf-8",
            errors="replace",
        )

    if isinstance(value, list):
        if value and all(isinstance(item, int) for item in value):
            raw = bytes(
                max(0, min(255, int(item)))
                for item in value
            )
            return raw.split(b"\x00", 1)[0].decode(
                "utf-8",
                errors="replace",
            )
        if len(value) == 1:
            return _ws_decode_text(value[0])

    return str(value)


def _ws_scalar(value, fallback=0.0):
    if isinstance(value, list):
        if not value:
            return float(fallback)
        value = value[0]

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return float(fallback)

    if not math.isfinite(numeric):
        return float(fallback)

    return numeric


def _next_req_id(counter):
    counter[0] += 1
    return counter[0]


def _ws_send(ws, payload):
    ws.send(
        json.dumps(
            payload,
            separators=(",", ":"),
        )
    )


def _ws_command_message(req_id, command_id, is_active):
    return {
        "req_id": int(req_id),
        "type": "command_set_is_active",
        "params": {
            "commands": [
                {
                    "id": int(command_id),
                    "is_active": bool(is_active),
                }
            ]
        },
    }


def _ws_dataref_set_message(
    req_id,
    dataref_id,
    value,
    index=None,
):
    item = {
        "id": int(dataref_id),
        "value": float(value),
    }

    if index is not None:
        item["index"] = int(index)

    return {
        "req_id": int(req_id),
        "type": "dataref_set_values",
        "params": {
            "datarefs": [item]
        },
    }


def _drain_key_queue_to_websocket(
    ws,
    key_queue,
    command_ids,
    brightness_ref_id,
    brightness_state,
    req_counter,
    device,
    hid_write_lock,
    max_events=128,
):
    """
    Send physical MCDU key phases to X-Plane through its WebSocket API.

    Unlike REST activate(duration), this preserves the real hardware press
    and release phases and never blocks the HID reader on an HTTP request.
    """
    processed = 0

    while processed < max_events:
        try:
            edge, hardware_index = key_queue.get_nowait()
        except queue.Empty:
            break

        processed += 1
        hardware_index = int(hardware_index)
        mapping = BB36_KEY_MAP.get(hardware_index)

        if mapping is None:
            if edge == "press":
                print(
                    f"BB36 KEY index={hardware_index:02d}: UNKNOWN"
                )
            continue

        label, action = mapping

        if action is None:
            if edge == "press":
                print(
                    f"BB36 KEY index={hardware_index:02d} "
                    f"{label}: no Zibo assignment"
                )
            continue

        if action in (
            "__brightness_up__",
            "__brightness_down__",
        ):
            # Brightness is a DataRef adjustment, not a command.
            if edge != "press":
                continue

            delta = (
                +0.1
                if action == "__brightness_up__"
                else -0.1
            )

            current = float(
                brightness_state.get("value", 0.85)
            )
            target = max(
                0.0,
                min(1.0, current + delta),
            )
            brightness_state["value"] = target

            if brightness_ref_id is not None:
                _ws_send(
                    ws,
                    _ws_dataref_set_message(
                        _next_req_id(req_counter),
                        brightness_ref_id,
                        target,
                        MCDU_BRIGHTNESS_INDEX,
                    ),
                )

            # Update physical screen immediately without waiting for the
            # simulator's 10-Hz echo.
            try:
                with hid_write_lock:
                    set_brightness(
                        device,
                        1,
                        round(target * 255),
                    )
            except Exception as exc:
                print(
                    f"BB36 physical brightness error: {exc}"
                )

            print(
                f"BB36 SCREEN BRIGHTNESS -> {target:.2f}"
            )
            continue

        command_id = command_ids.get(action)

        if command_id is None:
            if edge == "press":
                print(
                    f"BB36 KEY {label}: command not resolved "
                    f"({action})"
                )
            continue

        try:
            _ws_send(
                ws,
                _ws_command_message(
                    _next_req_id(req_counter),
                    command_id,
                    edge == "press",
                ),
            )

            if edge == "press":
                print(
                    f"BB36 KEY index={hardware_index:02d} "
                    f"{label} -> ZIBO WS"
                )

        except Exception as exc:
            # Put the event back so a reconnect can handle it if possible.
            # A release is especially important; X-Plane also automatically
            # releases active commands when this WebSocket disconnects.
            key_queue.put((edge, hardware_index))
            raise RuntimeError(
                f"BB36 WebSocket key send failed: {exc}"
            )


def xplane_mcdu_websocket_worker(
    api_version,
    fmc_ids,
    command_ids,
    brightness_ref_id,
    key_queue,
    fmc_state,
    fmc_state_lock,
    display_dirty_event,
    stop_event,
    device,
    hid_write_lock,
    transport_status,
):
    """
    One persistent X-Plane WebSocket owns all live FMC traffic.

    Data path:
        X-Plane pushes changed FMC strings at 10 Hz -> memory cache -> display

    Command path:
        BB36 HID edge -> key_queue -> command_set_is_active -> X-Plane

    There are no per-frame REST reads and no REST command activations here.
    REST is used only once at startup to resolve stable runtime IDs.
    """
    id_to_key = {
        str(int(ref_id)): key
        for key, ref_id in fmc_ids.items()
    }

    brightness_id_key = (
        str(int(brightness_ref_id))
        if brightness_ref_id is not None
        else None
    )

    req_counter = [1000]
    brightness_state = {"value": 0.85}

    while not stop_event.is_set():
        ws = None

        try:
            ws_url = (
                f"ws://127.0.0.1:8086/api/{api_version}"
            )

            ws = websocket.create_connection(
                ws_url,
                timeout=1.0,
                enable_multithread=True,
            )
            ws.settimeout(MCDU_WS_RECV_TIMEOUT)

            subscriptions = [
                {"id": int(ref_id)}
                for ref_id in fmc_ids.values()
            ]

            if brightness_ref_id is not None:
                subscriptions.append(
                    {
                        "id": int(brightness_ref_id),
                        "index": MCDU_BRIGHTNESS_INDEX,
                    }
                )

            _ws_send(
                ws,
                {
                    "req_id": _next_req_id(req_counter),
                    "type": "dataref_subscribe_values",
                    "params": {
                        "datarefs": subscriptions
                    },
                },
            )

            transport_status["connected"] = True
            transport_status["error"] = None

            print(
                "BB36 X-Plane WebSocket CONNECTED: "
                f"{len(fmc_ids)} FMC DataRefs subscribed; "
                "changed values stream at X-Plane's native update cadence."
            )

            while not stop_event.is_set():
                # Key events are handled before receive so even a screen with
                # no changing text has immediate hardware response.
                _drain_key_queue_to_websocket(
                    ws,
                    key_queue,
                    command_ids,
                    brightness_ref_id,
                    brightness_state,
                    req_counter,
                    device,
                    hid_write_lock,
                )

                try:
                    raw_message = ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue

                if not raw_message:
                    continue

                message = json.loads(raw_message)
                message_type = message.get("type")

                if message_type == "result":
                    if not message.get("success", False):
                        print(
                            "BB36 WebSocket request error: "
                            f"{message.get('error_code')} "
                            f"{message.get('error_message')}"
                        )
                    continue

                if message_type != "dataref_update_values":
                    continue

                updates = message.get("data", {})

                if not isinstance(updates, dict):
                    continue

                display_changed = False

                with fmc_state_lock:
                    for raw_id, value in updates.items():
                        id_key = str(raw_id).strip()

                        if (
                            brightness_id_key is not None
                            and id_key == brightness_id_key
                        ):
                            brightness_state["value"] = max(
                                0.0,
                                min(
                                    1.0,
                                    _ws_scalar(
                                        value,
                                        brightness_state["value"],
                                    ),
                                ),
                            )
                            continue

                        display_key = id_to_key.get(id_key)

                        if display_key is None:
                            continue

                        text = _ws_decode_text(value)

                        if fmc_state.get(display_key) != text:
                            fmc_state[display_key] = text
                            display_changed = True

                if display_changed:
                    display_dirty_event.set()

        except Exception as exc:
            transport_status["connected"] = False
            transport_status["error"] = str(exc)

            if not stop_event.is_set():
                print(
                    f"BB36 X-Plane WebSocket reconnecting: {exc}"
                )
                stop_event.wait(
                    MCDU_WS_RECONNECT_SECONDS
                )

        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass

    transport_status["connected"] = False


def bb36_key_reader(
    device,
    key_queue,
    stop_event,
):
    """
    Dedicated high-rate BB36 HID input reader.

    Critical rule:
    keypad sampling must never wait for the FMC display's many X-Plane HTTP
    reads. A short physical press can be only a few tens of milliseconds, so
    the reader continuously drains report-ID 1 and queues every rising edge.

    The main/display thread may be busy for hundreds of milliseconds and the
    key is still retained safely in key_queue.
    """
    previous_bits = None
    first_report_printed = False

    while not stop_event.is_set():
        try:
            report = device.read(128)
        except Exception as exc:
            print(f"BB36 keypad HID read error: {exc}")
            stop_event.wait(0.05)
            continue

        if not report:
            # Keep latency low without busy-spinning one CPU core.
            stop_event.wait(0.001)
            continue

        current = bytes(report)
        current_bits = _bb36_button_bits(current)

        if current_bits is None:
            continue

        if previous_bits is None:
            previous_bits = current_bits
            if not first_report_printed:
                print(
                    f"BB36 KEYPAD READER LOCKED len={len(current)} "
                    f"buttons=0x{current_bits:024X}"
                )
                first_report_printed = True
            continue

        changed = current_bits ^ previous_bits

        if changed:
            for hardware_index in range(96):
                mask = 1 << hardware_index

                if not (changed & mask):
                    continue

                pressed = bool(current_bits & mask)

                if pressed:
                    # Queue the edge immediately.  Never wait for X-Plane here.
                    key_queue.put(("press", hardware_index))
                else:
                    key_queue.put(("release", hardware_index))

        previous_bits = current_bits


def drain_bb36_key_events(
    device,
    key_queue,
    api_version,
    command_ids,
    brightness_ref_id,
    max_events=64,
):
    """
    Execute already-captured BB36 key events.

    This function is intentionally cheap. The high-rate HID thread has already
    guaranteed that quick taps cannot be lost while the display loop is busy.
    """
    processed = 0

    while processed < max_events:
        try:
            action, hardware_index = key_queue.get_nowait()
        except queue.Empty:
            break

        processed += 1

        mapping = BB36_KEY_MAP.get(int(hardware_index))

        if action == "press":
            _execute_bb36_key(
                device,
                api_version,
                command_ids,
                brightness_ref_id,
                int(hardware_index),
            )
        elif mapping is not None:
            label, _mapped_action = mapping
            print(
                f"BB36 KEY index={int(hardware_index):02d} "
                f"{label} RELEASE"
            )

    return processed


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--font",
        required=True,
    )

    parser.add_argument(
        "--refresh",
        type=float,
        default=MCDU_DISPLAY_MIN_INTERVAL,
        help=(
            "Minimum physical LCD redraw interval. "
            "X-Plane WebSocket sends changed DataRefs at up to 10 Hz. "
            "Default 0.045 s."
        ),
    )

    parser.add_argument(
        "--brightness",
        type=int,
        default=220,
    )

    args = parser.parse_args()

    if hid is None:
        print("ERROR: hidapi is not installed.")
        print("Run: py -m pip install hidapi")
        return 2

    if websocket is None:
        print("ERROR: websocket-client is not installed.")
        print("Run: py -m pip install websocket-client")
        return 2

    font_path = Path(args.font).expanduser().resolve()

    if not font_path.is_file():
        print(f"Font not found: {font_path}")
        return 2

    font_packets = read_font_packets(font_path)
    validate_font(font_packets)

    device = None
    stop_event = threading.Event()
    keypad_thread = None
    ws_thread = None

    try:
        device = open_bb36()
        initialize_display(
            device,
            font_packets,
            args.brightness,
        )

        print()
        print("Waiting for X-Plane Web API...")

        while True:
            try:
                api_version = detect_api_version()
                break
            except Exception:
                time.sleep(0.5)

        print(
            f"Connected to X-Plane Web API {api_version}"
        )
        print(
            "Resolving Zibo CAPTAIN FMC IDs once..."
        )

        fmc_ids = resolve_fmc_ids(api_version)
        command_ids = resolve_bb36_commands(
            api_version
        )

        try:
            brightness_ref_id = resolve_dataref_id(
                api_version,
                MCDU_BRIGHTNESS_DATAREF,
            )
            print(
                "BB36 brightness -> "
                f"{MCDU_BRIGHTNESS_DATAREF}"
                f"[{MCDU_BRIGHTNESS_INDEX}]"
            )
        except Exception as exc:
            brightness_ref_id = None
            print(
                f"OPTIONAL BB36 brightness unavailable: {exc}"
            )

        print()
        print("=" * 78)
        print("BB36 LIVE ZIBO FMC — WEBSOCKET MODE")
        print("=" * 78)
        print(
            "No per-frame HTTP polling."
        )
        print(
            "Zibo FMC strings are subscribed once and pushed "
            "only when they change."
        )
        print(
            "BB36 key press/release phases use X-Plane WebSocket commands."
        )
        print("Ctrl+C stops.")
        print()

        key_queue = queue.Queue()

        fmc_state = {}
        fmc_state_lock = threading.Lock()
        display_dirty_event = threading.Event()
        hid_write_lock = threading.Lock()

        transport_status = {
            "connected": False,
            "error": None,
        }

        keypad_thread = threading.Thread(
            target=bb36_key_reader,
            args=(
                device,
                key_queue,
                stop_event,
            ),
            name="BB36-MCDU-Keypad",
            daemon=True,
        )
        keypad_thread.start()

        ws_thread = threading.Thread(
            target=xplane_mcdu_websocket_worker,
            args=(
                api_version,
                fmc_ids,
                command_ids,
                brightness_ref_id,
                key_queue,
                fmc_state,
                fmc_state_lock,
                display_dirty_event,
                stop_event,
                device,
                hid_write_lock,
                transport_status,
            ),
            name="BB36-XPlane-WebSocket",
            daemon=True,
        )
        ws_thread.start()

        print(
            "BB36 FAST MODE: HID keypad + WebSocket simulator stream "
            "+ dirty-only LCD redraw."
        )

        previous_page = None
        last_display_write = 0.0
        min_display_interval = max(
            0.02,
            float(args.refresh),
        )
        frames = 0
        stats_started = time.monotonic()

        while True:
            # Wait until X-Plane says at least one FMC field changed.
            # A timeout lets Ctrl+C and transport status remain responsive.
            display_dirty_event.wait(0.10)

            if not display_dirty_event.is_set():
                continue

            display_dirty_event.clear()

            elapsed = (
                time.monotonic()
                - last_display_write
            )

            if elapsed < min_display_interval:
                # Coalesce multiple WebSocket updates into one complete
                # physical frame rather than drawing stale intermediate data.
                time.sleep(
                    min_display_interval - elapsed
                )

            with fmc_state_lock:
                values = dict(fmc_state)

            lines, colors = compose_zibo_page(
                values
            )

            state = (lines, colors)

            if state == previous_page:
                continue

            packets = page_packets(
                lines,
                colors,
            )

            with hid_write_lock:
                for packet in packets:
                    device.write(list(packet))

            previous_page = state
            last_display_write = time.monotonic()
            frames += 1

            print(
                "FMC PAGE -> "
                + lines[0].strip()
            )

            now = time.monotonic()

            if now - stats_started >= 5.0:
                hz = frames / max(
                    0.001,
                    now - stats_started,
                )
                print(
                    f"BB36 DISPLAY RATE: {hz:.1f} changed frames/sec "
                    "(WebSocket source max 10 Hz)"
                )
                frames = 0
                stats_started = now

    except KeyboardInterrupt:
        print(
            "\nStopping BB36 WebSocket live test."
        )

    except Exception as exc:
        print(
            f"\nBB36 live test error: {exc}"
        )
        return 1

    finally:
        stop_event.set()

        if keypad_thread is not None:
            keypad_thread.join(timeout=1.0)

        if ws_thread is not None:
            ws_thread.join(timeout=1.5)

        if device is not None:
            try:
                device.close()
            except Exception:
                pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())