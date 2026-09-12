#!/usr/bin/env python3
"""WINCTRL 3N PDC / EFIS BB62 support for the unified MuslimSim bridge.

Target hardware: WINCTRL VID 0x4098, PID 0xBB62 (reported by this unit as
``WINWING 3N PDC R``).  The physical side name is deliberately not inferred
from a user label: this module identifies the connected device by VID/PID.

The panel's report descriptor is known (report 0x01, 64 buttons and two
little-endian 16-bit axes). The physical control map was captured from this
unit. CAPT EFIS buttons and maintained selectors use the existing bridge REST
helpers through an injected action sink; this module opens no X-Plane socket.
Focused raw capture separated the rotary direction pulses from background HID
axis movement: MINS clockwise/counter-clockwise are bits 41/39 and BARO
clockwise/counter-clockwise are bits 44/42.

* the first report is a no-write baseline;
* subsequent reports can be safely printed with ``--diagnose-pdc``;
* a control only writes after a post-baseline physical edge;
* MINS and BARO write only on their confirmed post-baseline direction pulses;
* no display, LED, or panel output selector is guessed or written;
* HID disconnects stay isolated and reconnect automatically.

The generic 0x02 / 0xF0 output framing is included as pure packet builders.
It is parameterised with the PDC PID (62 BB) and has no runtime caller until
the panel's display/LED selector meaning has been captured.

The action sink injected by ``bridge/final.py`` keeps all PDC aircraft writes
on its existing ``set_dataref`` / ``activate_command`` path rather than
opening another per-device WebSocket.
"""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

try:
    import hid
except ImportError:  # pragma: no cover - only on installations without hidapi
    hid = None


PDC_VID = 0x4098
PDC_PID = 0xBB62
PDC_PRODUCT_LABEL = "WINCTRL 3N PDC / EFIS"
PDC_REPORT_ID_INPUT = 0x01
PDC_INPUT_MIN_LENGTH = 13
PDC_BUTTON_COUNT = 64
PDC_PACKET_SIZE = 64
PDC_LCD_PAYLOAD_SIZE = 32
PDC_RECONNECT_SECONDS = 1.0
PDC_DIAG_AXIS_DELTA = 4

PDC_PID_BYTES = bytes((PDC_PID & 0xFF, (PDC_PID >> 8) & 0xFF))

# Captured from this physical BB62 panel with tools/probe_pdc_bb62.py.
PDC_CONTROLS: Dict[str, Tuple[str, int]] = {
    "mins_mode_radio": ("bit", 23),
    "mins_mode_baro": ("bit", 24),
    "mins_knob_ccw": ("bit", 39),
    "mins_knob_cw": ("bit", 41),
    "mins_reset": ("bit", 15),
    "baro_mode_in": ("bit", 25),
    "baro_mode_hpa": ("bit", 26),
    "baro_knob_ccw": ("bit", 42),
    "baro_knob_cw": ("bit", 44),
    "baro_std": ("bit", 18),
    "vor_adf_1_vor": ("bit", 9),
    "vor_adf_1_off": ("bit", 10),
    "vor_adf_1_adf": ("bit", 11),
    "vor_adf_2_vor": ("bit", 12),
    "vor_adf_2_off": ("bit", 13),
    "vor_adf_2_adf": ("bit", 14),
    "mode_app": ("bit", 27),
    "mode_vor": ("bit", 28),
    "mode_map": ("bit", 29),
    "mode_plan": ("bit", 30),
    "range_5": ("bit", 31),
    "range_10": ("bit", 32),
    "range_20": ("bit", 33),
    "range_40": ("bit", 34),
    "range_80": ("bit", 35),
    "range_160": ("bit", 36),
    "range_320": ("bit", 37),
    "tfc": ("bit", 17),
    "wxr": ("bit", 2),
    "sta": ("bit", 3),
    "wpt": ("bit", 4),
    "arpt": ("bit", 5),
    "data": ("bit", 6),
    "pos": ("bit", 7),
    "terr": ("bit", 8),
    "fpv": ("bit", 0),
    "mtrs": ("bit", 1),
}

