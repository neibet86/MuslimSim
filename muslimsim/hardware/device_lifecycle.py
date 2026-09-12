#!/usr/bin/env python3
"""MuslimSim global physical-device lifecycle service.

MUSLIMSIM_DEVICE_LIFECYCLE_V1

This module deliberately does not own BB35 or BB36.  Their established path
routers remain authoritative.  It standardizes USB truth and hotplug recovery
for the remaining MuslimSim devices inside the existing bridge process.
"""
from __future__ import annotations

import inspect
import os
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence, Tuple

from .device_manager import resolve_serial_port_name

POLL_SECONDS = 0.25
RECONNECT_SETTLE_SECONDS = 0.25
SERIAL_RETRY_SECONDS = 0.30
SDL_RESTART_BACKOFF_SECONDS = 3.0

EXEMPT_DEVICE_KEYS = frozenset({"pfp3n_bb35", "mcdu32_bb36"})

# Exact USB IDs are preferred.  Product tokens are used only where the current
# bridge discovers a controller by its Windows product name rather than a
# published PID (pedals / MOZA A210).
DEVICE_SPECS: Dict[str, Dict[str, Any]] = {
    "pu_overhead": {
        "vid": 0x3561, "pid": 0x8561,
        "tokens": ("PU OVHD", "PU OVERHEAD"),
        "label": "PU Overhead",
    },
    "winctrl_throttle": {
        "vid": 0x4098, "pid": 0xB930,
        "tokens": ("URSA MINOR 32 THROTTLE",),
        "label": "WinCtrl throttle",
    },
    "winctrl_pedals": {
        "tokens": ("ORION COMBAT RUDDER PEDALS", "ORION RUDDER PEDALS"),
        "label": "WinCtrl pedals",
    },
    "agp_bb80": {
        "vid": 0x4098, "pid": 0xBB80,
        "tokens": ("AGP",),
        "label": "AGP BB80",
    },
    "pap3_mag": {
        "vid": 0x4098, "pid": 0xBF0F,
        "tokens": ("PAP", "MCP"),
        "label": "PAP3 MCP",
    },
    "pdc_bb62": {
        "vid": 0x4098, "pid": 0xBB62,
        "tokens": ("PDC",),
        "label": "PDC BB62",
    },
    "fcu_32_efis": {
        "vid": 0x4098, "pid": 0xBA01,
        "tokens": ("FCU", "EFIS"),
        "label": "FCU / EFIS BA01",
    },
    "ecam32": {
        "vid": 0x4098, "pid": 0xBB70,
        "tokens": ("ECAM",),
        "label": "ECAM32 BB70",
    },
    "moza_a210": {
        "tokens": ("MOZA A210",),
        "label": "MOZA A210",
    },
    "moza_ab6": {
        "tokens": ("MOZA AB6",),
        "label": "MOZA AB6",
    },
}

SDL_DEVICE_KEYS = ("pu_overhead", "winctrl_throttle", "winctrl_pedals")


def _project_root() -> Path:
    try:
        return Path(__file__).resolve().parents[2]
    except Exception:
        return Path.cwd()


_LOG_LOCK = threading.Lock()


def _log(message: str) -> None:
    text = f"{datetime.now().isoformat(timespec='milliseconds')} | {message}"
    try:
        log_path = _project_root() / "logs" / "device_lifecycle.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_LOCK:
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(text + "\n")
    except Exception:
        pass


@dataclass(frozen=True)
class PresenceSnapshot:
    known: bool
    present: bool
    generation: int
    product: str = ""
    path: str = ""
    last_change: float = 0.0


class _Binding:
    def __init__(
        self,
        device_key: str,
        start: Optional[Callable[[], Any]],
        stop: Optional[Callable[[], Any]],
    ) -> None:
        self.device_key = str(device_key)
        self.start = start if callable(start) else None
        self.stop = stop if callable(stop) else None
        self.lock = threading.Lock()
        self.transition = ""

    def update(
        self,
        start: Optional[Callable[[], Any]],
        stop: Optional[Callable[[], Any]],
    ) -> None:
        if callable(start):
            self.start = start
        if callable(stop):
            self.stop = stop

    def request(self, present: bool, generation: int) -> None:
        callback = self.start if present else self.stop
        if callback is None:
            return

        def worker() -> None:
            # One callback at a time per physical device.  Re-check current USB
            # truth after acquiring the lock so a fast unplug/replug cannot run
            # an obsolete transition after the newer one.
            with self.lock:
                current = _REGISTRY.snapshot(self.device_key)
                if not current.known or current.present != bool(present):
                    return
                self.transition = "reconnecting" if present else "stopping"
                action = "start" if present else "stop"
                _log(f"{self.device_key}: manager {action} requested (generation {generation})")
                try:
                    if present:
                        time.sleep(RECONNECT_SETTLE_SECONDS)
                        current = _REGISTRY.snapshot(self.device_key)
                        if not current.known or not current.present:
                            return
                    callback()
                    _log(f"{self.device_key}: manager {action} returned")
                except Exception as exc:
                    _log(f"{self.device_key}: manager {action} error: {type(exc).__name__}: {exc}")
                finally:
                    self.transition = ""

        threading.Thread(
            target=worker,
            name=f"MuslimSim-{self.device_key}-Lifecycle",
            daemon=True,
        ).start()


