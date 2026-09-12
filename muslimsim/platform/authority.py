from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from .contracts import RuntimeMode


class RouteDecision(str, Enum):
    OBSERVE_ONLY = "observe_only"
    PRACTICE_ONLY = "practice_only"
    LIVE_ROUTE = "live_route"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class AuthoritySnapshot:
    mode: str
    simulator_connected: bool
    aircraft_loaded: bool
    aircraft_powered: bool
    live_routes_enabled: bool
    practice_outputs_enabled: bool
    generation: int
    changed_at: float
    reason: str


class AuthorityCoordinator:
    """Single source of truth for Live/Practice and output power authority."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._mode = RuntimeMode.LIVE
        self._simulator_connected = False
        self._aircraft_loaded = False
        self._aircraft_powered = False
        self._generation = 0
        self._changed_at = time.time()
        self._reason = "startup-observation-only"

    def _bump(self, reason: str) -> None:
        self._generation += 1
        self._changed_at = time.time()
        self._reason = reason

    def set_mode(self, mode: RuntimeMode | str, *, reason: str = "user") -> AuthoritySnapshot:
        value = mode if isinstance(mode, RuntimeMode) else RuntimeMode(str(mode).lower().replace("test", "practice"))
        with self._lock:
            if value != self._mode:
                self._mode = value
                self._bump(f"mode:{value.value}:{reason}")
            return self.snapshot()

    def update_runtime(
        self,
        *,
        simulator_connected: bool | None = None,
        aircraft_loaded: bool | None = None,
        aircraft_powered: bool | None = None,
        reason: str = "runtime",
    ) -> AuthoritySnapshot:
        with self._lock:
            changed = False
            for attr, value in (
                ("_simulator_connected", simulator_connected),
                ("_aircraft_loaded", aircraft_loaded),
                ("_aircraft_powered", aircraft_powered),
            ):
                if value is not None and bool(value) != getattr(self, attr):
                    setattr(self, attr, bool(value))
                    changed = True
            if changed:
                self._bump(reason)
            return self.snapshot()

    def input_decision(self, *, device_enabled: bool = True, has_live_binding: bool = True) -> RouteDecision:
        with self._lock:
            if not device_enabled:
                return RouteDecision.BLOCKED
            if self._mode == RuntimeMode.PRACTICE:
                return RouteDecision.PRACTICE_ONLY
            if not has_live_binding:
                return RouteDecision.OBSERVE_ONLY
            if self._simulator_connected and self._aircraft_loaded:
                return RouteDecision.LIVE_ROUTE
            return RouteDecision.OBSERVE_ONLY

    def output_allowed(self, *, practice_capable: bool = True) -> bool:
        with self._lock:
            ready = self._simulator_connected and self._aircraft_loaded and self._aircraft_powered
            if self._mode == RuntimeMode.PRACTICE:
                return ready and practice_capable
            return ready

    def snapshot(self) -> AuthoritySnapshot:
        with self._lock:
            live = bool(
                self._mode == RuntimeMode.LIVE
                and self._simulator_connected
                and self._aircraft_loaded
            )
            practice = bool(
                self._mode == RuntimeMode.PRACTICE
                and self._simulator_connected
                and self._aircraft_loaded
                and self._aircraft_powered
            )
            return AuthoritySnapshot(
                mode=self._mode.value,
                simulator_connected=self._simulator_connected,
                aircraft_loaded=self._aircraft_loaded,
                aircraft_powered=self._aircraft_powered,
                live_routes_enabled=live,
                practice_outputs_enabled=practice,
                generation=self._generation,
                changed_at=self._changed_at,
                reason=self._reason,
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.snapshot())