# Every PDC_CONTROLS name plus a raw_bit_N placeholder for every other bit
# index the 64-button report exposes.  A bit not in PDC_CONTROLS has no
# confirmed real-world legend, but its exact HID position is still fixed and
# known, so it is preserved as a plain raw contact instead of being dropped:
# Studio can bind a simulator function to it once the owner picks one (see
# muslimsim/gui/studio.py's _EXPOSE_UNVERIFIED_CONTROLS).  MuslimSimPDCZiboDispatcher
# already no-ops safely on any control name it does not recognise, so this
# changes nothing for a bit that stays unmapped.
_PDC_KNOWN_BITS = frozenset(index for _kind, index in PDC_CONTROLS.values())
PDC_ALL_CONTROLS: Dict[str, Tuple[str, int]] = dict(PDC_CONTROLS)
PDC_ALL_CONTROLS.update({
    f"raw_bit_{index}": ("bit", index)
    for index in range(PDC_BUTTON_COUNT)
    if index not in _PDC_KNOWN_BITS
})

# These names and writability were validated against the currently running
# Zibo/X-Plane Web API before they were bound. They are CAPT-side only.
PDC_ZIBO_EFIS_DATAREFS: Dict[str, str] = {
    "map_mode": "laminar/B738/EFIS_control/capt/map_mode_pos",
    "map_range": "laminar/B738/EFIS/capt/map_range",
    "minimums": "laminar/B738/EFIS_control/cpt/minimums",
}

PDC_ZIBO_COMMANDS: Dict[str, str] = {
    "mins_reset": "laminar/B738/EFIS_control/capt/push_button/rst_press",
    "mins_up": "laminar/B738/EFIS_control/cpt/minimums_up",
    "mins_dn": "laminar/B738/EFIS_control/cpt/minimums_dn",
    "baro_in": "laminar/B738/EFIS_control/capt/baro_in_hpa_dn",
    "baro_hpa": "laminar/B738/EFIS_control/capt/baro_in_hpa_up",
    "baro_std": "laminar/B738/EFIS_control/capt/push_button/std_press",
    "baro_up": "laminar/B738/pilot/barometer_up",
    "baro_dn": "laminar/B738/pilot/barometer_down",
    "vor1_up": "laminar/B738/EFIS_control/capt/vor1_off_up",
    "vor1_dn": "laminar/B738/EFIS_control/capt/vor1_off_dn",
    "vor2_up": "laminar/B738/EFIS_control/capt/vor2_off_up",
    "vor2_dn": "laminar/B738/EFIS_control/capt/vor2_off_dn",
    "tfc": "laminar/B738/EFIS_control/capt/push_button/tfc_press",
    "wxr": "laminar/B738/EFIS_control/capt/push_button/wxr_press",
    "sta": "laminar/B738/EFIS_control/capt/push_button/sta_press",
    "wpt": "laminar/B738/EFIS_control/capt/push_button/wpt_press",
    "arpt": "laminar/B738/EFIS_control/capt/push_button/arpt_press",
    "data": "laminar/B738/EFIS_control/capt/push_button/data_press",
    "pos": "laminar/B738/EFIS_control/capt/push_button/pos_press",
    "terr": "laminar/B738/EFIS_control/capt/push_button/terr_press",
    "fpv": "laminar/B738/EFIS_control/capt/push_button/fpv_press",
    "mtrs": "laminar/B738/EFIS_control/capt/push_button/mtrs_press",
}

PDC_DATAREF_TARGETS = {
    "mins_mode_radio": ("minimums", 0.0),
    "mins_mode_baro": ("minimums", 1.0),
    "mode_app": ("map_mode", 0.0),
    "mode_vor": ("map_mode", 1.0),
    "mode_map": ("map_mode", 2.0),
    "mode_plan": ("map_mode", 3.0),
    "range_5": ("map_range", 0.0),
    "range_10": ("map_range", 1.0),
    "range_20": ("map_range", 2.0),
    "range_40": ("map_range", 3.0),
    "range_80": ("map_range", 4.0),
    "range_160": ("map_range", 5.0),
    "range_320": ("map_range", 6.0),
}

