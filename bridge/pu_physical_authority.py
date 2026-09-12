#!/usr/bin/env python3
"""MuslimSim PU maintained-control authority monitor V2.3 COMMAND EDGE.

Read-only observer. It never opens PU hardware and never writes X-Plane.
All simulator corrections are queued back to bridge/final.py.

V2.3 COMMAND EDGE changes:
- subscribes to Zibo command activation edges and rejects a conflicting virtual click immediately
- predicts the post-command detent so the existing main-thread restore handler can counter-step at once
- keeps the DataRef authority stream as the truth/fallback, but no longer reconnects merely because the cockpit is quiet
- retains V2.2 early-detent departure detection for DataRef-only maintained controls
- logs command-edge timing with millisecond timestamps
- keeps APU START, momentaries, encoder pulses and engine-start selectors excluded
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import threading
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple

try:
    import websocket
except ImportError:
    websocket = None


PU_AUTHORITY_WS_TIMEOUT = 0.025
PU_AUTHORITY_RECONNECT_SECONDS = 0.20
PU_AUTHORITY_RESTORE_COOLDOWN = 0.10
PU_AUTHORITY_BATTERY_COOLDOWN = 0.10
PU_AUTHORITY_PHYSICAL_GRACE = 0.12
PU_AUTHORITY_HTTP_TIMEOUT = 0.14
PU_AUTHORITY_FALLBACK_BATCH = 6
PU_AUTHORITY_FALLBACK_INTERVAL = 0.030
PU_AUTHORITY_COMMAND_EDGE_COOLDOWN = 0.050
# Animated maintained switches must be rejected as soon as they LEAVE the
# physical detent.  V2.1 normalized at 0.5, which let a slow Zibo switch
# travel halfway across before authority reacted.  Eight percent tolerates
# tiny animation/float noise while still catching the first visible movement.
PU_AUTHORITY_BOOLEAN_DEPARTURE = 0.08
PU_AUTHORITY_DISCRETE_TOLERANCE = 0.08

# key -> ((dataref_name, optional_array_index), ...)
OPTIONAL_FEEDBACK_CANDIDATES: Dict[str, Tuple[Tuple[str, Optional[int]], ...]] = {
    "battery_on": (
        ("laminar/B738/electric/battery_pos", None),
        ("sim/cockpit2/electrical/battery_on", 0),
    ),
    "light_56": (
        ("laminar/B738/switch/land_lights_left_pos", None),
        ("sim/cockpit2/switches/landing_lights_switch", 0),
    ),
    "light_57": (
        ("laminar/B738/switch/land_lights_right_pos", None),
        ("sim/cockpit2/switches/landing_lights_switch", 3),
    ),
    "light_58": (
        ("laminar/B738/toggle_switch/rwy_light_left", None),
        ("sim/cockpit2/switches/generic_lights_switch", 2),
    ),
    "light_59": (
        ("laminar/B738/toggle_switch/rwy_light_right", None),
        ("sim/cockpit2/switches/generic_lights_switch", 3),
    ),
    "light_60": (
        ("laminar/B738/toggle_switch/taxi_light_brightness_pos", None),
        ("sim/cockpit2/switches/generic_lights_switch", 4),
    ),
    "light_73": (
        ("laminar/B738/toggle_switch/logo_light", None),
        ("sim/cockpit2/switches/generic_lights_switch", 1),
    ),
    "light_76": (
        ("sim/cockpit2/switches/beacon_on", None),
        ("sim/cockpit/electrical/beacon_lights_on", None),
    ),
    "light_77": (
        ("sim/cockpit2/switches/generic_lights_switch", 0),
    ),
}

BOOLEAN_KEYS = {
    "battery_on",
    "light_56", "light_57", "light_58", "light_59",
    "light_60", "light_73", "light_76", "light_77",
}

# Command-edge guards.  Each tuple is (command name, mode, effect):
#   absolute -> effect is the resulting maintained state
#   delta    -> effect is one detent of movement
#   toggle   -> effect is ignored; the predicted state is inverted
#
# These are only OBSERVED.  The helper never activates a command itself; it
# queues the same pu_authority_restore event that final.py already handles.
COMMAND_EDGE_CANDIDATES: Dict[str, Tuple[Tuple[str, str, float], ...]] = {
    "battery_on": (
        ("laminar/B738/switch/battery_dn", "absolute", 1.0),
        ("laminar/B738/push_button/batt_full_off", "absolute", 0.0),
        # LevelUp compatibility: harmless on Zibo because it resolves only if present.
        ("laminar/B738/switch/battery_up", "absolute", 0.0),
    ),
    "light_56": (
        ("laminar/B738/switch/land_lights_left_on", "absolute", 1.0),
        ("laminar/B738/switch/land_lights_left_off", "absolute", 0.0),
        ("laminar/B738/switch/land_lights_ret_left_dn", "absolute", 1.0),
        ("laminar/B738/switch/land_lights_ret_left_up", "absolute", 0.0),
    ),
    "light_57": (
        ("laminar/B738/switch/land_lights_right_on", "absolute", 1.0),
        ("laminar/B738/switch/land_lights_right_off", "absolute", 0.0),
        ("laminar/B738/switch/land_lights_ret_right_dn", "absolute", 1.0),
        ("laminar/B738/switch/land_lights_ret_right_up", "absolute", 0.0),
    ),
    "light_58": (
        ("laminar/B738/switch/rwy_light_left_on", "absolute", 1.0),
        ("laminar/B738/switch/rwy_light_left_off", "absolute", 0.0),
    ),
    "light_59": (
        ("laminar/B738/switch/rwy_light_right_on", "absolute", 1.0),
        ("laminar/B738/switch/rwy_light_right_off", "absolute", 0.0),
    ),
    "light_60": (
        ("laminar/B738/toggle_switch/taxi_light_brightness_on", "absolute", 1.0),
        ("laminar/B738/toggle_switch/taxi_light_brightness_off", "absolute", 0.0),
        ("laminar/B738/toggle_switch/taxi_light_brightness_pos_dn", "absolute", 1.0),
        ("laminar/B738/toggle_switch/taxi_light_brightness_pos_up", "absolute", 0.0),
    ),
    "light_73": (
        ("laminar/B738/switch/logo_light_on", "absolute", 1.0),
        ("laminar/B738/switch/logo_light_off", "absolute", 0.0),
    ),
    "light_76": (
        ("sim/lights/beacon_lights_on", "absolute", 1.0),
        ("sim/lights/beacon_lights_off", "absolute", 0.0),
    ),
    "light_77": (
        ("laminar/B738/switch/wing_light_on", "absolute", 1.0),
        ("laminar/B738/switch/wing_light_off", "absolute", 0.0),
    ),
    "irs_left": (
        ("laminar/B738/toggle_switch/irs_L_left", "delta", -1.0),
        ("laminar/B738/toggle_switch/irs_L_right", "delta", 1.0),
    ),
    "irs_right": (
        ("laminar/B738/toggle_switch/irs_R_left", "delta", -1.0),
        ("laminar/B738/toggle_switch/irs_R_right", "delta", 1.0),
    ),
    "wiper_left": (
        ("laminar/B738/knob/left_wiper_up", "delta", 1.0),
        ("laminar/B738/knob/left_wiper_dn", "delta", -1.0),
    ),
    "wiper_right": (
        ("laminar/B738/knob/right_wiper_up", "delta", 1.0),
        ("laminar/B738/knob/right_wiper_dn", "delta", -1.0),
    ),
    "position_light": (
        ("laminar/B738/toggle_switch/position_light_up", "delta", 1.0),
        ("laminar/B738/toggle_switch/position_light_down", "delta", -1.0),
    ),
    # Existing bridge semantics prove DOWN increases seatbelt_sign_pos and UP decreases it.
    "seatbelt_sign": (
        ("laminar/B738/toggle_switch/seatbelt_sign_dn", "delta", 1.0),
        ("laminar/B738/toggle_switch/seatbelt_sign_up", "delta", -1.0),
    ),
    "l_pack": (
        ("laminar/B738/toggle_switch/l_pack_dn", "delta", 1.0),
        ("laminar/B738/toggle_switch/l_pack_up", "delta", -1.0),
    ),
    "isolation_valve": (
        ("laminar/B738/toggle_switch/iso_valve_dn", "delta", 1.0),
        ("laminar/B738/toggle_switch/iso_valve_up", "delta", -1.0),
    ),
    "r_pack": (
        ("laminar/B738/toggle_switch/r_pack_dn", "delta", 1.0),
        ("laminar/B738/toggle_switch/r_pack_up", "delta", -1.0),
    ),
    "bleed_air_1": (("laminar/B738/toggle_switch/bleed_air_1", "toggle", 0.0),),
    "bleed_air_apu": (("laminar/B738/toggle_switch/bleed_air_apu", "toggle", 0.0),),
    "bleed_air_2": (("laminar/B738/toggle_switch/bleed_air_2", "toggle", 0.0),),
    "eng_start_source": (
        ("laminar/B738/toggle_switch/eng_start_source_right", "delta", 1.0),
        ("laminar/B738/toggle_switch/eng_start_source_left", "delta", -1.0),
    ),
}

COMMAND_EDGE_RANGES: Dict[str, Tuple[float, float]] = {
    "irs_left": (0.0, 3.0), "irs_right": (0.0, 3.0),
    "wiper_left": (0.0, 3.0), "wiper_right": (0.0, 3.0),
    "position_light": (-1.0, 1.0),
    "seatbelt_sign": (0.0, 2.0),
    "l_pack": (0.0, 2.0), "isolation_valve": (0.0, 2.0), "r_pack": (0.0, 2.0),
    "eng_start_source": (-1.0, 1.0),
}

NEVER_REPLAY_KEYS = {
    "apu_start",
    "pu_eng1_start", "pu_eng2_start",
    "engine1_start", "engine2_start",
}


def _default_log_path() -> Path:
    try:
        root = Path(__file__).resolve().parent.parent
    except Exception:
        root = Path.cwd()
    return root / "logs" / "pu_authority_runtime.log"


def _append_log(message: str) -> None:
    try:
        path = _default_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        wall = time.time()
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(wall))
        millis = int((wall - int(wall)) * 1000.0)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp}.{millis:03d} | {message}\n")
    except Exception:
        pass


def _numeric(value: Any, index: Optional[int]) -> float:
    candidate = value
    if isinstance(candidate, dict):
        for key in ("value", "data"):
            if key in candidate:
                candidate = candidate[key]
                break

    if isinstance(candidate, list):
        if index is None:
            if not candidate:
                return math.nan
            candidate = candidate[0]
        else:
            if index < 0 or index >= len(candidate):
                return math.nan
            candidate = candidate[index]
            if isinstance(candidate, dict):
                for key in ("value", "data"):
                    if key in candidate:
                        candidate = candidate[key]
                        break

    try:
        number = float(candidate)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def _mismatch(key: str, actual: float, target: float) -> bool:
    """Return True as soon as virtual state leaves the physical detent.

    Two-position Zibo switch feedback can animate continuously between 0 and 1.
    Treating it as a boolean at 0.5 delays authority until half the animation is
    complete.  Instead, when hardware says ON, any drop below 0.92 is already an
    attempted takeover; when hardware says OFF, any rise above 0.08 is one.
    """
    actual = float(actual)
    target = float(target)
    if key in BOOLEAN_KEYS:
        if target >= 0.5:
            return actual < (1.0 - PU_AUTHORITY_BOOLEAN_DEPARTURE)
        return actual > PU_AUTHORITY_BOOLEAN_DEPARTURE
    if key == "panel_brightness":
        return abs(actual - target) > 0.0125
    return abs(actual - target) > PU_AUTHORITY_DISCRETE_TOLERANCE


def _distance(key: str, actual: float, target: float) -> float:
    if key in BOOLEAN_KEYS:
        return abs((1.0 if actual >= 0.5 else 0.0) - (1.0 if target >= 0.5 else 0.0))
    return abs(float(actual) - float(target))


class PUPhysicalAuthorityMonitor:
    """Monitor virtual switch state and request restoration to physical targets."""

    def __init__(
        self,
        *,
        api_version: str,
        api_root: str,
        dataref_names: Mapping[str, str],
        resolve_dataref_id: Callable[[str, str], int],
        event_q: Any,
        stop_evt: threading.Event,
        brightness_index: int = 0,
        diagnose: bool = False,
    ) -> None:
        self.api_version = str(api_version)
        self.api_root = str(api_root).rstrip("/")
        self.dataref_names = dict(dataref_names)
        self.resolve_dataref_id = resolve_dataref_id
        self.event_q = event_q
        self.stop_evt = stop_evt
        self.brightness_index = int(brightness_index)
        self.diagnose = bool(diagnose)

        self._lock = threading.Lock()
        self._targets: Dict[str, float] = {}
        self._actual: Dict[str, float] = {}
        self._fresh_ids: Dict[str, int] = {}
        self._resolved: Dict[str, Tuple[int, Optional[int], str]] = {}
        self._target_changed_at: Dict[str, float] = {}
        self._last_restore_at: Dict[str, float] = {}
        self._armed = False
        self._generation = 0
        self._subscription_generation = -1
        self._last_message_at = 0.0
        self._fallback_cursor = 0
        self._req_id = 9380
        self._thread = threading.Thread(
            target=self._worker,
            name="MuslimSim-PU-Physical-Authority",
            daemon=True,
        )
        self._log(
            f"V2.3 COMMAND EDGE monitor constructed api={self.api_version} root={self.api_root} "
            f"websocket={'yes' if websocket is not None else 'no'}"
        )

    def _log(self, message: str) -> None:
        _append_log(message)
        if self.diagnose:
            print(f"PU AUTHORITY V2.3: {message}")

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()
            self._log("worker thread started")

    def arm(self) -> None:
        with self._lock:
            self._armed = True
            for key in self._targets:
                self._target_changed_at[key] = 0.0
            cached = list(self._actual.items())
            target_count = len(self._targets)
        self._log(f"ARMED COMMAND EDGE with {target_count} maintained targets; detent departure={PU_AUTHORITY_BOOLEAN_DEPARTURE:.2f}")
        for key, actual in cached:
            self._maybe_emit(key, actual, force=True)

    def disarm(self) -> None:
        with self._lock:
            self._armed = False
        self._log("disarmed")

    def replace_targets(self, values: Mapping[str, Any]) -> None:
        clean: Dict[str, float] = {}
        for raw_key, raw_value in dict(values or {}).items():
            key = str(raw_key)
            if key in NEVER_REPLAY_KEYS:
                continue
            if not self._supported_key(key):
                continue
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(value):
                clean[key] = value

        with self._lock:
            self._targets = clean
            now = time.monotonic()
            self._target_changed_at = {key: now for key in clean}
            self._last_restore_at.clear()
            self._generation += 1
        self._log(
            "target baseline received: "
            + ", ".join(f"{k}={v:g}" for k, v in sorted(clean.items()))
        )

    def set_target(self, key: str, value: Any, *, immediate: bool = False) -> None:
        key = str(key)
        if key in NEVER_REPLAY_KEYS or not self._supported_key(key):
            return
        try:
            number = float(value)
        except (TypeError, ValueError):
            return
        if not math.isfinite(number):
            return

        with self._lock:
            is_new = key not in self._targets
            previous = self._targets.get(key)
            self._targets[key] = number
            self._target_changed_at[key] = 0.0 if immediate else time.monotonic()
            if is_new:
                self._generation += 1
            actual = self._actual.get(key)
        if previous is None or abs(float(previous) - number) > 1e-6:
            self._log(f"physical target {key}: {previous!r} -> {number:g}")
        if actual is not None:
            self._maybe_emit(key, actual, force=immediate)

    def targets_snapshot(self) -> Dict[str, float]:
        with self._lock:
            return dict(self._targets)

    def _supported_key(self, key: str) -> bool:
        if key in OPTIONAL_FEEDBACK_CANDIDATES:
            return True
        return key in self.dataref_names

    def _candidate_specs(self, key: str) -> Tuple[Tuple[str, Optional[int]], ...]:
        if key in OPTIONAL_FEEDBACK_CANDIDATES:
            return OPTIONAL_FEEDBACK_CANDIDATES[key]
        name = self.dataref_names.get(key)
        if not name:
            return ()
        index = self.brightness_index if key == "panel_brightness" else None
        return ((str(name), index),)

    def _resolve_target_refs(
        self, keys: Iterable[str]
    ) -> Tuple[list, Dict[str, list], Dict[str, Tuple[int, Optional[int], str]]]:
        subscriptions = []
        handlers: Dict[str, list] = {}
        resolved: Dict[str, Tuple[int, Optional[int], str]] = {}

        for key in keys:
            found = None
            last_error: Optional[BaseException] = None
            for name, index in self._candidate_specs(key):
                try:
                    ref_id = int(self.resolve_dataref_id(self.api_version, str(name)))
                    found = (ref_id, index, str(name))
                    break
                except Exception as exc:
                    last_error = exc
            if found is None:
                self._log(
                    f"feedback unavailable {key}: {last_error or 'no candidate dataref'}"
                )
                continue
            ref_id, index, name = found
            descriptor = {"id": int(ref_id)}
            if index is not None:
                descriptor["index"] = int(index)
            if descriptor not in subscriptions:
                subscriptions.append(descriptor)
            handlers.setdefault(str(int(ref_id)), []).append((key, index))
            resolved[key] = (int(ref_id), index, name)

        return subscriptions, handlers, resolved

    def _resolve_command_id(self, name: str) -> int:
        query = urllib.parse.urlencode({"filter[name]": str(name), "limit": 20})
        req = urllib.request.Request(
            f"{self.api_root}/api/{self.api_version}/commands?{query}",
            headers={"Accept": "application/json", "User-Agent": "MuslimSim-PU-Authority-V2.3-CommandEdge"},
        )
        with urllib.request.urlopen(req, timeout=PU_AUTHORITY_HTTP_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
        items = payload.get("data", []) if isinstance(payload, dict) else []
        if isinstance(items, dict):
            items = [items]
        for item in items:
            if isinstance(item, dict) and item.get("name") == name:
                return int(item["id"])
        raise RuntimeError(f"Command not found: {name}")

    def _resolve_command_refs(
        self, keys: Iterable[str]
    ) -> Tuple[list, Dict[str, list]]:
        subscriptions = []
        handlers: Dict[str, list] = {}
        seen_names = set()
        resolved_count = 0
        for key in keys:
            for name, mode, effect in COMMAND_EDGE_CANDIDATES.get(key, ()):
                if name in seen_names:
                    continue
                seen_names.add(name)
                try:
                    command_id = self._resolve_command_id(name)
                except Exception:
                    # Optional/aircraft-specific command spelling.  Absence is
                    # normal; DataRef authority remains available for this key.
                    continue
                descriptor = {"id": int(command_id)}
                if descriptor not in subscriptions:
                    subscriptions.append(descriptor)
                handlers.setdefault(str(int(command_id)), []).append(
                    (key, str(mode), float(effect), str(name))
                )
                resolved_count += 1
        self._log(
            f"command-edge refs resolved {len(subscriptions)} command IDs / "
            f"{resolved_count} guarded actions"
        )
        return subscriptions, handlers

    def _next_req_id(self) -> int:
        with self._lock:
            self._req_id += 1
            return self._req_id

    def _predict_command_actual(
        self, key: str, mode: str, effect: float, actual: float
    ) -> float:
        if mode == "absolute":
            return float(effect)
        if mode == "toggle":
            return 0.0 if float(actual) >= 0.5 else 1.0
        if mode == "delta":
            base = float(round(actual))
            predicted = base + float(effect)
            low, high = COMMAND_EDGE_RANGES.get(key, (-1.0e9, 1.0e9))
            return max(float(low), min(float(high), predicted))
        return float(actual)

    def _handle_command_active(
        self,
        raw_command_id: str,
        active: Any,
        handlers: Mapping[str, list],
    ) -> None:
        # The command update contains both press and release.  Only the active
        # edge represents an attempted cockpit movement.
        if not bool(active):
            return
        command_id = str(raw_command_id).strip()
        for key, mode, effect, name in handlers.get(command_id, ()):
            now = time.monotonic()
            with self._lock:
                if not self._armed:
                    continue
                target = self._targets.get(key)
                fresh_id = self._fresh_ids.get(key)
                if target is None or fresh_id is None:
                    continue
                actual = self._actual.get(key, target)
                if not math.isfinite(float(actual)):
                    actual = target
                predicted = self._predict_command_actual(
                    key, mode, effect, float(actual)
                )
                # Update the logical state immediately.  This is important:
                # when final.py sends the corrective command a few milliseconds
                # later, its command edge is then predicted TOWARD the physical
                # target and will not be mistaken for a second takeover.
                self._actual[key] = float(predicted)
                current_distance = _distance(key, float(actual), float(target))
                predicted_distance = _distance(key, float(predicted), float(target))
                if mode == "absolute":
                    should_restore = _mismatch(key, float(predicted), float(target))
                else:
                    should_restore = (
                        _mismatch(key, float(predicted), float(target))
                        and predicted_distance > current_distance + 0.01
                    )
                last_restore = self._last_restore_at.get(key, 0.0)
                if (
                    should_restore
                    and (now - last_restore) >= PU_AUTHORITY_COMMAND_EDGE_COOLDOWN
                ):
                    self._last_restore_at[key] = now
                    queue_restore = True
                else:
                    queue_restore = False

            if queue_restore:
                self._log(
                    f"COMMAND EDGE {key}: {name} predicts virtual={predicted:g} "
                    f"physical={target:g}; immediate restore queued"
                )
                self.event_q.put(
                    (
                        "pu_authority_restore",
                        key,
                        float(target),
                        float(predicted),
                        int(fresh_id),
                    )
                )
            elif self.diagnose:
                self._log(
                    f"command allowed {key}: {name} actual={actual:g} "
                    f"predicted={predicted:g} physical={target:g}"
                )

    def _ws_url(self) -> str:
        root = self.api_root
        if root.startswith("https://"):
            root = "wss://" + root[len("https://") :]
        elif root.startswith("http://"):
            root = "ws://" + root[len("http://") :]
        elif not root.startswith(("ws://", "wss://")):
            root = "ws://" + root
        return f"{root}/api/{self.api_version}"

    def _http_value(self, ref_id: int, index: Optional[int]) -> float:
        url = f"{self.api_root}/api/{self.api_version}/datarefs/{int(ref_id)}/value"
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "MuslimSim-PU-Authority-V2.3-CommandEdge"},
        )
        with urllib.request.urlopen(req, timeout=PU_AUTHORITY_HTTP_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
        data = payload.get("data") if isinstance(payload, dict) else payload
        return _numeric(data, index)

    def _record_actual(self, key: str, actual: float, *, force: bool = False) -> None:
        if not math.isfinite(actual):
            return
        with self._lock:
            self._actual[key] = actual
        self._maybe_emit(key, actual, force=force)

    def _prime_actuals(self, resolved: Mapping[str, Tuple[int, Optional[int], str]]) -> int:
        good = 0
        for key, (ref_id, index, _name) in resolved.items():
            if self.stop_evt.is_set():
                break
            try:
                actual = self._http_value(ref_id, index)
            except Exception as exc:
                self._log(f"initial feedback read failed {key}: {exc}")
                continue
            if math.isfinite(actual):
                good += 1
                self._record_actual(key, actual, force=True)
        self._log(f"initial REST state primed {good}/{len(resolved)} targets")
        return good

    def _fallback_poll_once(
        self, resolved: Mapping[str, Tuple[int, Optional[int], str]]
    ) -> None:
        items = list(sorted(resolved.items()))
        if not items:
            self.stop_evt.wait(PU_AUTHORITY_FALLBACK_INTERVAL)
            return
        start = self._fallback_cursor % len(items)
        count = min(PU_AUTHORITY_FALLBACK_BATCH, len(items))
        for offset in range(count):
            key, (ref_id, index, _name) = items[(start + offset) % len(items)]
            try:
                actual = self._http_value(ref_id, index)
            except Exception:
                continue
            if math.isfinite(actual):
                self._record_actual(key, actual)
        self._fallback_cursor = (start + count) % len(items)
        self.stop_evt.wait(PU_AUTHORITY_FALLBACK_INTERVAL)

    def _maybe_emit(self, key: str, actual: float, *, force: bool = False) -> None:
        now = time.monotonic()
        with self._lock:
            if not self._armed:
                return
            target = self._targets.get(key)
            fresh_id = self._fresh_ids.get(key)
            changed_at = self._target_changed_at.get(key, 0.0)
            last_restore = self._last_restore_at.get(key, 0.0)
            if target is None or fresh_id is None:
                return
            if not _mismatch(key, actual, target):
                return
            if (
                not force
                and changed_at > 0.0
                and (now - changed_at) < PU_AUTHORITY_PHYSICAL_GRACE
            ):
                return
            cooldown = (
                PU_AUTHORITY_BATTERY_COOLDOWN
                if key == "battery_on"
                else PU_AUTHORITY_RESTORE_COOLDOWN
            )
            if not force and (now - last_restore) < cooldown:
                return
            self._last_restore_at[key] = now

        self._log(
            f"MISMATCH {key}: virtual={actual:g} physical={target:g}; restore queued"
        )
        self.event_q.put(
            ("pu_authority_restore", key, float(target), float(actual), int(fresh_id))
        )

    def _worker(self) -> None:
        while not self.stop_evt.is_set():
            with self._lock:
                target_keys = tuple(sorted(self._targets))
                generation = self._generation
            if not target_keys:
                self.stop_evt.wait(0.05)
                continue

            try:
                subscriptions, handlers, resolved = self._resolve_target_refs(target_keys)
                if not resolved:
                    self._log("no maintained feedback refs resolved; retrying")
                    self.stop_evt.wait(PU_AUTHORITY_RECONNECT_SECONDS)
                    continue

                with self._lock:
                    self._fresh_ids = {key: spec[0] for key, spec in resolved.items()}
                    self._resolved = dict(resolved)
                    self._subscription_generation = generation
                self._log(f"feedback refs resolved {len(resolved)}/{len(target_keys)}")
                self._prime_actuals(resolved)

                # Resolve command IDs independently from final.py.  Missing
                # command spellings are optional; the normal DataRef watcher
                # remains in force for every resolved maintained control.
                command_subscriptions, command_handlers = self._resolve_command_refs(target_keys)

                if websocket is None:
                    self._log("websocket-client unavailable; bounded REST fallback active")
                    while not self.stop_evt.is_set():
                        with self._lock:
                            if self._generation != generation:
                                break
                        self._fallback_poll_once(resolved)
                    continue

                ws = None
                try:
                    ws = websocket.create_connection(
                        self._ws_url(), timeout=1.0, enable_multithread=True
                    )
                    ws.settimeout(PU_AUTHORITY_WS_TIMEOUT)
                    dataref_req = self._next_req_id()
                    ws.send(json.dumps({
                        "req_id": dataref_req,
                        "type": "dataref_subscribe_values",
                        "params": {"datarefs": subscriptions},
                    }, separators=(",", ":")))
                    command_req = None
                    if command_subscriptions:
                        command_req = self._next_req_id()
                        ws.send(json.dumps({
                            "req_id": command_req,
                            "type": "command_subscribe_is_active",
                            "params": {"commands": command_subscriptions},
                        }, separators=(",", ":")))
                    self._last_message_at = time.monotonic()
                    self._log(
                        f"WebSocket armed: {len(resolved)} DataRefs + "
                        f"{len(command_subscriptions)} command edges"
                    )

                    while not self.stop_evt.is_set():
                        with self._lock:
                            if self._generation != generation:
                                break
                        try:
                            raw = ws.recv()
                        except websocket.WebSocketTimeoutException:
                            # A quiet cockpit is healthy. X-Plane sends changed
                            # values; inactivity is NOT a reason to reconnect.
                            continue
                        if not raw:
                            continue
                        self._last_message_at = time.monotonic()
                        message = json.loads(raw)
                        msg_type = message.get("type")

                        if msg_type == "result":
                            req_id = message.get("req_id")
                            if req_id in {dataref_req, command_req}:
                                if message.get("success") is False:
                                    self._log(
                                        f"subscription failed req={req_id}: "
                                        f"{message.get('error_code')} {message.get('error_message')}"
                                    )
                                elif self.diagnose:
                                    kind = "command" if req_id == command_req else "dataref"
                                    self._log(f"{kind} subscription confirmed req={req_id}")
                            continue

                        if msg_type == "dataref_update_values":
                            updates = message.get("data", {})
                            if not isinstance(updates, dict):
                                continue
                            for raw_id, raw_value in updates.items():
                                for key, index in handlers.get(str(raw_id).strip(), ()):
                                    actual = _numeric(raw_value, index)
                                    self._record_actual(key, actual)
                            continue

                        if msg_type == "command_update_is_active":
                            updates = message.get("data", {})
                            if not isinstance(updates, dict):
                                continue
                            for raw_id, is_active in updates.items():
                                self._handle_command_active(
                                    str(raw_id), is_active, command_handlers
                                )
                            continue

                except Exception as exc:
                    if not self.stop_evt.is_set():
                        self._log(f"WebSocket disconnected: {exc}; REST guard active during reconnect")
                        # Only an actual socket error/close causes fallback now.
                        fallback_until = time.monotonic() + 0.50
                        while (
                            not self.stop_evt.is_set()
                            and time.monotonic() < fallback_until
                        ):
                            with self._lock:
                                if self._generation != generation:
                                    break
                            self._fallback_poll_once(resolved)
                finally:
                    if ws is not None:
                        try:
                            ws.close()
                        except Exception:
                            pass
            except Exception as exc:
                if not self.stop_evt.is_set():
                    self._log(f"worker error: {exc}")
                    self.stop_evt.wait(PU_AUTHORITY_RECONNECT_SECONDS)

        self._log("worker stopped")
