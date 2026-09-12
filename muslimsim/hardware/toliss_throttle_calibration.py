"""Validated, profile-scoped WinCtrl calibration for ToLiss A320/A321.

The WinCtrl quadrant exposes one contact at every Airbus thrust gate.  The
probe therefore records an axis value only while the matching contact is
closed; it never tries to infer a detent from a noisy motion plateau.  This
module owns no SDL/HID handle and is safe to share between the bridge, Studio,
profile validation, and offline tests.
"""

from __future__ import annotations

from copy import deepcopy
import threading
import time
from typing import Any, Dict, Mapping, Optional, Tuple


AIRCRAFT_FAMILY = "toliss-a320-a321"
PROFILE_NAME = "toliss-a320-a321-winctrl-v2"
SCHEMA_VERSION = 2
RAW_AXIS_MAX = 65535
MIN_GATE_SPACING = 100
SETTLE_SECONDS = 0.30
SETTLE_RAW_TOLERANCE = 40

DETENT_ORDER: Tuple[str, ...] = (
    "full_reverse",
    "reverse_idle",
    "idle",
    "climb",
    "flex_mct",
    "toga",
)

DETENT_LABELS = {
    "full_reverse": "FULL REV",
    "reverse_idle": "REV IDLE",
    "idle": "IDLE",
    "climb": "CL",
    "flex_mct": "FLEX/MCT",
    "toga": "TOGA",
}

# AirbusFBW/throttle_input is ToLiss's *final, signed cockpit-lever* input,
# not the raw 0..1 joystick axis configured by the ISCS detent sliders.  The
# installed A321 cockpit object places REV IDLE at -0.10, IDLE at 0.00 and CL
# at 0.70; its own FMOD gate conditions accept CL at 0.68..0.72 and FLEX/MCT
# at 0.86..0.90. The live cockpit's exact FLEX/MCT lever value is 0.875.
# Keeping these aircraft-side
# targets separate from the measured WinCtrl raw gates is the essential
# two-sided calibration contract:
#
#     measured physical gate -> canonical ToLiss direct-lever position
#
# Version 2 of the persisted raw-gate schema means every value was captured
# after the contact and axis remained settled, rather than at the contact's
# leading edge. The JSON shape is deliberately unchanged.
DIRECT_INPUT_TARGETS = {
    "full_reverse": -1.0,
    "reverse_idle": -0.10,
    "idle": 0.0,
    "climb": 0.70,
    "flex_mct": 0.875,
    "toga": 1.0,
}

# Button numbers are one-based, matching pygame/SDL's packed button bitmap in
# bridge/final.py.  Each side advances independently, so the owner may sweep
# both levers together or calibrate one lever at a time.
DETENT_BUTTONS = {
    "left": {
        "full_reverse": 17,
        "reverse_idle": 16,
        "idle": 15,
        "climb": 14,
        "flex_mct": 13,
        "toga": 12,
    },
    "right": {
        "full_reverse": 23,
        "reverse_idle": 22,
        "idle": 21,
        "climb": 20,
        "flex_mct": 19,
        "toga": 18,
    },
}

DEFAULT_RAW_GATES = {
    "left": {
        "full_reverse": 0,
        "reverse_idle": 14115,
        "idle": 20165,
        "climb": 45371,
        "flex_mct": 55453,
        "toga": 65535,
    },
    "right": {
        "full_reverse": 0,
        "reverse_idle": 14115,
        "idle": 20165,
        "climb": 45371,
        "flex_mct": 55453,
        "toga": 65535,
    },
}


def _button_pressed(button_bits: int, one_based_button: int) -> bool:
    return bool(int(button_bits) & (1 << (int(one_based_button) - 1)))


def default_calibration() -> Dict[str, Any]:
    """Return a fresh canonical fallback calibration."""

    return {
        "aircraft_family": AIRCRAFT_FAMILY,
        "version": SCHEMA_VERSION,
        "left": dict(DEFAULT_RAW_GATES["left"]),
        "right": dict(DEFAULT_RAW_GATES["right"]),
    }