PDC_COMMAND_TARGETS = {
    "mins_knob_ccw": "mins_dn",
    "mins_knob_cw": "mins_up",
    "baro_mode_in": "baro_in",
    "baro_mode_hpa": "baro_hpa",
    "mins_reset": "mins_reset",
    "baro_std": "baro_std",
    "baro_knob_ccw": "baro_dn",
    "baro_knob_cw": "baro_up",
    "tfc": "tfc",
    "wxr": "wxr",
    "sta": "sta",
    "wpt": "wpt",
    "arpt": "arpt",
    "data": "data",
    "pos": "pos",
    "terr": "terr",
    "fpv": "fpv",
    "mtrs": "mtrs",
}

# Zibo exposes the VOR/ADF position readback as read-only.  Do not infer its
# numeric ordering.  Instead, each physical selection uses the named up/down
# commands to first reach the relevant end-stop, then (for OFF) step once back
# to centre.  This makes every selector position absolute even when the panel
# and simulator started in different states.
PDC_VOR_ADF_COMMAND_SEQUENCES = {
    "vor_adf_1_vor": (("vor1_up", 2),),
    "vor_adf_1_off": (("vor1_up", 2), ("vor1_dn", 1)),
    "vor_adf_1_adf": (("vor1_dn", 2),),
    "vor_adf_2_vor": (("vor2_up", 2),),
    "vor_adf_2_off": (("vor2_up", 2), ("vor2_dn", 1)),
    "vor_adf_2_adf": (("vor2_dn", 2),),
}


@dataclass(frozen=True)
class PDCInputState:
    """One decoded report-0x01 input state."""

    buttons: int
    axes: Tuple[int, int]


@dataclass(frozen=True)
class PDCControlEvent:
    """A semantic event generated only from an explicitly supplied map."""

    control: str
    phase: str
    value: int


PDCActionSink = Callable[[PDCControlEvent], None]


class MuslimSimPDCZiboDispatcher:
    """Apply verified PDC events through bridge-provided REST helpers only."""

    def __init__(
        self,
        *,
        api_version: str,
        resolve_dataref_id: Callable[[str, str], int],
        set_dataref: Callable[[str, int, float], None],
        resolve_command_id: Callable[[str, str], int],
        activate_command: Callable[[str, int, float], None],
        diagnose: bool = False,
    ) -> None:
        self.api_version = str(api_version)
        self._resolve_dataref_id = resolve_dataref_id
        self._set_dataref = set_dataref
        self._resolve_command_id = resolve_command_id
        self._activate_command = activate_command
        self.diagnose = bool(diagnose)
        self._dataref_ids: Dict[str, int] = {}
        self._command_ids: Dict[str, int] = {}
        self._lock = threading.Lock()

    def _dataref_id(self, key: str, *, refresh: bool = False) -> int:
        if refresh or key not in self._dataref_ids:
            self._dataref_ids[key] = self._resolve_dataref_id(
                self.api_version,
                PDC_ZIBO_EFIS_DATAREFS[key],
            )
        return self._dataref_ids[key]

    def _command_id(self, key: str, *, refresh: bool = False) -> int:
        if refresh or key not in self._command_ids:
            self._command_ids[key] = self._resolve_command_id(
                self.api_version,
                PDC_ZIBO_COMMANDS[key],
            )
        return self._command_ids[key]

    @staticmethod
    def _is_stale_id(error: Exception) -> bool:
        return getattr(error, "code", None) == 404

    def _set_ref(self, key: str, value: float) -> None:
        try:
            self._set_dataref(
                self.api_version,
                self._dataref_id(key),
                float(value),
            )
        except Exception as exc:
            if not self._is_stale_id(exc):
                raise
            self._set_dataref(
                self.api_version,
                self._dataref_id(key, refresh=True),
                float(value),
            )

    def _activate(self, key: str, count: int = 1) -> None:
        for _ in range(max(1, int(count))):
            try:
                self._activate_command(
                    self.api_version,
                    self._command_id(key),
                    0.0,
                )
            except Exception as exc:
                if not self._is_stale_id(exc):
                    raise
                self._activate_command(
                    self.api_version,
                    self._command_id(key, refresh=True),
                    0.0,
                )

    def __call__(self, event: PDCControlEvent) -> None:
        if event.phase != "press":
            return

        with self._lock:
            dataref_target = PDC_DATAREF_TARGETS.get(event.control)
            if dataref_target is not None:
                key, value = dataref_target
                self._set_ref(key, value)
                if self.diagnose:
                    print(f"PDC {event.control} -> {key}={value:g}")
                return

            command_key = PDC_COMMAND_TARGETS.get(event.control)
            if command_key is not None:
                self._activate(command_key)
                if self.diagnose:
                    print(f"PDC {event.control} -> {command_key}")
                return

            sequence = PDC_VOR_ADF_COMMAND_SEQUENCES.get(event.control)
            if sequence is None:
                return
            for command_key, count in sequence:
                self._activate(command_key, count)
            if self.diagnose:
                print(
                    f"PDC {event.control} -> absolute VOR/ADF command sequence"
                )


