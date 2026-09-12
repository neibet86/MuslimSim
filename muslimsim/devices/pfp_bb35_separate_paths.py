#!/usr/bin/env python3
"""MuslimSim BB35 TRUE separate PFD / PFP-FMC path router.

This intentionally does NOT share one live BB35 display session between the
PFD and FMC renderers.

PFD path:
    fresh BB35 HID handle
    existing MuslimSim graphical PFD callback/worker
    independent PFD canvas/sequence state
    period x3 requests a complete handoff

PFP/FMC path:
    fresh BB35 HID handle
    original WinCtrl PFP3N font/config upload
    F2 24x14 FMC page + X-Plane WebSocket
    independent FMC state
    period x3 requests a complete handoff

Handoff:
    physical PERIOD (.) x3 requests the switch
    stop current worker(s)
    when leaving FMC, blank F2 while FMC is still sole owner
    close the HID handle completely
    short settle
    open the other path from scratch

PFD never sends F2. FMC is the only path allowed to send F2.

At no time do PFD and PFP/FMC own the same BB35 HID handle, canvas, renderer,
sequence counter or output thread.
"""

from __future__ import annotations

import base64
import binascii
import json
import math
from pathlib import Path
import queue
import threading
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Optional, Tuple

from .cdu_exec_alert import (
    BB35_EXEC_LIGHT_CHANNEL,
    EXEC_LIGHT_OFF,
    EXEC_LIGHT_ON,
    ZIBO_CAPTAIN_EXEC_LIGHT_DATAREFS,
    exec_light_active,
    exec_light_output_value,
)

try:
    import hid
except ImportError:
    hid = None

try:
    import websocket
except ImportError:
    websocket = None

BB35_VID = 0x4098
BB35_PID = 0xBB35
BB35_IDENTIFIER = 0x31
BB35_FAMILY = 0xBB
PFP_COLUMNS = 24
PFP_ROWS = 14
PACKET_SIZE = 64
F2_ID = 0xF2
F2_PAYLOAD = 63
PFP_GRID_X = 14
PFP_GRID_Y = 10

# Real WinCtrl PFP3N Screen Layout calibration.
#
# The .xpwwf font is authored at 23x29 (MCDU pitch).  The WinCtrl PFP3N
# implementation rebuilds it to 23x32 so the six LSK content rows align with
# the six physical line-select button rows.  Without this conversion, the top
# rows can look close while the lower rows progressively drift upward.
PFP_CELL_WIDTH = 23
PFP_CELL_HEIGHT = 32
PFP_AUTHORED_CELL_HEIGHT = 29
PFP_AUTHORED_RECORD_LEN = 4 + PFP_AUTHORED_CELL_HEIGHT * 3  # 91
PFP_FONT_CHUNK = 512
SECRET_PERIOD_INDEX = 38
SECRET_TAPS = 3
SECRET_GAP = 0.60
DISPLAY_SLASH_INDEX = 69
DISPLAY_SLASH_TAPS = 2
DISPLAY_SLASH_GAP = 0.55
DISPLAY_PAGE_ORDER = ("pfd", "nd", "eng_pri", "mfd", "hyd")
HANDOFF_SETTLE = 0.18
FMC_REFRESH_MIN = 0.045
WS_RECV_TIMEOUT = 0.01
WS_RECONNECT = 0.50
BRIGHTNESS_REF = "laminar/B738/electric/instrument_brightness"
BRIGHTNESS_INDEX = 10
POWER_REF = "sim/cockpit/electrical/avionics_on"

COLOR_BLACK = 0x0000
COLOR_AMBER = 0x0021
COLOR_WHITE = 0x0042
COLOR_CYAN = 0x0063
COLOR_GREEN = 0x0084
COLOR_MAGENTA = 0x00A5
COLOR_RED = 0x00C6
COLOR_YELLOW = 0x00E7
COLOR_GREY = 0x0129

FMC_DATAREFS: Dict[str, str] = {
    "line00_l": "laminar/B738/fmc1/Line00_L",
    "line00_s": "laminar/B738/fmc1/Line00_S",
    "entry": "laminar/B738/fmc1/Line_entry",
    "entry_i": "laminar/B738/fmc1/Line_entry_I",
}
for _line in range(1, 7):
    FMC_DATAREFS[f"line{_line:02d}_x"] = f"laminar/B738/fmc1/Line{_line:02d}_X"
    for _layer in ("L", "S", "I", "M"):
        FMC_DATAREFS[f"line{_line:02d}_{_layer.lower()}"] = (
            f"laminar/B738/fmc1/Line{_line:02d}_{_layer}"
        )

# Exact WinCtrl PFP3N physical-index -> Zibo FMC1 mapping.
PFP3_KEYS: Dict[int, Tuple[str, Optional[str]]] = {
    0:("LSK1L","laminar/B738/button/fmc1_1L"), 1:("LSK2L","laminar/B738/button/fmc1_2L"),
    2:("LSK3L","laminar/B738/button/fmc1_3L"), 3:("LSK4L","laminar/B738/button/fmc1_4L"),
    4:("LSK5L","laminar/B738/button/fmc1_5L"), 5:("LSK6L","laminar/B738/button/fmc1_6L"),
    6:("LSK1R","laminar/B738/button/fmc1_1R"), 7:("LSK2R","laminar/B738/button/fmc1_2R"),
    8:("LSK3R","laminar/B738/button/fmc1_3R"), 9:("LSK4R","laminar/B738/button/fmc1_4R"),
    10:("LSK5R","laminar/B738/button/fmc1_5R"), 11:("LSK6R","laminar/B738/button/fmc1_6R"),
    12:("INIT REF","laminar/B738/button/fmc1_init_ref"),
    13:("RTE","laminar/B738/button/fmc1_rte"),
    14:("CLB","laminar/B738/button/fmc1_clb"),
    15:("CRZ","laminar/B738/button/fmc1_crz"),
    16:("DES","laminar/B738/button/fmc1_des"),
    17:("BRT -","__brightness_down__"), 18:("BRT +","__brightness_up__"),
    19:("MENU","laminar/B738/button/fmc1_menu"),
    20:("LEGS","laminar/B738/button/fmc1_legs"),
    21:("DEP/ARR","laminar/B738/button/fmc1_dep_app"),
    22:("HOLD","laminar/B738/button/fmc1_hold"),
    23:("PROG","laminar/B738/button/fmc1_prog"),
    24:("EXEC","laminar/B738/button/fmc1_exec"),
    25:("N1 LIMIT","laminar/B738/button/fmc1_n1_lim"),
    26:("FIX","laminar/B738/button/fmc1_fix"),
    27:("PREV PAGE","laminar/B738/button/fmc1_prev_page"),
    28:("NEXT PAGE","laminar/B738/button/fmc1_next_page"),
    29:("1","laminar/B738/button/fmc1_1"), 30:("2","laminar/B738/button/fmc1_2"),
    31:("3","laminar/B738/button/fmc1_3"), 32:("4","laminar/B738/button/fmc1_4"),
    33:("5","laminar/B738/button/fmc1_5"), 34:("6","laminar/B738/button/fmc1_6"),
    35:("7","laminar/B738/button/fmc1_7"), 36:("8","laminar/B738/button/fmc1_8"),
    37:("9","laminar/B738/button/fmc1_9"),
    38:(".","laminar/B738/button/fmc1_period"),
    39:("0","laminar/B738/button/fmc1_0"), 40:("+/-","laminar/B738/button/fmc1_minus"),
    41:("A","laminar/B738/button/fmc1_A"), 42:("B","laminar/B738/button/fmc1_B"),
    43:("C","laminar/B738/button/fmc1_C"), 44:("D","laminar/B738/button/fmc1_D"),
    45:("E","laminar/B738/button/fmc1_E"), 46:("F","laminar/B738/button/fmc1_F"),
    47:("G","laminar/B738/button/fmc1_G"), 48:("H","laminar/B738/button/fmc1_H"),
    49:("I","laminar/B738/button/fmc1_I"), 50:("J","laminar/B738/button/fmc1_J"),
    51:("K","laminar/B738/button/fmc1_K"), 52:("L","laminar/B738/button/fmc1_L"),
    53:("M","laminar/B738/button/fmc1_M"), 54:("N","laminar/B738/button/fmc1_N"),
    55:("O","laminar/B738/button/fmc1_O"), 56:("P","laminar/B738/button/fmc1_P"),
    57:("Q","laminar/B738/button/fmc1_Q"), 58:("R","laminar/B738/button/fmc1_R"),
    59:("S","laminar/B738/button/fmc1_S"), 60:("T","laminar/B738/button/fmc1_T"),
    61:("U","laminar/B738/button/fmc1_U"), 62:("V","laminar/B738/button/fmc1_V"),
    63:("W","laminar/B738/button/fmc1_W"), 64:("X","laminar/B738/button/fmc1_X"),
    65:("Y","laminar/B738/button/fmc1_Y"), 66:("Z","laminar/B738/button/fmc1_Z"),
    67:("SPACE","laminar/B738/button/fmc1_SP"),
    68:("DEL","laminar/B738/button/fmc1_del"),
    69:("/","laminar/B738/button/fmc1_slash"),
    70:("CLR","laminar/B738/button/fmc1_clr"),
}


# Set from final.py by --trace-pfp-handoff.  Off by default, and when off the
# device handle is used directly with nothing wrapped around it.
TRACE_HANDOFF = False