class DeviceLifecycleRegistry:
    def __init__(self) -> None:
        self._hid = None
        self._global_stop: Optional[Any] = None
        self._lock = threading.RLock()
        self._states: Dict[str, PresenceSnapshot] = {
            key: PresenceSnapshot(False, False, 0)
            for key in DEVICE_SPECS
        }
        self._bindings: Dict[str, _Binding] = {}
        self._listeners: Dict[str, list] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def configure(self, hid_module: Any = None, global_stop: Any = None) -> "DeviceLifecycleRegistry":
        with self._lock:
            if hid_module is not None:
                self._hid = hid_module
            if global_stop is not None:
                self._global_stop = global_stop
        # Synchronous first scan means Studio registrations immediately get
        # real USB truth instead of a temporary guessed state.
        self.scan_once(initial=True)
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._stop.clear()
                self._thread = threading.Thread(
                    target=self._run,
                    name="MuslimSim-USB-Lifecycle",
                    daemon=True,
                )
                self._thread.start()
                _log("global USB lifecycle monitor started")
        return self

    def _externally_stopped(self) -> bool:
        stop = self._global_stop
        if stop is None:
            return False
        try:
            return bool(stop.is_set())
        except Exception:
            return False

    def snapshot(self, device_key: str) -> PresenceSnapshot:
        key = str(device_key)
        with self._lock:
            return self._states.get(key, PresenceSnapshot(False, False, 0))

    def generation(self, keys: Sequence[str]) -> Tuple[int, ...]:
        with self._lock:
            return tuple(self._states.get(k, PresenceSnapshot(False, False, 0)).generation for k in keys)

    def bind(
        self,
        device_key: str,
        start: Optional[Callable[[], Any]],
        stop: Optional[Callable[[], Any]],
    ) -> Optional[_Binding]:
        key = str(device_key)
        if key in EXEMPT_DEVICE_KEYS or key not in DEVICE_SPECS:
            return None
        if not callable(start) and not callable(stop):
            with self._lock:
                return self._bindings.get(key)
        with self._lock:
            binding = self._bindings.get(key)
            if binding is None:
                binding = _Binding(key, start, stop)
                self._bindings[key] = binding
            else:
                binding.update(start, stop)
            return binding

    def add_listener(self, device_key: str, callback: Callable[[bool, int], Any]) -> None:
        key = str(device_key)
        if key in EXEMPT_DEVICE_KEYS or key not in DEVICE_SPECS or not callable(callback):
            return
        with self._lock:
            listeners = self._listeners.setdefault(key, [])
            if callback not in listeners:
                listeners.append(callback)

    @staticmethod
    def _text(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode(errors="replace")
        return str(value or "")

    def _matches(self, info: Mapping[str, Any], spec: Mapping[str, Any]) -> bool:
        vid = spec.get("vid")
        pid = spec.get("pid")
        if vid is not None and pid is not None:
            try:
                if int(info.get("vendor_id", -1)) == int(vid) and int(info.get("product_id", -1)) == int(pid):
                    return True
            except Exception:
                pass
        tokens = tuple(str(t).upper() for t in spec.get("tokens", ()) if str(t).strip())
        if not tokens:
            return False
        product = self._text(info.get("product_string")).upper()
        manufacturer = self._text(info.get("manufacturer_string")).upper()
        haystack = product + " " + manufacturer
        return any(token in haystack for token in tokens)

    def scan_once(self, initial: bool = False) -> None:
        hid_module = self._hid
        if hid_module is None:
            return
        try:
            records = list(hid_module.enumerate())
        except Exception as exc:
            _log(f"USB enumeration error: {type(exc).__name__}: {exc}")
            return

        now = time.monotonic()
        transitions = []
        with self._lock:
            for key, spec in DEVICE_SPECS.items():
                match = next((item for item in records if isinstance(item, Mapping) and self._matches(item, spec)), None)
                present = match is not None
                old = self._states.get(key, PresenceSnapshot(False, False, 0))
                product = self._text(match.get("product_string")) if match else ""
                path = self._text(match.get("path")) if match else ""
                # The first successful enumeration establishes truth without
                # firing manager start/stop callbacks; existing startup code
                # remains the owner of the initial launch sequence.
                changed = old.known and old.present != present
                generation = old.generation + (1 if changed else 0)
                last_change = now if changed or not old.known else old.last_change
                self._states[key] = PresenceSnapshot(True, present, generation, product, path, last_change)
                if changed:
                    transitions.append((key, present, generation, product))

        for key, present, generation, product in transitions:
            _log(f"{key}: USB {'CONNECTED' if present else 'DISCONNECTED'} generation={generation} product={product!r}")
            with self._lock:
                binding = self._bindings.get(key)
                listeners = list(self._listeners.get(key, ()))
            if binding is not None:
                binding.request(present, generation)
            for callback in listeners:
                try:
                    callback(present, generation)
                except Exception as exc:
                    _log(f"{key}: listener error: {type(exc).__name__}: {exc}")

    def _run(self) -> None:
        while not self._stop.is_set() and not self._externally_stopped():
            self.scan_once()
            self._stop.wait(POLL_SECONDS)
        _log("global USB lifecycle monitor stopped")


_REGISTRY = DeviceLifecycleRegistry()


def configure(hid_module: Any = None, global_stop: Any = None) -> DeviceLifecycleRegistry:
    return _REGISTRY.configure(hid_module=hid_module, global_stop=global_stop)


def lifecycle_snapshot(device_key: str) -> Dict[str, Any]:
    snap = _REGISTRY.snapshot(device_key)
    return {
        "known": snap.known,
        "present": snap.present,
        "generation": snap.generation,
        "product": snap.product,
        "path": snap.path,
        "last_change": snap.last_change,
    }


_PU_SERIAL_LOCK = threading.RLock()
_PU_SERIAL_PROXY: Optional["ReconnectableSerialPort"] = None


def _pu_serial_online() -> Optional[bool]:
    with _PU_SERIAL_LOCK:
        proxy = _PU_SERIAL_PROXY
    if proxy is None:
        return None
    try:
        return bool(proxy.is_open)
    except Exception:
        return False


def _pu_serial_port() -> str:
    with _PU_SERIAL_LOCK:
        proxy = _PU_SERIAL_PROXY
    if proxy is None:
        return ""
    try:
        return str(proxy.port or "")
    except Exception:
        return ""


def wrap_status(
    device_key: str,
    base_status: Optional[Callable[[], Any]],
    *,
    start: Optional[Callable[[], Any]] = None,
    stop: Optional[Callable[[], Any]] = None,
) -> Optional[Callable[[], Dict[str, Any]]]:
    """Publish physical USB truth and register existing manager callbacks."""
    key = str(device_key)
    if key in EXEMPT_DEVICE_KEYS or key not in DEVICE_SPECS:
        return base_status

    binding = _REGISTRY.bind(key, start, stop)

    def status() -> Dict[str, Any]:
        base: Dict[str, Any] = {}
        if callable(base_status):
            try:
                value = base_status()
                if isinstance(value, Mapping):
                    base = dict(value)
                elif value is not None:
                    base = {"state": str(value)}
            except Exception as exc:
                base = {"state": "reconnecting", "detail": f"status callback error: {exc}"}
        elif isinstance(base_status, Mapping):
            base = dict(base_status)

        snap = _REGISTRY.snapshot(key)
        if not snap.known:
            # Never invent an unplug while HID enumeration is unavailable.
            return base or {"state": "unknown", "connected": False, "usb_connected": None}

        if not snap.present:
            return {
                "state": "disconnected",
                "detail": "USB not detected",
                "connected": False,
                "usb_connected": False,
                "live": False,
                "mirror": {},
                "values": {},
            }

        result = dict(base)
        result["usb_connected"] = True
        result["product"] = snap.product or result.get("product", "")

        # PU is a composite device: Windows may enumerate its HID interface
        # while COM5 is still reopening.  Do not claim LIVE until the serial
        # output owner has a real handle again.
        if key == "pu_overhead":
            online = _pu_serial_online()
            runtime_port = _pu_serial_port()
            if runtime_port:
                result["port"] = runtime_port
                result["port_policy"] = "automatic product discovery; COM is runtime-only"
            if online is False:
                result.update({
                    "state": "reconnecting",
                    "detail": "PU USB present; automatically resolving/reopening serial output",
                    "connected": False,
                    "live": False,
                })
                return result

        active_binding = binding or _REGISTRY.bind(key, None, None)
        if active_binding is not None and active_binding.transition:
            result.update({
                "state": active_binding.transition,
                "connected": False,
                "live": False,
            })
            return result

        state = str(result.get("state") or "connected").strip().lower()
        offlineish = {
            "disconnected", "offline", "waiting", "waiting-for-usb",
            "waiting-for-pap3", "waiting-for-pdc", "waiting-for-device",
            "reconnecting", "connecting", "starting", "stopping", "stopped",
            "dependency-missing", "error",
        }
        if state in offlineish or state.startswith("waiting"):
            # Individual device managers use several specific waiting-* labels.
            # Treat every waiting state as non-live instead of maintaining an
            # ever-growing hard-coded list of product-specific spellings.
            result.setdefault("connected", False)
            result.setdefault("live", False)
        else:
            result.setdefault("connected", True)
            result.setdefault("live", bool(result.get("connected")))
        return result

    return status


class _CombinedStopEvent:
    def __init__(self, global_stop: Any, keys: Sequence[str], baseline_generation: Tuple[int, ...]) -> None:
        self.global_stop = global_stop
        self.keys = tuple(keys)
        self.baseline_generation = tuple(baseline_generation)

    def _generation_changed(self) -> bool:
        return _REGISTRY.generation(self.keys) != self.baseline_generation

    def is_set(self) -> bool:
        try:
            if self.global_stop.is_set():
                return True
        except Exception:
            pass
        return self._generation_changed()

    def wait(self, timeout: Optional[float] = None) -> bool:
        if self.is_set():
            return True
        deadline = None if timeout is None else time.monotonic() + max(0.0, float(timeout))
        while not self.is_set():
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                quantum = min(0.05, remaining)
            else:
                quantum = 0.05
            try:
                if self.global_stop.wait(quantum):
                    return True
            except Exception:
                time.sleep(quantum)
        return True


class _QueueProxy:
    """Suppress only repeated startup safety snapshots after SDL hotplug."""
    def __init__(self, inner: Any, suppress_startup_snapshot: bool) -> None:
        self.inner = inner
        self.suppress_startup_snapshot = bool(suppress_startup_snapshot)

    def put(self, item: Any, *args: Any, **kwargs: Any) -> Any:
        if (
            self.suppress_startup_snapshot
            and isinstance(item, tuple)
            and len(item) >= 1
            and item[0] == "startup_hardware_snapshot"
        ):
            _log("SDL hotplug rebaseline: repeated startup_hardware_snapshot suppressed")
            return None
        # startup_pu_authority_baseline is deliberately NOT suppressed: the
        # actual maintained PU detents must regain authority after reconnect.
        return self.inner.put(item, *args, **kwargs)

    def put_nowait(self, item: Any) -> Any:
        return self.put(item, block=False)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


def wrap_sdl_reader(original: Callable[..., Any]) -> Callable[..., Any]:
    """Keep one SDL owner but restart it when PU/throttle/pedals USB changes.

    The pygame window is created once at supervised() entry and kept alive for
    the entire bridge session.  Reader sessions that call pygame.display.quit()
    or pygame.quit() in their finally blocks have those calls silenced so the
    window never flashes between restarts.
    """
    if getattr(original, "_muslimsim_lifecycle_v1", False):
        return original
    signature = inspect.signature(original)

    def supervised(*args: Any, **kwargs: Any) -> Any:
        try:
            bound = signature.bind_partial(*args, **kwargs)
            global_stop = bound.arguments.get("stop_evt")
            event_q = bound.arguments.get("event_q")
        except Exception:
            return original(*args, **kwargs)
        if global_stop is None or event_q is None:
            return original(*args, **kwargs)

        # Initialise pygame and the DirectInput helper window exactly once.
        # The window is made completely invisible: WS_EX_TOOLWINDOW removes it
        # from the taskbar and Alt+Tab, then SW_HIDE hides it entirely.
        # DirectInput still receives a valid HWND so controller input works.
        _pygame: Any = None
        try:
            import pygame as _pg  # type: ignore[import]
            os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
            os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "-10000,-10000")
            _pg.init()
            try:
                _pg.display.init()
                _pg.display.set_mode((1, 1), _pg.NOFRAME)
                # Strip the window from the taskbar and Alt+Tab on Windows.
                try:
                    import ctypes as _ct
                    _hwnd = _pg.display.get_wm_info().get("window")
                    if _hwnd:
                        _u32 = _ct.windll.user32
                        _GWL_EXSTYLE   = -20
                        _WS_EX_APPWINDOW  = 0x00040000
                        _WS_EX_TOOLWINDOW = 0x00000080
                        _WS_EX_NOACTIVATE = 0x08000000
                        _SW_HIDE = 0
                        _style = _u32.GetWindowLongW(_hwnd, _GWL_EXSTYLE)
                        _style = (_style & ~_WS_EX_APPWINDOW) | _WS_EX_TOOLWINDOW | _WS_EX_NOACTIVATE
                        _u32.SetWindowLongW(_hwnd, _GWL_EXSTYLE, _style)
                        _u32.ShowWindow(_hwnd, _SW_HIDE)
                except Exception as _we2:
                    _log(f"SDL window hide warning: {_we2}")
            except Exception as _we:
                _log(f"SDL pre-init display warning: {_we}")
            _pygame = _pg
        except Exception as _pe:
            _log(f"SDL pre-init failed, reader manages pygame itself: {_pe}")

        first_session = True
        try:
            while True:
                try:
                    if global_stop.is_set():
                        return None
                except Exception:
                    pass

                generation = _REGISTRY.generation(SDL_DEVICE_KEYS)
                session_stop = _CombinedStopEvent(global_stop, SDL_DEVICE_KEYS, generation)
                session_queue = _QueueProxy(event_q, suppress_startup_snapshot=not first_session)

                session_args = dict(bound.arguments)
                session_args["stop_evt"] = session_stop
                session_args["event_q"] = session_queue

                # Suppress the reader's teardown calls so our persistent
                # window survives.  pygame.joystick.quit() is allowed through
                # — the reader re-inits the joystick subsystem each session.
                _real_display_quit = _real_pygame_quit = None
                if _pygame is not None:
                    try:
                        _real_display_quit = _pygame.display.quit
                        _real_pygame_quit = _pygame.quit
                        _pygame.display.quit = lambda: None  # type: ignore[method-assign]
                        _pygame.quit = lambda: None          # type: ignore[method-assign]
                    except Exception:
                        _real_display_quit = _real_pygame_quit = None

                try:
                    original(**session_args)
                except TypeError:
                    rebound = signature.bind_partial(*args, **kwargs)
                    rebound.arguments["stop_evt"] = session_stop
                    rebound.arguments["event_q"] = session_queue
                    original(*rebound.args, **rebound.kwargs)
                except Exception as exc:
                    _log(f"SDL owner session error: {type(exc).__name__}: {exc}")
                finally:
                    if _pygame is not None and _real_display_quit is not None:
                        try:
                            _pygame.display.quit = _real_display_quit
                            _pygame.quit = _real_pygame_quit
                        except Exception:
                            pass

                first_session = False
                try:
                    if global_stop.is_set():
                        return None
                except Exception:
                    pass
                _log("SDL owner restarting after USB generation change / reader exit")
                try:
                    if global_stop.wait(SDL_RESTART_BACKOFF_SECONDS):
                        return None
                except Exception:
                    time.sleep(SDL_RESTART_BACKOFF_SECONDS)
        finally:
            # Real cleanup when the entire supervised loop exits.
            if _pygame is not None:
                try:
                    _pygame.joystick.quit()
                    _pygame.display.quit()
                    _pygame.quit()
                except Exception:
                    pass

    supervised.__name__ = getattr(original, "__name__", "_pu_controller_reader")
    supervised.__doc__ = getattr(original, "__doc__", None)
    supervised._muslimsim_lifecycle_v1 = True  # type: ignore[attr-defined]
    supervised.__wrapped__ = original  # type: ignore[attr-defined]
    return supervised


