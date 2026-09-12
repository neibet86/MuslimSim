"""WINCTRL 32 ECAM (BB70) input capture and capture-proven lamp support.

The BB70 capture contains three distinct report families:

* ``01`` / 12-byte input reports – the physical key matrix;
* ``02 01 00 00 00 01 ...`` – the 500 ms host keepalive which wakes the
  panel; and
* ``02 70 BB 00 00 03 49 <channel> <brightness> ...`` – panel-backlight
  and individual indicator writes.

The panel also returns 14-byte ``02 70 CB`` acknowledgements on its input
endpoint.  They are *not* key reports.  Keeping those families separate is
important: treating an acknowledgement as an input breaks the next key edge
and is the cause of intermittent ``first buttons work, then nothing moves``
symptoms.

The physical key positions still stay user-captured.  A report bit does not
receive an Airbus name until its owner assigns it to the matching visual key
in Studio.
"""

from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any, Callable, Dict, Optional


ECAM32_VID = 0x4098
ECAM32_PID = 0xBB70
ECAM32_INPUT_REPORT_ID = 0x01
ECAM32_INPUT_REPORT_LENGTH = 12
ECAM32_OUTPUT_REPORT_LENGTH = 14
# ``back light.pcapng`` records the two yellow faceplate illumination zones
# fading across their complete 0..255 range.  Those are distinct from the
# selected-page indicators below: 00 and 01 light the panel itself; 04..11
# are individual status lamps.
ECAM32_CAPTURED_BACKLIGHT_INDICES = (0x00, 0x01)
ECAM32_CAPTURED_LED_INDICES = tuple(range(0x04, 0x12))
ECAM32_CAPTURED_OUTPUT_INDICES = ECAM32_CAPTURED_BACKLIGHT_INDICES + ECAM32_CAPTURED_LED_INDICES
ECAM32_KEEPALIVE_INTERVAL_SECONDS = 0.45

# Physical BB70 report bits deliberately have no Airbus meaning until the
# owner presses each labelled key for the guided capture.  This one shared
# list keeps Studio and the command-window wizard on the exact same names.
ECAM32_A320_CONTROLS: tuple[tuple[str, str, str], ...] = (
    ("ecam_eng", "ENG", "A320 ECAM ENG page"),
    ("ecam_bleed", "BLEED", "A320 ECAM BLEED page"),
    ("ecam_press", "PRESS", "A320 ECAM PRESS page"),
    ("ecam_elec", "ELEC", "A320 ECAM ELEC page"),
    ("ecam_hyd", "HYD", "A320 ECAM HYD page"),
    ("ecam_fuel", "FUEL", "A320 ECAM FUEL page"),
    ("ecam_apu", "APU", "A320 ECAM APU page"),
    ("ecam_cond", "COND", "A320 ECAM COND page"),
    ("ecam_door", "DOOR", "A320 ECAM DOOR page"),
    ("ecam_wheel", "WHEEL", "A320 ECAM WHEEL page"),
    ("ecam_fctl", "F/CTL", "A320 ECAM F/CTL page"),
    ("ecam_all", "ALL", "A320 ECAM ALL pages"),
    ("ecam_clr_left", "CLR", "A320 ECAM left clear"),
    ("ecam_sts", "STS", "A320 ECAM status page"),
    ("ecam_rcl", "RCL", "A320 ECAM recall"),
    ("ecam_clr_right", "CLR", "A320 ECAM right clear"),
    ("ecam_to_config", "T.O\nCONFIG", "A320 take-off configuration"),
    ("ecam_emer_canc", "EMER\nCANC", "A320 emergency cancel"),
    # "Ecam Blank.pcapng" (2026-09-08) proved four distinct BB70 report bits
    # - raw_r01_b01_bit0, raw_r01_b01_bit2, raw_r01_b03_bit1,
    # raw_r01_b03_bit4 - that are not part of the eighteen labelled A320
    # contacts above: physically blank keycaps on this panel. Their real
    # panel position was not confirmed (only their electrical existence),
    # so no default role or LED is guessed here. The owner still assigns
    # each one to a raw contact through Studio's normal Identify flow, then
    # can give it any name via "Rename this control...".
    ("ecam_blank_1", "BLANK 1", "Unlabelled BB70 contact - assign any function"),
    ("ecam_blank_2", "BLANK 2", "Unlabelled BB70 contact - assign any function"),
    ("ecam_blank_3", "BLANK 3", "Unlabelled BB70 contact - assign any function"),
    ("ecam_blank_4", "BLANK 4", "Unlabelled BB70 contact - assign any function"),
)
ECAM32_A320_PAGE_KEYS = frozenset(
    key
    for key, _label, role in ECAM32_A320_CONTROLS
    if "page" in role.lower() or key == "ecam_all"
)

