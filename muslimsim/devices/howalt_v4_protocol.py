"""MUSLIMRTP/MUSLIMATC V4 direct HOWALT serial transport for MuslimSim.

This module deliberately does *not* depend on MobiFlight Connector.  It speaks
only the small runtime subset of the command protocol already present in the
firmware on the Hoowalt boards.  No configuration, flash, EEPROM, reset, name,
or serial-number commands are exposed here.

Normal ownership model:
    MuslimSim Studio -> MuslimSim bridge -> this module -> COM port -> board

It is simulator-agnostic; the existing MuslimSim bridge supplies any live simulator values.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    import serial  # type: ignore
    from serial.tools import list_ports  # type: ignore
except Exception:  # pragma: no cover - pyserial is optional
    serial = None
    list_ports = None


class NativeWindowsSerial:
    """Small standard-library Win32 serial backend for HOWALT runtime I/O.

    This exists so MuslimSim does not depend on pyserial being installed in the
    exact Python environment used by Studio. It intentionally implements only
    the methods used by the HOWALT transport.
    """

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.08, write_timeout: float = 0.6) -> None:
        if os.name != "nt":
            raise RuntimeError("NativeWindowsSerial is available only on Windows")
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._wintypes = wintypes
        self.port = str(port)
        self.timeout = max(0.0, float(timeout))
        self.write_timeout = max(0.0, float(write_timeout))
        self._closed = False
        self._muslimsim_backend = "win32-native"
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32 = kernel32

        class DCB(ctypes.Structure):
            _fields_ = [
                ("DCBlength", wintypes.DWORD),
                ("BaudRate", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("wReserved", wintypes.WORD),
                ("XonLim", wintypes.WORD),
                ("XoffLim", wintypes.WORD),
                ("ByteSize", wintypes.BYTE),
                ("Parity", wintypes.BYTE),
                ("StopBits", wintypes.BYTE),
                ("XonChar", ctypes.c_char),
                ("XoffChar", ctypes.c_char),
                ("ErrorChar", ctypes.c_char),
                ("EofChar", ctypes.c_char),
                ("EvtChar", ctypes.c_char),
                ("wReserved1", wintypes.WORD),
            ]

        class COMMTIMEOUTS(ctypes.Structure):
            _fields_ = [
                ("ReadIntervalTimeout", wintypes.DWORD),
                ("ReadTotalTimeoutMultiplier", wintypes.DWORD),
                ("ReadTotalTimeoutConstant", wintypes.DWORD),
                ("WriteTotalTimeoutMultiplier", wintypes.DWORD),
                ("WriteTotalTimeoutConstant", wintypes.DWORD),
            ]

        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        ]
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.GetCommState.argtypes = [wintypes.HANDLE, ctypes.POINTER(DCB)]
        kernel32.GetCommState.restype = wintypes.BOOL
        kernel32.SetCommState.argtypes = [wintypes.HANDLE, ctypes.POINTER(DCB)]
        kernel32.SetCommState.restype = wintypes.BOOL
        kernel32.SetCommTimeouts.argtypes = [wintypes.HANDLE, ctypes.POINTER(COMMTIMEOUTS)]
        kernel32.SetCommTimeouts.restype = wintypes.BOOL
        kernel32.SetupComm.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
        kernel32.SetupComm.restype = wintypes.BOOL
        kernel32.PurgeComm.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.PurgeComm.restype = wintypes.BOOL
        kernel32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        kernel32.ReadFile.restype = wintypes.BOOL
        kernel32.WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        kernel32.WriteFile.restype = wintypes.BOOL
        kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
        kernel32.FlushFileBuffers.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        device = self.port
        if not device.startswith("\\\\.\\"):
            device = "\\\\.\\" + device
        handle = kernel32.CreateFileW(
            device,
            0x80000000 | 0x40000000,  # GENERIC_READ | GENERIC_WRITE
            0,
            None,
            3,  # OPEN_EXISTING
            0,
            None,
        )
        invalid = ctypes.c_void_p(-1).value
        if handle == invalid or handle is None:
            raise ctypes.WinError(ctypes.get_last_error())
        self._handle = handle

        try:
            kernel32.SetupComm(handle, 8192, 8192)
            dcb = DCB()
            dcb.DCBlength = ctypes.sizeof(DCB)
            if not kernel32.GetCommState(handle, ctypes.byref(dcb)):
                raise ctypes.WinError(ctypes.get_last_error())
            dcb.BaudRate = int(baudrate)
            # fBinary + DTR_CONTROL_ENABLE + RTS_CONTROL_ENABLE; no HW/SW flow.
            dcb.flags = 0x00001011
            dcb.ByteSize = 8
            dcb.Parity = 0  # NOPARITY
            dcb.StopBits = 0  # ONESTOPBIT
            dcb.XonLim = 0
            dcb.XoffLim = 0
            if not kernel32.SetCommState(handle, ctypes.byref(dcb)):
                raise ctypes.WinError(ctypes.get_last_error())

            timeouts = COMMTIMEOUTS()
            timeouts.ReadIntervalTimeout = max(1, int(self.timeout * 1000))
            timeouts.ReadTotalTimeoutMultiplier = 0
            timeouts.ReadTotalTimeoutConstant = max(1, int(self.timeout * 1000))
            timeouts.WriteTotalTimeoutMultiplier = 0
            timeouts.WriteTotalTimeoutConstant = max(1, int(self.write_timeout * 1000))
            if not kernel32.SetCommTimeouts(handle, ctypes.byref(timeouts)):
                raise ctypes.WinError(ctypes.get_last_error())
            self.reset_input_buffer()
        except Exception:
            kernel32.CloseHandle(handle)
            self._closed = True
            raise

    def read(self, size: int = 1) -> bytes:
        if self._closed:
            return b""
        size = max(1, int(size))
        buf = self._ctypes.create_string_buffer(size)
        got = self._wintypes.DWORD(0)
        ok = self._kernel32.ReadFile(self._handle, buf, size, self._ctypes.byref(got), None)
        if not ok:
            err = self._ctypes.get_last_error()
            if self._closed or err in (6, 995):  # invalid handle / operation aborted
                return b""
            raise self._ctypes.WinError(err)
        return bytes(buf.raw[: got.value])

    def write(self, data: bytes) -> int:
        if self._closed:
            raise RuntimeError(f"Serial port {self.port} is closed")
        payload = bytes(data)
        if not payload:
            return 0
        written = self._wintypes.DWORD(0)
        buf = self._ctypes.create_string_buffer(payload)
        ok = self._kernel32.WriteFile(
            self._handle, buf, len(payload), self._ctypes.byref(written), None
        )
        if not ok:
            raise self._ctypes.WinError(self._ctypes.get_last_error())
        return int(written.value)

    def flush(self) -> None:
        if not self._closed:
            self._kernel32.FlushFileBuffers(self._handle)

    def reset_input_buffer(self) -> None:
        if not self._closed:
            # PURGE_RXABORT | PURGE_RXCLEAR
            self._kernel32.PurgeComm(self._handle, 0x0002 | 0x0008)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._kernel32.PurgeComm(self._handle, 0x0001 | 0x0002 | 0x0004 | 0x0008)
        except Exception:
            pass
        self._kernel32.CloseHandle(self._handle)


# WCH USB-serial IDs used by CH340/CH341-family drivers.  The supplied HOWALT
# captures are 1A86:7523; the additional WCH PIDs allow the same panel model to
# survive a newer Windows/WCH driver exposing another CH34x-compatible PID.
USB_VID = 0x1A86
USB_PID = 0x7523
KNOWN_WCH_PIDS = frozenset({0x7523, 0x5523, 0x55D3, 0x55D4})


def _registry_candidate_ports() -> List[str]:
    """Enumerate known WCH HOWALT candidates using only Windows stdlib."""
    if os.name != "nt":
        return []
    try:
        import winreg
    except Exception:
        return []
    result: List[str] = []
    root_path = r"SYSTEM\CurrentControlSet\Enum\USB"
    allowed_prefixes = tuple(
        f"VID_{USB_VID:04X}&PID_{pid:04X}" for pid in sorted(KNOWN_WCH_PIDS)
    )
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root_path) as usb_root:
            vendor_index = 0
            while True:
                try:
                    vendor_key_name = winreg.EnumKey(usb_root, vendor_index)
                except OSError:
                    break
                vendor_index += 1
                if not vendor_key_name.upper().startswith(allowed_prefixes):
                    continue
                try:
                    vendor_key = winreg.OpenKey(usb_root, vendor_key_name)
                except OSError:
                    continue
                with vendor_key:
                    instance_index = 0
                    while True:
                        try:
                            instance = winreg.EnumKey(vendor_key, instance_index)
                        except OSError:
                            break
                        instance_index += 1
                        try:
                            with winreg.OpenKey(
                                vendor_key, instance + r"\Device Parameters"
                            ) as params:
                                port, _ = winreg.QueryValueEx(params, "PortName")
                        except OSError:
                            continue
                        port = str(port or "").strip()
                        if (
                            re.fullmatch(r"COM\d+", port, flags=re.IGNORECASE)
                            and port.upper() not in [p.upper() for p in result]
                        ):
                            result.append(port)
    except OSError:
        return []
    return result


def _open_pyserial_port(
    port: str, *, baudrate: int, timeout: float, write_timeout: float
) -> Any:
    """Open HOWALT exactly as a normal 8N1 DTR-enabled serial device."""
    if serial is None:
        raise RuntimeError("pyserial is unavailable")
    ser = serial.Serial()
    ser.port = str(port)
    ser.baudrate = int(baudrate)
    ser.bytesize = serial.EIGHTBITS
    ser.parity = serial.PARITY_NONE
    ser.stopbits = serial.STOPBITS_ONE
    ser.timeout = float(timeout)
    ser.write_timeout = float(write_timeout)
    ser.xonxoff = False
    ser.rtscts = False
    ser.dsrdtr = False
    # MobiFlight's Mega board definition explicitly enables DTR.  Set the
    # desired modem-line state before open and assert it again afterward.
    ser.dtr = True
    ser.rts = True
    ser.open()
    try:
        ser.dtr = True
        ser.rts = True
        ser.reset_input_buffer()
    except Exception:
        pass
    try:
        setattr(ser, "_muslimsim_backend", "pyserial")
    except Exception:
        pass
    return ser


def serial_backend_name(ser: Any) -> str:
    value = str(getattr(ser, "_muslimsim_backend", "") or "").strip()
    if value:
        return value
    module = type(ser).__module__.lower()
    return "pyserial" if "serial" in module else type(ser).__name__


def open_serial_port(
    port: str, *, baudrate: int = 115200,
    timeout: float = 0.08, write_timeout: float = 0.6,
) -> Any:
    """Open a HOWALT COM port using the most compatible available backend.

    On Windows MuslimSim prefers pyserial when it is already present in the
    bridge environment (the main bridge commonly has it for COM5).  If that
    open fails or pyserial is absent, the built-in Win32 backend remains a
    dependency-free fallback.
    """
    failures: List[str] = []
    if serial is not None:
        try:
            return _open_pyserial_port(
                port, baudrate=baudrate, timeout=timeout,
                write_timeout=write_timeout,
            )
        except Exception as exc:
            failures.append(f"pyserial: {type(exc).__name__}: {exc}")

    if os.name == "nt":
        try:
            return NativeWindowsSerial(
                port, baudrate=baudrate, timeout=timeout,
                write_timeout=write_timeout,
            )
        except Exception as exc:
            failures.append(f"win32-native: {type(exc).__name__}: {exc}")

    if failures:
        raise RuntimeError("; ".join(failures))
    raise RuntimeError("HOWALT serial backend is unavailable")


DEFAULT_BAUD = 115200

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


def list_candidate_howalt_ports(port_hint: Optional[str] = None) -> List[str]:
    """Return only explicit or known WCH/HOWALT USB-serial candidate ports."""
    if port_hint:
        return [str(port_hint).strip()]
    result: List[str] = []
    if list_ports is not None:
        for item in list(list_ports.comports()):
            vid = getattr(item, "vid", None)
            pid = getattr(item, "pid", None)
            hwid = str(getattr(item, "hwid", "") or "").upper()
            structured = vid == USB_VID and pid in KNOWN_WCH_PIDS
            textual = False
            for known_pid in KNOWN_WCH_PIDS:
                hex_pid = f"{known_pid:04X}"
                if (
                    f"VID:PID={USB_VID:04X}:{hex_pid}" in hwid
                    or f"VID_{USB_VID:04X}&PID_{hex_pid}" in hwid
                    or f"VID_{USB_VID:04X}+PID_{hex_pid}" in hwid
                ):
                    textual = True
                    break
            if structured or textual:
                device = str(getattr(item, "device", "") or "").strip()
                if device and device.upper() not in [p.upper() for p in result]:
                    result.append(device)
    for port in _registry_candidate_ports():
        if port.upper() not in [p.upper() for p in result]:
            result.append(port)
    return result


def prepare_display_payload(value: Any, mask: int, points: int = 0) -> Tuple[str, int]:
    """Turn human display text into the firmware's digit+point planes.

    MobiFlight's MAX7219 runtime command sends decimal points separately from
    the character field.  Studio users naturally type values such as
    ``120.900``; consuming the dot as a character wastes one physical digit
    and can make a radio frequency appear blank or shifted.  This helper keeps
    the numeric characters on real digits and converts dots/commas to the
    matching point bit.
    """
    mask = int(mask) & 0xFF
    explicit_points = int(points) & 0xFF
    bits = [bit for bit in range(7, -1, -1) if mask & (1 << bit)]
    if not bits:
        return "", explicit_points

    raw = str(value if value is not None else "")
    raw = raw.replace(";", " ")
    tokens: List[List[Any]] = []
    for char in raw:
        if char in ".,":
            if tokens:
                tokens[-1][1] = True
            continue
        if ord(char) < 0x20 or ord(char) > 0x7E:
            char = " "
        tokens.append([char, False])

    # The firmware/display modules are right-aligned in normal MobiFlight use.
    if len(tokens) > len(bits):
        tokens = tokens[-len(bits):]
    tokens = [[" ", False] for _ in range(len(bits) - len(tokens))] + tokens

    encoded_points = explicit_points
    chars: List[str] = []
    for (char, has_point), bit in zip(tokens, bits):
        chars.append(str(char)[0] if str(char) else " ")
        if has_point:
            encoded_points |= 1 << bit
    return "".join(chars), encoded_points & 0xFF


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
    buttons: Tuple[str, ...]
    encoders: Tuple[str, ...]
    outputs: Tuple[str, ...]
    displays: Tuple[str, ...]
    identity_names: Tuple[str, ...] = ()
    default_brightness: Mapping[str, int] = field(default_factory=dict)
    display_masks: Mapping[str, int] = field(default_factory=dict)
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
    # MobiFlight's standard Mega connection contract waits 2000 ms after
    # opening a DTR-enabled serial port. HOWALT uses the same firmware family.
    boot_settle_seconds = 2.10
    identity_timeout = 2.60
    input_config_timeout = 4.00
    input_retrigger_timeout = 2.50
    keepalive_seconds = 8.0

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
        env_port = os.environ.get(f"{spec.software_name}_PORT") or os.environ.get(f"MUSLIMSIM_{spec.software_name}_PORT")
        chosen_port = port or env_port
        self.port_hint = str(chosen_port).strip() if chosen_port else None
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
        self.serial_backend = ""
        self.candidate_ports: List[str] = []
        self.probe_log: List[str] = []
        self.last_raw_frame = ""

        self.inputs: Dict[str, Dict[str, Any]] = {}
        self.outputs: Dict[str, int] = {name: 0 for name in spec.outputs}
        self.displays: Dict[str, Dict[str, Any]] = {
            name: {
                "text": "",
                "points": 0,
                # Each panel declares the intended MAX7219 positions. D203's
                # 0x0F and D201 SMG-1/2 0x3F are focused-capture confirmed.
                # D201 SMG-3/4 0x1F is isolated as the one photo-derived mask.
                "mask": int(spec.display_masks.get(name, 0xFF)) & 0xFF,
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
                "serial_backend": self.serial_backend,
                "candidate_ports": list(self.candidate_ports),
                "probe_log": list(self.probe_log[-12:]),
                "last_raw_frame": self.last_raw_frame,
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
            previous = int(self.outputs.get(output_name, 0))
            self.outputs[output_name] = level
        if previous != level:
            self._send(CMD_SET_PIN, index, level, require_connected=False)

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

        text, points = prepare_display_payload(value, mask, points)

        with self._state_lock:
            previous_state = dict(self.displays[display_name])
            previous_brightness = int(previous_state["brightness"])
            self.displays[display_name].update({
                "text": text,
                "points": points,
                "mask": mask,
            })
        display_changed = (
            str(previous_state.get("text", "")) != text
            or int(previous_state.get("points", 0)) != points
            or int(previous_state.get("mask", 0)) != mask
        )
        if display_changed:
            self._send(CMD_SET_MODULE, module, 0, text, points, mask, require_connected=False)
        if brightness is not None and int(brightness) != previous_brightness:
            self.set_display_brightness(display_name, int(brightness))

    def set_display_brightness(self, name: str, brightness: int) -> None:
        display_name = self._require_name(name, self.spec.displays)
        module = self.spec.display_indices[display_name]
        level = max(0, min(16, int(brightness)))
        with self._state_lock:
            previous = int(self.displays[display_name].get("brightness", 0))
            self.displays[display_name]["brightness"] = level
        if previous != level:
            self._send(CMD_SET_MODULE_BRIGHTNESS, module, 0, level, require_connected=False)

    def clear_display(self, name: str) -> None:
        display_name = self._require_name(name, self.spec.displays)
        # Use the panel-specific captured digit mask.  D203 has only four
        # physical squawk digits (0x0F); sending an eight-digit 0xFF blank
        # command can address nonexistent MAX7219 positions and was one source
        # of unreliable screen clearing/recovery.
        self.set_display(
            display_name,
            " " * max(1, int(self._default_mask(display_name)).bit_count()),
            mask=self._default_mask(display_name),
        )

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
                    mask = self._default_mask(display_name)
                    self.displays[display_name].update({
                        "text": " " * max(1, int(mask).bit_count()),
                        "points": 0,
                        "mask": mask,
                    })

    def mirror_practice_input(self, name: str, phase: str) -> None:
        """Mirror a Studio/Test-mode action into the live faceplate cache."""
        raw_name = self._resolve_name(name, self.spec.buttons + self.spec.encoders)
        if raw_name is None:
            return
        phase = str(phase)
        now = time.time()
        with self._state_lock:
            if raw_name in self.spec.buttons:
                pressed = phase != "release"
                raw = 0 if pressed else 1
                self.inputs[raw_name] = {
                    "raw": raw,
                    "pressed": pressed,
                    "phase": phase,
                    "practice": True,
                }
                kind = "button"
            else:
                raw = {
                    "left": 0, "left-fast": 1,
                    "right": 2, "right-fast": 3,
                }.get(phase, 2)
                self.inputs[raw_name] = {
                    "event_id": raw,
                    "phase": phase,
                    "practice": True,
                }
                kind = "encoder"
            self.last_event = {
                "device": self.spec.key,
                "software": self.spec.software_name,
                "control": raw_name,
                "index": self.spec.input_indices.get(raw_name),
                "kind": kind,
                "phase": phase,
                "raw": raw,
                "time": now,
                "practice": True,
            }

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
                    self.serial_backend = serial_backend_name(ser)
                self._set_state("connected", f"direct serial owner on {port}")
                if self.diagnose:
                    print(f"{self.spec.software_name}: CONNECTED {port} {identity}")

                # Keep the existing display/output behavior unchanged.
                self._send(CMD_POWER_SAVE, 0, require_connected=True)

                # INPUT ACTIVATION, capture-derived:
                #
                # The user's D201/D203 captures show that MobiFlight first
                # sends GetConfig (12;) and fully consumes the 10,<config>;
                # response. Only after that does the firmware reliably emit
                # button/encoder events. Then it sends the compatibility
                # retrigger form 23,5,<module-name>; and receives the current
                # button states followed by 34;.
                #
                # Waiting for both replies is important on the user's
                # MobiFlight 3.1.4 firmware: outputs can work while inputs
                # remain silent if we race ahead of this handshake.
                self._activate_inputs_from_capture()

                # Existing output replay is intentionally untouched.
                self._replay_outputs()

                # Re-publish maintained switch state after outputs are restored.
                self._retrigger_inputs_from_capture()

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
        # Do not spray identity queries at unrelated COM devices. The known HOWALT
        # D201/D203 hardware uses the CH340/CH341 USB bridge (1A86:7523). Some
        # Windows driver builds expose VID/PID as structured fields, while others
        # only include them in HWID, so support both representations.
        return list_candidate_howalt_ports(self.port_hint)

    def _find_and_open(self) -> Tuple[Any, Optional[str], Dict[str, str]]:
        owner = self.spec.key
        with _PROBE_LOCK:
            candidates = self._candidate_ports()
            with self._state_lock:
                self.candidate_ports = list(candidates)
                self.probe_log = (
                    [f"candidates: {', '.join(candidates)}"]
                    if candidates else
                    ["no WCH HOWALT COM candidates found"]
                )
            for port in candidates:
                if self.stop_evt.is_set():
                    return None, None, {}
                if not _claim_port(port, owner):
                    with self._state_lock:
                        self.probe_log.append(f"{port}: already claimed by another HOWALT router")
                    continue
                ser: Any = None
                keep_claim = False
                try:
                    ser = open_serial_port(
                        port,
                        baudrate=self.baud,
                        timeout=0.08,
                        write_timeout=0.6,
                    )
                    backend = serial_backend_name(ser)
                    with self._state_lock:
                        self.probe_log.append(f"{port}: opened with {backend}")
                    try:
                        ser.reset_input_buffer()
                    except Exception:
                        pass
                    self._decoder = FrameDecoder()

                    # Official MobiFlight Mega board definitions use a 2000 ms
                    # connection delay with DTR enabled. Opening CH340/Mega can
                    # reset the MCU; probing after only 350 ms can miss every
                    # button, encoder and output because identity never binds.
                    if self.stop_evt.wait(self.boot_settle_seconds):
                        return None, None, {}

                    identity = self._probe_identity(ser)
                    if identity:
                        with self._state_lock:
                            self.probe_log.append(
                                f"{port}: identity {identity.get('name','?')} "
                                f"{identity.get('firmware','')}"
                            )
                    else:
                        with self._state_lock:
                            self.probe_log.append(f"{port}: no MobiFlight identity reply")

                    if identity and identity_matches_spec(identity, self.spec):
                        identity["matched_model"] = self.spec.module_name
                        identity["portable_match"] = "model/protocol"
                        keep_claim = True
                        return ser, port, identity

                    if identity:
                        with self._state_lock:
                            self.probe_log.append(
                                f"{port}: belongs to another model; continuing"
                            )
                except Exception as exc:
                    message = f"{port}: {type(exc).__name__}: {exc}"
                    with self._state_lock:
                        self.probe_log.append(message)
                    if self.diagnose:
                        print(f"{self.spec.software_name}: probe {message}")
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
                with self._state_lock:
                    self.last_raw_frame = frame
                    if len(self.probe_log) < 40:
                        self.probe_log.append(f"RX {frame[:180]}")
                identity = parse_identity_frame(frame)
                if identity:
                    return identity
            time.sleep(0.01)
        return {}

    def _read_one_or_more_frames_until(
        self,
        *,
        deadline: float,
        stop_when: Callable[[str], bool],
        purpose: str,
    ) -> None:
        """Drain serial input through the normal decoder until a marker arrives.

        Every decoded frame is passed through _handle_frame(), so the initial
        retriggered switch positions populate the same live input mirror and
        HardwareLab route used by later physical movements.
        """
        while time.monotonic() < deadline and not self.stop_evt.is_set():
            ser = self._serial
            if ser is None:
                raise RuntimeError(
                    f"{self.spec.software_name}: serial closed during {purpose}"
                )
            chunk = ser.read(1024)
            if not chunk:
                time.sleep(0.005)
                continue
            with self._state_lock:
                self.last_rx_monotonic = time.monotonic()
            for frame in self._decoder.feed(bytes(chunk)):
                self.frames_rx += 1
                self._handle_frame(frame)
                if stop_when(frame):
                    return
        raise RuntimeError(
            f"{self.spec.software_name}: timed out waiting for {purpose}"
        )

    def _activate_inputs_from_capture(self) -> None:
        """Send 12; and wait for the full board configuration response.

        User capture evidence:
          OUT 12;
          IN  10,<full device configuration>;

        On the panel firmware this is the point after which input reporting is
        ready. The configuration is read-only; MuslimSim never writes/reset/
        saves/activates EEPROM configuration here.
        """
        self._send(CMD_GET_CONFIG, require_connected=True)

        def got_config(frame: str) -> bool:
            fields = [part.strip() for part in str(frame).split(",")]
            if not fields:
                return False
            try:
                command = int(fields[0])
            except ValueError:
                return False
            if command != CMD_INFO:
                return False
            # Identity command 10 has the MobiFlight type/name/serial/version
            # shape. The config response is the other command-10 payload.
            return parse_identity_fields(fields) == {} and len(fields) >= 2

        self._read_one_or_more_frames_until(
            deadline=time.monotonic() + self.input_config_timeout,
            stop_when=got_config,
            purpose="capture-confirmed GetConfig response (10,<config>;)",
        )
        with self._state_lock:
            self.probe_log.append(
                f"{self.connected_port or '?'}: input config handshake complete"
            )

    def _retrigger_inputs_from_capture(self) -> None:
        """Use the exact retrigger command observed on the user's panels.

        The working D201 capture shows:
          OUT 23,5,Hoowalt D201 RTP;
          IN  7,<button>,<0|1>; ... 34;

        The same startup capture also shows:
          OUT 23,5,Hoowalt D203 ATC;
          IN  maintained D203 button states ... 34;

        Extra arguments are intentionally preserved because this is the
        command form proven on the user's firmware 3.1.4.
        """
        self._send(
            CMD_TRIGGER, 5, self.spec.module_name,
            require_connected=True,
        )

        def retrigger_done(frame: str) -> bool:
            try:
                return int(str(frame).split(",", 1)[0].strip()) == CMD_RETRIGGER_DONE
            except Exception:
                return False

        self._read_one_or_more_frames_until(
            deadline=time.monotonic() + self.input_retrigger_timeout,
            stop_when=retrigger_done,
            purpose="capture-confirmed retrigger completion (34;)",
        )
        with self._state_lock:
            self.detail = (
                f"direct serial owner on {self.connected_port or '?'}; "
                "capture-confirmed inputs synchronized"
            )
            self.probe_log.append(
                f"{self.connected_port or '?'}: input retrigger 23,5,"
                f"{self.spec.module_name}; -> 34 complete"
            )

    def _read_loop(self) -> None:
        next_keepalive = time.monotonic() + self.keepalive_seconds
        while not self.stop_evt.is_set():
            ser = self._serial
            if ser is None:
                return
            now = time.monotonic()
            if now >= next_keepalive:
                # Keep the firmware out of display power-save while Studio owns it.
                self._send(CMD_POWER_SAVE, 0, require_connected=True)
                next_keepalive = now + self.keepalive_seconds
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
        with self._state_lock:
            self.last_raw_frame = str(frame)
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
            self._publish_input(name, phase, raw, kind="button")
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
            self._publish_input(name, phase, event_id, kind="encoder")
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

    def _publish_input(
        self, name: str, phase: str, raw: int, *, kind: str = "input"
    ) -> None:
        index = self.spec.input_indices.get(name)
        event = {
            "device": self.spec.key,
            "software": self.spec.software_name,
            "control": name,
            "index": index,
            "kind": str(kind),
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

        # A push-button can legally share a front-panel encoder's printed
        # name. If firmware ever emits command 7,BMQ1,... for HF SENS PUSH,
        # do not misroute that press as BMQ1 rotation. The event_sink handles
        # such type-aware combined controls separately.
        if (
            kind == "button"
            and name in self.spec.encoders
            and name not in self.spec.buttons
        ):
            return

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
            # Replay *every* cached display, including a deliberately blank
            # one.  A USB reconnect must never leave stale MAX7219 digits from
            # a previous owner/session on the physical panel.
            digit_count = max(1, mask.bit_count())
            replay_text, replay_points = prepare_display_payload(
                text, mask, points
            )
            self._send(
                CMD_SET_MODULE,
                module,
                0,
                replay_text[:digit_count].rjust(digit_count),
                replay_points,
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
        return int(self.spec.display_masks.get(display_name, 0xFF)) & 0xFF


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



def _normalize_identity_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    # The supplied captures/configs use "Hoowalt" while the product is often
    # referred to as "HOWALT". Treat that spelling variation as the same maker.
    text = text.replace("hoowalt", "howalt")
    return re.sub(r"[^a-z0-9]+", "", text)


def identity_matches_spec(identity: Mapping[str, Any], spec: PanelSpec) -> bool:
    """Portable model match; never locks to a captured serial number."""
    name = _normalize_identity_name(identity.get("name"))
    if not name:
        return False
    accepted = {
        _normalize_identity_name(spec.module_name),
        _normalize_identity_name(spec.title),
    }
    accepted.update(_normalize_identity_name(item) for item in spec.identity_names)
    accepted.discard("")
    if name in accepted:
        return True

    # Safe model-token fallback for otherwise cosmetic firmware naming changes.
    # Still require both the model number and function so a random CH340 device
    # can never be mistaken for a panel solely because it shares a USB bridge.
    if spec.key == "muslimrtp_d201":
        return "d201" in name and "rtp" in name
    if spec.key == "muslimatc_d203":
        return "d203" in name and ("atc" in name or "xpndr" in name or "transponder" in name)
    return False

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

MUSLIMSIM_HOWALT_V45_RUNTIME_REPAIR = True

MUSLIMSIM_HOWALT_V46_INPUT_HANDSHAKE = True

MUSLIMSIM_HOWALT_V47_TYPED_INPUT = True