class ReconnectableHIDDevice:
    """One logical AGP handle that survives physical USB replacement."""
    def __init__(self, device_key: str, opener: Callable[[], Any]) -> None:
        self.device_key = str(device_key)
        self.opener = opener
        self._lock = threading.RLock()
        self._raw: Any = None
        self._permanent_closed = False
        self._next_open = 0.0
        self._led_packets: Dict[int, bytes] = {}
        self._lcd_data: Optional[bytes] = None
        self._lcd_commit: Optional[bytes] = None
        _REGISTRY.add_listener(self.device_key, self._presence_changed)
        self._ensure_open(force=True)

    def _presence_changed(self, present: bool, generation: int) -> None:
        if not present:
            with self._lock:
                self._drop_raw_locked()
        else:
            with self._lock:
                self._next_open = 0.0
        _log(f"{self.device_key}: HID proxy saw {'replug' if present else 'unplug'} generation={generation}")

    def _drop_raw_locked(self) -> None:
        raw = self._raw
        self._raw = None
        if raw is not None:
            try:
                raw.close()
            except Exception:
                pass

    def _cache(self, report: Any) -> None:
        try:
            data = bytes(report)
        except Exception:
            return
        if len(data) >= 9 and data[0] == 0x02 and data[6] == 0x49:
            self._led_packets[int(data[7])] = data
        if len(data) >= 10 and data[0] == 0x02:
            if data[3] == 0x35:
                self._lcd_data = data
            elif data[3] == 0x11:
                self._lcd_commit = data

    def _replay_locked(self) -> None:
        raw = self._raw
        if raw is None:
            return
        try:
            for selector in sorted(self._led_packets):
                raw.write(list(self._led_packets[selector]))
            if self._lcd_data is not None:
                raw.write(list(self._lcd_data))
            if self._lcd_commit is not None:
                raw.write(list(self._lcd_commit))
            if self._led_packets or self._lcd_data is not None:
                _log(f"{self.device_key}: cached AGP output restored after reconnect")
        except Exception as exc:
            _log(f"{self.device_key}: cached output replay failed: {exc}")
            self._drop_raw_locked()

    def _ensure_open(self, force: bool = False) -> Any:
        with self._lock:
            if self._permanent_closed:
                return None
            if self._raw is not None:
                return self._raw
            snap = _REGISTRY.snapshot(self.device_key)
            if snap.known and not snap.present:
                return None
            now = time.monotonic()
            if not force and now < self._next_open:
                return None
            self._next_open = now + SERIAL_RETRY_SECONDS
            try:
                self._raw = self.opener()
                self._next_open = 0.0
                _log(f"{self.device_key}: HID handle opened/reopened")
                self._replay_locked()
            except Exception as exc:
                self._raw = None
                _log(f"{self.device_key}: HID open waiting: {type(exc).__name__}: {exc}")
            return self._raw

    def read(self, size: int = 64, *args: Any, **kwargs: Any) -> Any:
        raw = self._ensure_open()
        if raw is None:
            return []
        try:
            return raw.read(size, *args, **kwargs)
        except Exception as exc:
            with self._lock:
                _log(f"{self.device_key}: HID read lost handle: {exc}")
                self._drop_raw_locked()
            return []

    def write(self, report: Any) -> int:
        with self._lock:
            self._cache(report)
        raw = self._ensure_open()
        if raw is None:
            return 0
        try:
            return int(raw.write(list(report)) or 0)
        except Exception as exc:
            with self._lock:
                _log(f"{self.device_key}: HID write lost handle: {exc}")
                self._drop_raw_locked()
            return 0

    def set_nonblocking(self, value: int) -> None:
        raw = self._ensure_open()
        if raw is not None:
            try:
                raw.set_nonblocking(value)
            except Exception:
                pass

    def close(self) -> None:
        with self._lock:
            self._permanent_closed = True
            self._drop_raw_locked()

    def __getattr__(self, name: str) -> Any:
        raw = self._ensure_open()
        if raw is None:
            raise AttributeError(name)
        return getattr(raw, name)


