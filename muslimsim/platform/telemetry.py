from __future__ import annotations

import collections
import math
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Deque, Iterable, Mapping


@dataclass(frozen=True)
class TelemetrySample:
    sequence: int
    device_key: str
    control_key: str
    value: Any
    phase: str
    source: str
    timestamp: float
    kind: str = ""
    raw_signature: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TelemetryJournal:
    """Thread-safe, bounded latest-value journal.

    Continuous controls are coalesced to their newest value.  Button/selector
    edges also enter a bounded edge queue, so a quick press/release cannot be
    lost while Studio is drawing.  Profile and database work never runs here.
    """

    EDGE_PHASES = frozenset({"press", "release", "pulse", "baseline", "connect", "disconnect"})

    def __init__(self, *, max_edges: int = 4096, max_history: int = 8192) -> None:
        self._lock = threading.RLock()
        self._changed = threading.Condition(self._lock)
        self._sequence = 0
        self._latest: dict[str, dict[str, TelemetrySample]] = {}
        self._edges: Deque[TelemetrySample] = collections.deque(maxlen=max(64, int(max_edges)))
        self._history: Deque[TelemetrySample] = collections.deque(maxlen=max(256, int(max_history)))
        self._dropped_edges = 0

    @staticmethod
    def _equivalent(left: Any, right: Any) -> bool:
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            try:
                return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-9)
            except (TypeError, ValueError):
                return False
        return left == right

    def publish(
        self,
        device_key: str,
        control_key: str,
        value: Any,
        *,
        phase: str = "change",
        source: str = "physical",
        timestamp: float | None = None,
        kind: str = "",
        raw_signature: str = "",
        force: bool = False,
    ) -> TelemetrySample:
        device_key = str(device_key)
        control_key = str(control_key)
        phase = str(phase or "change")
        source = str(source or "physical")
        when = float(timestamp if timestamp is not None else time.time())

        with self._changed:
            previous = self._latest.get(device_key, {}).get(control_key)
            if (
                not force
                and previous is not None
                and phase == "change"
                and previous.phase == "change"
                and self._equivalent(previous.value, value)
            ):
                return previous

            self._sequence += 1
            sample = TelemetrySample(
                sequence=self._sequence,
                device_key=device_key,
                control_key=control_key,
                value=value,
                phase=phase,
                source=source,
                timestamp=when,
                kind=str(kind or ""),
                raw_signature=str(raw_signature or ""),
            )
            self._latest.setdefault(device_key, {})[control_key] = sample
            self._history.append(sample)
            if phase in self.EDGE_PHASES or kind in {"button", "selector", "rotary", "hat"}:
                if len(self._edges) == self._edges.maxlen:
                    self._dropped_edges += 1
                self._edges.append(sample)
            self._changed.notify_all()
            return sample

    @property
    def sequence(self) -> int:
        with self._lock:
            return self._sequence

    def wait_for_change(self, cursor: int, timeout: float = 0.75) -> int:
        deadline = time.monotonic() + max(0.0, min(float(timeout), 30.0))
        with self._changed:
            while self._sequence <= int(cursor):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._changed.wait(remaining)
            return self._sequence

    def poll(self, cursor: int = 0, *, timeout: float = 0.75, max_events: int = 512) -> dict[str, Any]:
        cursor = max(0, int(cursor))
        self.wait_for_change(cursor, timeout)
        with self._lock:
            latest = {
                device: {
                    control: sample.to_dict()
                    for control, sample in controls.items()
                    if sample.sequence > cursor
                }
                for device, controls in self._latest.items()
            }
            latest = {device: controls for device, controls in latest.items() if controls}
            events = [sample.to_dict() for sample in self._history if sample.sequence > cursor]
            if len(events) > max_events:
                events = events[-max_events:]
            return {
                "schema": 1,
                "cursor": self._sequence,
                "from": cursor,
                "latest": latest,
                "events": events,
                "dropped_edges": self._dropped_edges,
                "control_count": sum(len(items) for items in self._latest.values()),
                "device_count": len(self._latest),
            }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema": 1,
                "cursor": self._sequence,
                "latest": {
                    device: {control: sample.to_dict() for control, sample in controls.items()}
                    for device, controls in self._latest.items()
                },
                "edges": [sample.to_dict() for sample in self._edges],
                "dropped_edges": self._dropped_edges,
                "control_count": sum(len(items) for items in self._latest.values()),
                "device_count": len(self._latest),
            }

    def legacy_inputs(self) -> dict[str, dict[str, dict[str, Any]]]:
        """HardwareLab-compatible current input shape for the existing Studio."""
        with self._lock:
            return {
                device: {
                    control: {
                        "value": sample.value,
                        "phase": sample.phase,
                        "source": sample.source,
                        "updated": sample.timestamp,
                        "sequence": sample.sequence,
                    }
                    for control, sample in controls.items()
                }
                for device, controls in self._latest.items()
            }

    def clear_device(self, device_key: str) -> None:
        with self._changed:
            self._latest.pop(str(device_key), None)
            self._sequence += 1
            self._changed.notify_all()
