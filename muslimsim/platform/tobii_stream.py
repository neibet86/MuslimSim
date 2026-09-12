"""Read gaze and head pose from a Tobii tracker, without a third party in the way.

MuslimSim talks to every panel it owns directly. The Tobii tracker is the one
piece of hardware where that is not possible: its USB channel is encrypted -
measured at a full 8.000 bits of entropy per byte on the host-to-device path in
the owner's own calibration capture - so the device will not answer anything but
Tobii's own runtime. That runtime is already installed and running as a service
here, and it publishes a documented C API, ``tobii_stream_engine``. This module
binds to that API with ``ctypes`` and nothing else: no wrapper package, no
vendored SDK, no separate process.

What is honest about the dependency: the Tobii service must be running for any
of this to work. If it is not, or the tracker is unplugged, everything here
reports unavailable and MuslimSim carries on without eye tracking. Nothing in
the rest of the project may assume a tracker exists.

The library is found through the Windows environment - ``ProgramFiles`` and its
relatives - never through a hardcoded path, because the owner's install being on
C: is a fact about this machine and not about anyone else's.

This module deliberately does *no* smoothing, no filtering and no interpretation.
It reports what the tracker said. Deciding what the owner meant by it is
:mod:`muslimsim.platform.gaze_focus`, and keeping those two apart is what lets
the hard part be tested without hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple
import ctypes
import os
import threading


# MUSLIMSIM_TOBII_STREAM_V1

_LIBRARY = "tobii_stream_engine.dll"

# Where the Tobii runtime installs itself, relative to the Windows program
# directories. Read from the environment so no drive letter is assumed.
_PROGRAM_VARIABLES = ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)")
_SUBFOLDERS = (
    "Tobii/Tobii EyeX",
    "Tobii/Tobii Eye Tracking",
    "Tobii",
)

TOBII_FIELD_OF_USE_INTERACTIVE = 1

# tobii_error_t, in declaration order. Index is the value the API returns.
_ERRORS = (
    "no error", "internal", "insufficient license", "not supported",
    "not available", "connection failed", "timed out", "allocation failed",
    "invalid parameter", "calibration already started",
    "calibration not started", "already subscribed", "not subscribed",
    "operation failed", "conflicting api instances",
    "calibration busy", "callback in progress", "too many subscribers",
    "connection failed drive", "firmware upgrade in progress",
)


class TobiiUnavailable(RuntimeError):
    """No tracker, no runtime, or the runtime refused. Never fatal to MuslimSim."""


def _error_text(code: int) -> str:
    code = int(code)
    if 0 <= code < len(_ERRORS):
        return _ERRORS[code]
    return f"error {code}"


class _GazePoint(ctypes.Structure):
    _fields_ = [
        ("timestamp_us", ctypes.c_int64),
        ("validity", ctypes.c_int),
        ("position_xy", ctypes.c_float * 2),
    ]


class _HeadPose(ctypes.Structure):
    _fields_ = [
        ("timestamp_us", ctypes.c_int64),
        ("position_validity", ctypes.c_int),
        ("position_xyz", ctypes.c_float * 3),
        ("rotation_validity", ctypes.c_int * 3),
        ("rotation_xyz", ctypes.c_float * 3),
    ]


_GAZE_CALLBACK = ctypes.CFUNCTYPE(
    None, ctypes.POINTER(_GazePoint), ctypes.c_void_p
)
_HEAD_CALLBACK = ctypes.CFUNCTYPE(
    None, ctypes.POINTER(_HeadPose), ctypes.c_void_p
)
_URL_RECEIVER = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_void_p)


@dataclass
class GazeSample:
    """One reading, exactly as the tracker gave it."""

    timestamp: float
    """Tracker clock, in seconds."""

    x: float
    y: float
    """Normalised screen position, 0..1 across the active display."""

    valid: bool
    """False during a blink or when the eyes are not found. The position is
    meaningless when this is false - it is not a position of zero."""


@dataclass
class HeadSample:
    timestamp: float
    position: Tuple[float, float, float]
    """Millimetres from the tracker."""

    rotation: Tuple[float, float, float]
    """Radians."""

    valid: bool


def find_stream_engine(explicit: Optional[str] = None) -> Optional[Path]:
    """Locate ``tobii_stream_engine.dll`` on this machine.

    Checks an explicit path, then ``MUSLIMSIM_TOBII_DLL``, then the Windows
    program directories, then whatever the loader can already resolve.
    """

    if explicit:
        candidate = Path(explicit)
        return candidate if candidate.is_file() else None

    override = os.environ.get("MUSLIMSIM_TOBII_DLL")
    if override:
        candidate = Path(override)
        if candidate.is_file():
            return candidate

    seen = set()
    for variable in _PROGRAM_VARIABLES:
        base = os.environ.get(variable)
        if not base or base in seen:
            continue
        seen.add(base)
        for folder in _SUBFOLDERS:
            candidate = Path(base) / folder / _LIBRARY
            if candidate.is_file():
                return candidate
    return None


class TobiiStream:
    """One subscription to one tracker.

    Usage is a loop: :meth:`start`, then :meth:`poll` repeatedly, then
    :meth:`stop`. ``poll`` blocks until the runtime has something to say or the
    timeout expires, so it belongs on its own thread rather than in a UI tick.
    """

    def __init__(
        self,
        *,
        dll_path: Optional[str] = None,
        on_gaze: Optional[Callable[[GazeSample], None]] = None,
        on_head: Optional[Callable[[HeadSample], None]] = None,
    ) -> None:
        self._dll_path = find_stream_engine(dll_path)
        self._lib: Optional[ctypes.CDLL] = None
        self._api = ctypes.c_void_p()
        self._device = ctypes.c_void_p()
        self._on_gaze = on_gaze
        self._on_head = on_head
        self._lock = threading.Lock()
        self._latest_gaze: Optional[GazeSample] = None
        self._latest_head: Optional[HeadSample] = None
        self._url = ""
        self._head_subscribed = False
        # ctypes callbacks must be kept alive for as long as the runtime holds
        # them. Letting these be collected is a crash inside the DLL, not an
        # exception, so they are instance attributes on purpose.
        self._gaze_thunk = _GAZE_CALLBACK(self._gaze_trampoline)
        self._head_thunk = _HEAD_CALLBACK(self._head_trampoline)

    # -- properties ----------------------------------------------------------

    @property
    def library_path(self) -> Optional[Path]:
        return self._dll_path

    @property
    def device_url(self) -> str:
        return self._url

    @property
    def head_available(self) -> bool:
        return self._head_subscribed

    def latest_gaze(self) -> Optional[GazeSample]:
        with self._lock:
            return self._latest_gaze

    def latest_head(self) -> Optional[HeadSample]:
        with self._lock:
            return self._latest_head

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        if self._dll_path is None:
            raise TobiiUnavailable(
                "tobii_stream_engine.dll was not found. The Tobii runtime does "
                "not appear to be installed; set MUSLIMSIM_TOBII_DLL to point "
                "at it if it lives somewhere unusual."
            )
        try:
            self._lib = ctypes.CDLL(str(self._dll_path))
        except OSError as exc:
            raise TobiiUnavailable(f"could not load {self._dll_path}: {exc}") from exc

        self._check(self._lib.tobii_api_create(
            ctypes.byref(self._api), None, None), "tobii_api_create")

        urls = self._enumerate()
        if not urls:
            self._teardown()
            raise TobiiUnavailable(
                "the Tobii runtime is loaded but reports no tracker. Check that "
                "the device is plugged in and the Tobii service is running."
            )
        self._url = urls[0]

        self._check(self._lib.tobii_device_create(
            self._api,
            self._url.encode("utf-8"),
            ctypes.c_int(TOBII_FIELD_OF_USE_INTERACTIVE),
            ctypes.byref(self._device),
        ), "tobii_device_create")

        self._check(self._lib.tobii_gaze_point_subscribe(
            self._device, self._gaze_thunk, None), "tobii_gaze_point_subscribe")

        # Head pose is not on every model, and its absence is not a failure.
        code = self._lib.tobii_head_pose_subscribe(
            self._device, self._head_thunk, None)
        self._head_subscribed = code == 0

    def poll(self, timeout: float = 0.10) -> None:
        """Wait for the runtime, then deliver whatever arrived.

        ``tobii_wait_for_callbacks`` returning a timeout is normal - it means
        the tracker had nothing new - so it is not treated as an error.
        """

        if self._lib is None or not self._device:
            raise TobiiUnavailable("poll() before start()")
        devices = (ctypes.c_void_p * 1)(self._device)
        code = self._lib.tobii_wait_for_callbacks(ctypes.c_int(1), devices)
        if code not in (0, 6):        # 6 == timed out
            raise TobiiUnavailable(
                f"tobii_wait_for_callbacks: {_error_text(code)}")
        self._check(self._lib.tobii_device_process_callbacks(self._device),
                    "tobii_device_process_callbacks")

    def stop(self) -> None:
        if self._lib is None:
            return
        try:
            if self._device:
                if self._head_subscribed:
                    self._lib.tobii_head_pose_unsubscribe(self._device)
                self._lib.tobii_gaze_point_unsubscribe(self._device)
        except Exception:
            # Tearing down a tracker that has already gone away is not worth
            # reporting; the caller is shutting down either way.
            pass
        self._teardown()

    def __enter__(self) -> "TobiiStream":
        self.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.stop()

    # -- internals -----------------------------------------------------------

    def _teardown(self) -> None:
        if self._lib is None:
            return
        try:
            if self._device:
                self._lib.tobii_device_destroy(self._device)
        except Exception:
            pass
        try:
            if self._api:
                self._lib.tobii_api_destroy(self._api)
        except Exception:
            pass
        self._device = ctypes.c_void_p()
        self._api = ctypes.c_void_p()
        self._head_subscribed = False

    def _check(self, code: int, what: str) -> None:
        if int(code) != 0:
            raise TobiiUnavailable(f"{what}: {_error_text(code)}")

    def _enumerate(self) -> List[str]:
        found: List[str] = []

        def receive(url, _user_data):
            if url:
                found.append(url.decode("utf-8", "replace"))

        receiver = _URL_RECEIVER(receive)
        self._check(self._lib.tobii_enumerate_local_device_urls(
            self._api, receiver, None), "tobii_enumerate_local_device_urls")
        return found

    def _gaze_trampoline(self, pointer, _user_data) -> None:
        # Runs on the runtime's thread. Keep it short and never raise into C.
        try:
            point = pointer.contents
            sample = GazeSample(
                timestamp=point.timestamp_us / 1_000_000.0,
                x=float(point.position_xy[0]),
                y=float(point.position_xy[1]),
                valid=point.validity == 1,
            )
            with self._lock:
                self._latest_gaze = sample
            if self._on_gaze is not None:
                self._on_gaze(sample)
        except Exception:
            pass

    def _head_trampoline(self, pointer, _user_data) -> None:
        try:
            pose = pointer.contents
            sample = HeadSample(
                timestamp=pose.timestamp_us / 1_000_000.0,
                position=(
                    float(pose.position_xyz[0]),
                    float(pose.position_xyz[1]),
                    float(pose.position_xyz[2]),
                ),
                rotation=(
                    float(pose.rotation_xyz[0]),
                    float(pose.rotation_xyz[1]),
                    float(pose.rotation_xyz[2]),
                ),
                valid=pose.position_validity == 1,
            )
            with self._lock:
                self._latest_head = sample
            if self._on_head is not None:
                self._on_head(sample)
        except Exception:
            pass


__all__ = (
    "GazeSample", "HeadSample", "TobiiStream", "TobiiUnavailable",
    "find_stream_engine",
)