def wrap_hid_opener(device_key: str, original: Callable[[], Any]) -> Callable[[], Any]:
    key = str(device_key)
    if key != "agp_bb80" or getattr(original, "_muslimsim_lifecycle_v1", False):
        return original

    def opener() -> ReconnectableHIDDevice:
        return ReconnectableHIDDevice(key, original)

    opener.__name__ = getattr(original, "__name__", "_open_agp_display")
    opener.__doc__ = getattr(original, "__doc__", None)
    opener._muslimsim_lifecycle_v1 = True  # type: ignore[attr-defined]
    opener.__wrapped__ = original  # type: ignore[attr-defined]
    return opener


class ReconnectableSerialPort:
    """PU serial owner that survives runtime COM renumbering/replacement."""
    def __init__(
        self,
        original_serial: Callable[..., Any],
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
        *,
        value_state: int,
        dash_state: int,
        reset_seconds: float,
        dash_seconds: float,
        port_resolver: Optional[Callable[[], Optional[str]]] = None,
    ) -> None:
        self._original_serial = original_serial
        self._args = tuple(args)
        self._kwargs = dict(kwargs)
        self._port_resolver = port_resolver if callable(port_resolver) else None
        self._runtime_port = self._initial_port()
        self._value_state = int(value_state)
        self._dash_state = int(dash_state)
        self._reset_seconds = max(0.0, float(reset_seconds))
        self._dash_seconds = max(0.0, float(dash_seconds))
        self._lock = threading.RLock()
        self._raw: Any = None
        self._permanent_closed = False
        self._next_open = 0.0
        self._desired_dtr = False
        self._desired_rts = False
        self._ever_connected = False
        _REGISTRY.add_listener("pu_overhead", self._presence_changed)
        # Initial open is attempted without our own handshake because the
        # established final.py startup sequence immediately performs it.
        self._try_open(initial=True)
        global _PU_SERIAL_PROXY
        with _PU_SERIAL_LOCK:
            _PU_SERIAL_PROXY = self

    def _initial_port(self) -> str:
        candidate = self._kwargs.get("port")
        if candidate is None and self._args:
            candidate = self._args[0]
        return str(candidate or "").strip()

    def _resolve_runtime_port(self) -> str:
        resolver = self._port_resolver
        if resolver is not None:
            try:
                resolved = str(resolver() or "").strip()
            except Exception as exc:
                resolved = ""
                _log(f"pu_overhead: automatic COM resolver error: {type(exc).__name__}: {exc}")
            if resolved:
                if resolved.upper() != str(self._runtime_port or "").upper():
                    _log(
                        f"pu_overhead: automatic COM locator moved "
                        f"{self._runtime_port or '(none)'} -> {resolved}"
                    )
                self._runtime_port = resolved
                return resolved

            # In automatic mode the compatibility value (historically COM5)
            # exists only so final.py's established Serial() call is intercepted.
            # It is never a safe fallback identity.  If the product is not
            # currently resolved, do not open that COM number by guess.  An
            # already-open, already-identified handle may report its current
            # locator until it is dropped.
            if self._raw is not None:
                return str(self._runtime_port or "")
            return ""
        return str(self._runtime_port or self._initial_port())

    def _open_arguments(self) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
        port = self._resolve_runtime_port()
        args = list(self._args)
        kwargs = dict(self._kwargs)
        if "port" in kwargs:
            kwargs["port"] = port
        elif args:
            args[0] = port
        else:
            kwargs["port"] = port
        return tuple(args), kwargs

    @property
    def port(self) -> str:
        return self._resolve_runtime_port()

    def _presence_changed(self, present: bool, generation: int) -> None:
        with self._lock:
            if not present:
                self._drop_raw_locked()
            else:
                self._next_open = 0.0
        _log(f"pu_overhead: serial proxy saw {'replug' if present else 'unplug'} generation={generation}")

    def _drop_raw_locked(self) -> None:
        raw = self._raw
        self._raw = None
        if raw is not None:
            try:
                raw.close()
            except Exception:
                pass

    @staticmethod
    def _escape_rts(raw: Any, high: bool) -> None:
        try:
            raw.dtr = False
        except Exception:
            pass
        try:
            raw.rts = bool(high)
        except Exception:
            pass
        if os.name != "nt":
            return
        try:
            import ctypes
            handle = getattr(raw, "_port_handle", None)
            if handle is None:
                return
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.EscapeCommFunction.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            kernel32.EscapeCommFunction.restype = ctypes.c_bool
            kernel32.EscapeCommFunction(ctypes.c_void_p(handle), 6)  # CLRDTR
            kernel32.EscapeCommFunction(ctypes.c_void_p(handle), 3 if high else 4)  # SETRTS/CLRRTS
        except Exception:
            pass

    def _handshake_reconnect_locked(self, raw: Any) -> None:
        # Manufacture the same post-reset high -> low edge used by the proven
        # PU code, then return to whichever line state the bridge was using
        # before the unplug.
        self._escape_rts(raw, self._value_state != self._dash_state)
        if self._reset_seconds:
            time.sleep(self._reset_seconds)
        self._escape_rts(raw, False)
        if self._dash_seconds:
            time.sleep(self._dash_seconds)
        self._escape_rts(raw, bool(self._desired_rts))
        try:
            raw.dtr = bool(self._desired_dtr)
        except Exception:
            pass

    def _try_open(self, initial: bool = False) -> Any:
        with self._lock:
            if self._permanent_closed:
                return None
            if self._raw is not None:
                return self._raw
            snap = _REGISTRY.snapshot("pu_overhead")
            if snap.known and not snap.present:
                return None
            now = time.monotonic()
            if not initial and now < self._next_open:
                return None
            self._next_open = now + SERIAL_RETRY_SECONDS
            try:
                open_args, open_kwargs = self._open_arguments()
                if not self._resolve_runtime_port():
                    raise RuntimeError("supported PU serial endpoint is not currently present")
                raw = self._original_serial(*open_args, **open_kwargs)
                if not initial:
                    self._handshake_reconnect_locked(raw)
                else:
                    try:
                        raw.dtr = self._desired_dtr
                        raw.rts = self._desired_rts
                    except Exception:
                        pass
                self._raw = raw
                self._ever_connected = True
                self._next_open = 0.0
                _log(f"pu_overhead: COM handle opened/reopened on {self._runtime_port}")
            except Exception as exc:
                self._raw = None
                _log(f"pu_overhead: COM open waiting: {type(exc).__name__}: {exc}")
            return self._raw

    @property
    def is_open(self) -> bool:
        with self._lock:
            raw = self._raw
            if raw is None:
                return False
            try:
                return bool(raw.is_open)
            except Exception:
                return True

    @property
    def in_waiting(self) -> int:
        raw = self._try_open()
        if raw is None:
            return 0
        try:
            return int(raw.in_waiting)
        except Exception:
            return 0

    @property
    def dtr(self) -> bool:
        return bool(self._desired_dtr)

    @dtr.setter
    def dtr(self, value: Any) -> None:
        self._desired_dtr = bool(value)
        with self._lock:
            if self._raw is not None:
                try:
                    self._raw.dtr = self._desired_dtr
                except Exception:
                    pass

    @property
    def rts(self) -> bool:
        return bool(self._desired_rts)

    @rts.setter
    def rts(self, value: Any) -> None:
        self._desired_rts = bool(value)
        with self._lock:
            if self._raw is not None:
                try:
                    self._raw.rts = self._desired_rts
                except Exception:
                    pass

    @property
    def _port_handle(self) -> Any:
        with self._lock:
            return getattr(self._raw, "_port_handle", None) if self._raw is not None else None

    def write(self, data: Any) -> int:
        raw = self._try_open()
        if raw is None:
            return 0
        try:
            return int(raw.write(data) or 0)
        except Exception as exc:
            with self._lock:
                _log(f"pu_overhead: COM write lost handle: {exc}")
                self._drop_raw_locked()
            return 0

    def read(self, size: int = 1) -> bytes:
        raw = self._try_open()
        if raw is None:
            return b""
        try:
            return bytes(raw.read(size))
        except Exception:
            return b""

    def flush(self) -> None:
        raw = self._try_open()
        if raw is not None:
            try:
                raw.flush()
            except Exception:
                pass

    def close(self) -> None:
        global _PU_SERIAL_PROXY
        with self._lock:
            self._permanent_closed = True
            self._drop_raw_locked()
        with _PU_SERIAL_LOCK:
            if _PU_SERIAL_PROXY is self:
                _PU_SERIAL_PROXY = None

    def __getattr__(self, name: str) -> Any:
        raw = self._try_open()
        if raw is None:
            raise AttributeError(name)
        return getattr(raw, name)


