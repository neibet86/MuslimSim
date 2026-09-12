"""The WinCtrl throttle's two bands: forward thrust, and below idle.

The WinCtrl URSA MINOR is an Airbus-shaped quadrant -- one continuous lever
travel with detents -- driving a Boeing 737, which has no such thing.  A 737
has a thrust lever from IDLE forward, and a separate reverse lever that only
exists once the reverser handle is lifted.  The lever's travel therefore has
to be cut in two at the IDLE detent:

    full reverse ... REV IDLE ... IDLE ......... TOGA
    |<------ below idle ------->|<--- forward thrust --->|

Above IDLE the lever is the 737 thrust lever, 0 to 1.  Below IDLE is the red
REV travel: inert until the matching reverse handle is raised, and then it
drives only the reverse lever, through the REV IDLE gate at which Zibo's
reverse first responds.

**The three raw endpoints are per-unit and must be measured.**  They were
hard-coded from a capture of one throttle, and on the very machine that
capture came from the left lever now sits at 20165 while the code assumes
19308 -- which would command about 1.9% thrust with the lever in its idle
detent.  Every throttle has to be calibrated, which is what this module and
the calibration tab exist for.

The report is read exactly as the bridge reads it, and the mapping is the
bridge's own function rather than a copy, so what the calibration shows is
what the aeroplane will do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib.util
from pathlib import Path
import sys
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

try:
    import hid
except Exception:  # pragma: no cover - matches the rest of the project
    hid = None

PROJECT = Path(__file__).resolve().parents[2]

THROTTLE_VID = 0x4098
THROTTLE_PID = 0xB930
THROTTLE_REPORT_ID = 0x01

#: Byte offsets in the throttle's HID report.  These match `decode_report`
#: in bridge/final.py; the bridge reads the same device through Windows Raw
#: Input, but the report layout is the device's, not the transport's.
BUTTONS = slice(1, 13)
LEFT_AXIS = slice(13, 15)
RIGHT_AXIS = slice(15, 17)
SPEEDBRAKE_AXIS = slice(19, 21)
FLAP_AXIS = slice(21, 23)

RAW_MAX = 65535
MIN_REPORT_LENGTH = 23

#: The physical reverse handles, as one-based button numbers.
REVERSE_BUTTON = {"left": 40, "right": 41}
IDLE_CONTACT_BUTTON = {"left": 15, "right": 21}

#: A capture is only believable if the lever really moved.
MIN_BAND_COUNTS = 1500


@dataclass
class LeverCalibration:
    """The three measured points that define one lever's two bands."""

    idle_raw: int = 20165
    rev_idle_raw: int = 14115
    max_raw: int = RAW_MAX
    full_rev_raw: int = 0

    def valid(self) -> Tuple[bool, str]:
        """Whether these points describe a usable lever."""
        if not (0 <= self.full_rev_raw < self.rev_idle_raw < self.idle_raw
                < self.max_raw <= RAW_MAX):
            return False, (
                "the points are out of order: full reverse must be below "
                "REV IDLE, which must be below IDLE, which must be below TOGA"
            )

        if self.max_raw - self.idle_raw < MIN_BAND_COUNTS:
            return False, "the forward band is too small to be a real capture"

        if self.idle_raw - self.rev_idle_raw < MIN_BAND_COUNTS // 3:
            return False, "the REV IDLE gate is too small to be a real capture"

        return True, ""

    def as_dict(self) -> dict:
        return {
            "idle_raw": int(self.idle_raw),
            "rev_idle_raw": int(self.rev_idle_raw),
            "max_raw": int(self.max_raw),
            "full_rev_raw": int(self.full_rev_raw),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "LeverCalibration":
        calibration = cls()

        if not isinstance(payload, dict):
            return calibration

        for key in ("idle_raw", "rev_idle_raw", "max_raw", "full_rev_raw"):
            try:
                setattr(calibration, key, int(payload.get(key, getattr(calibration, key))))
            except (TypeError, ValueError):
                pass

        return calibration


@dataclass
class ThrottleCalibration:
    """Both levers, and whether the 737 split is being enforced."""

    left: LeverCalibration = field(default_factory=LeverCalibration)
    right: LeverCalibration = field(default_factory=LeverCalibration)
    #: The below-idle split is mandatory for a 737; this records that it has
    #: been calibrated, not whether it is optional.
    calibrated: bool = False

    def valid(self) -> Tuple[bool, str]:
        for name, lever in (("left", self.left), ("right", self.right)):
            ok, why = lever.valid()

            if not ok:
                return False, f"{name} lever: {why}"

        return True, ""

    def as_dict(self) -> dict:
        return {
            "left": self.left.as_dict(),
            "right": self.right.as_dict(),
            "calibrated": bool(self.calibrated),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "ThrottleCalibration":
        if not isinstance(payload, dict):
            return cls()

        return cls(
            left=LeverCalibration.from_dict(payload.get("left")),
            right=LeverCalibration.from_dict(payload.get("right")),
            calibrated=bool(payload.get("calibrated", False)),
        )

    def to_arguments(self) -> list[str]:
        """The bridge flags that impose this calibration."""
        return [
            "--throttle-left-idle", str(int(self.left.idle_raw)),
            "--throttle-left-rev-idle", str(int(self.left.rev_idle_raw)),
            "--throttle-right-idle", str(int(self.right.idle_raw)),
            "--throttle-right-rev-idle", str(int(self.right.rev_idle_raw)),
        ]


# --------------------------------------------------------------------------
# The bridge's own mapping
# --------------------------------------------------------------------------

_mapping: Optional[Callable] = None
_mapping_error: Optional[str] = None
_mapping_lock = threading.Lock()


def _load_mapping() -> None:
    """Borrow `_winctrl_throttle_values` from the bridge.

    Copying the arithmetic here would let the preview and the aeroplane
    disagree the first time one was changed, which is precisely the failure
    this calibration exists to remove.
    """
    global _mapping, _mapping_error

    if _mapping is not None or _mapping_error is not None:
        return

    try:
        if str(PROJECT) not in sys.path:
            sys.path.insert(0, str(PROJECT))

        spec = importlib.util.spec_from_file_location(
            "_ms_throttle_bridge", PROJECT / "bridge" / "final.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _mapping = getattr(module, "_winctrl_throttle_values")
    except Exception as exc:
        _mapping_error = str(exc)


def outputs(
    raw: int,
    lever: LeverCalibration,
    *,
    reverse_active: bool,
    idle_contact: bool = False,
) -> Tuple[float, float]:
    """(forward thrust, reverse lever) for one raw reading, as the bridge computes it."""
    with _mapping_lock:
        _load_mapping()

    if _mapping is None:
        return 0.0, 0.0

    try:
        return _mapping(
            int(raw),
            int(lever.idle_raw),
            int(lever.rev_idle_raw),
            bool(reverse_active),
            bool(idle_contact),
        )
    except Exception:
        return 0.0, 0.0


def mapping_error() -> Optional[str]:
    with _mapping_lock:
        _load_mapping()

    return _mapping_error


# --------------------------------------------------------------------------
# Reading the hardware
# --------------------------------------------------------------------------


@dataclass
class ThrottleSample:
    left_raw: int = 0
    right_raw: int = 0
    speedbrake_raw: int = 0
    flap_raw: int = 0
    buttons: int = 0
    stamp: float = 0.0

    def raw_for(self, side: str) -> int:
        return self.left_raw if side == "left" else self.right_raw

    def reverse_active(self, side: str) -> bool:
        return self.button(REVERSE_BUTTON[side])

    def idle_contact(self, side: str) -> bool:
        return self.button(IDLE_CONTACT_BUTTON[side])

    def button(self, one_based: int) -> bool:
        return bool(self.buttons & (1 << (int(one_based) - 1)))


class ThrottleReader:
    """Reads the throttle's raw report on a background thread.

    hidapi rather than Raw Input, because the panel is not a message loop.
    The report is the device's, so both transports see the same bytes -- but
    only one process can hold the device, so the bridge must be stopped.
    """

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._sample = ThrottleSample()
        self._error: Optional[str] = None

    @property
    def error(self) -> Optional[str]:
        with self._lock:
            return self._error

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self._thread is not None:
            return

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="muslimsim-throttle", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        self._thread = None

        if thread is not None:
            thread.join(timeout=2.0)

    def sample(self) -> ThrottleSample:
        with self._lock:
            return self._sample

    def age(self) -> float:
        with self._lock:
            stamp = self._sample.stamp

        return float("inf") if stamp == 0.0 else time.monotonic() - stamp

    def _run(self) -> None:
        if hid is None:
            with self._lock:
                self._error = "hidapi is unavailable"

            return

        device = None

        while not self._stop.is_set():
            if device is None:
                try:
                    entries = list(hid.enumerate(THROTTLE_VID, THROTTLE_PID))

                    if not entries:
                        with self._lock:
                            self._error = "the throttle is not plugged in"

                        if self._stop.wait(1.0):
                            return

                        continue

                    device = hid.device()
                    device.open_path(entries[0]["path"])
                    device.set_nonblocking(1)

                    with self._lock:
                        self._error = None

                except Exception as exc:
                    device = None

                    with self._lock:
                        self._error = (
                            f"{exc}.  The bridge holds this device while it "
                            "runs; stop it before calibrating."
                        )

                    if self._stop.wait(1.5):
                        return

                    continue

            try:
                report = device.read(64)
            except Exception as exc:
                try:
                    device.close()
                except Exception:
                    pass

                device = None

                with self._lock:
                    self._error = str(exc)

                continue

            if not report:
                time.sleep(0.002)
                continue

            if report[0] != THROTTLE_REPORT_ID or len(report) < MIN_REPORT_LENGTH:
                continue

            raw = bytes(report)

            with self._lock:
                self._sample = ThrottleSample(
                    left_raw=int.from_bytes(raw[LEFT_AXIS], "little"),
                    right_raw=int.from_bytes(raw[RIGHT_AXIS], "little"),
                    speedbrake_raw=int.from_bytes(raw[SPEEDBRAKE_AXIS], "little"),
                    flap_raw=int.from_bytes(raw[FLAP_AXIS], "little"),
                    buttons=int.from_bytes(raw[BUTTONS], "little"),
                    stamp=time.monotonic(),
                )

        if device is not None:
            try:
                device.close()
            except Exception:
                pass
