#!/usr/bin/env python3
"""MuslimSim WINCTRL 32 MCDU CAPTAIN (VID 4098 / PID BB36).

Integrated device module for the single MuslimSim bridge process.

Architecture
------------
BB36 HID keypad -> dedicated 1 ms HID reader -> queued edges
                 -> X-Plane WebSocket command press/release

Zibo FMC1 strings -> one X-Plane WebSocket subscription (10 Hz changed values)
                  -> in-memory FMC page cache
                  -> dirty-only 24 x 14 BB36 LCD redraw

The module never opens BB35 and never owns PU OVHD, throttle, AGP, or pedals.
If BB36 is absent/disconnected, the manager waits/reconnects without stopping
any other MuslimSim hardware.
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
from typing import Any, Dict, Optional, Tuple

try:
    import hid
except ImportError:
    hid = None

try:
    import websocket
except ImportError:
    websocket = None


MCDU_VID = 0x4098
MCDU_PID = 0xBB36
MCDU_IDENTIFIER = 0x32
MCDU_FAMILY = 0xBB
MCDU_COLUMNS = 24
MCDU_ROWS = 14
MCDU_PACKET_SIZE = 64
MCDU_F2_REPORT_ID = 0xF2
MCDU_F2_PAYLOAD_SIZE = 63
MCDU_GRID_X = 0x34
MCDU_GRID_Y = 0x25
MCDU_BRIGHTNESS_DATAREF = "laminar/B738/electric/instrument_brightness"
MCDU_BRIGHTNESS_INDEX = 10
MCDU_RECONNECT_SECONDS = 1.0
MCDU_WS_RECONNECT_SECONDS = 0.50
MCDU_WS_RECV_TIMEOUT = 0.01
MCDU_DISPLAY_MIN_INTERVAL = 0.045

COLOR_BLACK = 0x0000
COLOR_AMBER = 0x0021
COLOR_WHITE = 0x0042
COLOR_CYAN = 0x0063
COLOR_GREEN = 0x0084
COLOR_MAGENTA = 0x00A5
COLOR_RED = 0x00C6
COLOR_YELLOW = 0x00E7
COLOR_GREY = 0x0129

# The same Zibo captain FMC layers proven in the standalone WebSocket v4 test.
MCDU_FMC_DATAREFS: Dict[str, str] = {
    "line00_l": "laminar/B738/fmc1/Line00_L",
    "line00_s": "laminar/B738/fmc1/Line00_S",
    "entry": "laminar/B738/fmc1/Line_entry",
    "entry_i": "laminar/B738/fmc1/Line_entry_I",
}
for _line in range(1, 7):
    MCDU_FMC_DATAREFS[f"line{_line:02d}_x"] = f"laminar/B738/fmc1/Line{_line:02d}_X"
    for _layer in ("L", "S", "I", "M"):
        MCDU_FMC_DATAREFS[f"line{_line:02d}_{_layer.lower()}"] = (
            f"laminar/B738/fmc1/Line{_line:02d}_{_layer}"
        )

# Exact HARDWARE_MCDU physical-index map translated through the public
# WinCtrl Zibo profile. None deliberately means "no Zibo assignment".
MCDU_KEY_MAP: Dict[int, Tuple[str, Optional[str]]] = {
    0:("LSK1L","laminar/B738/button/fmc1_1L"), 1:("LSK2L","laminar/B738/button/fmc1_2L"),
    2:("LSK3L","laminar/B738/button/fmc1_3L"), 3:("LSK4L","laminar/B738/button/fmc1_4L"),
    4:("LSK5L","laminar/B738/button/fmc1_5L"), 5:("LSK6L","laminar/B738/button/fmc1_6L"),
    6:("LSK1R","laminar/B738/button/fmc1_1R"), 7:("LSK2R","laminar/B738/button/fmc1_2R"),
    8:("LSK3R","laminar/B738/button/fmc1_3R"), 9:("LSK4R","laminar/B738/button/fmc1_4R"),
    10:("LSK5R","laminar/B738/button/fmc1_5R"), 11:("LSK6R","laminar/B738/button/fmc1_6R"),
    12:("DIR -> LEGS","laminar/B738/button/fmc1_legs"),
    13:("PROG","laminar/B738/button/fmc1_prog"),
    14:("PERF -> N1 LIMIT","laminar/B738/button/fmc1_n1_lim"),
    15:("INIT -> INIT REF","laminar/B738/button/fmc1_init_ref"),
    16:("DATA",None), 17:("EMPTY TOP RIGHT -> EXEC","laminar/B738/button/fmc1_exec"),
    18:("BRIGHTNESS UP","__brightness_up__"),
    19:("F-PLN -> LEGS","laminar/B738/button/fmc1_legs"),
    20:("RAD NAV",None), 21:("FUEL PRED",None),
    22:("SEC F-PLN -> RTE","laminar/B738/button/fmc1_rte"), 23:("ATC COMM",None),
    24:("MENU","laminar/B738/button/fmc1_menu"),
    25:("BRIGHTNESS DOWN","__brightness_down__"),
    26:("AIRPORT -> DEP/ARR","laminar/B738/button/fmc1_dep_app"),
    27:("EMPTY BOTTOM LEFT -> FIX","laminar/B738/button/fmc1_fix"),
    28:("PREV PAGE","laminar/B738/button/fmc1_prev_page"), 29:("PAGE UP",None),
    30:("NEXT PAGE","laminar/B738/button/fmc1_next_page"), 31:("PAGE DOWN",None),
    32:("1","laminar/B738/button/fmc1_1"), 33:("2","laminar/B738/button/fmc1_2"),
    34:("3","laminar/B738/button/fmc1_3"), 35:("4","laminar/B738/button/fmc1_4"),
    36:("5","laminar/B738/button/fmc1_5"), 37:("6","laminar/B738/button/fmc1_6"),
    38:("7","laminar/B738/button/fmc1_7"), 39:("8","laminar/B738/button/fmc1_8"),
    40:("9","laminar/B738/button/fmc1_9"), 41:(".","laminar/B738/button/fmc1_period"),
    42:("0","laminar/B738/button/fmc1_0"), 43:("+/-","laminar/B738/button/fmc1_minus"),
    44:("A","laminar/B738/button/fmc1_A"), 45:("B","laminar/B738/button/fmc1_B"),
    46:("C","laminar/B738/button/fmc1_C"), 47:("D","laminar/B738/button/fmc1_D"),
    48:("E","laminar/B738/button/fmc1_E"), 49:("F","laminar/B738/button/fmc1_F"),
    50:("G","laminar/B738/button/fmc1_G"), 51:("H","laminar/B738/button/fmc1_H"),
    52:("I","laminar/B738/button/fmc1_I"), 53:("J","laminar/B738/button/fmc1_J"),
    54:("K","laminar/B738/button/fmc1_K"), 55:("L","laminar/B738/button/fmc1_L"),
    56:("M","laminar/B738/button/fmc1_M"), 57:("N","laminar/B738/button/fmc1_N"),
    58:("O","laminar/B738/button/fmc1_O"), 59:("P","laminar/B738/button/fmc1_P"),
    60:("Q","laminar/B738/button/fmc1_Q"), 61:("R","laminar/B738/button/fmc1_R"),
    62:("S","laminar/B738/button/fmc1_S"), 63:("T","laminar/B738/button/fmc1_T"),
    64:("U","laminar/B738/button/fmc1_U"), 65:("V","laminar/B738/button/fmc1_V"),
    66:("W","laminar/B738/button/fmc1_W"), 67:("X","laminar/B738/button/fmc1_X"),
    68:("Y","laminar/B738/button/fmc1_Y"), 69:("Z","laminar/B738/button/fmc1_Z"),
    70:("/","laminar/B738/button/fmc1_slash"), 71:("SPACE","laminar/B738/button/fmc1_SP"),
    72:("OVERFLY -> DEL","laminar/B738/button/fmc1_del"),
    73:("CLR","laminar/B738/button/fmc1_clr"),
}


def _http_json(api_root: str, url: str, timeout: float = 1.0) -> Any:
    req = urllib.request.Request(
        url,
        headers={"Accept":"application/json", "User-Agent":"MuslimSim-BB36-MCDU/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _resolve_dataref_id(api_root: str, api_version: str, name: str) -> int:
    query = urllib.parse.urlencode({"filter[name]":name, "limit":100})
    payload = _http_json(api_root, f"{api_root}/api/{api_version}/datarefs?{query}")
    items = payload.get("data", [])
    if isinstance(items, dict):
        items = [items]
    for item in items:
        if isinstance(item, dict) and item.get("name") == name:
            return int(item["id"])
    raise RuntimeError(f"DataRef not found: {name}")


def _resolve_command_id(api_root: str, api_version: str, name: str) -> int:
    query = urllib.parse.urlencode({"filter[name]":name, "limit":100})
    payload = _http_json(api_root, f"{api_root}/api/{api_version}/commands?{query}")
    items = payload.get("data", [])
    if isinstance(items, dict):
        items = [items]
    for item in items:
        if isinstance(item, dict) and item.get("name") == name:
            return int(item["id"])
    raise RuntimeError(f"Command not found: {name}")


def _decode_possible_base64_text(text: str) -> str:
    stripped = str(text).rstrip("\x00")
    if not stripped:
        return ""
    try:
        raw = base64.b64decode(stripped.encode("ascii"), validate=True)
        decoded = raw.split(b"\x00", 1)[0].decode("utf-8", errors="strict")
    except (UnicodeEncodeError, UnicodeDecodeError, ValueError, binascii.Error):
        return stripped
    printable = sum(1 for char in decoded if char.isprintable() or char == " ")
    return decoded if decoded and printable / max(1, len(decoded)) >= 0.90 else stripped


def _ws_decode_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _decode_possible_base64_text(value)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).split(b"\x00", 1)[0].decode("utf-8", errors="replace")
    if isinstance(value, list):
        if value and all(isinstance(item, int) for item in value):
            raw = bytes(max(0, min(255, int(item))) for item in value)
            return raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
        if len(value) == 1:
            return _ws_decode_text(value[0])
    return str(value)


def _ws_scalar(value: Any, fallback: float = 0.0) -> float:
    if isinstance(value, list):
        if not value:
            return float(fallback)
        value = value[0]
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return float(fallback)
    return numeric if math.isfinite(numeric) else float(fallback)


def _normalize_24(value: str) -> str:
    value = str(value or "").replace("\r", " ").replace("\n", " ")
    cleaned = []
    for char in value:
        code = ord(char)
        if 0x20 <= code <= 0x7E:
            cleaned.append(char)
        elif char == "°":
            cleaned.append("o")
        else:
            cleaned.append(" ")
    return "".join(cleaned)[:MCDU_COLUMNS].ljust(MCDU_COLUMNS)


def _overlay_coloured(base_text: str, base_colors: Tuple[int, ...], overlay: str, color: int):
    chars = list(_normalize_24(base_text))
    colors = list(base_colors)
    overlay = _normalize_24(overlay)
    for index, char in enumerate(overlay):
        if char != " ":
            chars[index] = char
            colors[index] = color
    return "".join(chars), tuple(colors)


def _compose_zibo_page(values: Dict[str, str]):
    lines = [" " * MCDU_COLUMNS for _ in range(MCDU_ROWS)]
    colors = [tuple([COLOR_WHITE] * MCDU_COLUMNS) for _ in range(MCDU_ROWS)]

    title_chars = list(_normalize_24(values.get("line00_l", "")))
    small_title = _normalize_24(values.get("line00_s", ""))
    for i, char in enumerate(small_title):
        if char != " ":
            title_chars[i] = char
    lines[0] = "".join(title_chars)

    for number in range(1, 7):
        label_row = 1 + (number - 1) * 2
        content_row = label_row + 1
        lines[label_row] = _normalize_24(values.get(f"line{number:02d}_x", ""))
        colors[label_row] = tuple([COLOR_CYAN] * MCDU_COLUMNS)
        text = _normalize_24(values.get(f"line{number:02d}_l", ""))
        row_colors = tuple([COLOR_WHITE] * MCDU_COLUMNS)
        text, row_colors = _overlay_coloured(text, row_colors, values.get(f"line{number:02d}_s", ""), COLOR_CYAN)
        text, row_colors = _overlay_coloured(text, row_colors, values.get(f"line{number:02d}_i", ""), COLOR_AMBER)
        text, row_colors = _overlay_coloured(text, row_colors, values.get(f"line{number:02d}_m", ""), COLOR_MAGENTA)
        lines[content_row] = text
        colors[content_row] = row_colors

    scratch = _normalize_24(values.get("entry", ""))
    scratch_colors = tuple([COLOR_WHITE] * MCDU_COLUMNS)
    scratch, scratch_colors = _overlay_coloured(scratch, scratch_colors, values.get("entry_i", ""), COLOR_AMBER)
    lines[13] = scratch
    colors[13] = scratch_colors
    return tuple(lines), tuple(colors)


def _read_font_packets(font_path: Path):
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
            raise ValueError("MCDU font ends inside a packet")
        packet = bytes(raw[offset:end])
        offset = end
        packet += b"\x00" * (MCDU_PACKET_SIZE - len(packet))
        packets.append(packet[:MCDU_PACKET_SIZE])
    if not packets or offset != len(raw):
        raise ValueError("MCDU font is malformed or has trailing data")
    combined = b"".join(packets)
    signature = bytes((0x08,0,0,0,MCDU_GRID_X,0,MCDU_GRID_Y,0,MCDU_ROWS,0,MCDU_COLUMNS,0))
    if b"\x32\xBB" not in combined or signature not in combined:
        raise ValueError("Font is not the original native 32/BB 24x14 MCDU resource")
    return tuple(packets)


def _black_background_packet() -> bytes:
    packet = bytearray(MCDU_PACKET_SIZE)
    packet[:16] = bytes((0xF0,0,0x03,0x12,MCDU_IDENTIFIER,MCDU_FAMILY,0,0,0x04,0x01,0,0,0xFD,0x24,0x07,0))
    packet[16:22] = bytes((0,1,0,0,0,0x0E))
    return bytes(packet)


def _text_grid_packet() -> bytes:
    packet = bytearray(MCDU_PACKET_SIZE)
    packet[:4] = bytes((0xF0,0,0,0x2A))
    p = 4
    packet[p:p+25] = bytes((MCDU_IDENTIFIER,MCDU_FAMILY,0,0,0x18,0x01,0,0,0,0,0,0,0,0x08,0,0,0,MCDU_GRID_X,0,MCDU_GRID_Y,0,MCDU_ROWS,0,MCDU_COLUMNS,0))
    c = 29
    packet[c:c+17] = bytes((MCDU_IDENTIFIER,MCDU_FAMILY,0,0,0x05,0x01,0,0,0,0,0,0,0x01,0,0,0,0))
    return bytes(packet)


def _set_brightness(device: Any, channel: int, brightness: int) -> None:
    device.write([0x02,MCDU_IDENTIFIER,MCDU_FAMILY,0,0,0x03,0x49,int(channel)&0xFF,max(0,min(255,int(brightness))),0,0,0,0,0])


def _page_packets(lines, colors):
    payload = bytearray()
    for row_index, line in enumerate(lines):
        text = _normalize_24(line)
        row_colors = colors[row_index]
        for index, char in enumerate(text):
            color = int(row_colors[index])
            payload.extend((color & 0xFF, (color >> 8) & 0xFF, ord(char)))
    packets = []
    while payload:
        chunk = payload[:MCDU_F2_PAYLOAD_SIZE]
        del payload[:MCDU_F2_PAYLOAD_SIZE]
        packet = bytearray((MCDU_F2_REPORT_ID,))
        packet.extend(chunk)
        packet.extend(b"\x00" * (MCDU_PACKET_SIZE - len(packet)))
        packets.append(bytes(packet))
    return tuple(packets)


def _button_bits(report: bytes) -> Optional[int]:
    if not report or len(report) < 13 or report[0] != 0x01:
        return None
    low = int.from_bytes(report[1:9], "little")
    high = int.from_bytes(report[9:13], "little")
    return low | (high << 64)


class MuslimSimBB36MCDU:
    """Auto-detecting BB36 manager running entirely inside final.py's process."""

    def __init__(
        self,
        api_version: str,
        api_root: str,
        font_path: Optional[str] = None,
        refresh_interval: float = MCDU_DISPLAY_MIN_INTERVAL,
        brightness: int = 220,
        diagnose: bool = False,
    ) -> None:
        self.api_version = str(api_version)
        self.api_root = str(api_root).rstrip("/")
        self.refresh_interval = max(0.02, float(refresh_interval))
        self.brightness = max(0, min(255, int(brightness)))
        self.diagnose = bool(diagnose)
        if font_path:
            self.font_path = Path(font_path).expanduser().resolve()
        else:
            project_root = Path(__file__).resolve().parents[2]
            self.font_path = project_root / "bridge" / "winctrl-pfp-b737-cockpit-compact17-font6.xpwwf"
        self.stop_event = threading.Event()
        self.manager_thread: Optional[threading.Thread] = None
        self._current_session_stop: Optional[threading.Event] = None
        self._status_lock = threading.Lock()
        self.status = "idle"

    def start(self) -> None:
        if self.manager_thread is not None and self.manager_thread.is_alive():
            return
        self.stop_event.clear()
        self.manager_thread = threading.Thread(
            target=self._manager,
            name="MuslimSim-BB36-Manager",
            daemon=True,
        )
        self.manager_thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        session_stop = self._current_session_stop
        if session_stop is not None:
            session_stop.set()
        if self.manager_thread is not None:
            self.manager_thread.join(timeout=3.0)

    def _set_status(self, status: str) -> None:
        with self._status_lock:
            changed = status != self.status
            self.status = status
        if changed and self.diagnose:
            print(f"MCDU BB36 status -> {status}")

    def _open_device(self):
        if hid is None:
            raise RuntimeError("hidapi unavailable: py -m pip install hidapi")
        devices = hid.enumerate(MCDU_VID, MCDU_PID)
        if not devices:
            raise FileNotFoundError("WINCTRL 32 MCDU CAPTAIN BB36 not connected")
        info = devices[0]
        path = info.get("path")
        if not path:
            raise RuntimeError("BB36 HID path unavailable")
        device = hid.device()
        device.open_path(path)
        try:
            device.set_nonblocking(1)
        except Exception:
            pass
        return device

    def _initialize_device(self, device: Any, hid_write_lock: threading.Lock) -> None:
        if not self.font_path.is_file():
            raise RuntimeError(f"BB36 font missing: {self.font_path}")
        packets = _read_font_packets(self.font_path)
        with hid_write_lock:
            for packet in packets:
                device.write(list(packet))
            time.sleep(0.20)
            device.write(list(_black_background_packet()))
            device.write(list(_text_grid_packet()))
            _set_brightness(device, 0, 128)
            _set_brightness(device, 1, self.brightness)

    def _resolve_runtime_ids(self):
        fmc_ids: Dict[str, int] = {}
        for key, name in MCDU_FMC_DATAREFS.items():
            try:
                fmc_ids[key] = _resolve_dataref_id(self.api_root, self.api_version, name)
            except Exception:
                # Optional layers may not exist in every Zibo build.
                pass
        if "line00_l" not in fmc_ids or "entry" not in fmc_ids:
            raise RuntimeError("required Zibo FMC1 display DataRefs unavailable")

        command_ids: Dict[str, int] = {}
        command_names = sorted({action for _label, action in MCDU_KEY_MAP.values() if action and not action.startswith("__")})
        for name in command_names:
            try:
                command_ids[name] = _resolve_command_id(self.api_root, self.api_version, name)
            except Exception:
                pass
        try:
            brightness_ref_id = _resolve_dataref_id(
                self.api_root, self.api_version, MCDU_BRIGHTNESS_DATAREF
            )
        except Exception:
            brightness_ref_id = None
        return fmc_ids, command_ids, brightness_ref_id

    def _manager(self) -> None:
        if hid is None:
            print("WARNING: BB36 MCDU disabled: install hidapi with  py -m pip install hidapi")
            self._set_status("dependency-missing")
            return
        if websocket is None:
            print("WARNING: BB36 MCDU disabled: install websocket-client with  py -m pip install websocket-client")
            self._set_status("dependency-missing")
            return

        absent_reported = False
        while not self.stop_event.is_set():
            device = None
            session_stop = threading.Event()
            self._current_session_stop = session_stop
            try:
                device = self._open_device()
                absent_reported = False
                hid_write_lock = threading.Lock()
                self._initialize_device(device, hid_write_lock)
                fmc_ids, command_ids, brightness_ref_id = self._resolve_runtime_ids()
                key_queue: "queue.Queue[Tuple[str, int]]" = queue.Queue()
                fmc_state: Dict[str, str] = {}
                fmc_state_lock = threading.Lock()
                display_dirty_event = threading.Event()
                transport_status: Dict[str, Any] = {"connected":False,"error":None}

                keypad_thread = threading.Thread(
                    target=self._keypad_reader,
                    args=(device, key_queue, session_stop),
                    name="MuslimSim-BB36-Keypad",
                    daemon=True,
                )
                ws_thread = threading.Thread(
                    target=self._websocket_worker,
                    args=(device, key_queue, fmc_ids, command_ids, brightness_ref_id,
                          fmc_state, fmc_state_lock, display_dirty_event,
                          hid_write_lock, transport_status, session_stop),
                    name="MuslimSim-BB36-WebSocket",
                    daemon=True,
                )
                display_thread = threading.Thread(
                    target=self._display_worker,
                    args=(device, fmc_state, fmc_state_lock, display_dirty_event,
                          hid_write_lock, session_stop),
                    name="MuslimSim-BB36-Display",
                    daemon=True,
                )
                keypad_thread.start(); ws_thread.start(); display_thread.start()
                self._set_status("connected")
                print(
                    "MCDU BB36 CONNECTED: WebSocket FMC1 stream + dedicated HID keypad "
                    f"({len(fmc_ids)} display refs, {len(command_ids)} key commands)."
                )

                while not self.stop_event.is_set() and not session_stop.wait(0.10):
                    if not keypad_thread.is_alive() or not display_thread.is_alive():
                        session_stop.set()
                        break

                session_stop.set()
                keypad_thread.join(timeout=1.0)
                ws_thread.join(timeout=1.5)
                display_thread.join(timeout=1.0)

            except FileNotFoundError:
                self._set_status("waiting-for-bb36")
                if not absent_reported:
                    print("MCDU BB36: waiting for WINCTRL 32 MCDU CAPTAIN (4098:BB36).")
                    absent_reported = True
            except Exception as exc:
                self._set_status("reconnecting")
                if not self.stop_event.is_set():
                    print(f"MCDU BB36 reconnecting after error: {exc}")
            finally:
                session_stop.set()
                if device is not None:
                    try:
                        device.close()
                    except Exception:
                        pass
                self._current_session_stop = None

            if not self.stop_event.is_set():
                self.stop_event.wait(MCDU_RECONNECT_SECONDS)

        self._set_status("stopped")

    def _keypad_reader(self, device: Any, key_queue: queue.Queue, session_stop: threading.Event) -> None:
        previous_bits = None
        consecutive_errors = 0
        while not self.stop_event.is_set() and not session_stop.is_set():
            try:
                report = device.read(128)
                consecutive_errors = 0
            except Exception as exc:
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    print(f"MCDU BB36 keypad disconnected: {exc}")
                    session_stop.set()
                    return
                session_stop.wait(0.01)
                continue
            if not report:
                session_stop.wait(0.001)
                continue
            current_bits = _button_bits(bytes(report))
            if current_bits is None:
                continue
            if previous_bits is None:
                previous_bits = current_bits
                if self.diagnose:
                    print(f"MCDU BB36 keypad baseline=0x{current_bits:024X}")
                continue
            changed = current_bits ^ previous_bits
            if changed:
                for hardware_index in range(96):
                    mask = 1 << hardware_index
                    if changed & mask:
                        key_queue.put(("press" if current_bits & mask else "release", hardware_index))
            previous_bits = current_bits

    @staticmethod
    def _ws_send(ws: Any, payload: Dict[str, Any]) -> None:
        ws.send(json.dumps(payload, separators=(",", ":")))

    @staticmethod
    def _next_req_id(counter: list) -> int:
        counter[0] += 1
        return counter[0]

    def _drain_keys(
        self,
        ws: Any,
        key_queue: queue.Queue,
        command_ids: Dict[str, int],
        brightness_ref_id: Optional[int],
        brightness_state: Dict[str, float],
        req_counter: list,
        device: Any,
        hid_write_lock: threading.Lock,
    ) -> None:
        processed = 0
        while processed < 128:
            try:
                edge, hardware_index = key_queue.get_nowait()
            except queue.Empty:
                break
            processed += 1
            mapping = MCDU_KEY_MAP.get(int(hardware_index))
            if mapping is None:
                continue
            label, action = mapping
            if action is None:
                if edge == "press" and self.diagnose:
                    print(f"MCDU BB36 {label}: intentionally unassigned for Zibo")
                continue
            if action in ("__brightness_up__", "__brightness_down__"):
                if edge != "press":
                    continue
                delta = 0.1 if action == "__brightness_up__" else -0.1
                target = max(0.0, min(1.0, float(brightness_state.get("value", 0.85)) + delta))
                brightness_state["value"] = target
                if brightness_ref_id is not None:
                    self._ws_send(ws, {
                        "req_id":self._next_req_id(req_counter),
                        "type":"dataref_set_values",
                        "params":{"datarefs":[{"id":int(brightness_ref_id),"index":MCDU_BRIGHTNESS_INDEX,"value":target}]},
                    })
                with hid_write_lock:
                    _set_brightness(device, 1, round(target * 255))
                if self.diagnose:
                    print(f"MCDU BB36 brightness -> {target:.2f}")
                continue
            command_id = command_ids.get(action)
            if command_id is None:
                if edge == "press":
                    print(f"MCDU BB36 {label}: Zibo command unavailable")
                continue
            self._ws_send(ws, {
                "req_id":self._next_req_id(req_counter),
                "type":"command_set_is_active",
                "params":{"commands":[{"id":int(command_id),"is_active":edge == "press"}]},
            })
            if edge == "press" and self.diagnose:
                print(f"MCDU BB36 key {hardware_index:02d} {label} -> Zibo")

    def _websocket_worker(
        self,
        device: Any,
        key_queue: queue.Queue,
        fmc_ids: Dict[str, int],
        command_ids: Dict[str, int],
        brightness_ref_id: Optional[int],
        fmc_state: Dict[str, str],
        fmc_state_lock: threading.Lock,
        display_dirty_event: threading.Event,
        hid_write_lock: threading.Lock,
        transport_status: Dict[str, Any],
        session_stop: threading.Event,
    ) -> None:
        id_to_key = {str(int(ref_id)):key for key, ref_id in fmc_ids.items()}
        brightness_id_key = str(int(brightness_ref_id)) if brightness_ref_id is not None else None
        req_counter = [1000]
        brightness_state = {"value":self.brightness / 255.0}

        while not self.stop_event.is_set() and not session_stop.is_set():
            ws = None
            try:
                ws = websocket.create_connection(
                    f"ws://127.0.0.1:8086/api/{self.api_version}",
                    timeout=1.0,
                    enable_multithread=True,
                )
                ws.settimeout(MCDU_WS_RECV_TIMEOUT)
                subscriptions = [{"id":int(ref_id)} for ref_id in fmc_ids.values()]
                if brightness_ref_id is not None:
                    subscriptions.append({"id":int(brightness_ref_id),"index":MCDU_BRIGHTNESS_INDEX})
                self._ws_send(ws, {
                    "req_id":self._next_req_id(req_counter),
                    "type":"dataref_subscribe_values",
                    "params":{"datarefs":subscriptions},
                })
                transport_status["connected"] = True
                transport_status["error"] = None

                while not self.stop_event.is_set() and not session_stop.is_set():
                    self._drain_keys(ws, key_queue, command_ids, brightness_ref_id,
                                     brightness_state, req_counter, device, hid_write_lock)
                    try:
                        raw_message = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    if not raw_message:
                        continue
                    message = json.loads(raw_message)
                    if message.get("type") == "result":
                        if not message.get("success", False) and self.diagnose:
                            print(
                                "MCDU BB36 WebSocket request error: "
                                f"{message.get('error_code')} {message.get('error_message')}"
                            )
                        continue
                    if message.get("type") != "dataref_update_values":
                        continue
                    updates = message.get("data", {})
                    if not isinstance(updates, dict):
                        continue
                    changed = False
                    with fmc_state_lock:
                        for raw_id, value in updates.items():
                            id_key = str(raw_id).strip()
                            if brightness_id_key is not None and id_key == brightness_id_key:
                                brightness_state["value"] = max(0.0, min(1.0, _ws_scalar(value, brightness_state["value"])))
                                continue
                            display_key = id_to_key.get(id_key)
                            if display_key is None:
                                continue
                            text = _ws_decode_text(value)
                            if fmc_state.get(display_key) != text:
                                fmc_state[display_key] = text
                                changed = True
                    if changed:
                        display_dirty_event.set()

            except Exception as exc:
                transport_status["connected"] = False
                transport_status["error"] = str(exc)
                if not session_stop.is_set() and self.diagnose:
                    print(f"MCDU BB36 WebSocket reconnecting: {exc}")
                session_stop.wait(MCDU_WS_RECONNECT_SECONDS)
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass
        transport_status["connected"] = False

    def _display_worker(
        self,
        device: Any,
        fmc_state: Dict[str, str],
        fmc_state_lock: threading.Lock,
        display_dirty_event: threading.Event,
        hid_write_lock: threading.Lock,
        session_stop: threading.Event,
    ) -> None:
        previous_page = None
        last_write = 0.0
        while not self.stop_event.is_set() and not session_stop.is_set():
            display_dirty_event.wait(0.10)
            if not display_dirty_event.is_set():
                continue
            display_dirty_event.clear()
            elapsed = time.monotonic() - last_write
            if elapsed < self.refresh_interval:
                session_stop.wait(self.refresh_interval - elapsed)
                if session_stop.is_set():
                    return
            with fmc_state_lock:
                values = dict(fmc_state)
            lines, colors = _compose_zibo_page(values)
            state = (lines, colors)
            if state == previous_page:
                continue
            try:
                packets = _page_packets(lines, colors)
                with hid_write_lock:
                    for packet in packets:
                        device.write(list(packet))
                previous_page = state
                last_write = time.monotonic()
                if self.diagnose:
                    print(f"MCDU BB36 page -> {lines[0].strip()}")
            except Exception as exc:
                print(f"MCDU BB36 display disconnected: {exc}")
                session_stop.set()
                return


def run_self_test() -> None:
    if MCDU_VID != 0x4098 or MCDU_PID != 0xBB36:
        raise AssertionError("BB36 VID/PID changed")
    if MCDU_KEY_MAP[0][1] != "laminar/B738/button/fmc1_1L":
        raise AssertionError("LSK1L map invalid")
    if MCDU_KEY_MAP[24][1] != "laminar/B738/button/fmc1_menu":
        raise AssertionError("MENU map invalid")
    if MCDU_KEY_MAP[73][1] != "laminar/B738/button/fmc1_clr":
        raise AssertionError("CLR map invalid")
    report = bytes((1,2) + (0,) * 62)
    if _button_bits(report) != 2:
        raise AssertionError("BB36 report bit decoder invalid")
    lines, colors = _compose_zibo_page({"line00_l":"MENU", "entry":"ABC"})
    if len(lines) != 14 or any(len(line) != 24 for line in lines):
        raise AssertionError("BB36 page geometry invalid")
    packets = _page_packets(lines, colors)
    if len(packets) != 16 or any(len(packet) != 64 for packet in packets):
        raise AssertionError("BB36 F2 page packet geometry invalid")