class _TracingDevice:
    """Pass-through HID handle that reports what a path sends, and when.

    The PFP 3N is the panel that works, so what it does to its screen on a
    handoff is the reference.  This records that without altering a single
    byte of it.
    """

    def __init__(self, device, label: str) -> None:
        self._device = device
        self._label = label
        self._phases = []
        self._current = None
        self._started = time.monotonic()

    # -- classification -----------------------------------------------------
    @staticmethod
    def _kind(report) -> str:
        data = bytes(report)

        if not data:
            return "empty"

        if data[0] == 0x02 and len(data) > 8 and data[6] == 0x49:
            return f"brightness ch{data[7]}={data[8]}"

        if data[0] == F2_ID:
            return "F2 character page"

        if data[0] == 0xF0:
            # One stream, not three.  Splitting on byte 1 and byte 3 chopped a
            # single font upload into hundreds of alternating fragments and
            # made the trace unreadable.
            return "F0 stream (font upload or graphics)"

        return f"other 0x{data[0]:02X}"

    # -- HID surface --------------------------------------------------------
    def write(self, report):
        kind = self._kind(report)
        now = time.monotonic()

        if self._current is None or self._current[0] != kind:
            self._current = [kind, 0, now, now]
            self._phases.append(self._current)

        self._current[1] += 1
        self._current[3] = now

        return self._device.write(report)

    def read(self, *args, **kwargs):
        return self._device.read(*args, **kwargs)

    def set_nonblocking(self, *args, **kwargs):
        return self._device.set_nonblocking(*args, **kwargs)

    def close(self):
        self.report("closing")
        return self._device.close()

    def __getattr__(self, name):
        return getattr(self._device, name)

    # -- output -------------------------------------------------------------
    def report(self, moment: str) -> None:
        if not self._phases:
            return

        total = sum(phase[1] for phase in self._phases)
        elapsed = time.monotonic() - self._started
        print(f"TRACE {self._label} [{moment}] {total} reports in {elapsed:.3f}s")

        for kind, count, first, last in self._phases:
            span = last - first
            print(f"TRACE     {count:5d}  {span:6.3f}s  {kind}")

        self._phases = []
        self._current = None


def _open_bb35():
    if hid is None:
        raise RuntimeError("hidapi unavailable; install hidapi")
    devices = hid.enumerate(BB35_VID, BB35_PID)
    if not devices:
        raise FileNotFoundError("WINCTRL 3N PFP CAPTAIN BB35 not connected")
    path = devices[0].get("path")
    if not path:
        raise RuntimeError("BB35 HID path unavailable")
    device = hid.device()
    device.open_path(path)
    try:
        device.set_nonblocking(1)
    except Exception:
        pass
    return device



# MUSLIMSIM_BB35_USB_RECONNECT_V1
BB35_USB_POLL_SECONDS = 0.10
BB35_USB_RECONNECT_SETTLE = 1.00

# MUSLIMSIM_BB35_OUTPUT_PROGRESS_WATCHDOG_V1
# BB35 supervision used to be thread liveness alone, which cannot see an output
# worker parked inside a native F0 write to a stalled panel: the thread stays
# alive, so the router kept reporting a frozen PFP3N as live indefinitely.
# The timeout matches BB36's measured value and BB35's own 6.0 s worker join:
# a wedged panel publishes no heartbeat at all after its path starts, so it
# surfaces at the 8.0 s grace, while a live panel having one slow frame stays
# under 4 s.  6.0 s separates the two, so only a genuine stall trips it.
BB35_PFD_STARTUP_GRACE_SECONDS = 8.0
BB35_PFD_PROGRESS_TIMEOUT_SECONDS = 6.0


def _bb35_present() -> bool:
    # Physical USB liveness. Simulator/WebSocket telemetry is NOT hardware
    # presence and must never keep Studio showing BB35 as live after unplug.
    if hid is None:
        return False
    try:
        return bool(hid.enumerate(BB35_VID, BB35_PID))
    except Exception:
        return False


def _button_bits(report: bytes) -> Optional[int]:
    if not report or len(report) < 13 or report[0] != 0x01:
        return None
    low = int.from_bytes(report[1:9], "little")
    high = int.from_bytes(report[9:13], "little")
    return low | (high << 64)


def _retarget_font_packet_raw(packet: bytes) -> bytes:
    """Retarget one source-length WinCtrl font packet to BB35 PFP3N."""
    converted = bytearray(packet)

    # Font resources are authored for the MCDU at 0x32/0xBB.
    for i in range(len(converted) - 1):
        if converted[i] == 0x32 and converted[i + 1] == 0xBB:
            converted[i] = BB35_IDENTIFIER
            converted[i + 1] = BB35_FAMILY

    # Original MCDU grid signature:
    # 08 00 00 00 34 00 25 00 0E 00 18 00
    signature = bytes((
        0x08, 0x00, 0x00, 0x00,
        0x34, 0x00,
        0x25, 0x00,
        0x0E, 0x00,
        0x18, 0x00,
    ))

    for i in range(len(converted) - len(signature) + 1):
        if bytes(converted[i:i + len(signature)]) == signature:
            # Same layout transformation used by the WinCtrl PFP3N:
            # actual left = 36 + layout.x
            # actual top  = 20 + layout.y
            converted[i + 4] = 36 + PFP_GRID_X
            converted[i + 6] = 20 + PFP_GRID_Y

    return bytes(converted)


def _font_put_u32(buffer: bytearray, offset: int, value: int) -> None:
    if offset + 4 > len(buffer):
        return
    value = int(value) & 0xFFFFFFFF
    buffer[offset:offset + 4] = value.to_bytes(4, "little")


def _font_read_u32(buffer: bytes, offset: int) -> int:
    if offset + 4 > len(buffer):
        return 0
    return int.from_bytes(buffer[offset:offset + 4], "little")


def _font_control_block_cmd(packet: bytes, index: int) -> int:
    """Return 05/06/07 for a WinCtrl font control block, else -1."""
    if index + 14 > len(packet):
        return -1

    if (
        packet[index + 1] == 0xBB
        and packet[index + 2] == 0x00
        and packet[index + 3] == 0x00
        and packet[index + 5] == 0x01
        and packet[index + 4] in (0x05, 0x06, 0x07)
    ):
        return int(packet[index + 4])

    return -1


def _font_parse_glyph_segment(
    packets,
    write_template: bytearray,
    commit_template: bytearray,
):
    """Parse one authored glyph-set segment using WinCtrl's proven rules."""
    geometry = bytearray()
    glyph_buffer = bytearray()
    write_addresses = []
    bytes_to_skip = 0

    for raw in packets:
        p = bytes(raw)

        if len(p) < 4 or p[0] != 0xF0 or p[1] != 0x00:
            continue

        packet_type = p[3]

        if packet_type == 0x2A:
            # Standalone geometry packet (large set).
            for i in range(4, max(4, len(p) - 13)):
                if _font_control_block_cmd(p, i) == 0x06:
                    geometry = bytearray(p[i:min(len(p), i + 42)])
                    break
            continue

        if packet_type == 0x12:
            # One glyph byte + COMMIT control block.
            if len(p) > 4:
                glyph_buffer.append(p[4])

            if (
                not commit_template
                and len(p) >= 22
                and _font_control_block_cmd(p, 5) == 0x05
            ):
                commit_template.extend(p[5:22])
            continue

        if packet_type != 0x3C:
            continue

        i = 4
        n = len(p)

        while i < n:
            if bytes_to_skip > 0:
                bytes_to_skip -= 1
                i += 1
                continue

            command = _font_control_block_cmd(p, i)

            if command >= 0:
                if command == 0x06 and not geometry and i + 42 <= n:
                    geometry = bytearray(p[i:i + 42])

                if command == 0x07:
                    if not write_template and i + 29 <= n:
                        write_template.extend(p[i:i + 29])
                    write_addresses.append(_font_read_u32(p, i + 8))

                total = 17 + p[i + 13]

                if i + total <= n:
                    i += total
                else:
                    bytes_to_skip = total - (n - i)
                    i = n

                continue

            glyph_buffer.append(p[i])
            i += 1

    if len(geometry) < 29:
        raise ValueError("could not locate WinCtrl glyph geometry")

    return geometry, glyph_buffer, write_addresses


