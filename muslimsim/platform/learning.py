from __future__ import annotations

import math
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from .contracts import InputEvent, ValidationError


@dataclass
class Candidate:
    device_key: str
    control_key: str
    score: float = 0.0
    samples: int = 0
    first_value: Any = None
    last_value: Any = None
    first_at: float = 0.0
    last_at: float = 0.0
    phases: set[str] = field(default_factory=set)
    raw_signature: str = ""
    kind: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["phases"] = sorted(self.phases)
        return data


@dataclass
class LearnSession:
    session_id: str
    started_at: float
    expires_at: float
    device_key: str = ""
    expected_kind: str = "any"
    replace_control: str = ""
    baseline: dict[tuple[str, str], Any] = field(default_factory=dict)
    candidates: dict[tuple[str, str], Candidate] = field(default_factory=dict)
    status: str = "listening"
    selected: tuple[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        ranked = sorted(self.candidates.values(), key=lambda item: (-item.score, -item.last_at, item.control_key))
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "expires_at": self.expires_at,
            "device_key": self.device_key,
            "expected_kind": self.expected_kind,
            "replace_control": self.replace_control,
            "status": self.status,
            "selected": list(self.selected) if self.selected else None,
            "candidates": [item.to_dict() for item in ranked[:20]],
        }


class LearningEngine:
    """Learn/relearn engine driven by the same physical telemetry stream."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._session: LearnSession | None = None

    def start(
        self,
        *,
        device_key: str = "",
        expected_kind: str = "any",
        timeout: float = 15.0,
        replace_control: str = "",
        baseline: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> LearnSession:
        now = time.time()
        session = LearnSession(
            session_id=str(uuid.uuid4()),
            started_at=now,
            expires_at=now + max(3.0, min(float(timeout), 120.0)),
            device_key=str(device_key or ""),
            expected_kind=str(expected_kind or "any"),
            replace_control=str(replace_control or ""),
        )
        for device, controls in dict(baseline or {}).items():
            for control, state in dict(controls or {}).items():
                value = state.get("value") if isinstance(state, Mapping) else state
                session.baseline[(str(device), str(control))] = value
        with self._lock:
            self._session = session
        return session

    def cancel(self) -> None:
        with self._lock:
            if self._session is not None:
                self._session.status = "cancelled"
            self._session = None

    @staticmethod
    def _numeric_delta(left: Any, right: Any) -> float:
        try:
            return abs(float(left) - float(right))
        except (TypeError, ValueError):
            return 0.0 if left == right else 1.0

    def observe(self, event: InputEvent) -> None:
        now = event.timestamp or time.time()
        with self._lock:
            session = self._session
            if session is None or session.status != "listening":
                return
            if now >= session.expires_at:
                session.status = "expired"
                return
            if session.device_key and event.device_key != session.device_key:
                return
            if event.phase == "baseline" or event.source in {"baseline", "practice-auto-retract"}:
                return

            key = (event.device_key, event.control_key)
            candidate = session.candidates.get(key)
            if candidate is None:
                candidate = Candidate(
                    device_key=event.device_key,
                    control_key=event.control_key,
                    first_value=event.value,
                    last_value=event.value,
                    first_at=now,
                    last_at=now,
                    raw_signature=event.raw_signature,
                    kind=event.kind,
                )
                session.candidates[key] = candidate
            candidate.samples += 1
            candidate.phases.add(str(event.phase))
            candidate.last_value = event.value
            candidate.last_at = now
            if event.raw_signature:
                candidate.raw_signature = event.raw_signature
            if event.kind:
                candidate.kind = event.kind

            expected = session.expected_kind
            phase = str(event.phase).lower()
            baseline_value = session.baseline.get(key, candidate.first_value)
            delta = self._numeric_delta(event.value, baseline_value)

            # Discrete edges are intentionally decisive: one clean press should
            # beat ambient axis noise. A press/release pair receives another
            # boost because it proves the source is a real momentary contact.
            if phase == "press":
                candidate.score += 12.0
            elif phase == "release":
                candidate.score += 5.0 if "press" in candidate.phases else 1.0
            elif phase == "pulse":
                candidate.score += 10.0
            elif event.kind in {"selector", "hat", "rotary"}:
                candidate.score += 7.0 + min(delta, 10.0)
            else:
                # Axes must move materially from the session baseline. Repeated
                # tiny jitter is capped and cannot win a learning session.
                candidate.score += min(8.0, max(0.0, delta) * 20.0)

            if expected != "any" and event.kind and event.kind != expected:
                candidate.score *= 0.4

            ranked = sorted(session.candidates.values(), key=lambda item: (-item.score, -item.last_at))
            if ranked:
                winner = ranked[0]
                runner = ranked[1] if len(ranked) > 1 else None
                decisive = winner.score >= 12.0 and (runner is None or winner.score >= runner.score + 4.0)
                if decisive:
                    session.selected = (winner.device_key, winner.control_key)

    def status(self) -> dict[str, Any]:
        with self._lock:
            if self._session is None:
                return {"status": "idle"}
            if self._session.status == "listening" and time.time() >= self._session.expires_at:
                self._session.status = "expired"
            return self._session.to_dict()

    def selected(self) -> Candidate:
        with self._lock:
            session = self._session
            if session is None:
                raise ValidationError("No active learning session")
            if session.selected is None:
                ranked = sorted(session.candidates.values(), key=lambda item: (-item.score, -item.last_at))
                if not ranked or ranked[0].score < 3.0:
                    raise ValidationError("No physical control has been identified yet")
                if len(ranked) > 1 and math.isclose(ranked[0].score, ranked[1].score, abs_tol=2.0):
                    raise ValidationError("More than one control moved; repeat learning and move only one control")
                session.selected = (ranked[0].device_key, ranked[0].control_key)
            session.status = "selected"
            return session.candidates[session.selected]

    def complete(self) -> Candidate:
        candidate = self.selected()
        with self._lock:
            if self._session is not None:
                self._session.status = "completed"
                self._session = None
        return candidate
