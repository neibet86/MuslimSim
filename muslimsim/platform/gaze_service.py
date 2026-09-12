"""Run the gaze stabiliser as something Studio can switch on and off.

:mod:`muslimsim.platform.gaze_focus` decides *when* the owner is focusing on
something. :mod:`muslimsim.platform.tobii_stream` reads the tracker. This joins
the two and does something with the answer: it puts the pointer where the owner
is looking, once, and then holds it absolutely still for as long as they keep
looking there.

**The pointer is warped, not driven.** A pointer that follows gaze continuously
is unusable for precision work - it is the shakiness this exists to remove, just
smoothed. Instead nothing happens at all until a fixation is established, then
the pointer is placed once at the anchor, and then it does not move again until
the owner looks somewhere else. One write per fixation, not thirty a second.

**The physical mouse always wins.** Before every warp the real cursor position
is compared with the last position written here. If they differ, the owner has
moved the mouse, and the stabiliser stands back for a grace period rather than
fighting for the cursor. That is also the escape hatch: moving the mouse always
takes control back, without reaching for the toggle.

**It knows when a knob is being turned.** Studio calls
:meth:`note_control_activity` whenever the bridge reports new physical input,
which widens and holds the focus lock. Somebody a third of the way through
turning a knob is not trying to look away.

The tracker runs on its own thread. It never touches Tk, and Studio never waits
on it - the toggle starts and stops a thread, and reads a small status snapshot
whenever it feels like it.

Nothing here is required. With no tracker, no runtime, or the service switched
off, MuslimSim behaves exactly as it did before.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple
import ctypes
import math
import threading
import time

from .gaze_focus import FocusSettings, FocusState, GazeFocus
from .tobii_stream import TobiiStream, TobiiUnavailable, find_stream_engine


# MUSLIMSIM_GAZE_SERVICE_V1


@dataclass(frozen=True)
class PointerSettings:
    """How the stabilised point reaches the cursor."""

    mouse_tolerance: float = 3.0
    """Pixels. If the cursor is further than this from where this service last
    put it, the owner moved the mouse."""

    mouse_grace: float = 1.2
    """Seconds to keep out of the way after the owner touches the mouse."""

    minimum_step: float = 2.0
    """Do not rewrite the cursor for a move smaller than this. With the anchor
    frozen this is what turns a fixation into a single warp instead of a stream
    of identical writes - and the silence between writes is what makes the
    physical-mouse check possible at all."""


class NullPointer:
    """Somewhere for the point to go when there is no desktop. Used by tests."""

    def __init__(self, size: Tuple[int, int] = (1920, 1080)) -> None:
        self._size = size
        self._position = (0, 0)
        self.writes: list = []

    def size(self) -> Tuple[int, int]:
        return self._size

    def position(self) -> Optional[Tuple[int, int]]:
        return self._position

    def move(self, x: int, y: int) -> None:
        self._position = (int(x), int(y))
        self.writes.append(self._position)


class WindowsPointer:
    """The real cursor.

    Screen size and cursor position are both read through ``user32``, and the
    cursor is written through it too, so all three share whatever coordinate
    space Windows has given this process. That is deliberate: a DPI-scaled
    desktop reports a smaller screen *and* accepts the matching smaller
    coordinates, so as long as nothing mixes the two spaces there is no scaling
    to correct for.
    """

    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32

    def size(self) -> Tuple[int, int]:
        return (
            int(self._user32.GetSystemMetrics(0)),
            int(self._user32.GetSystemMetrics(1)),
        )

    def position(self) -> Optional[Tuple[int, int]]:
        point = ctypes.wintypes.POINT() if hasattr(ctypes, "wintypes") else None
        if point is None:
            class _Point(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
            point = _Point()
        if not self._user32.GetCursorPos(ctypes.byref(point)):
            return None
        return (int(point.x), int(point.y))

    def move(self, x: int, y: int) -> None:
        self._user32.SetCursorPos(int(x), int(y))


class GazeFocusService:
    """The switchable feature: tracker in, steady pointer out."""

    def __init__(
        self,
        *,
        settings: Optional[FocusSettings] = None,
        pointer_settings: Optional[PointerSettings] = None,
        pointer: Any = None,
        stream_factory: Optional[Callable[..., Any]] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings or FocusSettings()
        self.pointer_settings = pointer_settings or PointerSettings()
        self._pointer = pointer
        self._stream_factory = stream_factory or TobiiStream
        self._clock = clock

        self._lock = threading.RLock()
        self._focus = GazeFocus(self.settings)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._stream = None
        self._running = False
        self._error = ""
        self._detail = ""

        self._written: Optional[Tuple[int, int]] = None
        self._yield_until = 0.0
        self._samples = 0
        self._invalid = 0
        self._warps = 0
        self._state: Optional[FocusState] = None
        # The focus detector runs on the tracker's own clock - device uptime,
        # not this process's monotonic clock - because that is what stamps the
        # samples. Anything that reaches into it has to speak the same clock or
        # the comparison is meaningless, so control activity is timestamped
        # against the newest sample rather than against time.monotonic().
        self._sample_clock: Optional[float] = None

    # -- can this run at all -------------------------------------------------

    def availability(self) -> Tuple[bool, str]:
        """Whether the feature can be switched on, and why not when it cannot.

        Only the cheap check: is the runtime installed. Whether a tracker is
        actually plugged in is not known until the subscription is attempted,
        and asking costs a connection, so that answer arrives from
        :meth:`start` instead.
        """

        library = find_stream_engine()
        if library is None:
            return False, "Tobii runtime not installed"
        return True, str(library)

    # -- lifecycle -----------------------------------------------------------

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def start(self) -> None:
        """Open the tracker and begin. Raises TobiiUnavailable if it cannot."""

        with self._lock:
            if self._running:
                return
            self._focus = GazeFocus(self.settings)
            self._written = None
            self._yield_until = 0.0
            self._samples = self._invalid = self._warps = 0
            self._error = ""
            self._state = None

        stream = self._stream_factory(on_gaze=self._on_gaze)
        # Started on this thread on purpose: a tracker that is not there must
        # fail in front of the owner who just clicked the toggle, not quietly
        # on a worker thread a moment later.
        stream.start()

        with self._lock:
            self._stream = stream
            self._running = True
            self._detail = getattr(stream, "device_url", "") or ""
            self._stop = threading.Event()
            self._thread = threading.Thread(
                target=self._pump, name="muslimsim-gaze", daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            thread = self._thread
            stream = self._stream
            self._running = False
            self._thread = None
            self._stream = None
        self._stop.set()
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.5)
        if stream is not None:
            try:
                stream.stop()
            except Exception as exc:
                with self._lock:
                    self._error = f"{type(exc).__name__}: {exc}"

    def _pump(self) -> None:
        stream = self._stream
        while not self._stop.is_set():
            try:
                stream.poll(0.10)
            except Exception as exc:
                with self._lock:
                    self._error = f"{type(exc).__name__}: {exc}"
                    self._running = False
                return

    # -- inputs from the rest of Studio --------------------------------------

    def note_control_activity(self) -> None:
        """A physical control was just used; hold the focus lock open."""

        with self._lock:
            when = self._sample_clock
        if when is None:
            # Nothing has arrived from the tracker yet, so there is no lock to
            # hold and no clock to hold it against.
            return
        self._focus.hold(when)

    # -- the gaze path -------------------------------------------------------

    def _on_gaze(self, sample) -> None:
        # Runs on the Tobii runtime's thread.
        with self._lock:
            self._samples += 1
            self._sample_clock = sample.timestamp
            if not sample.valid:
                self._invalid += 1
        state = self._focus.update(
            sample.timestamp, sample.x, sample.y, valid=sample.valid,
        )
        with self._lock:
            self._state = state
        self._apply(state)

    def _apply(self, state: FocusState) -> None:
        pointer = self._resolve_pointer()
        if pointer is None:
            return
        options = self.pointer_settings
        now = self._clock()

        written = self._written
        if written is not None:
            actual = pointer.position()
            if actual is not None:
                strayed = math.hypot(actual[0] - written[0], actual[1] - written[1])
                if strayed > options.mouse_tolerance:
                    # The owner has the mouse. Stand back rather than fight for
                    # the cursor - and this is also how they take it back.
                    self._written = None
                    self._yield_until = now + options.mouse_grace
                    return

        if now < self._yield_until or not state.focused:
            return

        width, height = pointer.size()
        target = (
            int(round(min(max(state.point[0], 0.0), 1.0) * (width - 1))),
            int(round(min(max(state.point[1], 0.0), 1.0) * (height - 1))),
        )
        if self._written is not None:
            moved = math.hypot(
                target[0] - self._written[0], target[1] - self._written[1]
            )
            if moved < options.minimum_step:
                return
        pointer.move(target[0], target[1])
        self._written = target
        with self._lock:
            self._warps += 1

    def _resolve_pointer(self):
        if self._pointer is not None:
            return self._pointer
        try:
            self._pointer = WindowsPointer()
        except Exception as exc:
            with self._lock:
                self._error = f"no pointer: {type(exc).__name__}: {exc}"
            return None
        return self._pointer

    # -- what Studio shows ---------------------------------------------------

    def status(self) -> Dict[str, Any]:
        with self._lock:
            state = self._state
            samples = self._samples
            invalid = self._invalid
            return {
                "running": self._running,
                "detail": self._detail,
                "error": self._error,
                "samples": samples,
                "valid_ratio": (samples - invalid) / samples if samples else 0.0,
                "warps": self._warps,
                "state": state.state if state is not None else "",
                "focused": bool(state.focused) if state is not None else False,
                "view_gain": state.view_gain if state is not None else 1.0,
            }

    def summary(self) -> str:
        """One short line for the toggle, stable enough not to flicker.

        Deliberately carries no counter and no live number: text that changes
        every tick in the corner of the window is exactly what the owner asked
        to be rid of. This changes when the state changes, and not otherwise.
        """

        status = self.status()
        if status["error"]:
            return f"Eye focus - {status['error']}"
        if not status["running"]:
            return "Eye focus"
        if status["samples"] == 0:
            return "Eye focus - waiting for the tracker"
        if status["valid_ratio"] < 0.05:
            return "Eye focus - no eyes found"
        return "Eye focus - on"


__all__ = (
    "GazeFocusService", "NullPointer", "PointerSettings", "WindowsPointer",
)
