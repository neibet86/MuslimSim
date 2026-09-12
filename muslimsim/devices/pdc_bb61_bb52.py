#!/usr/bin/env python3
"""
MuslimSim fixed-side WinWing PDC support.

Captured hardware:
    Captain / LEFT : WINWING 3N PDC L  VID 4098 PID BB61
    First Officer  : WINWING 3M PDC R  VID 4098 PID BB52

This module stays inside the existing MuslimSim Python process.  It never
creates no bridge subprocess. V5.1 adds only the owner-captured fixed-PDC backlight output.

MUSLIMSIM_PDC_BB61_BB52_CLEAN_V1
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
import queue
import threading
import time

try:
    import hid
except Exception:
    hid = None


PDC_VID = 0x4098
BB61_PID = 0xBB61   # 3N PDC — Captain side
BB51_PID = 0xBB51   # 3M PDC — Captain side (same role, different model)
BB52_PID = 0xBB52   # 3M PDC — First Officer side
# BB62 (3N PDC FO side) is handled by muslimsim.devices.pdc_bb62, not here.

# PIDs that use model byte 0x60 in the backlight packet; all others use 0x50.
_3N_PIDS: frozenset = frozenset({BB61_PID})

BUTTON_BYTES_START = 1
BUTTON_BYTES_END = 9
ENUM_INTERVAL = 0.25
READ_SIZE = 128
IDLE_SLEEP = 0.002

# MUSLIMSIM_PDC_FIXED_BACKLIGHT_V51
# Owner captures 2026-09-03 prove one 14-byte brightness report per fixed PDC.
# BB61 LEFT uses model byte 0x60; BB52 RIGHT uses 0x50. Channel 0 is the
# faceplate backlight, brightness is 0..255, and value 0 is capture-proven OFF.
# MUSLIMSIM_PDC_DETENT_KNOB_V1
# The MINS and BARO knobs are not simple spring switches. Each is a two-stage
# rotary with five contacts: a rest contact, one detent contact per direction,
# and one "held past the notch" contact per direction. Turning to the detent is
# one click. Tugging past the notch and holding is the fast run, and the panel
# reports only that it is being held - never a speed - so the speed is ours to
# choose. Ten steps a second moves BARO through a full inch of mercury in two
# seconds, which is about what the knob feels like in the aircraft. It is one
# number on purpose: if the owner wants a different feel, this is the only line
# that changes.
PDC_KNOB_FAST_STEPS_PER_SECOND = 10.0
PDC_KNOB_FAST_PERIOD = 1.0 / PDC_KNOB_FAST_STEPS_PER_SECOND

PDC_INPUT_REPORT_ID = 0x01
PDC_INPUT_REPORT_LEN = 17
PDC_BACKLIGHT_CHANNEL = 0x00
PDC_BACKLIGHT_MIN = 0
PDC_BACKLIGHT_MAX = 255



@dataclass(frozen=True)
class PDCEvent:
    control: str
    value: Any
    phase: str = "change"
    side: str = ""


@dataclass(frozen=True)
class PDCState:
    buttons: Tuple[int, ...]
    axes: Tuple[int, ...]
    report: bytes


def _button_bits(report: bytes) -> int:
    if len(report) < BUTTON_BYTES_END:
        return 0
    bits = 0
    for offset, byte in enumerate(report[BUTTON_BYTES_START:BUTTON_BYTES_END]):
        bits |= int(byte) << (offset * 8)
    return bits


def _pressed(bits: int, button: int) -> bool:
    return bool(int(bits) & (1 << (int(button) - 1)))


def _active_buttons(report: bytes) -> Tuple[int, ...]:
    bits = _button_bits(report)
    return tuple(index for index in range(1, 65) if _pressed(bits, index))


def _is_input_report(report: bytes) -> bool:
    # MUSLIMSIM_PDC_VARIABLE_INPUT_V6
    # The logical fixed-PDC input payload needs at least 17 bytes and always
    # carries report ID 01.  The user's direct Python HID captures prove that
    # Windows/hidapi pads both BB61 and BB52 reads to 64 bytes.  Accept that
    # transport form instead of requiring an exact USB payload length.
    # Backlight acknowledgements remain excluded because they are report ID 02.
    return len(report) >= PDC_INPUT_REPORT_LEN and report[0] == PDC_INPUT_REPORT_ID


def _first_pressed(bits: int, mapping: Mapping[int, Any]) -> Optional[Any]:
    for button, value in mapping.items():
        if _pressed(bits, button):
            return value
    return None


# Final maps locked from the user's guided + raw captures.
BB61_MOMENTARY: Dict[int, str] = {
    1: "fpv",
    2: "mtrs",
    3: "wxr",
    4: "sta",
    5: "wpt",
    6: "arpt",
    7: "data",
    8: "pos",
    9: "terr",
    16: "mins_rst",
    17: "ctr",
    18: "tfc",
    19: "baro_std",
}
BB61_VOR1 = {10: 0, 11: 1, 12: 2}  # VOR / OFF / ADF1
BB61_VOR2 = {13: 0, 14: 1, 15: 2}  # VOR / OFF / ADF2
# BUG-12: these two were the only selectors on either PDC written with their
# bit -> index pairs descending.  Every other selector here ascends - VOR1/VOR2,
# MAP MODE, MAP RANGE - and the bit ranges are contiguous only when these ascend
# too (mins 24..25, baro 26..27, then MAP MODE from 28).  Reversed, the owner
# turned the switch to HPA and Studio showed IN, and to RADIO and it showed
# BARO.  The same decoded index feeds X-Plane through _set_maintained, so the
# simulator was driven to the wrong position as well, not just the panel.
BB61_MINS_MODE = {24: 0, 25: 1}    # RADIO / BARO
BB61_BARO_UNIT = {26: 0, 27: 1}    # IN / HPA
BB61_MAP_MODE = {28: 0, 29: 1, 30: 2, 31: 3}  # APP / VOR / MAP / PLN
BB61_MAP_RANGE = {
    32: 0, 33: 1, 34: 2, 35: 3,
    36: 4, 37: 5, 38: 6, 39: 7,
}
# BUG-14: these were read as four independent spring contacts, so the only
# thing the panel could say was "a detent was touched". The 3M PDC L FULL
# capture shows five contacts per knob, and the two that were missing are the
# ones the owner was asking about. Turning to the detent asserts 42 (or 40);
# tugging past the notch drops it and asserts 21 (or 20) for as long as the
# knob is held there. Read as four bits, that gesture produced two clicks - the
# detent on the way out and again on the way back - instead of a fast run.
BB61_DETENT_KNOBS: Dict[str, Dict[str, int]] = {
    "mins": {"dec": 40, "rest": 41, "inc": 42, "dec_fast": 20, "inc_fast": 21},
    "baro": {"dec": 43, "rest": 44, "inc": 45, "dec_fast": 22, "inc_fast": 23},
}

BB52_MOMENTARY: Dict[int, str] = {
    1: "fpv",
    2: "mtrs",
    3: "vsd",
    4: "wxr",
    5: "sta",
    6: "wpt",
    7: "arpt",
    8: "data",
    9: "pos",
    10: "terr",
    17: "mins_rst",
    18: "ctr",
    19: "tfc",
    20: "baro_std",
    21: "range_dec",
    22: "range_inc",
}
BB52_VOR1 = {11: 0, 12: 1, 13: 2}
BB52_VOR2 = {14: 0, 15: 1, 16: 2}
# BUG-12, the same inversion on the right-hand unit: mins 25..26, baro 27..28,
# then MAP MODE from 29.
BB52_MINS_MODE = {25: 0, 26: 1}    # RADIO / BARO
BB52_BARO_UNIT = {27: 0, 28: 1}    # IN / HPA
BB52_MAP_MODE = {29: 0, 30: 1, 31: 2, 32: 3}
# The right-hand unit carries the same five contacts per knob, but it does not
# lay them out the same way, so these are read from the 3M PDC R FULL capture
# rather than mirrored from BB61. MINS is a tidy ladder 33..37; BARO keeps its
# detents at 38..40 and puts its two past-the-notch contacts back at 23 and 24.
BB52_DETENT_KNOBS: Dict[str, Dict[str, int]] = {
    "mins": {"dec": 34, "rest": 35, "inc": 36, "dec_fast": 33, "inc_fast": 37},
    "baro": {"dec": 38, "rest": 39, "inc": 40, "dec_fast": 23, "inc_fast": 24},
}



# BB51 independently verified by the owner's 38-step 2026-09-11 capture.
# Evidence SHA256: c5b68f0909d6d070374900681bccf48b9bf2f67c886d3f8f83c52d641bcf5ecc
BB51_MOMENTARY = {4: 'wxr', 5: 'sta', 6: 'wpt', 7: 'arpt', 8: 'data', 9: 'pos', 10: 'terr', 1: 'fpv', 2: 'mtrs', 3: 'vsd', 17: 'mins_rst', 20: 'baro_std', 18: 'ctr', 19: 'tfc', 22: 'range_inc', 21: 'range_dec'}
BB51_SELECTOR_MAPS = (('mins_mode', {25: 0, 26: 1}), ('baro_unit', {27: 0, 28: 1}), ('vor1', {11: 0, 12: 1, 13: 2}), ('vor2', {14: 0, 15: 1, 16: 2}), ('map_mode', {29: 0, 30: 1, 31: 2, 32: 3}))
BB51_DETENT_KNOBS = {'mins': {'dec': 34, 'inc': 36, 'dec_fast': 33, 'inc_fast': 37, 'rest': 35}, 'baro': {'dec': 38, 'inc': 40, 'dec_fast': 23, 'inc_fast': 24, 'rest': 39}}

class _FixedPDCBase:
    """One exact-PID read-only HID owner with automatic unplug/replug recovery."""

    product_label = "PDC"
    candidate_pids: Tuple[int, ...] = ()   # subclasses set; first is preferred
    side = ""
    momentary: Mapping[int, str] = {}
    selector_maps: Sequence[Tuple[str, Mapping[int, Any]]] = ()
    detent_knobs: Mapping[str, Mapping[str, int]] = {}

    def __init__(
        self,
        *,
        diagnose: bool = False,
        action_sink: Optional[Callable[[PDCEvent], None]] = None,
        keep_3m_backlight_on: bool = False,
    ) -> None:
        self.keep_3m_backlight_on = bool(keep_3m_backlight_on)
        self.diagnose = bool(diagnose)
        self._action_sink = action_sink
        self._active_pid: Optional[int] = None

        self._state_lock = threading.RLock()
        self._status = "stopped"
        self._status_detail = ""
        self._last_error = ""
        self._last_report: Optional[bytes] = None
        self._last_bits = 0
        self._mirror: Dict[str, Any] = {}
        self._ever_connected = False
        self._backlight_requested: Optional[int] = None
        self._backlight_sent: Optional[int] = None
        self._startup_ready = threading.Event()

        # Detent-knob state: the phase each knob is in, and when the next fast
        # step is due. Bounded by the number of knobs, never by how long the
        # session runs.
        self._knob_phase: Dict[str, Tuple[str, str]] = {}
        self._knob_repeat_at: Dict[str, Tuple[float, str]] = {}
        self._knob_pressed: Dict[str, str] = {}
        self._clock: Callable[[], float] = time.monotonic

        self.stop_evt = threading.Event()
        self._reader: Optional[threading.Thread] = None
        self._event_worker: Optional[threading.Thread] = None
        self._event_q: "queue.Queue[PDCEvent]" = queue.Queue(maxsize=512)

    @property
    def pid(self) -> int:
        """The PID we are currently open on, or the preferred PID if not yet connected."""
        return self._active_pid if self._active_pid is not None else (self.candidate_pids[0] if self.candidate_pids else 0)

    @property
    def output_model_byte(self) -> int:
        """Model byte for the backlight packet: 0x60 for 3N panels, 0x50 for 3M panels."""
        return 0x60 if self.pid in _3N_PIDS else 0x50

    @property
    def status(self) -> str:
        with self._state_lock:
            return self._status

    @property
    def status_detail(self) -> str:
        with self._state_lock:
            return self._status_detail

    @property
    def last_state(self) -> Optional[PDCState]:
        with self._state_lock:
            report = self._last_report
            if report is None:
                return None
            axes: Tuple[int, ...] = ()
            if len(report) > 14:
                # Captures show the two SDL-exposed auxiliary values in this
                # region.  They are diagnostic only; PDC control decoding never
                # depends on them.
                axes = (int(report[13]), int(report[14]))
            return PDCState(
                buttons=_active_buttons(report),
                axes=axes,
                report=bytes(report),
            )

    def set_action_sink(
        self,
        sink: Optional[Callable[[PDCEvent], None]],
    ) -> None:
        self._action_sink = sink

    @staticmethod
    def _normalize_backlight(value: Any) -> int:
        try:
            level = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("PDC panel_backlight must be numeric") from exc
        if not (level == level and abs(level) != float("inf")):
            raise ValueError("PDC panel_backlight must be finite")
        if 0.0 <= level <= 1.0:
            level *= PDC_BACKLIGHT_MAX
        return max(PDC_BACKLIGHT_MIN, min(PDC_BACKLIGHT_MAX, int(round(level))))

    def _backlight_packet(self, brightness: Any) -> bytes:
        value = self._normalize_backlight(brightness)
        model = int(self.output_model_byte) & 0xFF
        if model not in {0x50, 0x60}:
            raise RuntimeError(f"No captured fixed-PDC output model byte for {self.pid:04X}")
        return bytes((
            0x02, model, 0xBB, 0x00, 0x00, 0x03, 0x49,
            PDC_BACKLIGHT_CHANNEL, value, 0x00, 0x00, 0x00, 0x00, 0x00,
        ))

    def set_lab_output(self, control_key: str, value: Any) -> int:
        # The control-server thread only changes desired state. The same reader
        # thread that owns this exact HID handle performs the physical write.
        if str(control_key) != "panel_backlight":
            raise ValueError(f"Unsupported fixed-PDC output {control_key!r}")
        level = self._normalize_backlight(value)
        with self._state_lock:
            self._backlight_requested = level
        return level

    def _write_backlight(self, device: Any, brightness: Any) -> int:
        level = self._normalize_backlight(brightness)
        device.write(list(self._backlight_packet(level)))
        with self._state_lock:
            self._backlight_sent = level
        return level

    def _write_requested_backlight(self, device: Any, *, force: bool = False) -> None:
        with self._state_lock:
            requested = self._backlight_requested
            sent = self._backlight_sent
        # Owner-requested 3M exception: its backlight stays on while this
        # owner runs in Live/Practice, including simulator-off and idle states.
        # Only verified 3M PIDs qualify. Shutdown writes zero directly below.
        if self.keep_3m_backlight_on and self.pid in (0xBB51, 0xBB52):
            requested = 255
        if requested is None or (not force and requested == sent):
            return
        self._write_backlight(device, requested)

    def _set_status(self, state: str, detail: str = "") -> None:
        with self._state_lock:
            self._status = str(state)
            self._status_detail = str(detail)

    def _enumerate(self) -> List[Dict[str, Any]]:
        if hid is None:
            return []
        for pid in self.candidate_pids:
            rows = list(hid.enumerate(PDC_VID, int(pid)))
            if rows:
                self._active_pid = pid
                rows.sort(
                    key=lambda item: (
                        0 if int(item.get("usage_page", 0) or 0) == 0x01 else 1,
                        0 if int(item.get("usage", 0) or 0) == 0x04 else 1,
                        int(item.get("interface_number", -1) or -1),
                    )
                )
                return rows
        self._active_pid = None
        return []

    def _present(self) -> bool:
        try:
            return bool(self._enumerate())
        except Exception:
            return False

    def _open(self):
        if hid is None:
            raise RuntimeError("hidapi is unavailable")
        entries = self._enumerate()
        if not entries:
            raise FileNotFoundError(
                f"{self.product_label} VID 4098 PID {self.pid:04X} not found"
            )
        # BUG-13: this used to take entries[0] with no further check. The PDC
        # role is carried by the PID, which SimAppPro can reassign, so if both
        # units are ever left on the same PID two owners silently fight over
        # one physical panel and the other is never seen at all. The serial is
        # burned into each unit and does not move with the role, so it is the
        # only reliable way to tell one box from the other.
        serials = {
            str(row.get("serial_number") or "").strip()
            for row in entries
            if str(row.get("serial_number") or "").strip()
        }
        if len(serials) > 1:
            raise RuntimeError(
                f"{self.product_label}: {len(serials)} different WinWing units are "
                f"reporting PID {self.pid:04X} ({', '.join(sorted(serials))}). "
                "MuslimSim will not guess which one holds this role. Give each "
                "unit its own role in SimAppPro so one panel answers per PID."
            )
        path = entries[0].get("path")
        if not path:
            raise RuntimeError("Windows HID path is missing")
        device = hid.device()
        device.open_path(path)
        try:
            device.set_nonblocking(1)
        except Exception:
            pass
        with self._state_lock:
            self._serial = str(entries[0].get("serial_number") or "").strip()
        return device, entries[0]

    def _queue_event(self, event: PDCEvent) -> None:
        try:
            self._event_q.put_nowait(event)
        except queue.Full:
            try:
                self._event_q.get_nowait()
            except queue.Empty:
                pass
            try:
                self._event_q.put_nowait(event)
            except queue.Full:
                pass

    def _emit(self, control: str, value: Any, phase: str = "change") -> None:
        self._queue_event(
            PDCEvent(
                control=str(control),
                value=value,
                phase=str(phase),
                side=self.side,
            )
        )

    def _decode_maintained(self, bits: int) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        for control, mapping in self.selector_maps:
            value = _first_pressed(bits, mapping)
            if value is not None:
                values[control] = value
        return values

    # ---- detent knobs (MINS / BARO) ---------------------------------
    #
    # Five contacts per knob, three phases:
    #
    #     rest  ->  detent  ->  fast
    #
    # Turning to the detent is one click. Holding past the notch is a fast run
    # at PDC_KNOB_FAST_PERIOD. Letting go springs the knob back through the
    # detent to rest, and that return is not a turn - it is the spring - so it
    # must not click again.

    def _knob_position(
        self,
        knob: Mapping[str, int],
        bits: int,
    ) -> Tuple[str, str]:
        """The phase and direction one knob is showing right now."""

        for direction in ("inc", "dec"):
            button = knob.get(direction + "_fast")
            if button and _pressed(bits, button):
                return "fast", direction
        for direction in ("inc", "dec"):
            button = knob.get(direction)
            if button and _pressed(bits, button):
                return "detent", direction
        return "rest", ""

    def _reset_detent_knobs(self) -> None:
        with self._state_lock:
            names = list(self._knob_pressed)
            self._knob_phase = {}
            self._knob_repeat_at = {}
        # Whatever was being held is not being held any more.
        for name in names:
            self._release_knob(name)
        with self._state_lock:
            self._knob_pressed = {}

    def _seed_detent_knobs(self, bits: int) -> None:
        """Adopt the knob positions at connect without calling them turns.

        Momentary and relative inputs are never replayed at connection. A knob
        the owner happens to be holding when the panel is plugged in is a
        position to adopt, not a click to send to the simulator.
        """

        seeded = {
            name: self._knob_position(knob, bits)
            for name, knob in self.detent_knobs.items()
        }
        with self._state_lock:
            self._knob_phase = seeded
            self._knob_repeat_at = {}
            self._knob_pressed = {}

    def _emit_knob_step(self, name: str, direction: str) -> None:
        """One click of a knob.

        Press only. The release comes when the knob is back at rest, and that
        matters more than it looks: ``HardwareLab.input`` keeps one record per
        control, last event wins, and Studio only animates a knob whose latest
        record is a press with a non-zero value. Emitting the release straight
        after the press would leave every knob reading "released" between
        frames and the faceplate would sit still while the real panel turned.
        Repeats re-press, the way a held key repeats, so each step carries a
        fresh timestamp for Studio to see.
        """

        control = f"{name}_{direction}"
        with self._state_lock:
            held = self._knob_pressed.get(name)
            self._knob_pressed[name] = control
        if held is not None and held != control:
            self._emit(held, 0, "release")
        self._emit(control, 1, "press")

    def _release_knob(self, name: str) -> None:
        """The knob is back at rest; let go of whatever it was pressing."""

        with self._state_lock:
            control = self._knob_pressed.pop(name, None)
        if control is not None:
            self._emit(control, 0, "release")

    def _update_detent_knobs(self, bits: int) -> None:
        if not self.detent_knobs:
            return
        for name, knob in self.detent_knobs.items():
            phase, direction = self._knob_position(knob, bits)
            with self._state_lock:
                was_phase, was_direction = self._knob_phase.get(name, ("rest", ""))
                if (phase, direction) == (was_phase, was_direction):
                    continue
                self._knob_phase[name] = (phase, direction)
                if phase == "fast":
                    self._knob_repeat_at[name] = (
                        self._clock() + PDC_KNOB_FAST_PERIOD, direction,
                    )
                else:
                    self._knob_repeat_at.pop(name, None)

            # A click is the entry into a detent from rest. Entering the fast
            # position straight from rest means the detent was crossed inside
            # one USB frame, and that click still happened. Coming back the
            # other way - fast to detent to rest - is the spring, not a turn.
            if phase == "rest":
                self._release_knob(name)
            elif was_phase == "rest":
                self._emit_knob_step(name, direction)

    def _service_detent_knobs(self) -> None:
        """Repeat whichever knobs are held past the notch.

        Driven from the reader loop, which already spins on a non-blocking
        read, so a held knob costs no thread and no timer of its own however
        many panels are added later.
        """

        with self._state_lock:
            if not self._knob_repeat_at:
                return
            now = self._clock()
            due = [
                (name, direction)
                for name, (at, direction) in self._knob_repeat_at.items()
                if now >= at
            ]
            # The next step is due a period from now, not a period from when
            # this one was owed, so a stalled loop cannot bank up a burst.
            for name, direction in due:
                self._knob_repeat_at[name] = (now + PDC_KNOB_FAST_PERIOD, direction)
        for name, direction in due:
            self._emit_knob_step(name, direction)

    def _accept_baseline(self, report: bytes) -> None:
        bits = _button_bits(report)
        maintained = self._decode_maintained(bits)
        with self._state_lock:
            self._last_report = bytes(report)
            self._last_bits = bits
            self._mirror = dict(maintained)
        self._seed_detent_knobs(bits)
        # Maintained positions are safe to snapshot.  Momentary, spring and
        # relative inputs are intentionally NOT replayed at connection.
        for control, value in maintained.items():
            self._emit(control, value, "baseline")
        self._emit("__lifecycle__", 1, "connected")

    def _accept_report(self, report: bytes) -> None:
        report = bytes(report)
        bits = _button_bits(report)
        with self._state_lock:
            old_bits = self._last_bits
            old_maintained = self._decode_maintained(old_bits)
            self._last_report = report
            self._last_bits = bits

        # Momentary / relative inputs are edge-driven.
        for button, control in self.momentary.items():
            before = _pressed(old_bits, button)
            after = _pressed(bits, button)
            if before == after:
                continue
            self._emit(control, int(after), "press" if after else "release")

        # The MINS and BARO knobs are two-stage detent rotaries, not spring
        # switches, so they are decoded as a phase change rather than as four
        # loose contacts.
        self._update_detent_knobs(bits)

        maintained = self._decode_maintained(bits)
        with self._state_lock:
            self._mirror.update(maintained)
        for control, value in maintained.items():
            if old_maintained.get(control) != value:
                self._emit(control, value, "change")

        if self.diagnose:
            print(
                f"{self.product_label} report buttons={_active_buttons(report)} "
                f"maintained={maintained}"
            )

    def replay_maintained(self) -> None:
        with self._state_lock:
            report = self._last_report
        if report is None:
            return
        maintained = self._decode_maintained(_button_bits(report))
        for control, value in maintained.items():
            self._emit(control, value, "baseline")

    def _event_loop(self) -> None:
        while not self.stop_evt.is_set() or not self._event_q.empty():
            try:
                event = self._event_q.get(timeout=0.10)
            except queue.Empty:
                continue
            sink = self._action_sink
            if sink is None:
                continue
            try:
                sink(event)
            except Exception as exc:
                with self._state_lock:
                    self._last_error = f"{type(exc).__name__}: {exc}"
                if self.diagnose:
                    print(
                        f"{self.product_label} action sink error: "
                        f"{type(exc).__name__}: {exc}"
                    )

    def _read_first_stable(self, device) -> bytes:
        deadline = time.monotonic() + 1.20
        last: Optional[bytes] = None
        last_change = time.monotonic()
        while not self.stop_evt.is_set() and time.monotonic() < deadline:
            data = device.read(READ_SIZE)
            if not data:
                time.sleep(IDLE_SLEEP)
                continue
            report = bytes(data)
            if not _is_input_report(report):
                continue
            if report != last:
                last = report
                last_change = time.monotonic()
                continue
            if time.monotonic() - last_change >= 0.08:
                return report
        if last is None:
            raise RuntimeError("no input report received")
        return last

    def _reader_loop(self) -> None:
        self._set_status("starting", "starting USB supervisor")
        device = None
        next_presence_check = 0.0

        while not self.stop_evt.is_set():
            if device is None:
                if hid is None:
                    self._startup_ready.set()
                    self._set_status(
                        "waiting-for-usb",
                        "hidapi unavailable; install Python hidapi",
                    )
                    self.stop_evt.wait(0.50)
                    continue

                entries = []
                try:
                    entries = self._enumerate()
                except Exception as exc:
                    with self._state_lock:
                        self._last_error = f"{type(exc).__name__}: {exc}"
                if not entries:
                    self._startup_ready.set()
                    state = "reconnecting" if self._ever_connected else "waiting-for-usb"
                    self._set_status(
                        state,
                        f"USB 4098:{self.pid:04X} not present",
                    )
                    self.stop_evt.wait(ENUM_INTERVAL)
                    continue

                self._set_status(
                    "connecting",
                    f"opening USB 4098:{self.pid:04X}",
                )
                try:
                    device, entry = self._open()
                    baseline = self._read_first_stable(device)
                    self._accept_baseline(baseline)
                    self._write_requested_backlight(device, force=True)
                    self._ever_connected = True
                    self._set_status(
                        "connected",
                        str(entry.get("product_string") or self.product_label),
                    )
                    next_presence_check = time.monotonic() + ENUM_INTERVAL
                    if self.diagnose:
                        print(
                            f"{self.product_label} CONNECTED "
                            f"4098:{self.pid:04X}"
                        )
                    continue
                except Exception as exc:
                    if device is not None:
                        try:
                            device.close()
                        except Exception:
                            pass
                    device = None
                    with self._state_lock:
                        self._last_error = f"{type(exc).__name__}: {exc}"
                    self._startup_ready.set()
                    self._set_status("reconnecting", str(exc))
                    self.stop_evt.wait(ENUM_INTERVAL)
                    continue

            # Connected read loop.
            try:
                data = device.read(READ_SIZE)
                if data:
                    report = bytes(data)
                    if _is_input_report(report):
                        with self._state_lock:
                            previous = self._last_report
                        if previous != report:
                            self._accept_report(report)
                else:
                    time.sleep(IDLE_SLEEP)

                self._service_detent_knobs()
                self._write_requested_backlight(device)
                now = time.monotonic()
                if now >= next_presence_check:
                    next_presence_check = now + ENUM_INTERVAL
                    if not self._present():
                        raise OSError(
                            f"USB 4098:{self.pid:04X} disconnected"
                        )
            except Exception as exc:
                if self.diagnose:
                    print(
                        f"{self.product_label} DISCONNECTED: "
                        f"{type(exc).__name__}: {exc}"
                    )
                try:
                    device.close()
                except Exception:
                    pass
                device = None
                with self._state_lock:
                    self._last_report = None
                    self._last_bits = 0
                    self._mirror = {}
                    self._backlight_sent = None
                    self._last_error = f"{type(exc).__name__}: {exc}"
                # A knob held past the notch when the cable is pulled must stop
                # repeating, not run on against a panel that is no longer there.
                self._reset_detent_knobs()
                self._emit("__lifecycle__", 0, "disconnected")
                self._set_status(
                    "reconnecting",
                    f"USB 4098:{self.pid:04X} disconnected",
                )

        if device is not None:
            try:
                self._write_backlight(device, 0)
            except Exception:
                pass
            try:
                device.close()
            except Exception:
                pass
        self._set_status("stopped", "")

    def start(self) -> None:
        if self._reader is not None and self._reader.is_alive():
            return
        self.stop_evt.clear()
        self._startup_ready.clear()
        self._event_worker = threading.Thread(
            target=self._event_loop,
            name=f"MuslimSim-{self.pid:04X}-events",
            daemon=True,
        )
        self._reader = threading.Thread(
            target=self._reader_loop,
            name=f"MuslimSim-{self.pid:04X}-usb",
            daemon=True,
        )
        self._event_worker.start()
        self._reader.start()
        self._startup_ready.wait(1.35)

    def stop(self) -> None:
        self.stop_evt.set()
        if self._reader is not None and self._reader.is_alive():
            self._reader.join(timeout=2.0)
        if self._event_worker is not None and self._event_worker.is_alive():
            self._event_worker.join(timeout=1.0)
        self._reader = None
        self._event_worker = None
        self._set_status("stopped", "")

    def service_snapshot(self) -> Dict[str, Any]:
        with self._state_lock:
            report = self._last_report
            return {
                "state": self._status,
                "detail": self._status_detail,
                "side": self.side,
                "product": self.product_label,
                "vid": PDC_VID,
                "pid": int(self.pid),
                # The PID says which role SimAppPro currently assigns; the
                # serial says which physical box that is. Only the serial
                # survives a role reassignment, so Studio can use it to notice
                # that two known units have swapped rather than treating them
                # as unknown hardware.
                "serial": getattr(self, "_serial", ""),
                "present": report is not None,
                "mirror": {**dict(self._mirror), "panel_backlight": self._backlight_sent},
            }

    def diagnostics_snapshot(self) -> Dict[str, Any]:
        with self._state_lock:
            report = self._last_report
            return {
                "state": self._status,
                "detail": self._status_detail,
                "side": self.side,
                "product": self.product_label,
                "vid": f"{PDC_VID:04X}",
                "pid": f"{self.pid:04X}",
                "serial": getattr(self, "_serial", ""),
                "buttons": [] if report is None else list(_active_buttons(report)),
                "selectors": dict(self._mirror),
                "raw_hex": None if report is None else report.hex(" "),
                "panel_backlight_requested": self._backlight_requested,
                "panel_backlight_sent": self._backlight_sent,
                "last_error": self._last_error,
            }


class MuslimSimPDCBB61Left(_FixedPDCBase):
    product_label = "WINWING PDC Captain"
    candidate_pids = (BB61_PID, BB51_PID)   # 3N preferred; 3M accepted when configured as Captain
    side = "capt"
    momentary = BB61_MOMENTARY
    selector_maps = (
        ("vor1", BB61_VOR1),
        ("vor2", BB61_VOR2),
        ("mins_mode", BB61_MINS_MODE),
        ("baro_unit", BB61_BARO_UNIT),
        ("map_mode", BB61_MAP_MODE),
        ("map_range", BB61_MAP_RANGE),
    )
    detent_knobs = BB61_DETENT_KNOBS

    def _accept_baseline(self, report: bytes) -> None:
        # Select once per connection, before decoding or seeding knob phases.
        # Keep the legacy role key and saved bindings; only the raw map differs.
        if self.pid == BB51_PID:
            self.momentary = BB51_MOMENTARY
            self.selector_maps = BB51_SELECTOR_MAPS
            self.detent_knobs = BB51_DETENT_KNOBS
        else:
            self.momentary = type(self).momentary
            self.selector_maps = type(self).selector_maps
            self.detent_knobs = type(self).detent_knobs
        super()._accept_baseline(report)

    def _present(self) -> bool:
        # A connected BB51 must not adopt BB61's identity/output model just
        # because another panel becomes visible in the preferred PID scan.
        if self._last_report is not None and self._active_pid is not None:
            try:
                return bool(hid is not None and hid.enumerate(PDC_VID, self._active_pid))
            except Exception:
                return False
        return super()._present()


class MuslimSimPDCBB52Right(_FixedPDCBase):
    product_label = "WINWING PDC First Officer"
    candidate_pids = (BB52_PID,)   # 3M only; 3N FO (BB62) handled by pdc_bb62 driver
    side = "fo"
    momentary = BB52_MOMENTARY
    selector_maps = (
        ("vor1", BB52_VOR1),
        ("vor2", BB52_VOR2),
        ("mins_mode", BB52_MINS_MODE),
        ("baro_unit", BB52_BARO_UNIT),
        ("map_mode", BB52_MAP_MODE),
    )
    detent_knobs = BB52_DETENT_KNOBS


class MuslimSimPDCZiboSideDispatcher:
    """Zibo dispatcher + maintained-position authority for one fixed crew side."""

    BUTTON_SUFFIX = {
        "wxr": "wxr_press",
        "sta": "sta_press",
        "wpt": "wpt_press",
        "arpt": "arpt_press",
        "data": "data_press",
        "pos": "pos_press",
        "terr": "terr_press",
        "mins_rst": "rst_press",
        "ctr": "ctr_press",
        "tfc": "tfc_press",
        "baro_std": "std_press",
        "mtrs": "mtrs_press",
        "fpv": "fpv_press",
    }

    def __init__(
        self,
        *,
        api_version: str,
        side: str,
        resolve_dataref_id: Callable[[str, str], int],
        read_dataref: Callable[..., Any],
        set_dataref: Callable[[str, int, Any], None],
        resolve_command_id: Callable[[str, str], int],
        activate_command: Callable[..., None],
        diagnose: bool = False,
        authority_allowed: Optional[Callable[[str], bool]] = None,
    ) -> None:
        side = str(side).strip().lower()
        if side not in {"capt", "fo"}:
            raise ValueError("side must be 'capt' or 'fo'")

        self.api_version = api_version
        self.side = side
        self.resolve_dataref_id = resolve_dataref_id
        self.read_dataref = read_dataref
        self.set_dataref = set_dataref
        self.resolve_command_id = resolve_command_id
        self.activate_command = activate_command
        self.diagnose = bool(diagnose)
        self.authority_allowed = authority_allowed

        self._command_ids: Dict[str, Optional[int]] = {}
        self._dataref_ids: Dict[str, Optional[int]] = {}
        self._targets: Dict[str, float] = {}
        self._lock = threading.RLock()
        self._stop_evt = threading.Event()

        crew = "capt" if self.side == "capt" else "fo"
        mins_crew = "cpt" if self.side == "capt" else "fo"
        self._feedback_names = {
            "map_mode": f"laminar/B738/EFIS_control/{crew}/map_mode_pos",
            "map_range": f"laminar/B738/EFIS/{crew}/map_range",
            "mins_mode": f"laminar/B738/EFIS_control/{mins_crew}/minimums",
            "baro_unit": f"laminar/B738/EFIS_control/{crew}/baro_in_hpa",
        }

        self._authority_thread = threading.Thread(
            target=self._authority_loop,
            name=f"MuslimSim-PDC-{self.side}-authority",
            daemon=True,
        )
        self._authority_thread.start()

    def _allowed(self, control: str) -> bool:
        callback = self.authority_allowed
        if callback is None:
            return True
        try:
            return bool(callback(control))
        except Exception:
            return False

    def _resolve_command(self, name: str) -> Optional[int]:
        if name in self._command_ids:
            return self._command_ids[name]
        try:
            command_id = int(self.resolve_command_id(self.api_version, name))
        except Exception:
            command_id = None
        self._command_ids[name] = command_id
        return command_id

    def _resolve_dataref(self, control: str) -> Optional[int]:
        if control in self._dataref_ids:
            return self._dataref_ids[control]
        name = self._feedback_names.get(control)
        if not name:
            return None
        try:
            ref_id = int(self.resolve_dataref_id(self.api_version, name))
        except Exception:
            ref_id = None
        self._dataref_ids[control] = ref_id
        return ref_id

    def _pulse(self, name: str, *, repeat: int = 1) -> bool:
        command_id = self._resolve_command(name)
        if command_id is None:
            if self.diagnose:
                print(f"PDC {self.side}: command unavailable {name}")
            return False
        ok = True
        for index in range(max(1, int(repeat))):
            try:
                self.activate_command(
                    self.api_version,
                    int(command_id),
                    duration=0.0,
                )
            except TypeError:
                self.activate_command(self.api_version, int(command_id))
            except Exception:
                self._command_ids.pop(name, None)
                ok = False
                break
            if index + 1 < repeat:
                time.sleep(0.018)
        return ok

    def _crew_command(self, suffix: str) -> str:
        return (
            f"laminar/B738/EFIS_control/"
            f"{'capt' if self.side == 'capt' else 'fo'}/{suffix}"
        )

    def _button(self, control: str) -> None:
        if control == "vsd":
            if self.side != "fo":
                return
            candidates = (
                "laminar/B738/EFIS_control/fo/push_button/vsd_press",
                "laminar/B738/EFIS_control/fo/vsd_press",
            )
            for name in candidates:
                if self._pulse(name):
                    return
            return
        suffix = self.BUTTON_SUFFIX.get(control)
        if suffix:
            self._pulse(self._crew_command(f"push_button/{suffix}"))

    def _directional_pair(self, control: str) -> Tuple[str, str]:
        crew = "capt" if self.side == "capt" else "fo"
        if control == "map_mode":
            return (
                f"laminar/B738/EFIS_control/{crew}/map_mode_up",
                f"laminar/B738/EFIS_control/{crew}/map_mode_dn",
            )
        if control == "map_range":
            return (
                f"laminar/B738/EFIS_control/{crew}/map_range_up",
                f"laminar/B738/EFIS_control/{crew}/map_range_dn",
            )
        if control == "baro_unit":
            return (
                f"laminar/B738/EFIS_control/{crew}/baro_in_hpa_up",
                f"laminar/B738/EFIS_control/{crew}/baro_in_hpa_dn",
            )
        if control == "mins_mode":
            mins_crew = "cpt" if self.side == "capt" else "fo"
            return (
                f"laminar/B738/EFIS_control/{mins_crew}/minimums_up",
                f"laminar/B738/EFIS_control/{mins_crew}/minimums_dn",
            )
        raise KeyError(control)

    def _set_maintained(self, control: str, target: float) -> None:
        if not self._allowed(control):
            self.release_control(control)
            return

        ref_id = self._resolve_dataref(control)
        wrote = False
        if ref_id is not None:
            try:
                self.set_dataref(self.api_version, int(ref_id), float(target))
                wrote = True
            except Exception:
                self._dataref_ids.pop(control, None)

        # If an aircraft revision blocks the absolute write, deterministically
        # saturate with the same native directional commands used by BB62.
        if not wrote:
            try:
                up, down = self._directional_pair(control)
            except KeyError:
                up = down = ""
            if up and down:
                max_value = {
                    "map_mode": 3,
                    "map_range": 7,
                    "mins_mode": 1,
                    "baro_unit": 1,
                }[control]
                self._pulse(up, repeat=max_value + 2)
                down_steps = max_value - int(round(target))
                if down_steps > 0:
                    self._pulse(down, repeat=down_steps)

        with self._lock:
            self._targets[control] = float(target)

        if self.diagnose:
            print(
                f"PDC {self.side} physical authority target "
                f"{control}={target:g}"
            )

    def _set_vor(self, control: str, target: int) -> None:
        # No trustworthy position-feedback DataRef has been proven for these
        # selectors.  Reconnect/physical movement is deterministic, but there
        # is intentionally no continuous mouse-takeover monitor for VOR1/2.
        target = max(0, min(2, int(target)))
        crew = "capt" if self.side == "capt" else "fo"
        base = f"laminar/B738/EFIS_control/{crew}/{control}_off"
        up = base + "_up"
        down = base + "_dn"

        if target == 0:          # VOR
            self._pulse(up, repeat=2)
        elif target == 1:        # OFF
            self._pulse(up, repeat=2)
            self._pulse(down, repeat=1)
        else:                    # ADF
            self._pulse(down, repeat=2)

    def release_control(self, control: str) -> None:
        with self._lock:
            self._targets.pop(str(control), None)

    def _relative(self, control: str) -> None:
        crew = "capt" if self.side == "capt" else "fo"
        if control == "range_inc":
            self._pulse(f"laminar/B738/EFIS_control/{crew}/map_range_up")
        elif control == "range_dec":
            self._pulse(f"laminar/B738/EFIS_control/{crew}/map_range_dn")
        elif control == "mins_inc":
            self._pulse(
                "laminar/B738/pfd/"
                + ("dh_pilot_up" if self.side == "capt" else "dh_copilot_up")
            )
        elif control == "mins_dec":
            self._pulse(
                "laminar/B738/pfd/"
                + ("dh_pilot_dn" if self.side == "capt" else "dh_copilot_dn")
            )
        elif control == "baro_inc":
            self._pulse(
                "laminar/B738/"
                + ("pilot/barometer_up" if self.side == "capt" else "copilot/barometer_up")
            )
        elif control == "baro_dec":
            self._pulse(
                "laminar/B738/"
                + ("pilot/barometer_down" if self.side == "capt" else "copilot/barometer_down")
            )

    def __call__(self, event: PDCEvent) -> None:
        control = str(event.control)
        phase = str(event.phase)

        if control == "__lifecycle__":
            if not bool(event.value):
                with self._lock:
                    self._targets.clear()
            return

        if control in {"map_mode", "map_range", "mins_mode", "baro_unit"}:
            self._set_maintained(control, float(event.value))
            return

        if control in {"vor1", "vor2"}:
            if self._allowed(control):
                self._set_vor(control, int(event.value))
            return

        if phase != "press" or not bool(event.value):
            return

        if control in self.BUTTON_SUFFIX or control == "vsd":
            self._button(control)
            return

        if control in {
            "range_inc", "range_dec",
            "mins_inc", "mins_dec",
            "baro_inc", "baro_dec",
        }:
            self._relative(control)

    def _read_value(self, control: str, ref_id: int) -> Optional[float]:
        try:
            value = self.read_dataref(self.api_version, int(ref_id), timeout=0.30)
        except TypeError:
            try:
                value = self.read_dataref(self.api_version, int(ref_id))
            except Exception:
                return None
        except Exception:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _authority_loop(self) -> None:
        while not self._stop_evt.is_set():
            with self._lock:
                targets = dict(self._targets)

            for control, target in targets.items():
                if self._stop_evt.is_set():
                    break
                if not self._allowed(control):
                    continue
                ref_id = self._resolve_dataref(control)
                if ref_id is None:
                    continue
                actual = self._read_value(control, ref_id)
                if actual is None:
                    continue
                if abs(actual - target) <= 0.20:
                    continue
                try:
                    self.set_dataref(self.api_version, int(ref_id), float(target))
                    if self.diagnose:
                        print(
                            f"PDC {self.side} AUTHORITY {control}: "
                            f"virtual={actual:g} physical={target:g} -> restored"
                        )
                except Exception:
                    self._dataref_ids.pop(control, None)
            self._stop_evt.wait(0.10)

    def stop(self) -> None:
        self._stop_evt.set()
        if self._authority_thread.is_alive():
            self._authority_thread.join(timeout=1.0)


def _selftest_report(buttons: Iterable[int], *, counter: int = 0) -> bytes:
    report = bytearray(64)
    report[0] = 0x01
    bits = 0
    for button in buttons:
        bits |= 1 << (int(button) - 1)
    for offset in range(8):
        report[1 + offset] = (bits >> (offset * 8)) & 0xFF
    report[13] = int(counter) & 0xFF
    report[14] = (int(counter) >> 8) & 0xFF
    return bytes(report)


def selftest() -> None:
    # Captured canonical baselines.
    bb61 = _selftest_report((11, 14, 25, 27, 28, 32, 41, 44))
    left = MuslimSimPDCBB61Left()
    decoded_left = left._decode_maintained(_button_bits(bb61))
    assert decoded_left == {
        "vor1": 1,
        "vor2": 1,
        "mins_mode": 0,
        "baro_unit": 0,
        "map_mode": 0,
        "map_range": 0,
    }

    bb52 = _selftest_report((12, 15, 26, 28, 29, 35, 39), counter=1)
    right = MuslimSimPDCBB52Right()
    decoded_right = right._decode_maintained(_button_bits(bb52))
    assert decoded_right == {
        "vor1": 1,
        "vor2": 1,
        "mins_mode": 0,
        "baro_unit": 0,
        "map_mode": 0,
    }

    events: List[PDCEvent] = []
    right._action_sink = events.append
    right._accept_baseline(bb52)
    # Drain queued baseline internally without threads.
    while not right._event_q.empty():
        events.append(right._event_q.get_nowait())
    # Baseline contains only maintained + lifecycle; no range pulse.
    assert not any(e.control in {"range_inc", "range_dec"} for e in events)

    events.clear()
    right._last_report = bb52
    right._last_bits = _button_bits(bb52)
    pressed = _selftest_report(
        (12, 15, 21, 26, 28, 29, 35, 39),
        counter=0,
    )
    right._accept_report(pressed)
    queued = []
    while not right._event_q.empty():
        queued.append(right._event_q.get_nowait())
    assert any(
        e.control == "range_dec" and e.phase == "press"
        for e in queued
    )

    print("PDC BB61/BB52 decoder self-test: PASS")


if __name__ == "__main__":
    selftest()
