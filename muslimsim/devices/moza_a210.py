"""Capture-proven reader for the MOZA A210 / AY210 FFB base joystick input.

``moza_A210.pcapng`` establishes the public HID input collection for
VID ``346E`` / PID ``1001``.  Report ``01`` is 34 bytes long and contains:

* eight unsigned 16-bit Generic Desktop axes (X, Y, Z, Rx, Ry, Rz, Slider,
  Dial),
* one four-bit hat switch, and
* 128 ordinary HID Button usages.

This module deliberately reads only that standard input collection.  It does
not write to the force-feedback interface or infer which physical face label
owns a particular generic button number.  The Studio can therefore show the
real yoke motion and every observed contact safely, while the user can map
the captured HID controls to a simulator role.
"""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

try:  # pragma: no cover - optional dependency is supplied by the bridge runtime
    import hid
except ImportError:  # pragma: no cover
    hid = None


MOZA_A210_VID = 0x346E
MOZA_A210_PID = 0x1001
MOZA_A210_REPORT_ID = 0x01
MOZA_A210_REPORT_LENGTH = 34
MOZA_A210_AXIS_KEYS: Tuple[str, ...] = (
    "axis_x", "axis_y", "axis_z", "axis_rx", "axis_ry", "axis_rz",
    "axis_slider", "axis_dial",
)
MOZA_A210_BUTTON_COUNT = 128
MOZA_A210_RECONNECT_SECONDS = 1.0
# A complete HID report can arrive much faster than Studio's render pulse.
# Sampling axes at 50 Hz keeps the UI responsive and still mirrors movement
# smoothly. Button edges remain immediate.
MOZA_A210_AXIS_INTERVAL_SECONDS = 0.020


@dataclass(frozen=True)
class MozaA210InputEvent:
    """One capture-proven normalized HID input event."""

    control: str
    value: float
    phase: str
    raw_value: int


InputSink = Callable[[MozaA210InputEvent], None]


def moza_a210_report(raw: Any) -> Optional[bytes]:
    """Normalize a report read by hidapi without accepting another interface."""

    report = bytes(raw or b"")
    # Some hidapi builds prepend a zero report-number byte.  The Windows
    # capture starts at Report ID 01; accept both representations only.
    if len(report) >= MOZA_A210_REPORT_LENGTH + 1 and report[0] == 0 and report[1] == MOZA_A210_REPORT_ID:
        report = report[1:]
    if len(report) < MOZA_A210_REPORT_LENGTH or report[0] != MOZA_A210_REPORT_ID:
        return None
    return report[:MOZA_A210_REPORT_LENGTH]


def decode_moza_a210_report(raw: Any) -> Optional[Dict[str, Any]]:
    """Decode exactly the HID collection described in the recorded report."""

    report = moza_a210_report(raw)
    if report is None:
        return None
    axes = {
        key: int.from_bytes(report[1 + index * 2:3 + index * 2], "little")
        for index, key in enumerate(MOZA_A210_AXIS_KEYS)
    }
    # The hat consumes the low nibble of byte 17. Button 1 starts at bit 4,
    # then continues as a contiguous 128-bit HID Button usage range.
    buttons = []
    for zero_index in range(MOZA_A210_BUTTON_COUNT):
        bit_index = 4 + zero_index
        byte_index = 17 + bit_index // 8
        bit_offset = bit_index % 8
        buttons.append(bool(report[byte_index] & (1 << bit_offset)))
    return {
        "report": report,
        "axes": axes,
        "hat": int(report[17] & 0x0F),
        "buttons": tuple(buttons),
    }