def normalise_calibration(settings: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate and canonicalise one saved ToLiss six-gate calibration."""

    if not isinstance(settings, Mapping):
        raise ValueError("ToLiss throttle calibration must be an object")
    permitted = {"aircraft_family", "version", "left", "right"}
    unknown = set(settings) - permitted
    if unknown:
        raise ValueError(
            "Unsupported ToLiss throttle calibration fields: "
            + ", ".join(sorted(str(item) for item in unknown))
        )
    if str(settings.get("aircraft_family") or "") != AIRCRAFT_FAMILY:
        raise ValueError("This calibration is only for the ToLiss A320/A321 family")
    try:
        version = int(settings.get("version"))
    except (TypeError, ValueError):
        version = -1
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported ToLiss throttle calibration version {version}"
        )

    result: Dict[str, Any] = {
        "aircraft_family": AIRCRAFT_FAMILY,
        "version": SCHEMA_VERSION,
    }
    for side in ("left", "right"):
        raw_side = settings.get(side)
        if not isinstance(raw_side, Mapping):
            raise ValueError(f"ToLiss throttle calibration is missing {side} gates")
        unknown_gates = set(raw_side) - set(DETENT_ORDER)
        missing_gates = set(DETENT_ORDER) - set(raw_side)
        if unknown_gates:
            raise ValueError(
                f"Unsupported {side} throttle gates: "
                + ", ".join(sorted(str(item) for item in unknown_gates))
            )
        if missing_gates:
            raise ValueError(
                f"Missing {side} throttle gates: "
                + ", ".join(DETENT_LABELS[item] for item in DETENT_ORDER if item in missing_gates)
            )

        gates: Dict[str, int] = {}
        for gate in DETENT_ORDER:
            value = raw_side.get(gate)
            if isinstance(value, bool):
                raise ValueError(f"{side} {DETENT_LABELS[gate]} raw value must be a number")
            try:
                raw_value = int(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{side} {DETENT_LABELS[gate]} raw value must be a number"
                ) from exc
            if not 0 <= raw_value <= RAW_AXIS_MAX:
                raise ValueError(
                    f"{side} {DETENT_LABELS[gate]} must be between 0 and {RAW_AXIS_MAX}"
                )
            gates[gate] = raw_value

        for lower, upper in zip(DETENT_ORDER, DETENT_ORDER[1:]):
            if gates[upper] - gates[lower] < MIN_GATE_SPACING:
                raise ValueError(
                    f"{side} gates must increase from FULL REV to TOGA "
                    f"with at least {MIN_GATE_SPACING} raw counts between gates"
                )
        result[side] = gates
    return result


def calibration_to_raw_anchors(
    settings: Mapping[str, Any],
) -> Dict[str, Tuple[Tuple[str, int, int], ...]]:
    """Convert persisted left/right gates into bridge interpolation anchors."""

    calibration = normalise_calibration(settings)
    return {
        "engine1": tuple(
            (gate, int(calibration["left"][gate]), DETENT_BUTTONS["left"][gate])
            for gate in DETENT_ORDER
        ),
        "engine2": tuple(
            (gate, int(calibration["right"][gate]), DETENT_BUTTONS["right"][gate])
            for gate in DETENT_ORDER
        ),
    }


class TolissThrottleDetentProbe:
    """Capture six contact-held, settled raw gates for each physical lever."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._generation = 0
        self._active = False
        self._completed = False
        self._saved = False
        self._error = ""
        self._captured: Dict[str, Dict[str, int]] = {"left": {}, "right": {}}
        self._next_index = {"left": 0, "right": 0}
        self._settling: Dict[str, Optional[Dict[str, Any]]] = {
            "left": None,
            "right": None,
        }
        self._completion_pending: Optional[Dict[str, Any]] = None

    def start(self) -> Dict[str, Any]:
        with self._lock:
            self._generation += 1
            self._active = True
            self._completed = False
            self._saved = False
            self._error = ""
            self._captured = {"left": {}, "right": {}}
            self._next_index = {"left": 0, "right": 0}
            self._settling = {"left": None, "right": None}
            self._completion_pending = None
            return self._snapshot_locked()

    def cancel(self) -> Dict[str, Any]:
        with self._lock:
            self._active = False
            self._completed = False
            self._saved = False
            self._settling = {"left": None, "right": None}
            self._completion_pending = None
            self._error = ""
            return self._snapshot_locked()

    def is_active(self) -> bool:
        """Cheap fixed-rate check; unlike snapshot(), it copies no state."""

        with self._lock:
            return self._active

    def observe(
        self, left_raw: int, right_raw: int, button_bits: int,
        *, now: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Observe one snapshot and save a gate only after it settles."""

        with self._lock:
            if not self._active:
                return self._snapshot_locked()
            observed_at = time.monotonic() if now is None else float(now)
            raw_values = {
                "left": max(0, min(RAW_AXIS_MAX, int(left_raw))),
                "right": max(0, min(RAW_AXIS_MAX, int(right_raw))),
            }
            errors = []
            for side in ("left", "right"):
                index = self._next_index[side]
                if index >= len(DETENT_ORDER):
                    continue
                gate = DETENT_ORDER[index]
                button = DETENT_BUTTONS[side][gate]
                if not _button_pressed(button_bits, button):
                    # The complete dwell must occur inside one continuous
                    # contact closure. Passing through a gate cannot leave a
                    # stale candidate that later completes by itself.
                    self._settling[side] = None
                    continue
                raw_value = raw_values[side]
                settling = self._settling[side]
                if settling is None or settling.get("gate") != gate:
                    self._settling[side] = {
                        "gate": gate,
                        "raw": raw_value,
                        "last_motion": observed_at,
                    }
                    continue

                previous_raw = int(settling["raw"])
                settling["raw"] = raw_value
                if abs(raw_value - previous_raw) >= SETTLE_RAW_TOLERANCE:
                    settling["last_motion"] = observed_at
                if observed_at - float(settling["last_motion"]) < SETTLE_SECONDS:
                    continue

                if index:
                    previous_gate = DETENT_ORDER[index - 1]
                    previous_raw = self._captured[side][previous_gate]
                    if raw_value - previous_raw < MIN_GATE_SPACING:
                        errors.append(
                            f"{side.upper()} {DETENT_LABELS[gate]} was too close to "
                            f"{DETENT_LABELS[previous_gate]}; move away and settle in "
                            f"{DETENT_LABELS[gate]} again"
                        )
                        continue
                self._captured[side][gate] = raw_value
                self._next_index[side] = index + 1
                self._settling[side] = None
            self._error = " • ".join(errors)

            if all(
                self._next_index[side] == len(DETENT_ORDER)
                for side in ("left", "right")
            ):
                candidate = {
                    "aircraft_family": AIRCRAFT_FAMILY,
                    "version": SCHEMA_VERSION,
                    "left": dict(self._captured["left"]),
                    "right": dict(self._captured["right"]),
                }
                self._completion_pending = normalise_calibration(candidate)
                self._active = False
                self._completed = True
                self._settling = {"left": None, "right": None}
            return self._snapshot_locked(observed_at)

    def consume_completed(self) -> Optional[Dict[str, Any]]:
        """Return a completed calibration once so one SDL event causes one save."""

        with self._lock:
            if self._completion_pending is None:
                return None
            result = deepcopy(self._completion_pending)
            self._completion_pending = None
            return result

    def mark_saved(self) -> Dict[str, Any]:
        with self._lock:
            if self._completed:
                self._saved = True
            return self._snapshot_locked()

    def mark_save_error(self, error: Any) -> Dict[str, Any]:
        with self._lock:
            self._saved = False
            self._error = str(error)
            return self._snapshot_locked()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self, now: Optional[float] = None) -> Dict[str, Any]:
        observed_at = time.monotonic() if now is None else float(now)
        next_gates: Dict[str, Optional[str]] = {}
        for side in ("left", "right"):
            index = self._next_index[side]
            next_gates[side] = (
                DETENT_ORDER[index] if index < len(DETENT_ORDER) else None
            )
        settling: Dict[str, Optional[Dict[str, Any]]] = {}
        for side in ("left", "right"):
            candidate = self._settling[side]
            if candidate is None:
                settling[side] = None
                continue
            settling[side] = {
                "gate": str(candidate["gate"]),
                "raw": int(candidate["raw"]),
                "remaining_ms": max(
                    0,
                    int(round(1000.0 * (
                        SETTLE_SECONDS
                        - (observed_at - float(candidate["last_motion"]))
                    ))),
                ),
            }
        return {
            "generation": self._generation,
            "active": self._active,
            "completed": self._completed,
            "saved": self._saved,
            "error": self._error,
            "captured": deepcopy(self._captured),
            "next": next_gates,
            "settling": settling,
            "progress": {
                side: self._next_index[side] for side in ("left", "right")
            },
            "total": len(DETENT_ORDER),
        }