def pdc_decode_input_report(report: bytes) -> Optional[PDCInputState]:
    """Decode the documented 64-button/two-axis PDC input report."""
    raw = bytes(report)
    if len(raw) < PDC_INPUT_MIN_LENGTH or raw[0] != PDC_REPORT_ID_INPUT:
        return None
    return PDCInputState(
        buttons=int.from_bytes(raw[1:9], byteorder="little", signed=False),
        axes=(
            int.from_bytes(raw[9:11], byteorder="little", signed=False),
            int.from_bytes(raw[11:13], byteorder="little", signed=False),
        ),
    )


def pdc_control_events(
    previous: PDCInputState,
    current: PDCInputState,
    controls: Mapping[str, Tuple[str, int]],
) -> Tuple[PDCControlEvent, ...]:
    """Return events for an explicit map; an empty map deliberately returns none."""
    events = []
    changed_bits = previous.buttons ^ current.buttons
    for name, spec in controls.items():
        if not isinstance(spec, tuple) or len(spec) != 2:
            continue
        kind, index = spec
        index = int(index)
        if kind == "bit" and 0 <= index < PDC_BUTTON_COUNT:
            mask = 1 << index
            if changed_bits & mask:
                events.append(PDCControlEvent(
                    control=str(name),
                    phase="press" if current.buttons & mask else "release",
                    value=1 if current.buttons & mask else 0,
                ))
        elif kind == "axis" and 0 <= index < len(current.axes):
            if current.axes[index] != previous.axes[index]:
                events.append(PDCControlEvent(
                    control=str(name),
                    phase="change",
                    value=int(current.axes[index]),
                ))
    return tuple(events)


def _normalize_sequence(value: int) -> int:
    sequence = int(value) & 0xFF
    return sequence if sequence else 1


def _next_sequence(value: int) -> int:
    sequence = (int(value) + 1) & 0xFF
    return sequence if sequence else 1