# Captured host -> BB70 report which is acknowledged by ``02 70 CB ...``.
# It is deliberately fixed at the recorded length and cadence.
ECAM32_WAKE_REPORT = bytes.fromhex("0201000000010000000000000000")

# These contact/lamp pairs were observed one-at-a-time in Ecam.pcapng.  They
# only allow Studio to illuminate a *learned* contact with a proven lamp
# address; all other raw contacts remain capture-only until their lamp address
# is recorded too.
ECAM32_CAPTURED_CONTACT_LED_INDEX = {
    "raw_r01_b01_bit4": 0x04,
    "raw_r01_b01_bit5": 0x05,
    "raw_r01_b01_bit6": 0x06,
    "raw_r01_b01_bit7": 0x07,
    "raw_r01_b02_bit0": 0x08,
    "raw_r01_b02_bit1": 0x09,
    "raw_r01_b02_bit2": 0x0A,
    "raw_r01_b02_bit3": 0x0B,
    "raw_r01_b02_bit4": 0x0C,
    "raw_r01_b02_bit5": 0x0D,
    "raw_r01_b02_bit6": 0x0E,
}


def ecam32_led_report(led_index: int, value: int | float | bool) -> bytes:
    """Build the exact captured 14-byte BB70 illumination report.

    The recordings demonstrate only the two panel-backlight channels and the
    fourteen individual indicator channels.  Rejecting every other number is
    safer than expanding a vendor range by assumption.
    """

    index = int(led_index)
    if index not in ECAM32_CAPTURED_OUTPUT_INDICES:
        raise ValueError(f"BB70 illumination channel {index:02X} was not captured")
    try:
        state = int(round(float(value)))
    except (TypeError, ValueError) as exc:
        raise ValueError("BB70 illumination brightness must be numeric") from exc
    state = max(0, min(255, state))
    return bytes((
        0x02, 0x70, 0xBB, 0x00, 0x00, 0x03, 0x49,
        index, state, 0x00, 0x00, 0x00, 0x00, 0x00,
    ))


def is_ecam32_key_report(report: bytes) -> bool:
    """Return true only for the capture-proven physical-key report family.

    USBPcap records the logical 12-byte packet.  Windows hidapi exposes that
    same report in the descriptor's padded 64-byte read buffer, so a longer
    buffer beginning with report ID ``01`` is still a valid key report.
    """

    return len(report) >= ECAM32_INPUT_REPORT_LENGTH and bool(report) and report[0] == ECAM32_INPUT_REPORT_ID


@dataclass(frozen=True)
class Ecam32RawEvent:
    """One physical report-bit transition, without an invented button name."""

    control: str
    value: int
    phase: str
    report_id: int
    byte_index: int
    bit_index: int


InputSink = Callable[[Ecam32RawEvent], None]


def decode_report_transition(previous: bytes, current: bytes) -> tuple[Ecam32RawEvent, ...]:
    """Return only changed bits between two BB70 reports.

    The report identifier remains part of every captured control name.  This
    protects learned mappings should a later firmware expose another report
    with a different layout.
    """

    if not previous or not current or len(previous) != len(current):
        return ()
    report_id = int(current[0]) if current else 0
    events: list[Ecam32RawEvent] = []
    # Byte zero is the report ID, not a physical input.  Never expose it as a
    # learnable contact, including during the first received report.
    for byte_index, (before, after) in enumerate(zip(previous, current)):
        if byte_index == 0:
            continue
        changed = int(before) ^ int(after)
        for bit_index in range(8):
            mask = 1 << bit_index
            if not changed & mask:
                continue
            events.append(Ecam32RawEvent(
                control=f"raw_r{report_id:02x}_b{byte_index:02d}_bit{bit_index}",
                value=1 if int(after) & mask else 0,
                phase="press" if int(after) & mask else "release",
                report_id=report_id,
                byte_index=byte_index,
                bit_index=bit_index,
            ))
    return tuple(events)