def install_serial_proxy(
    serial_module: Any,
    *,
    port: str,
    value_state: int,
    dash_state: int,
    reset_seconds: float,
    dash_seconds: float,
    port_resolver: Optional[Callable[[], Optional[str]]] = None,
) -> None:
    """Patch the PU serial owner while allowing its runtime COM number to move.

    ``port`` remains the initial/compatibility locator. ``port_resolver`` is
    consulted on every reopen, so unplug/replug or another Windows PC may
    assign a different COM number without changing the product identity.
    """
    if serial_module is None or not hasattr(serial_module, "Serial"):
        return
    if getattr(serial_module, "_muslimsim_lifecycle_v1_serial", False):
        return
    original_serial = serial_module.Serial
    target_port = str(port).strip().upper()

    def serial_factory(*args: Any, **kwargs: Any) -> Any:
        candidate = kwargs.get("port")
        if candidate is None and args:
            candidate = args[0]
        if str(candidate or "").strip().upper() != target_port:
            return original_serial(*args, **kwargs)
        return ReconnectableSerialPort(
            original_serial,
            tuple(args),
            dict(kwargs),
            value_state=value_state,
            dash_state=dash_state,
            reset_seconds=reset_seconds,
            dash_seconds=dash_seconds,
            port_resolver=port_resolver,
        )

    serial_module.Serial = serial_factory
    serial_module._muslimsim_lifecycle_v1_serial = True
    serial_module._muslimsim_lifecycle_v1_original_serial = original_serial
    _log(f"pu_overhead: reconnectable serial factory installed for {target_port} with automatic product resolver={bool(port_resolver)}")


__all__ = [
    "configure",
    "lifecycle_snapshot",
    "wrap_status",
    "wrap_sdl_reader",
    "wrap_hid_opener",
    "install_serial_proxy",
    "ReconnectableHIDDevice",
    "ReconnectableSerialPort",
    "DEVICE_SPECS",
    "resolve_serial_port_name",
]
