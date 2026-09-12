"""Live axis and button reading, for calibration inside the application.

Calibrating a pedal set by reading numbers off a console is not calibration;
you need to see the bar move while your foot moves.  This is the part that
makes that possible: a background reader that keeps the latest position of
every axis on every attached controller, cheap enough to poll at 60 Hz from
a UI timer.

SDL is used rather than raw HID because it is what the bridge itself uses for
these devices, so the numbers shown here are the same numbers the bridge
acts on.  Calibrating against a different source would be worse than useless
-- it would look right and behave wrong.

Only one process can own an SDL joystick at a time, so the bridge must not be
holding the device while it is being calibrated.  The caller is responsible
for stopping it first; `SDL_CONTENTION_NOTE` is the message to show.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

SDL_CONTENTION_NOTE = (
    "The bridge holds these controllers while it runs.  Stop it, or stop "
    "this device, before calibrating."
)

#: Axes below this movement are treated as noise when auto-detecting which
#: axis a control belongs to.
MOVEMENT_THRESHOLD = 0.15

POLL_INTERVAL = 1.0 / 90.0


@dataclass
class ControllerInfo:
    index: int
    name: str
    guid: str
    axes: int
    buttons: int
    hats: int


@dataclass
class AxisCalibration:
    """What a raw SDL axis reading means for one physical control.

    SDL reports -1.0 to +1.0, but a real pedal rarely reaches either end, and
    a throttle detent sits wherever the hardware puts it.  These four numbers
    turn the raw value into a usable 0..1 travel.
    """

    minimum: float = -1.0
    maximum: float = 1.0
    centre: Optional[float] = None
    deadzone: float = 0.02
    invert: bool = False

    def normalise(self, raw: float) -> float:
        """Raw SDL value to 0..1 travel, honouring this calibration."""
        low, high = self.minimum, self.maximum

        if high - low < 1e-6:
            return 0.0

        value = (float(raw) - low) / (high - low)
        value = max(0.0, min(1.0, value))

        if self.invert:
            value = 1.0 - value

        return value

    def centred(self, raw: float) -> float:
        """Raw value to -1..+1 about the captured centre, for a rudder."""
        centre = self.centre if self.centre is not None else (
            (self.minimum + self.maximum) / 2.0
        )
        value = float(raw)

        if abs(value - centre) <= self.deadzone:
            return 0.0

        if value >= centre:
            span = max(1e-6, self.maximum - centre)
            result = (value - centre) / span
        else:
            span = max(1e-6, centre - self.minimum)
            result = (value - centre) / span

        result = max(-1.0, min(1.0, result))

        return -result if self.invert else result

    def as_dict(self) -> dict:
        return {
            "minimum": self.minimum,
            "maximum": self.maximum,
            "centre": self.centre,
            "deadzone": self.deadzone,
            "invert": self.invert,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "AxisCalibration":
        calibration = cls()

        if not isinstance(payload, dict):
            return calibration

        for key in ("minimum", "maximum", "deadzone"):
            try:
                setattr(calibration, key, float(payload.get(key, getattr(calibration, key))))
            except (TypeError, ValueError):
                pass

        centre = payload.get("centre")

        try:
            calibration.centre = None if centre is None else float(centre)
        except (TypeError, ValueError):
            calibration.centre = None

        calibration.invert = bool(payload.get("invert", False))
        return calibration


@dataclass
class _Snapshot:
    axes: Dict[int, List[float]] = field(default_factory=dict)
    buttons: Dict[int, List[bool]] = field(default_factory=dict)
    stamp: float = 0.0


class AxisReader:
    """Keeps the live position of every axis on every attached controller.

    Runs SDL on its own thread with the dummy video driver, so it never opens
    a window and never competes with Tk for the main loop.
    """

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._snapshot = _Snapshot()
        self._controllers: List[ControllerInfo] = []
        self._error: Optional[str] = None
        self._started = threading.Event()

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            return

        self._stop.clear()
        self._started.clear()
        self._thread = threading.Thread(
            target=self._run, name="muslimsim-axes", daemon=True
        )
        self._thread.start()
        # Give SDL a moment so the first UI paint has controllers to show.
        self._started.wait(3.0)

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None

        if thread is not None:
            thread.join(timeout=3.0)

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def error(self) -> Optional[str]:
        with self._lock:
            return self._error

    # -- reading -----------------------------------------------------------

    def controllers(self) -> List[ControllerInfo]:
        with self._lock:
            return list(self._controllers)

    def find(self, name_fragment: str) -> Optional[ControllerInfo]:
        """The first controller whose name contains this fragment."""
        needle = name_fragment.lower()

        for controller in self.controllers():
            if needle in controller.name.lower():
                return controller

        return None

    def axis(self, controller_index: int, axis_index: int) -> float:
        with self._lock:
            values = self._snapshot.axes.get(controller_index)

        if not values or axis_index >= len(values):
            return 0.0

        return values[axis_index]

    def axes(self, controller_index: int) -> List[float]:
        with self._lock:
            return list(self._snapshot.axes.get(controller_index, ()))

    def buttons(self, controller_index: int) -> List[bool]:
        with self._lock:
            return list(self._snapshot.buttons.get(controller_index, ()))

    def age(self) -> float:
        """Seconds since the last successful sample; large means stalled."""
        with self._lock:
            stamp = self._snapshot.stamp

        return float("inf") if stamp == 0.0 else time.monotonic() - stamp

    # -- the reader thread -------------------------------------------------

    def _run(self) -> None:
        # No window, ever: this runs beside a Tk main loop.
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")

        try:
            import pygame
        except Exception as exc:
            with self._lock:
                self._error = f"pygame is unavailable: {exc}"

            self._started.set()
            return

        try:
            pygame.init()
            pygame.joystick.init()
        except Exception as exc:
            with self._lock:
                self._error = f"SDL would not start: {exc}"

            self._started.set()
            return

        sticks = []

        try:
            found: List[ControllerInfo] = []

            for index in range(pygame.joystick.get_count()):
                try:
                    stick = pygame.joystick.Joystick(index)
                    stick.init()
                except Exception:
                    continue

                sticks.append(stick)
                found.append(
                    ControllerInfo(
                        index=index,
                        name=stick.get_name(),
                        guid=getattr(stick, "get_guid", lambda: "")(),
                        axes=stick.get_numaxes(),
                        buttons=stick.get_numbuttons(),
                        hats=stick.get_numhats(),
                    )
                )

            with self._lock:
                self._controllers = found
                self._error = None if found else "No controllers were found."

            self._started.set()

            while not self._stop.is_set():
                pygame.event.pump()

                axes: Dict[int, List[float]] = {}
                buttons: Dict[int, List[bool]] = {}

                for position, stick in enumerate(sticks):
                    try:
                        axes[position] = [
                            stick.get_axis(a) for a in range(stick.get_numaxes())
                        ]
                        buttons[position] = [
                            bool(stick.get_button(b))
                            for b in range(stick.get_numbuttons())
                        ]
                    except Exception:
                        continue

                with self._lock:
                    self._snapshot = _Snapshot(axes, buttons, time.monotonic())

                time.sleep(POLL_INTERVAL)

        except Exception as exc:
            with self._lock:
                self._error = str(exc)

            self._started.set()

        finally:
            for stick in sticks:
                try:
                    stick.quit()
                except Exception:
                    pass

            try:
                pygame.joystick.quit()
                pygame.quit()
            except Exception:
                pass


class MovementWatcher:
    """Finds which axis a control belongs to by watching it move.

    Asking the user to work out that the left toe brake is axis 1 is asking
    them to do the machine's job.  This records where every axis started and
    reports whichever moved furthest, which is the axis they just pressed.
    """

    def __init__(self, reader: AxisReader, controller_index: int) -> None:
        self.reader = reader
        self.controller_index = controller_index
        self.baseline = reader.axes(controller_index)
        self.extremes: List[Tuple[float, float]] = [
            (value, value) for value in self.baseline
        ]

    def sample(self) -> None:
        values = self.reader.axes(self.controller_index)

        for index, value in enumerate(values):
            if index >= len(self.extremes):
                self.extremes.append((value, value))
                continue

            low, high = self.extremes[index]
            self.extremes[index] = (min(low, value), max(high, value))

    def travel(self) -> List[float]:
        return [high - low for low, high in self.extremes]

    def best(self) -> Optional[int]:
        """The axis that moved most, if anything moved enough to be sure."""
        travel = self.travel()

        if not travel:
            return None

        widest = max(travel)

        if widest < MOVEMENT_THRESHOLD:
            return None

        return travel.index(widest)

    def calibration_for(self, axis_index: int) -> Optional[AxisCalibration]:
        if axis_index >= len(self.extremes):
            return None

        low, high = self.extremes[axis_index]

        if high - low < MOVEMENT_THRESHOLD:
            return None

        return AxisCalibration(minimum=low, maximum=high)