def _resize_font_cell_height(
    packets,
    new_height: int = PFP_CELL_HEIGHT,
    new_width: int = PFP_CELL_WIDTH,
):
    """Rebuild the authored 23x29 WinCtrl glyph stream at 23x32.

    This is a direct Python implementation of the WinCtrl plugin's
    Font::ResizeCellHeight / padGlyphsToHeight logic.  It preserves the
    original 29 bitmap rows and appends blank rows below each glyph; the ink
    therefore stays the same size while the additional cell height becomes
    vertical row pitch.  That is the specific mechanism used by WinCtrl to
    line the 14 PFP rows up with the physical LSK keys.
    """
    new_height = int(new_height)
    new_width = int(new_width)

    if new_height <= PFP_AUTHORED_CELL_HEIGHT:
        return list(packets)

    reset_indices = []
    flush_template = None

    for index, raw in enumerate(packets):
        p = bytes(raw)

        if (
            len(p) >= 4
            and p[0] == 0xF0
            and p[1] == 0x00
            and p[3] == 0x02
        ):
            reset_indices.append(index)

        if (
            len(p) >= 4
            and p[0] == 0xF0
            and p[1] == 0x01
            and flush_template is None
        ):
            flush_template = p

    if len(reset_indices) < 2 or flush_template is None:
        raise ValueError(
            "unexpected WinCtrl font structure while resizing "
            f"(resets={len(reset_indices)})"
        )

    # Authored stream segmentation. The resize output deliberately omits the
    # 0x02 reset packets, matching the actual WinCtrl resize format.
    reset0, reset1 = reset_indices[0], reset_indices[1]
    segment0 = packets[:reset0]
    segment1 = packets[reset0 + 1:reset1]
    suffix = packets[reset1:]

    write_template = bytearray()
    commit_template = bytearray()

    geo0, buf0, addresses0 = _font_parse_glyph_segment(
        segment0, write_template, commit_template
    )
    geo1, buf1, addresses1 = _font_parse_glyph_segment(
        segment1, write_template, commit_template
    )

    if len(write_template) != 29 or len(commit_template) != 17:
        raise ValueError("WinCtrl font WRITE/COMMIT templates were not found")

    sequence = 0
    output = []
    new_record_len = 4 + new_height * 3
    bottom_padding_rows = new_height - PFP_AUTHORED_CELL_HEIGHT

    def make_packet(packet_type: int, payload: bytes) -> bytes:
        nonlocal sequence

        result = bytearray(64)
        result[0] = 0xF0
        result[1] = 0x00
        result[2] = sequence & 0xFF
        result[3] = int(packet_type) & 0xFF

        payload = bytes(payload)
        result[4:4 + min(60, len(payload))] = payload[:60]

        sequence = (sequence + 1) & 0xFF
        return bytes(result)

    def emit_set(geometry, source_buffer, original_addresses):
        geo = bytearray(geometry)

        glyph_count = _font_read_u32(geo, 29)
        old_record_len = _font_read_u32(geo, 25)
        size_field = _font_read_u32(geo, 37)
        size_constant = max(
            0,
            size_field - glyph_count * old_record_len,
        )

        # Geometry fields used by WinCtrl:
        # width @21, height @23, record length @25, total size @37.
        geo[21:23] = int(new_width).to_bytes(2, "little")
        geo[23:25] = int(new_height).to_bytes(2, "little")
        _font_put_u32(geo, 25, new_record_len)
        _font_put_u32(
            geo,
            37,
            glyph_count * new_record_len + size_constant,
        )

        def descriptor_address_for_glyph(glyph_index: int) -> int:
            if not original_addresses:
                return 0

            for j in range(len(original_addresses) - 1):
                g0 = (j * PFP_FONT_CHUNK) // PFP_AUTHORED_RECORD_LEN
                g1 = ((j + 1) * PFP_FONT_CHUNK) // PFP_AUTHORED_RECORD_LEN

                if glyph_index >= g0 and glyph_index < g1 and g1 > g0:
                    a0 = original_addresses[j]
                    a1 = original_addresses[j + 1]
                    return a0 + (a1 - a0) * (glyph_index - g0) // (g1 - g0)

            return original_addresses[-1]

        # Preserve all original glyph ink, then add blank rows underneath.
        source = bytes(source_buffer)
        records = len(source) // PFP_AUTHORED_RECORD_LEN
        rebuilt = bytearray()

        for glyph in range(records):
            start = glyph * PFP_AUTHORED_RECORD_LEN
            record = source[start:start + PFP_AUTHORED_RECORD_LEN]

            rebuilt.extend(record[:4])
            rebuilt.extend(
                record[
                    4:
                    4 + PFP_AUTHORED_CELL_HEIGHT * 3
                ]
            )
            rebuilt.extend(b"\x00" * (bottom_padding_rows * 3))

        target_length = glyph_count * new_record_len

        if len(rebuilt) < target_length:
            rebuilt.extend(b"\x00" * (target_length - len(rebuilt)))

        real_length = len(rebuilt)

        # Geometry report.
        geometry_payload = bytearray(60)
        geometry_payload[:min(60, len(geo))] = geo[:60]
        output.append(make_packet(0x2A, geometry_payload))

        chunk_count = (
            real_length + PFP_FONT_CHUNK - 1
        ) // PFP_FONT_CHUNK

        for chunk_index in range(chunk_count):
            offset = chunk_index * PFP_FONT_CHUNK
            length = min(PFP_FONT_CHUNK, real_length - offset)
            is_last = chunk_index + 1 == chunk_count

            descriptor_address = descriptor_address_for_glyph(
                offset // new_record_len
            )

            write_block = bytearray(write_template)
            _font_put_u32(write_block, 8, descriptor_address)
            _font_put_u32(write_block, 13, length + 12)
            _font_put_u32(write_block, 21, offset)
            _font_put_u32(write_block, 25, length)

            # Set discriminator: 05 for set0, 06 for set1.
            write_block[17] = geo[17]

            commit_block = bytearray(commit_template)
            _font_put_u32(commit_block, 8, descriptor_address)

            unit = bytearray(write_block)
            unit.extend(rebuilt[offset:offset + length])
            unit.extend(commit_block)

            if not is_last:
                if len(unit) < 600:
                    unit.extend(b"\x00" * (600 - len(unit)))
                else:
                    del unit[600:]

                for part in range(9):
                    output.append(
                        make_packet(
                            0x3C,
                            unit[part * 60:(part + 1) * 60],
                        )
                    )

                output.append(
                    make_packet(0x12, unit[540:600])
                )

                # Three authored flush reports after every chunk.
                output.extend([bytes(flush_template)] * 3)

            else:
                raw_length = len(unit)

                while len(unit) % 60:
                    unit.append(0)

                packet_count = len(unit) // 60

                for part in range(max(0, packet_count - 1)):
                    output.append(
                        make_packet(
                            0x3C,
                            unit[part * 60:(part + 1) * 60],
                        )
                    )

                last_type = (
                    0x3C
                    if raw_length % 60 == 0
                    else raw_length % 60
                )

                output.append(
                    make_packet(
                        last_type,
                        unit[(packet_count - 1) * 60:packet_count * 60],
                    )
                )

                output.extend([bytes(flush_template)] * 3)

    emit_set(geo0, buf0, addresses0)
    emit_set(geo1, buf1, addresses1)

    for raw in suffix:
        p = bytes(raw)

        if (
            len(p) >= 4
            and p[0] == 0xF0
            and p[1] == 0x00
            and p[3] == 0x02
        ):
            continue

        output.append(p)

    return output


def _load_font_packets(font_path: Path):
    raw = font_path.read_bytes()
    source_packets = []
    offset = 0

    while offset < len(raw):
        length = raw[offset]
        offset += 1

        if length == 0:
            break

        end = offset + length

        if end > len(raw):
            raise ValueError("BB35 font resource ends inside a packet")

        # Keep the original packet length while parsing/rebuilding the font.
        source_packets.append(
            _retarget_font_packet_raw(
                bytes(raw[offset:end])
            )
        )
        offset = end

    if not source_packets or offset != len(raw):
        raise ValueError("BB35 font resource malformed")

    # Critical PFP3N calibration: 23x29 authored font -> 23x32 cells.
    resized = _resize_font_cell_height(
        source_packets,
        PFP_CELL_HEIGHT,
        PFP_CELL_WIDTH,
    )

    # hidapi output reports are normalized to complete 64-byte reports only
    # after the WinCtrl font stream has been rebuilt.
    packets = []

    for raw_packet in resized:
        packet = bytes(raw_packet)

        if len(packet) < PACKET_SIZE:
            packet += b"\x00" * (PACKET_SIZE - len(packet))

        packets.append(packet[:PACKET_SIZE])

    return tuple(packets)


def _black_packet() -> bytes:
    packet = bytearray(PACKET_SIZE)
    packet[:16] = bytes((
        0xF0,0,0x03,0x12,BB35_IDENTIFIER,BB35_FAMILY,0,0,
        0x04,0x01,0,0,0xFD,0x24,0x07,0,
    ))
    packet[16:22] = bytes((0,1,0,0,0,0x0E))
    return bytes(packet)


def _grid_packet() -> bytes:
    packet = bytearray(PACKET_SIZE)
    packet[:4] = bytes((0xF0,0,0,0x2A))
    p = 4
    packet[p:p+25] = bytes((
        BB35_IDENTIFIER,BB35_FAMILY,0,0,0x18,0x01,0,0,
        0,0,0,0,0,0x08,0,0,0,
        36+PFP_GRID_X,0,20+PFP_GRID_Y,0,PFP_ROWS,0,PFP_COLUMNS,0,
    ))
    c = 29
    packet[c:c+17] = bytes((
        BB35_IDENTIFIER,BB35_FAMILY,0,0,0x05,0x01,0,0,
        0,0,0,0,1,0,0,0,0,
    ))
    return bytes(packet)


def _set_brightness(device: Any, channel: int, value: int) -> None:
    device.write([
        0x02,BB35_IDENTIFIER,BB35_FAMILY,0,0,0x03,0x49,
        int(channel)&0xFF,max(0,min(255,int(value))),0,0,0,0,0,
    ])


def _blank_f2_packets():
    # ProductFMC::clearDisplay() uses 16 complete blank F2 reports.
    blank = bytearray((F2_ID,))
    for _ in range(PFP_COLUMNS):
        blank.extend((0x42,0x00,ord(' ')))
    # That report is 73 bytes; the firmware consumes HID-size chunks in the
    # same sequential page stream, so use the normal full-page encoder below
    # instead of relying on an overlength report.
    lines = tuple(" " * PFP_COLUMNS for _ in range(PFP_ROWS))
    colors = tuple(tuple(COLOR_WHITE for _ in range(PFP_COLUMNS)) for _ in range(PFP_ROWS))
    return _page_packets(lines, colors)


def _normalize_24(value: str) -> str:
    value = str(value or "").replace("\r"," ").replace("\n"," ")
    out = []
    for ch in value:
        code = ord(ch)
        if 0x20 <= code <= 0x7E:
            out.append(ch)
        elif ch == "°":
            out.append("o")
        else:
            out.append(" ")
    return "".join(out)[:PFP_COLUMNS].ljust(PFP_COLUMNS)


def _overlay(base: str, colors, overlay: str, color: int):
    chars = list(_normalize_24(base))
    row_colors = list(colors)
    overlay = _normalize_24(overlay)
    for i, ch in enumerate(overlay):
        if ch != " ":
            chars[i] = ch
            row_colors[i] = color
    return "".join(chars), tuple(row_colors)


def _compose_page(values: Dict[str, str]):
    lines = [" " * PFP_COLUMNS for _ in range(PFP_ROWS)]
    colors = [tuple([COLOR_WHITE] * PFP_COLUMNS) for _ in range(PFP_ROWS)]
    title = list(_normalize_24(values.get("line00_l","")))
    for i, ch in enumerate(_normalize_24(values.get("line00_s",""))):
        if ch != " ":
            title[i] = ch
    lines[0] = "".join(title)
    for n in range(1,7):
        label_row = 1 + (n-1)*2
        content_row = label_row + 1
        lines[label_row] = _normalize_24(values.get(f"line{n:02d}_x",""))
        colors[label_row] = tuple([COLOR_CYAN]*PFP_COLUMNS)
        text = _normalize_24(values.get(f"line{n:02d}_l",""))
        row_colors = tuple([COLOR_WHITE]*PFP_COLUMNS)
        text,row_colors = _overlay(text,row_colors,values.get(f"line{n:02d}_s",""),COLOR_CYAN)
        text,row_colors = _overlay(text,row_colors,values.get(f"line{n:02d}_i",""),COLOR_AMBER)
        text,row_colors = _overlay(text,row_colors,values.get(f"line{n:02d}_m",""),COLOR_MAGENTA)
        lines[content_row] = text
        colors[content_row] = row_colors
    scratch = _normalize_24(values.get("entry",""))
    scratch_colors = tuple([COLOR_WHITE]*PFP_COLUMNS)
    scratch,scratch_colors = _overlay(scratch,scratch_colors,values.get("entry_i",""),COLOR_AMBER)
    lines[13] = scratch
    colors[13] = scratch_colors
    return tuple(lines), tuple(colors)