def pdc_led_packet(selector: int, value: int) -> bytes:
    """Build the known 0x02 output frame with the PDC's own PID."""
    return bytes((
        0x02,
        *PDC_PID_BYTES,
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


def pdc_initialize_packet(sequence: int) -> bytes:
    """Build the known generic F0 initialization frame for PID BB62."""
    sequence = _normalize_sequence(sequence)
    packet = bytearray(PDC_PACKET_SIZE)
    packet[0:4] = bytes((0xF0, 0x00, sequence, 0x12))
    packet[4:24] = bytes((
        *PDC_PID_BYTES, 0x00, 0x00,
        0x04, 0x01, 0x00, 0x00,
        0x26, 0xCC, 0x00, 0x00,
        0x00, 0x01, 0x00, 0x00,
        0x00, 0x03, 0x00, 0x00,
    ))
    return bytes(packet)


def pdc_lcd_packets(
    payload: bytes,
    sequence: int,
) -> Tuple[Tuple[bytes, bytes, bytes, bytes], int]:
    """Build one parameterised 0xF0 LCD transaction without writing it."""
    if len(payload) != PDC_LCD_PAYLOAD_SIZE:
        raise ValueError(
            f"PDC LCD payload must be {PDC_LCD_PAYLOAD_SIZE} bytes"
        )

    seq = _normalize_sequence(sequence)
    frames = []
    data_frame = bytearray(PDC_PACKET_SIZE)
    data_frame[0:4] = bytes((0xF0, 0x00, seq, 0x38))
    data_frame[4:18] = bytes((
        *PDC_PID_BYTES, 0x00, 0x00,
        0x02, 0x01, 0x00, 0x00,
        0xDF, 0xA2, 0x50, 0x00,
        0x00, 0xB0,
    ))
    data_frame[25:57] = payload
    frames.append(bytes(data_frame))
    seq = _next_sequence(seq)

    for _ in range(2):
        empty_frame = bytearray(PDC_PACKET_SIZE)
        empty_frame[0:4] = bytes((0xF0, 0x00, seq, 0x38))
        frames.append(bytes(empty_frame))
        seq = _next_sequence(seq)

    commit = bytearray(PDC_PACKET_SIZE)
    commit[0:4] = bytes((0xF0, 0x00, seq, 0x2A))
    commit[0x1D:0x1F] = PDC_PID_BYTES
    commit[0x21] = 0x03
    commit[0x22] = 0x01
    commit[0x25] = 0xDF
    commit[0x26] = 0xA2
    commit[0x27] = 0x50
    frames.append(bytes(commit))
    seq = _next_sequence(seq)

    return (frames[0], frames[1], frames[2], frames[3]), seq


class MuslimSimPDCBB62:
    """Fault-isolated BB62 HID manager with a no-write startup baseline."""

    def __init__(
        self,
        *,
        diagnose: bool = False,
        action_sink: Optional[PDCActionSink] = None,
    ) -> None:
        self.diagnose = bool(diagnose)
        self.action_sink = action_sink
        self.stop_event = threading.Event()
        self._manager_thread: Optional[threading.Thread] = None
        self._status = "stopped"
        self._status_lock = threading.Lock()
        self._last_state: Optional[PDCInputState] = None
        self._last_state_lock = threading.Lock()

    @property
    def status(self) -> str:
        with self._status_lock:
            return self._status

    @property
    def last_state(self) -> Optional[PDCInputState]:
        with self._last_state_lock:
            return self._last_state

    def _set_status(self, value: str) -> None:
        with self._status_lock:
            self._status = str(value)

    def start(self) -> None:
        if self._manager_thread and self._manager_thread.is_alive():
            return
        self.stop_event.clear()
        self._manager_thread = threading.Thread(
            target=self._manager,
            name="MuslimSim-PDC-BB62",
            daemon=True,
        )
        self._manager_thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self._manager_thread is not None:
            self._manager_thread.join(timeout=3.0)
        self._set_status("stopped")

    def _manager(self) -> None:
        if hid is None:
            print(
                "WARNING: PDC BB62 disabled: install hidapi with "
                "py -m pip install hidapi"
            )
            self._set_status("dependency-missing")
            return

        absent_reported = False
        while not self.stop_event.is_set():
            device = None
            try:
                device = self._open_device()
                absent_reported = False
                self._set_status("connected")
                print(
                    "PDC BB62 CONNECTED: WINCTRL 4098:BB62; "
                    "CAPT EFIS selectors, buttons, MINS, and BARO mapped."
                )
                self._run_input_session(device)
            except FileNotFoundError:
                self._set_status("waiting-for-pdc")
                if not absent_reported:
                    print(
                        "PDC BB62: waiting for WINCTRL 3N PDC / EFIS "
                        "(4098:BB62)."
                    )
                    absent_reported = True
            except Exception as exc:
                self._set_status("reconnecting")
                if not self.stop_event.is_set():
                    print(f"PDC BB62 reconnecting after error: {exc}")
            finally:
                if device is not None:
                    try:
                        device.close()
                    except Exception:
                        pass

            if not self.stop_event.is_set():
                self.stop_event.wait(PDC_RECONNECT_SECONDS)
        self._set_status("stopped")

    @staticmethod
    def _open_device() -> Any:
        devices = hid.enumerate(PDC_VID, PDC_PID)
        if not devices:
            raise FileNotFoundError(
                f"{PDC_PRODUCT_LABEL} ({PDC_VID:04X}:{PDC_PID:04X}) "
                "not connected"
            )
        chosen = next(
            (
                info for info in devices
                if "PDC" in str(info.get("product_string") or "").upper()
            ),
            devices[0],
        )
        path = chosen.get("path")
        if not path:
            raise RuntimeError("PDC BB62 HID path unavailable")
        device = hid.device()
        device.open_path(path)
        try:
            device.set_nonblocking(1)
        except Exception:
            pass
        return device

    def _run_input_session(self, device: Any) -> None:
        previous: Optional[PDCInputState] = None
        read_errors = 0
        unexpected_report_seen = False
        while not self.stop_event.is_set():
            try:
                report = device.read(PDC_PACKET_SIZE)
                read_errors = 0
            except Exception as exc:
                read_errors += 1
                if read_errors >= 3:
                    raise ConnectionError(f"PDC HID disconnected: {exc}") from exc
                self.stop_event.wait(0.01)
                continue
            if not report:
                self.stop_event.wait(0.001)
                continue

            current = pdc_decode_input_report(bytes(report))
            if current is None:
                if self.diagnose and not unexpected_report_seen:
                    raw = bytes(report)
                    report_id = raw[0] if raw else -1
                    print(
                        f"PDC BB62 ignored HID report len={len(raw)} "
                        f"id=0x{report_id & 0xFF:02X}"
                    )
                    unexpected_report_seen = True
                continue

            with self._last_state_lock:
                self._last_state = current
            if previous is None:
                previous = current
                if self.diagnose:
                    print(
                        "PDC BB62 startup baseline captured; aircraft unchanged "
                        f"(buttons=0x{current.buttons:016X}, "
                        f"X={current.axes[0]}, Y={current.axes[1]})."
                    )
                continue

            changed_bits = previous.buttons ^ current.buttons
            axis_changed = tuple(
                abs(current.axes[index] - previous.axes[index])
                >= PDC_DIAG_AXIS_DELTA
                for index in range(2)
            )
            if changed_bits or any(axis_changed):
                if self.diagnose:
                    pressed = [
                        index for index in range(PDC_BUTTON_COUNT)
                        if changed_bits & (1 << index)
                        and current.buttons & (1 << index)
                    ]
                    released = [
                        index for index in range(PDC_BUTTON_COUNT)
                        if changed_bits & (1 << index)
                        and not current.buttons & (1 << index)
                    ]
                    print(
                        "PDC BB62 raw "
                        f"buttons=0x{current.buttons:016X} "
                        f"changed=0x{changed_bits:016X} "
                        f"press={pressed} release={released} "
                        f"axes=X:{current.axes[0]} Y:{current.axes[1]}"
                    )

                # Events begin only after the first-report baseline. Rotary
                # movement is accepted only from its confirmed direction bit.
                if PDC_CONTROLS and self.action_sink is not None:
                    for event in pdc_control_events(
                        previous,
                        current,
                        PDC_ALL_CONTROLS,
                    ):
                        try:
                            self.action_sink(event)
                        except Exception as exc:
                            print(
                                "PDC BB62 bridge action failed; "
                                f"input remains isolated: {exc}"
                            )
            previous = current


__all__ = [
    "MuslimSimPDCBB62",
    "MuslimSimPDCZiboDispatcher",
    "PDC_ALL_CONTROLS",
    "PDC_BUTTON_COUNT",
    "PDC_CONTROLS",
    "PDC_INPUT_MIN_LENGTH",
    "PDC_PID",
    "PDC_VID",
    "PDC_ZIBO_COMMANDS",
    "PDC_ZIBO_EFIS_DATAREFS",
    "PDCControlEvent",
    "PDCInputState",
    "pdc_control_events",
    "pdc_decode_input_report",
    "pdc_initialize_packet",
    "pdc_lcd_packets",
    "pdc_led_packet",
]