class MuslimSimMozaA210:
    """Own the A210 standard HID input handle on a background thread."""

    def __init__(
        self,
        *,
        input_sink: Optional[InputSink] = None,
        diagnose: bool = False,
        hid_api: Any = None,
        vid: int = MOZA_A210_VID,
        pid: int = MOZA_A210_PID,
        label: str = "MOZA A210",
    ) -> None:
        # MUSLIMSIM_MOZA_AB6_CAPTURE_V1
        # The AB6 (346E:1002) returns a byte-identical HID report descriptor
        # and the same 34-byte report 01 - established by reading both
        # descriptors, not assumed from the shared vendor id.  These three
        # parameters default to the A210, so every existing caller opens the
        # same device and behaves exactly as it did before.
        self.input_sink = input_sink
        self.diagnose = bool(diagnose)
        self.vid = int(vid)
        self.pid = int(pid)
        self.label = str(label)
        self._hid = hid if hid_api is None else hid_api
        self.stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._state_lock = threading.Lock()
        self._status = "stopped"
        self._last_report: Optional[bytes] = None
        self._last_snapshot: Dict[str, Any] = {}

    @property
    def status(self) -> str:
        with self._state_lock:
            return self._status

    @property
    def last_report(self) -> Optional[bytes]:
        with self._state_lock:
            return self._last_report

    def _set_status(self, value: str) -> None:
        with self._state_lock:
            self._status = str(value)

    def live_snapshot(self) -> Dict[str, Any]:
        """Return live normalized and raw values without exposing HID access."""

        with self._state_lock:
            return dict(self._last_snapshot)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self.stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"MuslimSim-{self.label.replace(' ', '-')}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._set_status("stopped")

    def _open(self) -> Any:
        if self._hid is None:
            raise RuntimeError("hidapi is not installed")
        devices = list(self._hid.enumerate(self.vid, self.pid))
        # Only the standard joystick collection (usage page 1, usage 4) has
        # the report captured above.  Do not accidentally open an FFB/vendor
        # interface with the same VID/PID.
        matches = [
            item for item in devices
            if int(item.get("usage_page") or 0) == 0x01 and int(item.get("usage") or 0) == 0x04
        ]
        if not matches:
            raise FileNotFoundError(
                f"{self.label} joystick HID interface "
                f"({self.vid:04X}:{self.pid:04X}) is not connected"
            )
        path = matches[0].get("path")
        if not path:
            raise RuntimeError(f"{self.label} HID path is unavailable")
        device = self._hid.device()
        device.open_path(path)
        try:
            device.set_nonblocking(1)
        except Exception:
            pass
        return device

    def _emit(self, control: str, value: float, phase: str, raw_value: int) -> None:
        event = MozaA210InputEvent(control, float(value), str(phase), int(raw_value))
        if self.diagnose:
            print(f"{self.label} {event.control} {event.phase} raw={event.raw_value}")
        if self.input_sink is not None:
            self.input_sink(event)

    @staticmethod
    def _normal_axis(raw_value: int) -> float:
        return max(0.0, min(1.0, int(raw_value) / 65535.0))

    def _store_snapshot(self, state: Mapping[str, Any]) -> None:
        axes = dict(state["axes"])
        buttons = tuple(bool(value) for value in state["buttons"])
        with self._state_lock:
            self._last_snapshot = {
                "state": self._status,
                "raw_axes": axes,
                "axes": {key: self._normal_axis(value) for key, value in axes.items()},
                "hat": int(state["hat"]),
                "pressed_buttons": [index + 1 for index, pressed in enumerate(buttons) if pressed],
                "report_id": MOZA_A210_REPORT_ID,
                "length": MOZA_A210_REPORT_LENGTH,
                "raw_hex": bytes(state["report"]).hex(),
            }

    def _emit_changes(self, previous: Optional[Mapping[str, Any]], current: Mapping[str, Any], *, axis_due: bool) -> None:
        if previous is None:
            # First report establishes the initial position, so Studio is
            # already aligned when it opens. Contacts are not emitted until a
            # real edge happens, preventing a held switch from being treated
            # as a fresh press at startup.
            for key, raw_value in dict(current["axes"]).items():
                self._emit(key, self._normal_axis(int(raw_value)), "change", int(raw_value))
            self._emit("hat", float(int(current["hat"])), "change", int(current["hat"]))
            return
        if axis_due:
            for key, raw_value in dict(current["axes"]).items():
                if int(raw_value) != int(dict(previous["axes"])[key]):
                    self._emit(key, self._normal_axis(int(raw_value)), "change", int(raw_value))
        if int(current["hat"]) != int(previous["hat"]):
            self._emit("hat", float(int(current["hat"])), "change", int(current["hat"]))
        for zero_index, (before, after) in enumerate(zip(previous["buttons"], current["buttons"])):
            if bool(before) == bool(after):
                continue
            number = zero_index + 1
            self._emit(
                f"button_{number:03d}",
                1.0 if after else 0.0,
                "press" if after else "release",
                1 if after else 0,
            )

    def _run(self) -> None:
        if self._hid is None:
            self._set_status("dependency-missing")
            return
        while not self.stop_event.is_set():
            device = None
            try:
                device = self._open()
                self._set_status("connected")
                previous_emitted: Optional[Dict[str, Any]] = None
                latest: Optional[Dict[str, Any]] = None
                last_axis_emit = 0.0
                while not self.stop_event.is_set():
                    decoded = decode_moza_a210_report(device.read(MOZA_A210_REPORT_LENGTH))
                    if decoded is None:
                        self.stop_event.wait(0.002)
                        continue
                    now = time.monotonic()
                    latest = decoded
                    with self._state_lock:
                        self._last_report = bytes(decoded["report"])
                    self._store_snapshot(decoded)
                    # Button and hat edges must not wait for the sampling
                    # timer; axes wait only enough to protect the UI from a
                    # high-rate USB stream.
                    immediate_change = previous_emitted is not None and (
                        int(decoded["hat"]) != int(previous_emitted["hat"])
                        or tuple(decoded["buttons"]) != tuple(previous_emitted["buttons"])
                    )
                    axis_due = previous_emitted is None or now - last_axis_emit >= MOZA_A210_AXIS_INTERVAL_SECONDS
                    if axis_due or immediate_change:
                        self._emit_changes(previous_emitted, decoded, axis_due=axis_due)
                        previous_emitted = decoded
                        if axis_due:
                            last_axis_emit = now
                # `latest` is deliberately not emitted after stop: physical
                # input may never touch a Tk thread during shutdown.
            except FileNotFoundError:
                self._set_status("waiting-for-moza-a210")
            except Exception as exc:
                self._set_status(f"reconnecting: {exc}")
            finally:
                if device is not None:
                    try:
                        device.close()
                    except Exception:
                        pass
            self.stop_event.wait(MOZA_A210_RECONNECT_SECONDS)
        self._set_status("stopped")


__all__ = (
    "MOZA_A210_AXIS_KEYS", "MOZA_A210_BUTTON_COUNT", "MOZA_A210_PID",
    "MOZA_A210_REPORT_ID", "MOZA_A210_REPORT_LENGTH", "MOZA_A210_VID",
    "MozaA210InputEvent", "MuslimSimMozaA210", "decode_moza_a210_report",
    "moza_a210_report",
)