class MuslimSimECAM32:
    """Non-blocking BB70 key observer and limited capture-proven output driver.

    HID ownership remains in the bridge child process.  UI requests only
    update a small thread-safe output queue; the HID thread performs all
    writes and keeps polling keys, so output tests cannot freeze Studio.
    """

    def __init__(self, *, input_sink: Optional[InputSink] = None, hid_api: Any = None) -> None:
        self.input_sink = input_sink
        self._hid = hid_api
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self.status = "stopped"
        self.detail = ""
        self.last_report: bytes = b""
        self.last_ack: bytes = b""
        self.reports_seen = 0
        self.contacts_seen: set[str] = set()
        # >>> MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 >>>
        # Default physical state is dark/off.  Keepalive/backlight is now an
        # explicit Test output or future Live-authorised output, not a startup
        # side effect.
        self._keepalive_enabled = False
        self._last_keepalive_at = 0.0
        self._wake_writes = 0
        self._lamp_writes = 0
        self._requested_lamps: Dict[int, int] = {
            index: 0 for index in ECAM32_CAPTURED_OUTPUT_INDICES
        }
        self._last_sent_lamps: Dict[int, int] = {}
        # <<< MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 <<<

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self.status = "starting"
            self.detail = "opening passive BB70 input observer"
            self._thread = threading.Thread(target=self._run, name="MuslimSim-ECAM32", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        # >>> MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 >>>
        # A controlled Studio stop must request a captured OFF state before the
        # HID owner exits.  If the process is force-killed, no shutdown code can
        # run and that case is intentionally out of scope.
        with self._lock:
            self._keepalive_enabled = False
            for index in ECAM32_CAPTURED_OUTPUT_INDICES:
                self._requested_lamps[index] = 0
        # <<< MUSLIMSIM GLOBAL OUTPUT AUTHORITY V1 <<<
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        with self._lock:
            self._thread = None
            if self.status != "error":
                self.status = "stopped"

    def live_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "status": self.status,
                "detail": self.detail,
                "report_length": len(self.last_report),
                "report_id": int(self.last_report[0]) if self.last_report else None,
                "reports_seen": self.reports_seen,
                "contacts_seen": sorted(self.contacts_seen),
                "input_protocol": "captured 12-byte report 0x01",
                "output_protocol": "captured BB70 keepalive + 0x49 backlight/indicator reports",
                "wake_enabled": self._keepalive_enabled,
                "wake_writes": self._wake_writes,
                "lamp_writes": self._lamp_writes,
                "lamps": {f"{index:02X}": value for index, value in sorted(self._requested_lamps.items())},
                "last_ack": self.last_ack.hex() if self.last_ack else "",
            }

    def set_lab_output(self, control: str, value: Any) -> None:
        """Queue only the BB70 actions proved by the supplied capture."""

        key = str(control or "").strip().lower()
        try:
            requested = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("ECAM lamp and wake values must be numeric") from exc
        with self._lock:
            if key == "panel_wake":
                self._keepalive_enabled = bool(requested > 0)
                # Reset the cadence so a virtual wake request is sent on the
                # next HID loop rather than waiting for an old timer.
                self._last_keepalive_at = 0.0
                return
            if key == "panel_backlight":
                # The normal panel control is deliberately a simple on/off
                # action: non-zero means the capture-proven full 255 value on
                # both yellow zones.  This prevents a generic test's value
                # of ``1`` being mistaken for near-dark brightness.
                brightness = 255 if requested > 0 else 0
                for index in ECAM32_CAPTURED_BACKLIGHT_INDICES:
                    self._requested_lamps[index] = brightness
                return
            if key in {"panel_backlight_1", "panel_backlight_2"}:
                index = 0x00 if key.endswith("_1") else 0x01
                self._requested_lamps[index] = max(0, min(255, int(round(requested))))
                return
            if key == "button_backlight":
                for index in ECAM32_CAPTURED_LED_INDICES:
                    self._requested_lamps[index] = 1 if requested > 0 else 0
                return
            if key.startswith("led_"):
                try:
                    index = int(key[4:], 16)
                except ValueError as exc:
                    raise ValueError(f"Unknown ECAM output {control}") from exc
                if index not in ECAM32_CAPTURED_LED_INDICES:
                    raise ValueError(f"ECAM lamp {index:02X} has not been captured")
                self._requested_lamps[index] = 1 if requested > 0 else 0
                return
        raise ValueError(f"ECAM does not expose output {control}")

    def _load_hid(self) -> Any:
        if self._hid is not None:
            return self._hid
        import hid  # type: ignore[import-not-found]
        self._hid = hid
        return hid

    def _write_blackout(self, device: Any) -> None:
        """Send only capture-proven BB70 OFF packets before release."""

        for index in ECAM32_CAPTURED_OUTPUT_INDICES:
            device.write(list(ecam32_led_report(index, 0)))
        with self._lock:
            self._last_sent_lamps = {
                index: 0 for index in ECAM32_CAPTURED_OUTPUT_INDICES
            }

    def _run(self) -> None:
        device: Any = None
        previous: Optional[bytes] = None
        self._last_keepalive_at = 0.0
        while not self._stop.is_set():
            try:
                if device is None:
                    hid_api = self._load_hid()
                    candidates = list(hid_api.enumerate(ECAM32_VID, ECAM32_PID))
                    if not candidates:
                        with self._lock:
                            self.status = "waiting"
                            self.detail = "WINCTRL 32 ECAM (BB70) not found"
                        self._stop.wait(0.7)
                        continue
                    path = candidates[0].get("path")
                    if not path:
                        raise RuntimeError("BB70 HID path was not supplied by Windows")
                    device = hid_api.device()
                    device.open_path(path)
                    try:
                        device.set_nonblocking(1)
                    except Exception:
                        pass
                    previous = None
                    with self._lock:
                        self.status = "running"
                        self.detail = "BB70 key capture and captured lamp protocol ready"

                now = time.monotonic()
                with self._lock:
                    keepalive_due = self._keepalive_enabled and (
                        now - self._last_keepalive_at >= ECAM32_KEEPALIVE_INTERVAL_SECONDS
                    )
                    pending_lamps = {
                        index: state
                        for index, state in self._requested_lamps.items()
                        if self._last_sent_lamps.get(index) != state
                    }
                if keepalive_due:
                    device.write(list(ECAM32_WAKE_REPORT))
                    with self._lock:
                        self._last_keepalive_at = now
                        self._wake_writes += 1
                for index, state in pending_lamps.items():
                    device.write(list(ecam32_led_report(index, state)))
                    with self._lock:
                        self._last_sent_lamps[index] = state
                        self._lamp_writes += 1

                report = bytes(device.read(128))
                if not report:
                    self._stop.wait(0.008)
                    continue
                # The captured wake/LED acknowledgement is a 14-byte report
                # on the same endpoint as the 12-byte key matrix.  It must be
                # retained for diagnostics but never fed into the contact
                # transition decoder or it becomes the next baseline.
                if len(report) >= ECAM32_OUTPUT_REPORT_LENGTH and report.startswith(b"\x02\x70\xCB"):
                    with self._lock:
                        self.last_ack = report[:ECAM32_OUTPUT_REPORT_LENGTH]
                    continue
                if not is_ecam32_key_report(report):
                    with self._lock:
                        self.detail = f"ignored non-key BB70 report {report.hex()}"
                    continue
                # hidapi pads this report to the interface's 64-byte input
                # buffer.  Only the first capture-proven 12 bytes are the
                # key matrix; keeping the padding would make its length vary
                # from the USB capture and suppress every contact transition.
                report = report[:ECAM32_INPUT_REPORT_LENGTH]
                with self._lock:
                    self.last_report = report
                    self.reports_seen += 1
                if previous is None:
                    # A BB70 may be silent at rest.  If its first event report
                    # contains exactly one asserted contact, it is safe to use
                    # that observed transition rather than requiring the owner
                    # to press the same button twice just to establish a
                    # baseline.  Multiple changed bits still establish a
                    # neutral baseline only; their identity is not guessed.
                    events = decode_report_transition(bytes(len(report)), report)
                    if len(events) != 1:
                        events = ()
                elif len(previous) == len(report):
                    events = decode_report_transition(previous, report)
                else:
                    events = ()
                for event in events:
                    with self._lock:
                        self.contacts_seen.add(event.control)
                    if self.input_sink is not None:
                        self.input_sink(event)
                previous = report
            except Exception as exc:
                if device is not None:
                    try:
                        device.close()
                    except Exception:
                        pass
                device = None
                previous = None
                with self._lock:
                    self.status = "waiting"
                    self.detail = f"BB70 observer reconnecting: {exc}"
                self._stop.wait(0.7)
        if device is not None:
            try:
                self._write_blackout(device)
            except Exception:
                pass
            try:
                device.close()
            except Exception:
                pass
