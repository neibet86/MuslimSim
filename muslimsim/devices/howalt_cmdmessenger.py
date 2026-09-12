"""Direct HOWALT/MobiFlight-firmware serial transport for MuslimSim.

This module deliberately does *not* depend on MobiFlight Connector.  It speaks
only the small runtime subset of the command protocol already present in the
firmware on the Hoowalt boards.  No configuration, flash, EEPROM, reset, name,
or serial-number commands are exposed here.

Normal ownership model:
    MuslimSim Studio -> MuslimSim bridge -> this module -> COM port -> board

The same module is also used by the MUSLIMRTP / MUSLIMATC diagnostic launchers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    import serial  # type: ignore
    from serial.tools import list_ports  # type: ignore
except Exception:  # pragma: no cover - allows import/tests without pyserial
    serial = None
    list_ports = None

DEFAULT_BAUD = 115200
USB_VID = 0x1A86
USB_PID = 0x7523

# Runtime command ids used by the already-installed firmware.
CMD_SET_MODULE = 1
CMD_SET_PIN = 2
CMD_STATUS = 5
CMD_ENCODER_CHANGE = 6
CMD_BUTTON_CHANGE = 7
CMD_GET_INFO = 9
CMD_INFO = 10
CMD_GET_CONFIG = 12
CMD_CONFIG_ACTIVATED = 17
CMD_POWER_SAVE = 18
CMD_TRIGGER = 23
CMD_SET_MODULE_BRIGHTNESS = 26
CMD_RETRIGGER_DONE = 34

ENCODER_PHASES: Dict[int, str] = {
    0: "left",
    1: "left-fast",
    2: "right",
    3: "right-fast",
}

InputRouter = Callable[[int, str], bool]
EventSink = Callable[[Mapping[str, Any]], None]

# Several HOWALT panels use the same VID/PID.  In the MuslimSim bridge they are
# all owned by one process, so serialize probing and keep a process-local claim
# table to avoid one panel opening a COM port already assigned to another.
_PROBE_LOCK = threading.RLock()
_CLAIMED_LOCK = threading.RLock()
_CLAIMED_PORTS: Dict[str, str] = {}


def _claim_port(port: str, owner: str) -> bool:
    key = str(port).upper()
    with _CLAIMED_LOCK:
        current = _CLAIMED_PORTS.get(key)
        if current is not None and current != owner:
            return False
        _CLAIMED_PORTS[key] = owner
        return True


def _release_port(port: Optional[str], owner: str) -> None:
    if not port:
        return
    key = str(port).upper()
    with _CLAIMED_LOCK:
        if _CLAIMED_PORTS.get(key) == owner:
            _CLAIMED_PORTS.pop(key, None)


def encode_command(command: int, *args: Any) -> bytes:
    """Encode a CmdMessenger-style ASCII command terminated by ';'."""
    fields = [str(int(command))]
    for arg in args:
        text = str(arg)
        # The HOWALT runtime fields contain no delimiters.  Refuse to silently
        # construct a second command if a caller gives unsafe text.
        if ";" in text or "," in text:
            raise ValueError("HOWALT command argument may not contain ',' or ';'")
        fields.append(text)
    return (",".join(fields) + ";").encode("ascii", errors="strict")


class FrameDecoder:
    """Incremental semicolon-delimited ASCII frame decoder."""

    def __init__(self, max_buffer: int = 64 * 1024) -> None:
        self.buffer = bytearray()
        self.max_buffer = int(max_buffer)

    def feed(self, data: bytes) -> List[str]:
        if not data:
            return []
        self.buffer.extend(data)
        if len(self.buffer) > self.max_buffer:
            # Keep only a small tail after malformed/noisy input.
            del self.buffer[:-4096]
        frames: List[str] = []
        while True:
            try:
                end = self.buffer.index(ord(";"))
            except ValueError:
                break
            raw = bytes(self.buffer[:end])
            del self.buffer[: end + 1]
            text = raw.decode("ascii", errors="replace").strip("\r\n \t")
            if text:
                frames.append(text)
        return frames


@dataclass(frozen=True)
class PanelSpec:
    key: str
    software_name: str
    title: str
    module_name: str
    expected_serial: Optional[str]
    buttons: Tuple[str, ...]
    encoders: Tuple[str, ...]
    outputs: Tuple[str, ...]
    displays: Tuple[str, ...]
    default_brightness: Mapping[str, int] = field(default_factory=dict)
    aliases: Mapping[str, str] = field(default_factory=dict)

    @property
    def input_indices(self) -> Dict[str, int]:
        result: Dict[str, int] = {}
        for index, name in enumerate(self.buttons):
            result[name] = index
        for index, name in enumerate(self.encoders, start=32):
            result[name] = index
        return result

    @property
    def output_indices(self) -> Dict[str, int]:
        return {name: index for index, name in enumerate(self.outputs)}

    @property
    def display_indices(self) -> Dict[str, int]:
        return {name: index for index, name in enumerate(self.displays)}


class HowaltDirectRouter:
    """Reconnectable, Studio-oriented owner for one HOWALT serial panel."""

    reconnect_seconds = 1.0
    identity_timeout = 2.8

    def __init__(
        self,
        spec: PanelSpec,
        *,
        port: Optional[str] = None,
        input_router: Optional[InputRouter] = None,
        event_sink: Optional[EventSink] = None,
        diagnose: bool = False,
        baud: int = DEFAULT_BAUD,
    ) -> None:
        self.spec = spec
        self.port_hint = str(port).strip() if port else None
        self.input_router = input_router
        self.event_sink = event_sink
        self.diagnose = bool(diagnose)
        self.baud = int(baud)

        self.stop_evt = threading.Event()
        self.supervisor: Optional[threading.Thread] = None
        self._serial: Any = None
        self._decoder = FrameDecoder()
        self._write_lock = threading.RLock()
        self._state_lock = threading.RLock()

        self.connected_port: Optional[str] = None
        self.state = "stopped"
        self.detail = "not started"
        self.identity: Dict[str, str] = {}
        self.config_text = ""
        self.frames_rx = 0
        self.frames_tx = 0
        self.last_rx_monotonic = 0.0
        self.last_tx_monotonic = 0.0
        self.last_event: Dict[str, Any] = {}
        self.last_error = ""

        self.inputs: Dict[str, Dict[str, Any]] = {}
        self.outputs: Dict[str, int] = {name: 0 for name in spec.outputs}
        self.displays: Dict[str, Dict[str, Any]] = {
            name: {
                "text": "",
                "points": 0,
                "mask": 0xFF,
                "brightness": int(spec.default_brightness.get(name, 7)),
            }
            for name in spec.displays
        }

    # ------------------------------------------------------------------
    # Lifecycle / Studio contract
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self.supervisor is not None and self.supervisor.is_alive():
            return
        self.stop_evt.clear()
        self._set_state("waiting", "searching for HOWALT serial panel")
        self.supervisor = threading.Thread(
            target=self._run,
            name=f"{self.spec.software_name}-SERIAL",
            daemon=True,
        )
        self.supervisor.start()

    def stop(self) -> None:
        self.stop_evt.set()
        self._close_serial()
        if self.supervisor is not None and self.supervisor is not threading.current_thread():
            self.supervisor.join(timeout=3.5)
        self.supervisor = None
        self._set_state("stopped", "driver stopped")

    def studio_snapshot(self) -> Dict[str, Any]:
        with self._state_lock:
            return {
                "state": self.state,
                "live": self.state == "connected" and self._serial is not None,
                "software": self.spec.software_name,
                "device": self.spec.key,
                "title": self.spec.title,
                "module_name": self.spec.module_name,
                "port": self.connected_port or "",
                "identity": dict(self.identity),
                "inputs": {name: dict(value) for name, value in self.inputs.items()},
                "outputs": dict(self.outputs),
                "displays": {name: dict(value) for name, value in self.displays.items()},
                "last_event": dict(self.last_event),
                "frames_rx": int(self.frames_rx),
                "frames_tx": int(self.frames_tx),
                "detail": self.detail,
                "error": self.last_error,
            }

    def service_snapshot(self) -> Dict[str, Any]:
        mirror = self.studio_snapshot()
        return {
            "state": mirror["state"],
            "detail": mirror["detail"],
            "mirror": mirror,
        }

    # ------------------------------------------------------------------
    # Hardware output API exposed to MuslimSim Studio
    # ------------------------------------------------------------------
    def set_lab_output(self, control: str, value: Any) -> None:
        raw_name = str(control).strip()
        normalized = raw_name.lower().replace("_", " ").replace("-", " ")
        alias = self.spec.aliases.get(normalized, raw_name)

        if normalized in {"all off", "alloff", "blackout"}:
            self.all_off()
            return

        output_name = self._resolve_name(alias, self.spec.outputs)
        if output_name is not None:
            self.set_output(output_name, value)
            return

        display_name = self._resolve_name(alias, self.spec.displays)
        if display_name is not None:
            if isinstance(value, Mapping):
                self.set_display(
                    display_name,
                    value.get("text", value.get("value", "")),
                    points=int(value.get("points", 0) or 0),
                    mask=int(value.get("mask", self._default_mask(display_name)) or 0),
                    brightness=(
                        int(value["brightness"])
                        if value.get("brightness") is not None
                        else None
                    ),
                )
            else:
                self.set_display(display_name, value)
            return

        # Convenience control for each display's brightness.
        if normalized.endswith(" brightness"):
            prefix = normalized[: -len(" brightness")].strip()
            target = self._resolve_name(prefix, self.spec.displays)
            if target is not None:
                self.set_display_brightness(target, int(value))
                return

        raise KeyError(f"Unknown {self.spec.software_name} output control: {control}")

    def set_output(self, name: str, value: Any) -> None:
        output_name = self._require_name(name, self.spec.outputs)
        index = self.spec.output_indices[output_name]
        if isinstance(value, bool):
            level = 255 if value else 0
        elif isinstance(value, float) and 0.0 <= value <= 1.0:
            level = round(value * 255)
        else:
            level = int(value)
            # Treat common boolean integer input naturally.
            if level in (0, 1):
                level = 255 if level else 0
        level = max(0, min(255, level))
        with self._state_lock:
            self.outputs[output_name] = level
        self._send(CMD_SET_PIN, index, level, require_connected=True)

    def set_display(
        self,
        name: str,
        value: Any,
        *,
        points: int = 0,
        mask: Optional[int] = None,
        brightness: Optional[int] = None,
    ) -> None:
        display_name = self._require_name(name, self.spec.displays)
        module = self.spec.display_indices[display_name]
        if mask is None:
            mask = self._default_mask(display_name)
        mask = int(mask) & 0xFF
        points = int(points) & 0xFF

        text = str(value)
        text = text.replace(",", " ").replace(";", " ")
        digit_count = max(1, int(mask).bit_count())
        text = text[:digit_count].rjust(digit_count)

        with self._state_lock:
            previous_brightness = int(self.displays[display_name]["brightness"])
            self.displays[display_name].update({
                "text": text,
                "points": points,
                "mask": mask,
            })

        self._send(CMD_SET_MODULE, module, 0, text, points, mask, require_connected=True)
        if brightness is not None and int(brightness) != previous_brightness:
            self.set_display_brightness(display_name, int(brightness))

    def set_display_brightness(self, name: str, brightness: int) -> None:
        display_name = self._require_name(name, self.spec.displays)
        module = self.spec.display_indices[display_name]
        level = max(0, min(16, int(brightness)))
        with self._state_lock:
            self.displays[display_name]["brightness"] = level
        self._send(CMD_SET_MODULE_BRIGHTNESS, module, 0, level, require_connected=True)

    def clear_display(self, name: str) -> None:
        display_name = self._require_name(name, self.spec.displays)
        self.set_display(display_name, " " * 8, mask=0xFF)

    def all_off(self) -> None:
        # Maintain desired state even while unplugged; replay will restore off.
        for output_name in self.spec.outputs:
            try:
                self.set_output(output_name, 0)
            except RuntimeError:
                with self._state_lock:
                    self.outputs[output_name] = 0
        for display_name in self.spec.displays:
            try:
                self.clear_display(display_name)
            except RuntimeError:
                with self._state_lock:
                    self.displays[display_name].update({"text": " " * 8, "points": 0, "mask": 0xFF})

    # ------------------------------------------------------------------
    # Serial transport
    # ------------------------------------------------------------------
    def _run(self) -> None:
        while not self.stop_evt.is_set():
            try:
                ser, port, identity = self._find_and_open()
                if ser is None or port is None:
                    self._set_state("waiting", f"{self.spec.module_name} not detected")
                    self.stop_evt.wait(self.reconnect_seconds)
                    continue

                self._serial = ser
                self.connected_port = port
                with self._state_lock:
                    self.identity = dict(identity)
                    self.last_error = ""
                self._set_state("connected", f"direct serial owner on {port}")
                if self.diagnose:
                    print(f"{self.spec.software_name}: CONNECTED {port} {identity}")

                # Keep the panel awake, get its current configuration for the
                # Studio diagnostic mirror, restore desired outputs, then ask
                # firmware to publish every current physical input position.
                self._send(CMD_POWER_SAVE, 0, require_connected=True)
                self._send(CMD_GET_CONFIG, require_connected=True)
                self._replay_outputs()
                self._send(CMD_TRIGGER, 5, self.spec.module_name, require_connected=True)

                self._read_loop()
            except Exception as exc:
                if not self.stop_evt.is_set():
                    message = f"{type(exc).__name__}: {exc}"
                    with self._state_lock:
                        self.last_error = message
                    self._set_state("reconnecting", message)
                    if self.diagnose:
                        print(f"{self.spec.software_name}: {message}")
            finally:
                self._close_serial()

            if not self.stop_evt.is_set():
                self.stop_evt.wait(self.reconnect_seconds)

    def _candidate_ports(self) -> List[str]:
        if self.port_hint:
            return [self.port_hint]
        if list_ports is None:
            return []
        ports = list(list_ports.comports())
        # Do not spray identity queries at unrelated COM devices.  The captures
        # establish VID 1A86 / PID 7523 for these panels; an explicit --port
        # remains available for machines whose USB-serial driver omits VID/PID.
        return [
            item.device for item in ports
            if getattr(item, "vid", None) == USB_VID
            and getattr(item, "pid", None) == USB_PID
        ]

    def _find_and_open(self) -> Tuple[Any, Optional[str], Dict[str, str]]:
        if serial is None:
            raise RuntimeError("pyserial is not installed")

        owner = self.spec.key
        with _PROBE_LOCK:
            for port in self._candidate_ports():
                if self.stop_evt.is_set():
                    return None, None, {}
                if not _claim_port(port, owner):
                    continue
                ser: Any = None
                keep_claim = False
                try:
                    ser = serial.Serial(
                        port=port,
                        baudrate=self.baud,
                        bytesize=serial.EIGHTBITS,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE,
                        timeout=0.08,
                        write_timeout=0.6,
                    )
                    # Opening a Mega/CH340 may reset the MCU. Let its startup
                    # settle, then ask for identity. Avoid destructive commands.
                    try:
                        ser.reset_input_buffer()
                    except Exception:
                        pass
                    self._decoder = FrameDecoder()
                    identity = self._probe_identity(ser)
                    if identity and identity.get("name") == self.spec.module_name:
                        expected = self.spec.expected_serial
                        got_serial = identity.get("serial")
                        if expected and got_serial and got_serial != expected:
                            # Keep the exact captured serial as a diagnostic, not
                            # a vendor lock. The module name uniquely separates
                            # D201 RTP from D203 ATC, so a replacement board of
                            # the same type remains usable without code changes.
                            identity["expected_serial"] = expected
                            identity["serial_note"] = "replacement serial accepted"
                            if self.diagnose:
                                print(
                                    f"{self.spec.software_name}: {port} serial "
                                    f"{got_serial} differs from captured {expected}; "
                                    "module name matched, accepting panel."
                                )
                        keep_claim = True
                        return ser, port, identity
                except Exception as exc:
                    if self.diagnose:
                        print(f"{self.spec.software_name}: probe {port}: {exc}")
                finally:
                    if not keep_claim:
                        if ser is not None:
                            try:
                                ser.close()
                            except Exception:
                                pass
                        _release_port(port, owner)
        return None, None, {}

    def _probe_identity(self, ser: Any) -> Dict[str, str]:
        deadline = time.monotonic() + self.identity_timeout
        next_query = 0.0
        decoder = FrameDecoder()
        while time.monotonic() < deadline and not self.stop_evt.is_set():
            now = time.monotonic()
            if now >= next_query:
                ser.write(encode_command(CMD_GET_INFO))
                try:
                    ser.flush()
                except Exception:
                    pass
                next_query = now + 0.8
            chunk = ser.read(512)
            for frame in decoder.feed(bytes(chunk or b"")):
                identity = parse_identity_frame(frame)
                if identity:
                    return identity
            time.sleep(0.01)
        return {}

    def _read_loop(self) -> None:
        while not self.stop_evt.is_set():
            ser = self._serial
            if ser is None:
                return
            data = ser.read(1024)
            if not data:
                continue
            with self._state_lock:
                self.last_rx_monotonic = time.monotonic()
            for frame in self._decoder.feed(bytes(data)):
                self.frames_rx += 1
                self._handle_frame(frame)

    def _send(self, command: int, *args: Any, require_connected: bool = False) -> bool:
        packet = encode_command(command, *args)
        with self._write_lock:
            ser = self._serial
            if ser is None:
                if require_connected:
                    raise RuntimeError(f"{self.spec.software_name} is not connected")
                return False
            ser.write(packet)
            try:
                ser.flush()
            except Exception:
                pass
            with self._state_lock:
                self.frames_tx += 1
                self.last_tx_monotonic = time.monotonic()
        if self.diagnose:
            print(f"{self.spec.software_name} TX: {packet.decode('ascii').rstrip()}")
        return True

    def _handle_frame(self, frame: str) -> None:
        if self.diagnose:
            print(f"{self.spec.software_name} RX: {frame};")
        fields = [part.strip() for part in frame.split(",")]
        if not fields:
            return
        try:
            command = int(fields[0])
        except ValueError:
            return

        if command == CMD_INFO:
            identity = parse_identity_fields(fields)
            if identity:
                with self._state_lock:
                    self.identity = identity
            elif len(fields) >= 2:
                with self._state_lock:
                    self.config_text = ",".join(fields[1:])
            return

        if command == CMD_BUTTON_CHANGE and len(fields) >= 3:
            name = fields[1]
            try:
                raw = int(fields[2])
            except ValueError:
                return
            # MobiFlight button input is pull-up/active-low on these boards.
            phase = "press" if raw == 0 else "release"
            with self._state_lock:
                self.inputs[name] = {"raw": raw, "pressed": raw == 0, "phase": phase}
            self._publish_input(name, phase, raw)
            return

        if command == CMD_ENCODER_CHANGE and len(fields) >= 3:
            name = fields[1]
            try:
                event_id = int(fields[2])
            except ValueError:
                return
            phase = ENCODER_PHASES.get(event_id, f"encoder-{event_id}")
            with self._state_lock:
                self.inputs[name] = {"event_id": event_id, "phase": phase}
            self._publish_input(name, phase, event_id)
            return

        if command == CMD_STATUS:
            with self._state_lock:
                self.detail = ",".join(fields[1:]) or self.detail
        elif command == CMD_CONFIG_ACTIVATED:
            with self._state_lock:
                self.detail = "firmware configuration active"
        elif command == CMD_RETRIGGER_DONE:
            with self._state_lock:
                self.detail = f"direct serial owner on {self.connected_port or '?'}; inputs synchronized"

    def _publish_input(self, name: str, phase: str, raw: int) -> None:
        index = self.spec.input_indices.get(name)
        event = {
            "device": self.spec.key,
            "software": self.spec.software_name,
            "control": name,
            "index": index,
            "phase": phase,
            "raw": raw,
            "time": time.time(),
        }
        with self._state_lock:
            self.last_event = event
        if self.event_sink is not None:
            try:
                self.event_sink(event)
            except Exception:
                pass
        if index is not None and self.input_router is not None:
            try:
                self.input_router(int(index), str(phase))
            except Exception:
                pass

    def _replay_outputs(self) -> None:
        # Copy under lock so Studio can update desired state concurrently.
        with self._state_lock:
            outputs = dict(self.outputs)
            displays = {name: dict(value) for name, value in self.displays.items()}
        for name, level in outputs.items():
            self._send(CMD_SET_PIN, self.spec.output_indices[name], int(level), require_connected=True)
        for name, state in displays.items():
            module = self.spec.display_indices[name]
            brightness = int(state.get("brightness", self.spec.default_brightness.get(name, 7)))
            self._send(CMD_SET_MODULE_BRIGHTNESS, module, 0, max(0, min(16, brightness)), require_connected=True)
            text = str(state.get("text", ""))
            mask = int(state.get("mask", self._default_mask(name))) & 0xFF
            points = int(state.get("points", 0)) & 0xFF
            if text:
                digit_count = max(1, mask.bit_count())
                self._send(
                    CMD_SET_MODULE,
                    module,
                    0,
                    text[:digit_count].rjust(digit_count),
                    points,
                    mask,
                    require_connected=True,
                )

    def _close_serial(self) -> None:
        ser = self._serial
        port = self.connected_port
        self._serial = None
        self.connected_port = None
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
        _release_port(port, self.spec.key)

    def _set_state(self, state: str, detail: str) -> None:
        with self._state_lock:
            self.state = str(state)
            self.detail = str(detail)

    def _default_mask(self, display_name: str) -> int:
        # D203's squawk uses four right-hand MAX7219 digits; D201 radio fields
        # are exposed as all eight by default and Studio can pass a custom mask.
        if self.spec.key == "muslimatc_d203" and display_name == "SMG":
            return 0x0F
        return 0xFF

    @staticmethod
    def _resolve_name(candidate: str, names: Sequence[str]) -> Optional[str]:
        c = str(candidate).strip().lower().replace("_", " ").replace("-", " ")
        for name in names:
            n = name.lower().replace("_", " ").replace("-", " ")
            if c == n:
                return name
        return None

    def _require_name(self, candidate: str, names: Sequence[str]) -> str:
        name = self._resolve_name(candidate, names)
        if name is None:
            raise KeyError(candidate)
        return name


def parse_identity_fields(fields: Sequence[str]) -> Dict[str, str]:
    # Capture form: 10,MobiFlight Mega,Hoowalt D20x ...,SN-...,3.1.4,3.1.4
    if len(fields) >= 6 and fields[0] == str(CMD_INFO) and fields[1].startswith("MobiFlight"):
        return {
            "module_type": fields[1],
            "name": fields[2],
            "serial": fields[3],
            "firmware": fields[4],
            "protocol": fields[5],
        }
    return {}


def parse_identity_frame(frame: str) -> Dict[str, str]:
    return parse_identity_fields([part.strip() for part in frame.split(",")])