def _bb35_simulator_offline_page():
    """Build an honest BB35 F2 standby page through the proven grid path."""

    lines = [" " * PFP_COLUMNS for _ in range(PFP_ROWS)]
    colors = [tuple([COLOR_WHITE] * PFP_COLUMNS) for _ in range(PFP_ROWS)]

    def place(row: int, text: str, colour: int) -> None:
        text = str(text)[:PFP_COLUMNS]
        start = max(0, (PFP_COLUMNS - len(text)) // 2)
        line = (" " * start + text).ljust(PFP_COLUMNS)[:PFP_COLUMNS]
        lines[row] = line
        colors[row] = tuple(
            colour if character != " " else COLOR_WHITE
            for character in line
        )

    place(0, "MUSLIMSIM", COLOR_MAGENTA)
    place(3, "PFP OFFLINE", COLOR_AMBER)
    place(5, "SIM STOPPED", COLOR_WHITE)
    place(7, "START X-PLANE", COLOR_GREEN)
    place(11, "DEVELOPED BY", COLOR_WHITE)
    place(12, "MUSLIMSIM", COLOR_MAGENTA)
    place(13, "WINCTRL PFP", COLOR_GREEN)
    return tuple(lines), tuple(colors)


def _page_packets(lines, colors):
    payload = bytearray()
    for row_i,line in enumerate(lines):
        text = _normalize_24(line)
        for col,ch in enumerate(text):
            color = int(colors[row_i][col])
            payload.extend((color&0xFF,(color>>8)&0xFF,ord(ch)))
    packets = []
    while payload:
        chunk = payload[:F2_PAYLOAD]
        del payload[:F2_PAYLOAD]
        packet = bytearray((F2_ID,))
        packet.extend(chunk)
        packet.extend(b"\x00" * (PACKET_SIZE-len(packet)))
        packets.append(bytes(packet))
    return tuple(packets)


def _http_json(url: str, timeout: float = 1.0):
    req = urllib.request.Request(url, headers={
        "Accept":"application/json",
        "User-Agent":"MuslimSim-BB35-SeparatePaths/1.0",
    })
    with urllib.request.urlopen(req,timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _resolve_dataref(api_root: str, api_version: str, name: str) -> int:
    q = urllib.parse.urlencode({"filter[name]":name,"limit":100})
    payload = _http_json(f"{api_root}/api/{api_version}/datarefs?{q}")
    items = payload.get("data",[])
    if isinstance(items,dict): items=[items]
    for item in items:
        if isinstance(item,dict) and item.get("name") == name:
            return int(item["id"])
    raise RuntimeError(f"DataRef not found: {name}")


def _resolve_command(api_root: str, api_version: str, name: str) -> int:
    q = urllib.parse.urlencode({"filter[name]":name,"limit":100})
    payload = _http_json(f"{api_root}/api/{api_version}/commands?{q}")
    items = payload.get("data",[])
    if isinstance(items,dict): items=[items]
    for item in items:
        if isinstance(item,dict) and item.get("name") == name:
            return int(item["id"])
    raise RuntimeError(f"Command not found: {name}")


def _decode_text(value: Any) -> str:
    if value is None: return ""
    if not isinstance(value,str): return str(value)
    stripped = value.rstrip("\x00")
    if not stripped: return ""
    try:
        raw = base64.b64decode(stripped.encode("ascii"),validate=True)
        decoded = raw.split(b"\x00",1)[0].decode("utf-8",errors="strict")
        printable = sum(1 for c in decoded if c.isprintable() or c == " ")
        if decoded and printable/max(1,len(decoded)) >= 0.90:
            return decoded
    except (UnicodeEncodeError,UnicodeDecodeError,ValueError,binascii.Error):
        pass
    return stripped


def _scalar(value: Any, fallback: float) -> float:
    if isinstance(value,list):
        if not value: return float(fallback)
        value = value[0]
    try: x=float(value)
    except (TypeError,ValueError): return float(fallback)
    return x if math.isfinite(x) else float(fallback)


class _TriplePeriodDetector:
    def __init__(self, callback: Callable[[], None]):
        self.callback = callback
        self.count = 0
        self.last = 0.0

    def press(self) -> bool:
        now = time.monotonic()
        if self.count and now - self.last > SECRET_GAP:
            self.count = 0
        self.count += 1
        self.last = now
        if self.count >= SECRET_TAPS:
            self.count = 0
            self.callback()
            return True
        return False

    def reset(self) -> None:
        self.count = 0
        self.last = 0.0



class _DoubleSlashDetector:
    """Detect two quick physical SLASH presses without using the FMC path."""

    def __init__(self, callback: Callable[[], None]) -> None:
        self.callback = callback
        self.count = 0
        self.last = 0.0

    def press(self) -> bool:
        now = time.monotonic()

        if self.count and now - self.last > DISPLAY_SLASH_GAP:
            self.count = 0

        self.count += 1
        self.last = now

        if self.count >= DISPLAY_SLASH_TAPS:
            self.count = 0
            self.callback()
            return True

        return False


class BB35PFDPath:
    """Fresh BB35 session for the existing graphical F0 PFD; never sends F2."""
    def __init__(
        self,
        open_pfd: Callable[[], Tuple[Any, Any]],
        pfd_worker: Callable[..., None],
        api_version: str,
        pfd_ids: Dict[str, int],
        refresh_interval: float,
        toggle_callback: Callable[[], None],
        diagnose: bool = False,
        input_router: Optional[Callable[[int, str], bool]] = None,
    ) -> None:
        self.open_pfd = open_pfd
        self.pfd_worker = pfd_worker
        self.api_version = api_version
        self.pfd_ids = pfd_ids
        self.refresh_interval = refresh_interval
        self.toggle_callback = toggle_callback
        self.diagnose = diagnose
        self.input_router = input_router
        self.device = None
        self.canvas = None
        self.stop_evt = threading.Event()
        self.worker = None
        self.keys = None
        self.status = {"frames":0,"error":None,"last_sample_ms":None,"last_render_ms":None,"live":False}
        self.status_lock = threading.Lock()

        # MUSLIMSIM_BB35_OUTPUT_PROGRESS_WATCHDOG_V1
        # Seeded by start(); the shared v46 worker republishes it at the top of
        # every frame, so a stale value means the panel is not being refreshed.
        self.started_monotonic = 0.0

        # Graphical-display page is local to this BB35 PFD session.
        # It is intentionally unrelated to the PERIOD x3 FMC/PFD path router.
        self.display_page_lock = threading.Lock()
        self.display_page = "pfd"

    def set_simulator_connected(self, connected: bool) -> None:
        # Offline and live frames use the same native-F0 owner.  Reconnect is
        # a repaint, not permission to touch the persistent F2 presentation.
        del connected

    def get_display_page(self) -> str:
        with self.display_page_lock:
            return self.display_page

    def _cycle_display_page(self) -> None:
        with self.display_page_lock:
            current = self.display_page
            try:
                index = DISPLAY_PAGE_ORDER.index(current)
            except ValueError:
                index = 0

            self.display_page = DISPLAY_PAGE_ORDER[
                (index + 1) % len(DISPLAY_PAGE_ORDER)
            ]
            page = self.display_page

        print(
            f"BB35 DISPLAY -> {page.upper().replace('_', ' ')} "
            "(SLASH / x2)"
        )

    def start(self) -> None:
        self.stop_evt.clear()
        self.device, self.canvas = self.open_pfd()

        if TRACE_HANDOFF:
            self.device = _TracingDevice(self.device, "BB35 PFD")

            # The canvas holds its own reference to the raw handle, so tracing
            # only self.device misses every graphics write the PFD path makes
            # -- which is the path that matters.
            #
            # And the canvas may be a viewport wrapping another canvas, so
            # walk down to whichever one actually owns the handle.  Setting
            # the outer wrapper's copy changes nothing: it is the inner canvas
            # that writes, which is why this panel's PFD produced no trace at
            # all while the other's produced thousands of reports.
            target = self.canvas
            while getattr(target, "_canvas", None) is not None:
                target = target._canvas

            if getattr(target, "device", None) is not None:
                target.device = self.device

            if target is not self.canvas:
                self.canvas.device = self.device

            print("TRACE BB35 PFD path opened (the open itself is not traced)")

        # PFD PATH RULE: never send F2 from this session.
        # The outgoing FMC path is responsible for blanking its own F2 plane
        # before it closes.  This new PFD path owns only native F0 graphics.

        # Clear the annunciator immediately on ownership transfer.  The live
        # worker may light it only after both Zibo EXEC and aircraft power are
        # confirmed.
        _set_brightness(
            self.device,
            BB35_EXEC_LIGHT_CHANNEL,
            EXEC_LIGHT_OFF,
        )

        # Force the fresh native canvas to repaint the complete PFD surface.
        try:
            self.canvas.colour(6,7,13)
            self.canvas.fill(0,0,640,480)
            self.canvas.command(0x103)
        except Exception:
            pass

        # MUSLIMSIM_BB35_PFD_WORKER_SIGNATURE_COMPAT_V1
        # Adapt historical 8-arg BB35 call to current v46 9-arg worker.
        _pfd_worker_args = (
            self.device,
            self.canvas,
            self.api_version,
            self.pfd_ids,
            self.refresh_interval,
            self.stop_evt,
            self.status,
            self.status_lock,
        )

        try:
            import inspect as _bb35_inspect
            _pfd_worker_count = len(
                _bb35_inspect.signature(self.pfd_worker).parameters
            )
        except Exception:
            _pfd_worker_count = 8

        if _pfd_worker_count >= 9:
            _pfd_worker_args = _pfd_worker_args + (self.get_display_page,)

        if self.diagnose:
            print(
                "BB35 PFD worker launch: "
                f"callback_args={_pfd_worker_count} "
                f"supplied_args={len(_pfd_worker_args)}"
            )

        # MUSLIMSIM_BB35_OUTPUT_PROGRESS_WATCHDOG_V1
        # Seed progress before the worker starts.  Without a seed, a worker
        # that blocks on its very first native write would leave the heartbeat
        # at zero, which the watchdog has to read as "no heartbeat published"
        # rather than as a stall - the exact case that left BB35 frozen.
        _bb35_started = time.monotonic()
        self.started_monotonic = _bb35_started
        with self.status_lock:
            self.status["heartbeat_monotonic"] = _bb35_started

        self.worker = threading.Thread(
            target=self.pfd_worker,
            args=_pfd_worker_args,
            name="BB35-PFD-PATH",
            daemon=True,
        )
        self.keys = threading.Thread(
            target=self._key_reader,
            name="BB35-PFD-SECRET",
            daemon=True,
        )
        self.worker.start()
        self.keys.start()
        if TRACE_HANDOFF and isinstance(self.device, _TracingDevice):
            self.device.report("PFD entry")

        print('BB35 PATH -> PFD (fresh F0-only HID session; PERIOD x3 -> PFP/FMC; SLASH x2 cycles PFD/ND/ENG PRI/MFD/HYD)')

    def _key_reader(self) -> None:
        previous = None
        period_detector = _TriplePeriodDetector(self.toggle_callback)
        slash_detector = _DoubleSlashDetector(self._cycle_display_page)

        while not self.stop_evt.is_set():
            try:
                report = self.device.read(128)
            except Exception:
                return
            if not report:
                self.stop_evt.wait(0.001)
                continue
            bits = _button_bits(bytes(report))
            if bits is None: continue
            if previous is None:
                previous = bits
                continue
            changed = previous ^ bits

            for index in range(96):
                mask = 1 << index
                if not changed & mask:
                    continue
                edge = "press" if bits & mask else "release"
                consumed = False
                if self.input_router is not None:
                    try:
                        consumed = bool(self.input_router(index, edge))
                    except Exception:
                        consumed = False
                if consumed or edge != "press":
                    continue
                if index == SECRET_PERIOD_INDEX:
                    period_detector.press()
                elif index == DISPLAY_SLASH_INDEX:
                    slash_detector.press()

            previous = bits

    def stop(self) -> None:
        self.stop_evt.set()
        if self.keys is not None: self.keys.join(timeout=1.0)
        if self.worker is not None: self.worker.join(timeout=6.0)

        # MUSLIMSIM_BB35_TEARDOWN_SOLE_WRITER_V1
        # The darkening reports below share one hidapi handle with the output
        # worker.  If that worker is still inside a native F0 burst they
        # interleave with it, and the panel is left holding a torn native
        # transaction - which outlives the handle close, so the next Studio
        # start finds a frozen screen that no reopen can clear.  BB36 already
        # guards its own teardown exactly this way.  When the worker exits
        # within its existing 6.0 s join, which is the established case, the
        # writes below are unchanged.
        worker_still_alive = bool(
            self.worker is not None and self.worker.is_alive()
        )
        if worker_still_alive:
            print(
                "BB35 PFD output did not stop within 6.0 s; releasing the "
                "handle without a competing blackout write."
            )

        if TRACE_HANDOFF and isinstance(self.device, _TracingDevice):
            self.device.report("PFD leaving")
        if self.device is not None:
            # Graphics-only PFD path: darken BB35 before releasing the handle.
            if not worker_still_alive:
                try:
                    _set_brightness(
                        self.device,
                        BB35_EXEC_LIGHT_CHANNEL,
                        EXEC_LIGHT_OFF,
                    )
                    _set_brightness(self.device,1,0)
                    _set_brightness(self.device,0,0)
                except Exception:
                    pass
            # Closing the handle after the bounded join is also what unblocks a
            # stalled native write on Windows, so it still happens either way.
            try:
                self.device.close()
            except Exception:
                pass
            if worker_still_alive and self.worker is not None:
                self.worker.join(timeout=1.0)
        self.device = None
        self.canvas = None
        self.worker = None
        self.keys = None


# MUSLIMSIM_BB35_FMC_BLACK_ESCAPE_RECOVERY_V1
class BB35FMCPath:
    """Fresh BB35 session for the original WinCtrl F2 PFP/FMC presentation."""
    def __init__(
        self,
        api_root: str,
        api_version: str,
        font_path: str,
        toggle_callback: Callable[[], None],
        diagnose: bool = False,
        input_router: Optional[Callable[[int, str], bool]] = None,
    ) -> None:
        self.api_root = api_root.rstrip('/')
        self.api_version = api_version
        self.font_path = Path(font_path).expanduser().resolve()
        self.toggle_callback = toggle_callback
        self.diagnose = diagnose
        self.input_router = input_router
        self.device = None
        self.stop_evt = threading.Event()
        self.key_queue: "queue.Queue[Tuple[str,int]]" = queue.Queue()
        self.fmc_state: Dict[str,str] = {}
        self.state_lock = threading.Lock()
        self.dirty = threading.Event()
        self.simulator_connected = threading.Event()
        self.simulator_connected.set()
        self.threads = []
        # True only after the FMC WebSocket has subscribed successfully.
        # The HID reader uses it to provide a PERIOD x3 escape when the
        # transport cannot process the normal secret sequence.
        self.ws_ready = threading.Event()

    def set_simulator_connected(self, connected: bool) -> None:
        """Publish transport state without reopening or power-cycling BB35."""

        if connected:
            self.simulator_connected.set()
        else:
            self.simulator_connected.clear()
            with self.state_lock:
                self.fmc_state.clear()
        self.dirty.set()

    def start(self) -> None:
        if websocket is None:
            raise RuntimeError('websocket-client unavailable')
        if not self.font_path.is_file():
            raise RuntimeError(f'BB35 FMC font missing: {self.font_path}')
        self.stop_evt.clear()
        self.ws_ready.clear()
        self.device = _open_bb35()

        if TRACE_HANDOFF:
            self.device = _TracingDevice(self.device, "BB35 FMC")

        # This path initializes itself completely; it assumes nothing from PFD.
        packets = _load_font_packets(self.font_path)
        print(
            "BB35 PFP/FMC physical layout: "
            f"{PFP_CELL_WIDTH}x{PFP_CELL_HEIGHT} cells, "
            f"grid x={PFP_GRID_X} y={PFP_GRID_Y}"
        )
        for packet in packets:
            self.device.write(list(packet))
        time.sleep(0.20)
        self.device.write(list(_black_packet()))
        self.device.write(list(_grid_packet()))
        for packet in _blank_f2_packets():
            self.device.write(list(packet))
        _set_brightness(self.device,0,0)
        _set_brightness(self.device,1,0)
        _set_brightness(self.device,BB35_EXEC_LIGHT_CHANNEL,EXEC_LIGHT_OFF)

        keypad = threading.Thread(target=self._key_reader,name='BB35-FMC-KEYPAD',daemon=True)
        ws = threading.Thread(target=self._ws_worker,name='BB35-FMC-WS',daemon=True)
        display = threading.Thread(target=self._display_worker,name='BB35-FMC-DISPLAY',daemon=True)
        self.threads = [keypad,ws,display]
        for thread in self.threads: thread.start()
        if TRACE_HANDOFF and isinstance(self.device, _TracingDevice):
            self.device.report("FMC entry")

        print('BB35 PATH -> PFP/FMC (fresh original-F2 HID session; press PERIOD x3 for PFD)')

    def _key_reader(self) -> None:
        previous = None
        offline_period_detector = _TriplePeriodDetector(
            self.toggle_callback
        )

        while not self.stop_evt.is_set():
            try:
                report = self.device.read(128)
            except Exception:
                return

            if not report:
                self.stop_evt.wait(0.001)
                continue

            bits = _button_bits(bytes(report))
            if bits is None:
                continue

            if previous is None:
                previous = bits
                continue

            changed = bits ^ previous
            websocket_ready = self.ws_ready.is_set()

            # Once the normal FMC command path is ready, it owns PERIOD
            # buffering so one or two taps remain ordinary decimal points.
            if websocket_ready:
                offline_period_detector.reset()

            for index in range(96):
                mask = 1 << index
                if not changed & mask:
                    continue

                edge = "press" if bits & mask else "release"

                if (
                    index == SECRET_PERIOD_INDEX
                    and not websocket_ready
                ):
                    # Keep this physical contact visible in Studio even while
                    # the transport is down, but never allow a custom mapping
                    # to consume the emergency display escape.
                    if self.input_router is not None:
                        try:
                            self.input_router(index, edge)
                        except Exception:
                            pass

                    # There is no usable simulator socket on which a normal
                    # decimal point could be sent.  Three quick presses always
                    # remain able to return the hardware to the PFD path.
                    if (
                        edge == "press"
                        and offline_period_detector.press()
                    ):
                        print(
                            "BB35 FMC ESCAPE: PERIOD (.) x3 while "
                            "WebSocket unavailable -> PFD handoff requested"
                        )
                    continue

                self.key_queue.put((edge, index))

            previous = bits

    @staticmethod
    def _send(ws: Any, payload: Dict[str,Any]) -> None:
        ws.send(json.dumps(payload,separators=(',',':')))

    def _resolve_ids(self):
        fmc_ids = {}
        for key,name in FMC_DATAREFS.items():
            try: fmc_ids[key] = _resolve_dataref(self.api_root,self.api_version,name)
            except Exception: pass
        if 'line00_l' not in fmc_ids or 'entry' not in fmc_ids:
            raise RuntimeError('required Zibo FMC1 refs unavailable')
        commands = {}
        names = sorted({a for _l,a in PFP3_KEYS.values() if a and not a.startswith('__')})
        for name in names:
            try: commands[name] = _resolve_command(self.api_root,self.api_version,name)
            except Exception: pass
        try: brightness_id = _resolve_dataref(self.api_root,self.api_version,BRIGHTNESS_REF)
        except Exception: brightness_id = None
        try: power_id = _resolve_dataref(self.api_root,self.api_version,POWER_REF)
        except Exception: power_id = None
        exec_light_id = None
        for name in ZIBO_CAPTAIN_EXEC_LIGHT_DATAREFS:
            try:
                exec_light_id = _resolve_dataref(
                    self.api_root, self.api_version, name
                )
                break
            except Exception:
                pass
        return fmc_ids,commands,brightness_id,power_id,exec_light_id

    def _ws_worker(self) -> None:
        pending_periods = 0
        period_deadline = 0.0
        last_period = 0.0
        req = [1000]
        brightness = 0.85
        last_ws_error = ""
        exec_active = False
        last_exec_output: Optional[int] = None

        def apply_exec_output(powered: bool) -> None:
            nonlocal last_exec_output
            target = exec_light_output_value(
                exec_active,
                simulator_connected=self.simulator_connected.is_set(),
                display_powered=powered,
            )
            if target != last_exec_output and self.device is not None:
                _set_brightness(
                    self.device, BB35_EXEC_LIGHT_CHANNEL, target
                )
                last_exec_output = target

        while not self.stop_evt.is_set():
            if not self.simulator_connected.is_set():
                self.ws_ready.clear()
                pending_periods = 0
                period_deadline = 0.0
                exec_active = False
                apply_exec_output(False)

                # Physical edges from a stopped simulator session must never
                # replay as FMC commands after X-Plane starts again.
                try:
                    while True:
                        self.key_queue.get_nowait()
                except queue.Empty:
                    pass

                self.stop_evt.wait(WS_RECONNECT)
                continue

            ws = None
            powered = False

            try:
                # Re-resolve numeric IDs for every new X-Plane process.
                resolved = tuple(self._resolve_ids())
                if len(resolved) == 5:
                    (
                        fmc_ids,
                        commands,
                        brightness_id,
                        power_id,
                        exec_light_id,
                    ) = resolved
                elif len(resolved) == 4:
                    (
                        fmc_ids,
                        commands,
                        brightness_id,
                        power_id,
                    ) = resolved
                    exec_light_id = None
                elif len(resolved) == 3:
                    # Compatibility with a historical router that predates
                    # the aircraft-power return value.
                    fmc_ids, commands, brightness_id = resolved
                    power_id = None
                    exec_light_id = None
                else:
                    raise RuntimeError(
                        "BB35 FMC ID resolver returned "
                        f"{len(resolved)} values; expected 3, 4 or 5"
                    )

                id_to_key = {
                    str(value): key
                    for key, value in fmc_ids.items()
                }
                brightness_key = (
                    str(brightness_id)
                    if brightness_id is not None
                    else None
                )
                power_key = (
                    str(power_id)
                    if power_id is not None
                    else None
                )
                exec_light_key = (
                    str(exec_light_id)
                    if exec_light_id is not None
                    else None
                )

                ws = websocket.create_connection(
                    f"ws://127.0.0.1:8086/api/{self.api_version}",
                    timeout=1.0,
                    enable_multithread=True,
                )
                ws.settimeout(WS_RECV_TIMEOUT)

                req[0] += 1
                subs = [
                    {"id": int(value)}
                    for value in fmc_ids.values()
                ]
                if brightness_id is not None:
                    subs.append({
                        "id": int(brightness_id),
                        "index": BRIGHTNESS_INDEX,
                    })
                if power_id is not None:
                    subs.append({"id": int(power_id)})
                if exec_light_id is not None:
                    subs.append({"id": int(exec_light_id)})

                self._send(
                    ws,
                    {
                        "req_id": req[0],
                        "type": "dataref_subscribe_values",
                        "params": {"datarefs": subs},
                    },
                )

                # A missing power DataRef must not recreate an inescapable
                # black panel on older bridge/router combinations.  Current
                # builds normally resolve power_id and remain correctly gated.
                if power_id is None:
                    powered = True
                    _set_brightness(self.device, 0, 128)
                    _set_brightness(
                        self.device,
                        1,
                        round(brightness * 255),
                    )
                    print(
                        "BB35 FMC power DataRef unavailable; using "
                        "simulator-connected brightness fallback"
                    )
                apply_exec_output(powered)

                self.ws_ready.set()
                last_ws_error = ""

                if self.diagnose:
                    print(
                        "BB35 FMC WebSocket ready: display, keys, "
                        "PERIOD x3 escape, and power subscription active"
                    )

                while (
                    not self.stop_evt.is_set()
                    and self.simulator_connected.is_set()
                ):
                    now = time.monotonic()

                    # One or two PERIOD taps are ordinary FMC decimal points
                    # after the secret-sequence timeout expires.
                    if pending_periods and now >= period_deadline:
                        period_cmd = commands.get(
                            PFP3_KEYS[SECRET_PERIOD_INDEX][1]
                        )
                        if period_cmd is not None:
                            for _ in range(pending_periods):
                                for active in (True, False):
                                    req[0] += 1
                                    self._send(
                                        ws,
                                        {
                                            "req_id": req[0],
                                            "type": "command_set_is_active",
                                            "params": {
                                                "commands": [{
                                                    "id": period_cmd,
                                                    "is_active": active,
                                                }]
                                            },
                                        },
                                    )
                        pending_periods = 0
                        period_deadline = 0.0

                    processed = 0
                    while processed < 128:
                        try:
                            edge, index = self.key_queue.get_nowait()
                        except queue.Empty:
                            break

                        processed += 1
                        index = int(index)
                        reserved_period = (
                            index == SECRET_PERIOD_INDEX
                        )

                        consumed = False
                        if self.input_router is not None:
                            try:
                                consumed = bool(
                                    self.input_router(index, edge)
                                )
                            except Exception:
                                consumed = False

                        # PERIOD x3 is a hardware lifecycle escape and cannot
                        # be swallowed by Test mode or a profile remapping.
                        if consumed and not reserved_period:
                            continue

                        if reserved_period:
                            if edge != "press":
                                continue

                            current = time.monotonic()
                            if (
                                pending_periods
                                and current - last_period > SECRET_GAP
                            ):
                                period_cmd = commands.get(
                                    PFP3_KEYS[SECRET_PERIOD_INDEX][1]
                                )
                                if period_cmd is not None:
                                    for _ in range(pending_periods):
                                        for active in (True, False):
                                            req[0] += 1
                                            self._send(
                                                ws,
                                                {
                                                    "req_id": req[0],
                                                    "type": "command_set_is_active",
                                                    "params": {
                                                        "commands": [{
                                                            "id": period_cmd,
                                                            "is_active": active,
                                                        }]
                                                    },
                                                },
                                            )
                                pending_periods = 0

                            pending_periods += 1
                            last_period = current
                            period_deadline = current + SECRET_GAP

                            if pending_periods >= SECRET_TAPS:
                                pending_periods = 0
                                period_deadline = 0.0
                                self.toggle_callback()
                            continue

                        # Another key ends an incomplete secret sequence, so
                        # forward the buffered decimal point(s) before it.
                        if edge == "press" and pending_periods:
                            period_cmd = commands.get(
                                PFP3_KEYS[SECRET_PERIOD_INDEX][1]
                            )
                            if period_cmd is not None:
                                for _ in range(pending_periods):
                                    for active in (True, False):
                                        req[0] += 1
                                        self._send(
                                            ws,
                                            {
                                                "req_id": req[0],
                                                "type": "command_set_is_active",
                                                "params": {
                                                    "commands": [{
                                                        "id": period_cmd,
                                                        "is_active": active,
                                                    }]
                                                },
                                            },
                                        )
                            pending_periods = 0
                            period_deadline = 0.0

                        mapping = PFP3_KEYS.get(index)
                        if mapping is None:
                            continue

                        label, action = mapping
                        if action is None:
                            continue

                        if action in (
                            "__brightness_up__",
                            "__brightness_down__",
                        ):
                            if edge != "press":
                                continue

                            delta = (
                                0.1
                                if action.endswith("up__")
                                else -0.1
                            )
                            brightness = max(
                                0.0,
                                min(1.0, brightness + delta),
                            )

                            if brightness_id is not None:
                                req[0] += 1
                                self._send(
                                    ws,
                                    {
                                        "req_id": req[0],
                                        "type": "dataref_set_values",
                                        "params": {
                                            "datarefs": [{
                                                "id": brightness_id,
                                                "index": BRIGHTNESS_INDEX,
                                                "value": brightness,
                                            }]
                                        },
                                    },
                                )

                            _set_brightness(
                                self.device,
                                1,
                                round(brightness * 255)
                                if powered
                                else 0,
                            )
                            continue

                        command_id = commands.get(action)
                        if command_id is None:
                            continue

                        req[0] += 1
                        self._send(
                            ws,
                            {
                                "req_id": req[0],
                                "type": "command_set_is_active",
                                "params": {
                                    "commands": [{
                                        "id": command_id,
                                        "is_active": edge == "press",
                                    }]
                                },
                            },
                        )

                        if edge == "press" and self.diagnose:
                            print(
                                f"BB35 FMC key {index:02d} {label}"
                            )

                    try:
                        raw = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue

                    if not raw:
                        continue

                    message = json.loads(raw)
                    if (
                        message.get("type")
                        != "dataref_update_values"
                    ):
                        continue

                    updates = message.get("data", {})
                    if not isinstance(updates, dict):
                        continue

                    changed = False
                    with self.state_lock:
                        for raw_id, value in updates.items():
                            key = str(raw_id).strip()

                            if (
                                power_key is not None
                                and key == power_key
                            ):
                                new_powered = (
                                    _scalar(value, 0.0) >= 0.5
                                )
                                if new_powered != powered:
                                    powered = new_powered
                                    _set_brightness(
                                        self.device,
                                        0,
                                        128 if powered else 0,
                                    )
                                    _set_brightness(
                                        self.device,
                                        1,
                                        round(brightness * 255)
                                        if powered
                                        else 0,
                                    )
                                    apply_exec_output(powered)
                                continue

                            if (
                                exec_light_key is not None
                                and key == exec_light_key
                            ):
                                exec_active = exec_light_active(value)
                                apply_exec_output(powered)
                                continue

                            if (
                                brightness_key is not None
                                and key == brightness_key
                            ):
                                brightness = max(
                                    0.0,
                                    min(
                                        1.0,
                                        _scalar(value, brightness),
                                    ),
                                )
                                if powered:
                                    _set_brightness(
                                        self.device,
                                        1,
                                        round(brightness * 255),
                                    )
                                continue

                            display_key = id_to_key.get(key)
                            if display_key is None:
                                continue

                            text = _decode_text(value)
                            if self.fmc_state.get(display_key) != text:
                                self.fmc_state[display_key] = text
                                changed = True

                    if changed:
                        self.dirty.set()

            except Exception as exc:
                self.ws_ready.clear()
                pending_periods = 0
                period_deadline = 0.0

                message = f"{type(exc).__name__}: {exc}"
                if (
                    not self.stop_evt.is_set()
                    and (self.diagnose or message != last_ws_error)
                ):
                    print(
                        "BB35 FMC WebSocket reconnect: "
                        + message
                    )
                last_ws_error = message
                self.stop_evt.wait(WS_RECONNECT)

            finally:
                self.ws_ready.clear()
                exec_active = False
                try:
                    apply_exec_output(False)
                except Exception:
                    pass
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass

    def _display_worker(self) -> None:
        previous = None
        last_write = 0.0
        self.dirty.set()
        while not self.stop_evt.is_set():
            self.dirty.wait(0.10)
            if not self.dirty.is_set(): continue
            self.dirty.clear()
            elapsed = time.monotonic() - last_write
            if elapsed < FMC_REFRESH_MIN:
                self.stop_evt.wait(FMC_REFRESH_MIN-elapsed)
                if self.stop_evt.is_set(): return
            with self.state_lock:
                values = dict(self.fmc_state)
            lines,colors = _compose_page(values)
            state=(lines,colors)
            if state == previous: continue
            try:
                for packet in _page_packets(lines,colors):
                    self.device.write(list(packet))
                previous=state
                last_write=time.monotonic()
                if self.diagnose:
                    print('BB35 FMC page -> ' + lines[0].strip())
            except Exception:
                return

    def stop(self) -> None:
        self.stop_evt.set()
        self.ws_ready.clear()
        self.dirty.set()
        for thread in self.threads:
            thread.join(timeout=1.5)
        self.threads = []
        if self.device is not None:
            try:
                _set_brightness(
                    self.device,
                    BB35_EXEC_LIGHT_CHANNEL,
                    EXEC_LIGHT_OFF,
                )
                _set_brightness(self.device,1,0)
                _set_brightness(self.device,0,0)
                # FMC path is the sole owner here. Blank the entire F2 plane
                # before releasing the device to the PFD path.
                for packet in _blank_f2_packets():
                    self.device.write(list(packet))
                self.device.write(list(_black_packet()))
                time.sleep(0.06)
            except Exception:
                pass
            try: self.device.close()
            except Exception: pass
            self.device = None


class MuslimSimBB35PathRouter:
    """Supervisor that runs exactly one BB35 path at a time."""
    def __init__(
        self,
        api_root: str,
        api_version: str,
        font_path: str,
        open_pfd: Callable[[], Tuple[Any,Any]],
        pfd_worker: Callable[...,None],
        pfd_ids: Dict[str,int],
        pfd_refresh: float,
        diagnose: bool = False,
        input_router: Optional[Callable[[int, str], bool]] = None,
    ) -> None:
        self.api_root = api_root
        self.api_version = api_version
        self.font_path = font_path
        self.open_pfd = open_pfd
        self.pfd_worker = pfd_worker
        self.pfd_ids = pfd_ids
        self.pfd_refresh = pfd_refresh
        self.diagnose = diagnose
        self.input_router = input_router
        self.stop_evt = threading.Event()
        self.toggle_evt = threading.Event()
        self.supervisor = None
        self.active = None
        self.mode = 'pfd'
        self.simulator_connected = True

    def set_simulator_connected(self, connected: bool) -> None:
        """Tell the current sole display owner whether X-Plane is alive."""

        self.simulator_connected = bool(connected)
        active = self.active
        if active is not None and hasattr(active, "set_simulator_connected"):
            active.set_simulator_connected(self.simulator_connected)

    def request_toggle(self) -> None:
        # Both BB35 display paths call this only after the physical PERIOD key
        # completes the three-tap lifecycle sequence.
        print(
            "BB35 SECRET: PERIOD (.) x3 -> full PFD/FMC path handoff requested"
        )
        self.toggle_evt.set()

    def start(self) -> None:
        if self.supervisor is not None and self.supervisor.is_alive(): return
        self.stop_evt.clear()
        # stop() sets toggle_evt only to wake the supervisor.  That wake-up
        # must never survive into a later device/profile restart or the first
        # supervisor pass silently changes PFD into FMC/practice mode.
        self.toggle_evt.clear()
        self.supervisor = threading.Thread(target=self._run,name='BB35-PATH-ROUTER',daemon=True)
        self.supervisor.start()

    def _make_path(self):
        if self.mode == 'pfd':
            path = BB35PFDPath(
                self.open_pfd,self.pfd_worker,self.api_version,self.pfd_ids,
                self.pfd_refresh,self.request_toggle,self.diagnose,self.input_router,
            )
        else:
            path = BB35FMCPath(
                self.api_root,self.api_version,self.font_path,
                self.request_toggle,self.diagnose,self.input_router,
            )
        if hasattr(path, "set_simulator_connected"):
            path.set_simulator_connected(self.simulator_connected)
        return path

    def studio_snapshot(self) -> Dict[str, Any]:
        """Return a read-only view of the page the real PFP path owns."""

        active = self.active
        snapshot: Dict[str, Any] = {"mode": self.mode, "state": "starting"}
        if active is None:
            return snapshot
        if isinstance(active, BB35FMCPath):
            with active.state_lock:
                values = dict(active.fmc_state)
            if not self.simulator_connected:
                lines, _colors = _bb35_simulator_offline_page()
            else:
                lines, _colors = _compose_page(values)
            snapshot.update({
                "state": "fmc",
                "lines": list(lines),
                "standby": "SIM STOPPED" if not self.simulator_connected else "",
            })
            return snapshot
        if isinstance(active, BB35PFDPath):
            with active.status_lock:
                status = dict(active.status)
            snapshot.update({
                "state": "pfd",
                "page": active.get_display_page(),
                "pfd": status.get("mirror", {}),
                "live": bool(status.get("live")),
                "frames": int(status.get("frames", 0) or 0),
                "detail": str(status.get("error") or ""),
            })
        return snapshot

    def _run(self) -> None:
        while not self.stop_evt.is_set():
            try:
                self.active = self._make_path()
                self.active.start()
            except Exception as exc:
                self.active = None
                if not self.stop_evt.is_set():
                    print(f'BB35 {self.mode.upper()} path start failed: {exc}; retrying')
                    self.stop_evt.wait(1.0)
                continue

            while not self.stop_evt.is_set() and not self.toggle_evt.wait(0.05):
                pass

            if self.stop_evt.is_set():
                break

            self.toggle_evt.clear()
            old_mode = self.mode

            # Full lifecycle teardown before the other path is even created.
            if self.active is not None:
                self.active.stop()
                self.active = None

            self.stop_evt.wait(HANDOFF_SETTLE)
            if self.stop_evt.is_set(): break

            self.mode = 'fmc' if old_mode == 'pfd' else 'pfd'
            print(f'BB35 HANDOFF: {old_mode.upper()} -> {self.mode.upper()}')

        if self.active is not None:
            self.active.stop()
            self.active = None

    def stop(self) -> None:
        self.stop_evt.set()
        self.toggle_evt.set()
        if self.supervisor is not None:
            self.supervisor.join(timeout=8.0)
        self.supervisor = None

# MUSLIMSIM_BB35_SECRET_TRIGGERS_RESTORED_V1
# MUSLIMSIM_BB35_ROUTER_CONTRACT_RECOVERY_V1
# Preserve the original, feature-complete router as the base contract.
_MuslimSimBB35PathRouterContractBase = MuslimSimBB35PathRouter


class MuslimSimBB35PathRouter(_MuslimSimBB35PathRouterContractBase):
    # Original BB35 router contract plus physical USB hotplug supervision.

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # The restored base owns input_router, studio_snapshot(), path creation,
        # button routing, and every established PFD/FMC behavior.
        super().__init__(*args, **kwargs)
        self._usb_status_lock = threading.Lock()
        self._usb_status = "starting"
        self._usb_status_detail = ""

    def _get_usb_status(self) -> Tuple[str, str]:
        # Do not override any original router ``status`` attribute/property.
        # The restored base contract remains authoritative for its own API.
        with self._usb_status_lock:
            return self._usb_status, self._usb_status_detail

    def _set_usb_status(self, state: str, detail: str = "") -> None:
        with self._usb_status_lock:
            self._usb_status = str(state)
            self._usb_status_detail = str(detail)

    def _active_is_healthy(self) -> bool:
        active = self.active

        if active is None or not _bb35_present():
            return False

        worker = getattr(active, "worker", None)
        keys = getattr(active, "keys", None)
        if worker is not None or keys is not None:
            if not (
                worker is not None
                and worker.is_alive()
                and keys is not None
                and keys.is_alive()
            ):
                return False

            # MUSLIMSIM_BB35_OUTPUT_PROGRESS_WATCHDOG_V1
            # is_alive() cannot see a worker parked inside a native F0 write to
            # a stalled panel, so BB35 was reported live while its screen was
            # frozen and the router never reopened it.  The shared v46 worker
            # already publishes a frame-start heartbeat; read it.
            return self._output_is_progressing(active)

        threads = getattr(active, "threads", None)
        if isinstance(threads, list):
            return bool(threads) and all(
                thread.is_alive() for thread in threads
            )

        return True

    @staticmethod
    def _output_is_progressing(active: Any) -> bool:
        """False only once the graphical worker has stopped producing frames."""

        started = float(getattr(active, "started_monotonic", 0.0) or 0.0)
        now = time.monotonic()
        if started <= 0.0 or now - started < BB35_PFD_STARTUP_GRACE_SECONDS:
            return True

        try:
            with active.status_lock:
                heartbeat = float(
                    active.status.get("heartbeat_monotonic", 0.0) or 0.0
                )
        except Exception:
            return True

        if heartbeat <= 0.0:
            # A worker build that publishes no heartbeat keeps its historical
            # is_alive()-only contract rather than being restarted blindly.
            return True

        age = now - heartbeat
        if age <= BB35_PFD_PROGRESS_TIMEOUT_SECONDS:
            return True

        print(
            "BB35 PFD output heartbeat stale "
            f"{age:.1f}s; the panel is no longer being refreshed"
        )
        return False

    def _stop_active_path(self) -> None:
        active = self.active
        self.active = None

        if active is None:
            return

        try:
            active.stop()
        except Exception as exc:
            if self.diagnose:
                print(f"BB35 active-path stop warning: {exc}")

    def live_snapshot(self) -> Dict[str, Any]:
        # Physical USB truth for the private control service.
        present = _bb35_present()

        if not present:
            return {
                "state": "offline",
                "connected": False,
                "usb_connected": False,
                "mode": str(self.mode),
                "values": {},
                "detail": "WINCTRL 3N PFP CAPTAIN BB35 is disconnected",
            }

        if self.active is None:
            usb_state, usb_detail = self._get_usb_status()
            return {
                "state": usb_state,
                "connected": False,
                "usb_connected": True,
                "mode": str(self.mode),
                "values": {},
                "detail": usb_detail,
            }

        pfd_status: Dict[str, Any] = {}
        active_status = getattr(self.active, "status", None)
        active_status_lock = getattr(self.active, "status_lock", None)

        if isinstance(active_status, dict):
            try:
                if active_status_lock is not None:
                    with active_status_lock:
                        pfd_status = dict(active_status)
                else:
                    pfd_status = dict(active_status)
            except Exception:
                pfd_status = {}

        _usb_state, usb_detail = self._get_usb_status()
        return {
            "state": str(self.mode),
            "connected": True,
            "usb_connected": True,
            "mode": str(self.mode),
            "status": pfd_status,
            "detail": usb_detail,
        }

    def service_snapshot(self) -> Dict[str, Any]:
        # One authoritative status object for MuslimSim Studio.
        snapshot = self.live_snapshot()

        if not snapshot.get("usb_connected", False):
            snapshot["mirror"] = {
                "state": "offline",
                "lines": [],
            }
            return snapshot

        try:
            mirror = self.studio_snapshot()
        except Exception as exc:
            mirror = {}
            snapshot["detail"] = (
                f"{snapshot.get('detail') or ''} "
                f"Studio mirror error: {exc}"
            ).strip()

        snapshot["mirror"] = (
            dict(mirror) if isinstance(mirror, dict) else {}
        )
        return snapshot

    def start(self) -> None:
        if (
            self.supervisor is not None
            and self.supervisor.is_alive()
        ):
            return

        self.stop_evt.clear()
        self.toggle_evt.clear()
        self._set_usb_status("starting")
        self.supervisor = threading.Thread(
            target=self._run,
            name="BB35-PATH-ROUTER",
            daemon=True,
        )
        self.supervisor.start()

    def _run(self) -> None:
        while not self.stop_evt.is_set():
            if not _bb35_present():
                self._set_usb_status(
                    "waiting-for-pfp3n",
                    "WINCTRL 3N PFP CAPTAIN BB35 is disconnected",
                )
                self.stop_evt.wait(BB35_USB_POLL_SECONDS)
                continue

            try:
                self._set_usb_status(
                    "connecting",
                    f"Opening BB35 {str(self.mode).upper()} path",
                )

                # This is the restored original path factory. It preserves
                # input_router and every existing Studio/key integration.
                self.active = self._make_path()
                self.active.start()

                self._set_usb_status(
                    "connected",
                    f"BB35 {str(self.mode).upper()} path live",
                )
            except Exception as exc:
                self._stop_active_path()

                if not self.stop_evt.is_set():
                    self._set_usb_status(
                        "reconnecting",
                        f"{type(exc).__name__}: {exc}",
                    )
                    print(
                        f"BB35 {str(self.mode).upper()} path start failed: "
                        f"{exc}; retrying"
                    )
                    self.stop_evt.wait(1.0)
                continue

            reason = ""

            while not self.stop_evt.is_set():
                if self.toggle_evt.wait(BB35_USB_POLL_SECONDS):
                    reason = "toggle"
                    break

                if not _bb35_present():
                    reason = "usb-disconnected"
                    break

                if not self._active_is_healthy():
                    reason = "path-failed"
                    break

            if self.stop_evt.is_set():
                break

            if reason in {"usb-disconnected", "path-failed"}:
                if reason == "usb-disconnected":
                    state = "waiting-for-pfp3n"
                    detail = (
                        "WINCTRL 3N PFP CAPTAIN BB35 USB disconnected"
                    )
                else:
                    state = "reconnecting"
                    detail = (
                        f"BB35 {str(self.mode).upper()} "
                        "worker exited unexpectedly"
                    )

                self._set_usb_status(state, detail)
                print(
                    detail
                    + "; closing the failed path and preserving the same mode"
                )
                self._stop_active_path()

                while (
                    not self.stop_evt.is_set()
                    and not _bb35_present()
                ):
                    self._set_usb_status(
                        "waiting-for-pfp3n",
                        "WINCTRL 3N PFP CAPTAIN BB35 is disconnected",
                    )
                    self.stop_evt.wait(BB35_USB_POLL_SECONDS)

                if self.stop_evt.is_set():
                    break

                self._set_usb_status(
                    "reconnecting",
                    f"BB35 USB present; reopening "
                    f"{str(self.mode).upper()} path",
                )
                print(
                    "BB35 USB reconnected -> reopening "
                    f"{str(self.mode).upper()} path"
                )
                self.stop_evt.wait(BB35_USB_RECONNECT_SETTLE)

                # Hotplug never changes PFD/FMC mode.
                continue

            # PERIOD x3 remains the only PFD/FMC mode transition.
            self.toggle_evt.clear()
            old_mode = str(self.mode)

            self._set_usb_status(
                "handoff",
                f"{old_mode.upper()} path closing",
            )
            self._stop_active_path()

            self.stop_evt.wait(HANDOFF_SETTLE)
            if self.stop_evt.is_set():
                break

            self.mode = "fmc" if old_mode == "pfd" else "pfd"
            print(
                f"BB35 HANDOFF: {old_mode.upper()} -> "
                f"{str(self.mode).upper()}"
            )

        self._stop_active_path()
        self._set_usb_status("stopped")

    def stop(self) -> None:
        self._set_usb_status("stopping")
        self.stop_evt.set()
        self.toggle_evt.set()

        if self.supervisor is not None:
            self.supervisor.join(timeout=8.0)

        self.supervisor = None



def run_self_test() -> None:
    if (PFP_CELL_WIDTH, PFP_CELL_HEIGHT) != (23, 32):
        raise AssertionError("PFP3N font cell geometry must be 23x32")
    if PFP_GRID_Y != 10:
        raise AssertionError("PFP3N calibrated Y origin must be 10")
    if SECRET_TAPS != 3:
        raise AssertionError("BB35 path switch must require exactly three PERIOD presses")
    if DISPLAY_SLASH_INDEX != 69 or DISPLAY_SLASH_TAPS != 2:
        raise AssertionError("BB35 display-page switch must be SLASH index 69 x2")
    if SECRET_PERIOD_INDEX != 38:
        raise AssertionError("secret period hardware index changed")
    if PFP3_KEYS[SECRET_PERIOD_INDEX][1] != "laminar/B738/button/fmc1_period":
        raise AssertionError("PERIOD Zibo mapping invalid")
    if PFP3_KEYS[24][1] != "laminar/B738/button/fmc1_exec":
        raise AssertionError("EXEC mapping invalid")
    if PFP3_KEYS[70][1] != "laminar/B738/button/fmc1_clr":
        raise AssertionError("CLR mapping invalid")
    if BB35_EXEC_LIGHT_CHANNEL != 16:
        raise AssertionError("BB35 EXEC annunciator must remain channel 16")
    if not exec_light_active([1.0]) or exec_light_active(float("nan")):
        raise AssertionError("BB35 EXEC indication must remain discrete")
    if (
        exec_light_output_value(
            1.0, simulator_connected=False, display_powered=True
        ) != EXEC_LIGHT_OFF
        or exec_light_output_value(
            1.0, simulator_connected=True, display_powered=False
        ) != EXEC_LIGHT_OFF
        or exec_light_output_value(
            1.0, simulator_connected=True, display_powered=True
        ) != EXEC_LIGHT_ON
    ):
        raise AssertionError("BB35 EXEC alert escaped Live output authority")

    class _ExecPacketDevice:
        def __init__(self) -> None:
            self.writes = []

        def write(self, report: Any) -> int:
            packet = bytes(report)
            self.writes.append(packet)
            return len(packet)

    exec_device = _ExecPacketDevice()
    _set_brightness(
        exec_device,
        BB35_EXEC_LIGHT_CHANNEL,
        EXEC_LIGHT_ON,
    )
    if (
        len(exec_device.writes) != 1
        or exec_device.writes[0][1] != BB35_IDENTIFIER
        or exec_device.writes[0][6:9]
        != bytes((0x49, BB35_EXEC_LIGHT_CHANNEL, EXEC_LIGHT_ON))
    ):
        raise AssertionError("BB35 EXEC annunciator packet is invalid")

    report = bytearray(64)
    report[0] = 1
    report[1 + SECRET_PERIOD_INDEX // 8] = 1 << (SECRET_PERIOD_INDEX % 8)
    if _button_bits(bytes(report)) != (1 << SECRET_PERIOD_INDEX):
        raise AssertionError("button decoder invalid")

    lines, colors = _compose_page({
        "line00_l": "MENU",
        "entry": "ABC",
    })
    if len(lines) != PFP_ROWS or any(len(line) != PFP_COLUMNS for line in lines):
        raise AssertionError("FMC page geometry invalid")

    packets = _page_packets(lines, colors)
    if len(packets) != 16 or any(len(packet) != PACKET_SIZE for packet in packets):
        raise AssertionError("FMC F2 packet geometry invalid")
    if any(packet[0] != F2_ID for packet in packets):
        raise AssertionError("FMC page must use the F2 report ID")

    pfd_path = BB35PFDPath(
        lambda: (None, None), lambda *args: None, "v3", {}, 0.10,
        lambda: None,
    )
    pfd_path.set_simulator_connected(True)
    if pfd_path.get_display_page() != "pfd":
        raise AssertionError("BB35 reconnect changed its persistent F0 page")

    stable_router = MuslimSimBB35PathRouter(
        "http://127.0.0.1:8086", "v3", ".",
        lambda: (None, None), lambda *args: None, {}, 0.10,
    )
    stable_router.request_toggle()
    if not stable_router.toggle_evt.is_set() or stable_router.mode != "pfd":
        raise AssertionError("BB35 PERIOD x3 must request the PFD/FMC handoff")
    stable_router.toggle_evt.clear()

    restart_router = MuslimSimBB35PathRouter(
        "http://127.0.0.1:8086", "v3", ".",
        lambda: (None, None), lambda *args: None, {}, 0.10,
    )
    restart_router.toggle_evt.set()
    restart_router._run = lambda: None
    restart_router.start()
    restart_router.supervisor.join(timeout=1.0)
    if restart_router.toggle_evt.is_set() or restart_router.mode != "pfd":
        raise AssertionError("BB35 device restart must preserve PFD mode")

    # Triple-period detector must switch on the third press, not before.
    callbacks = []
    detector = _TriplePeriodDetector(lambda: callbacks.append("toggle"))
    if detector.press():
        raise AssertionError("first PERIOD press toggled too early")
    if detector.press():
        raise AssertionError("second PERIOD press toggled too early")
    if not detector.press():
        raise AssertionError("third PERIOD press did not request a toggle")
    if callbacks != ["toggle"]:
        raise AssertionError("triple PERIOD callback count is incorrect")

    offline_path = BB35FMCPath(
        "http://127.0.0.1:8086", "v3", ".", lambda: None
    )
    offline_path.fmc_state["line00_l"] = "STALE"
    offline_path.set_simulator_connected(False)
    if offline_path.simulator_connected.is_set() or offline_path.fmc_state:
        raise AssertionError("BB35 disconnect must clear its stale FMC cache")
