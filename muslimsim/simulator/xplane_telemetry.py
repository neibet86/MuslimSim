"""Shared X-Plane telemetry and session resource registry.

MuslimSim performance rule
==========================

One aircraft state value should enter MuslimSim once, then be distributed to
every consumer that needs it.

This module therefore owns **read-only simulator distribution** only:

* one X-Plane WebSocket connection;
* additive DataRef subscriptions;
* one latest-value cache per DataRef ID;
* named consumer groups for diagnostics;
* thread-safe scalar / array-index reads;
* connection generations and invalidation;
* positive DataRef/command ID caches for the current X-Plane session;
* bounded negative-resolution backoff while an aircraft/plugin is still
  publishing its resources.

It deliberately does **not** own:

* hardware/HID/serial/SDL;
* simulator writes;
* command activation;
* DataRef writes;
* aircraft mappings;
* output power authority.

The bridge remains the sole owner of those paths.

X-Plane's local Web API pushes subscribed DataRef values at roughly 10 Hz and
only sends subsequent values when they change.  A cached value is therefore
still current even if its individual timestamp is old; connection generation
and WebSocket health decide whether the cache is valid.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
import math
import threading
import time
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Sequence, Set, Tuple


class ResourceBackoffError(RuntimeError):
    """A resource lookup is intentionally waiting for its next retry slot."""


@dataclass(frozen=True)
class ResourceFailure:
    failures: int
    retry_at: float
    message: str


class XPlaneSessionResourceCache:
    """Thread-safe X-Plane DataRef/command ID registry for one simulator generation.

    X-Plane IDs are session-scoped.  Successful lookups are therefore cached
    until MuslimSim observes a full simulator disconnect/reconnect edge.

    Failed lookups are *not* cached as "missing".  They receive a short bounded
    retry delay so an aircraft loading 40 plugin DataRefs cannot trigger dozens
    of identical REST searches every few milliseconds.
    """

    def __init__(
        self,
        *,
        base_retry_seconds: float = 0.25,
        max_retry_seconds: float = 5.0,
    ) -> None:
        self.base_retry_seconds = max(0.05, float(base_retry_seconds))
        self.max_retry_seconds = max(
            self.base_retry_seconds, float(max_retry_seconds)
        )
        self._lock = threading.RLock()
        self._generation = 0
        self._datarefs: Dict[Tuple[str, str], int] = {}
        self._commands: Dict[Tuple[str, str], int] = {}
        self._failures: Dict[Tuple[str, str, str], ResourceFailure] = {}
        self._metrics = {
            "dataref_hits": 0,
            "command_hits": 0,
            "dataref_resolves": 0,
            "command_resolves": 0,
            "resolution_failures": 0,
            "backoff_skips": 0,
            "generation_resets": 0,
        }

    @property
    def generation(self) -> int:
        with self._lock:
            return int(self._generation)

    def new_generation(self) -> int:
        """Forget session-scoped IDs after a simulator process reconnect."""
        with self._lock:
            self._generation += 1
            self._datarefs.clear()
            self._commands.clear()
            self._failures.clear()
            self._metrics["generation_resets"] += 1
            return int(self._generation)

    def _cache(self, kind: str) -> MutableMapping[Tuple[str, str], int]:
        if kind == "dataref":
            return self._datarefs
        if kind == "command":
            return self._commands
        raise KeyError(kind)

    def get(self, kind: str, api_version: str, name: str) -> Optional[int]:
        key = (str(api_version), str(name))
        with self._lock:
            value = self._cache(kind).get(key)
            if value is not None:
                metric = "dataref_hits" if kind == "dataref" else "command_hits"
                self._metrics[metric] += 1
                return int(value)
            return None

    def before_resolve(
        self,
        kind: str,
        api_version: str,
        name: str,
        *,
        now: Optional[float] = None,
    ) -> None:
        if now is None:
            now = time.monotonic()
        key = (kind, str(api_version), str(name))
        with self._lock:
            failure = self._failures.get(key)
            if failure is not None and now < failure.retry_at:
                self._metrics["backoff_skips"] += 1
                remaining = max(0.0, failure.retry_at - now)
                raise ResourceBackoffError(
                    f"{kind} lookup backoff {remaining:.2f}s: {name}"
                )
            metric = (
                "dataref_resolves"
                if kind == "dataref"
                else "command_resolves"
            )
            self._metrics[metric] += 1

    def remember(
        self,
        kind: str,
        api_version: str,
        name: str,
        resource_id: int,
    ) -> int:
        key = (str(api_version), str(name))
        failure_key = (kind, str(api_version), str(name))
        with self._lock:
            self._cache(kind)[key] = int(resource_id)
            self._failures.pop(failure_key, None)
        return int(resource_id)

    def failure(
        self,
        kind: str,
        api_version: str,
        name: str,
        exc: BaseException,
        *,
        now: Optional[float] = None,
    ) -> ResourceFailure:
        if now is None:
            now = time.monotonic()
        key = (kind, str(api_version), str(name))
        with self._lock:
            previous = self._failures.get(key)
            count = 1 if previous is None else previous.failures + 1
            delay = min(
                self.max_retry_seconds,
                self.base_retry_seconds * (2 ** min(8, count - 1)),
            )
            record = ResourceFailure(
                failures=count,
                retry_at=now + delay,
                message=str(exc),
            )
            self._failures[key] = record
            self._metrics["resolution_failures"] += 1
            return record

    def invalidate_name(
        self,
        kind: str,
        api_version: str,
        name: str,
    ) -> None:
        key = (str(api_version), str(name))
        with self._lock:
            self._cache(kind).pop(key, None)
            self._failures.pop((kind, str(api_version), str(name)), None)

    def status(self) -> Dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            return {
                "generation": int(self._generation),
                "dataref_ids": len(self._datarefs),
                "command_ids": len(self._commands),
                "backoff_entries": sum(
                    1 for item in self._failures.values()
                    if item.retry_at > now
                ),
                "metrics": dict(self._metrics),
            }


def _numeric(value: Any, index: Optional[int] = None) -> Optional[float]:
    """Extract a numeric scalar/index from an X-Plane WebSocket value."""

    if index is None:
        if isinstance(value, (int, float)):
            result = float(value)
            return result if math.isfinite(result) else None
        # A scalar DataRef occasionally arrives wrapped in a one-item list.
        if isinstance(value, (list, tuple)) and len(value) == 1:
            item = value[0]
            if isinstance(item, (int, float)):
                result = float(item)
                return result if math.isfinite(result) else None
        return None

    if isinstance(value, (list, tuple)):
        if 0 <= int(index) < len(value):
            item = value[int(index)]
            if isinstance(item, (int, float)):
                result = float(item)
                return result if math.isfinite(result) else None
    return None


class SharedXPlaneTelemetryHub:
    """One additive WebSocket DataRef stream shared across MuslimSim devices."""

    def __init__(
        self,
        api_version: str,
        websocket_module: Any,
        *,
        host: str = "127.0.0.1",
        port: int = 8086,
        external_stop: Optional[threading.Event] = None,
        reconnect_min_seconds: float = 0.25,
        reconnect_max_seconds: float = 5.0,
        first_value_wait_seconds: float = 0.12,
        receive_timeout_seconds: float = 0.10,
    ) -> None:
        self.api_version = str(api_version)
        self.websocket_module = websocket_module
        self.url = f"ws://{host}:{int(port)}/api/{self.api_version}"
        self.external_stop = external_stop
        self.reconnect_min_seconds = max(
            0.05, float(reconnect_min_seconds)
        )
        self.reconnect_max_seconds = max(
            self.reconnect_min_seconds, float(reconnect_max_seconds)
        )
        self.first_value_wait_seconds = max(
            0.0, float(first_value_wait_seconds)
        )
        self.receive_timeout_seconds = max(
            0.02, float(receive_timeout_seconds)
        )

        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = threading.Thread(
            target=self._worker,
            name="MuslimSim-XPlane-Telemetry-Hub",
            daemon=True,
        )

        # Whole-DataRef subscriptions are intentional.  They make array index
        # distribution deterministic and avoid X-Plane's sparse-index
        # resubscription ordering rules.
        self._desired: Set[int] = set()
        self._pending: Set[int] = set()
        self._subscribed: Set[int] = set()
        self._values: Dict[int, Any] = {}
        self._groups: Dict[str, Set[int]] = defaultdict(set)
        self._id_groups: Dict[int, Set[str]] = defaultdict(set)
        self._listeners: Dict[int, Any] = {}
        self._next_listener_token = 1

        self.connected = False
        self.last_message = 0.0
        self.last_update = 0.0
        self.error = ""
        self._generation = 0
        self._next_req_id = 12000
        self._ws = None
        self._subscription_requests_by_req: Dict[
            int, Tuple[Tuple[int, ...], bool]
        ] = {}
        self._rejected_ids: Set[int] = set()

        self._metrics: Dict[str, int] = {
            "ws_connects": 0,
            "ws_disconnects": 0,
            "subscription_requests": 0,
            "subscription_ids": 0,
            "subscription_batch_failures": 0,
            "subscription_rejected_ids": 0,
            "update_messages": 0,
            "updated_values": 0,
            "cache_reads": 0,
            "cache_misses": 0,
            "read_waits": 0,
            "read_timeouts": 0,
            "rest_fallbacks": 0,
            "rest_reuse_reads": 0,
            "rest_rate_limited": 0,
            "invalidations": 0,
            "listener_callbacks": 0,
            "listener_errors": 0,
        }
        self._rest_fallback_by_id: Dict[int, int] = defaultdict(int)
        self._rest_cache: Dict[
            Tuple[int, Optional[int]], Tuple[float, float]
        ] = {}
        self._rest_last_request: Dict[
            Tuple[int, Optional[int]], float
        ] = {}
        self._rest_inflight: Set[Tuple[int, Optional[int]]] = set()

    @property
    def generation(self) -> int:
        with self._lock:
            return int(self._generation)

    @property
    def available(self) -> bool:
        return self.websocket_module is not None

    def _should_stop(self) -> bool:
        return bool(
            self._stop.is_set()
            or (
                self.external_stop is not None
                and self.external_stop.is_set()
            )
        )

    def start(self) -> None:
        if not self.available:
            with self._lock:
                self.error = "websocket-client unavailable"
            return
        if not self._thread.is_alive():
            self._thread.start()

    def stop(self, timeout: float = 1.5) -> None:
        self._stop.set()
        self._wake.set()
        ws = None
        with self._lock:
            ws = self._ws
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        if self._thread.is_alive():
            self._thread.join(timeout=max(0.0, float(timeout)))

    def register_group(
        self,
        name: str,
        dataref_ids: Iterable[int],
    ) -> Tuple[int, ...]:
        group = str(name).strip() or "unnamed"
        added = []
        with self._condition:
            for raw_id in dataref_ids:
                try:
                    ref_id = int(raw_id)
                except (TypeError, ValueError):
                    continue
                self._groups[group].add(ref_id)
                self._id_groups[ref_id].add(group)
                if ref_id not in self._desired:
                    self._desired.add(ref_id)
                    self._pending.add(ref_id)
                    added.append(ref_id)
            if added:
                self._wake.set()
                self._condition.notify_all()
        return tuple(added)

    def ensure(
        self,
        dataref_id: int,
        *,
        group: str = "dynamic.legacy",
    ) -> bool:
        ref_id = int(dataref_id)
        with self._condition:
            self._groups[group].add(ref_id)
            self._id_groups[ref_id].add(group)
            if ref_id in self._desired:
                return False
            self._desired.add(ref_id)
            self._pending.add(ref_id)
            self._wake.set()
            self._condition.notify_all()
            return True

    def invalidate(self, reason: str = "") -> int:
        """Invalidate values while keeping desired subscriptions for reconnect."""
        with self._condition:
            self._generation += 1
            self._values.clear()
            self._rest_cache.clear()
            self._rest_inflight.clear()
            self._subscription_requests_by_req.clear()
            self._rejected_ids.clear()
            self._subscribed.clear()
            self._pending = set(self._desired)
            self.connected = False
            if reason:
                self.error = str(reason)
            self._metrics["invalidations"] += 1
            self._wake.set()
            self._condition.notify_all()
            return int(self._generation)

    def external_connection(self, connected: bool) -> None:
        """Accept the bridge watchdog edge without taking output ownership."""
        if connected:
            return

        self.invalidate("bridge watchdog: simulator offline")
        # Wake/close the receive call as well. Otherwise a socket that has not
        # failed at the TCP layer yet could keep the worker blocked while the
        # bridge has already declared X-Plane offline.
        ws = None
        with self._lock:
            ws = self._ws
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

    def begin_rest_fallback(
        self,
        dataref_id: int,
        *,
        index: Optional[int] = None,
        reuse_seconds: float = 1.00,
        min_request_interval: float = 0.50,
        inflight_wait_seconds: float = 0.05,
    ) -> Tuple[str, Optional[float]]:
        """Coalesce/rate-limit REST reads while the stream is unavailable.

        Returns ``("value", value)`` when a recent fallback result can be
        reused, ``("fetch", None)`` for the one caller allowed to perform the
        REST request, or ``("skip", None)`` when another bounded request would
        be too aggressive.
        """

        key = (int(dataref_id), None if index is None else int(index))
        reuse_seconds = max(0.0, float(reuse_seconds))
        min_request_interval = max(0.05, float(min_request_interval))
        deadline = time.monotonic() + max(0.0, float(inflight_wait_seconds))

        with self._condition:
            while True:
                now = time.monotonic()
                cached = self._rest_cache.get(key)
                if (
                    cached is not None
                    and now - cached[1] <= reuse_seconds
                ):
                    self._metrics["rest_reuse_reads"] += 1
                    return "value", float(cached[0])

                if key not in self._rest_inflight:
                    last_request = self._rest_last_request.get(key, 0.0)
                    if now - last_request >= min_request_interval:
                        self._rest_inflight.add(key)
                        self._rest_last_request[key] = now
                        return "fetch", None

                    self._metrics["rest_rate_limited"] += 1
                    return "skip", None

                remaining = deadline - now
                if remaining <= 0.0:
                    self._metrics["rest_rate_limited"] += 1
                    return "skip", None
                self._condition.wait(timeout=min(remaining, 0.02))

    def finish_rest_fallback(
        self,
        dataref_id: int,
        value: Optional[float],
        *,
        index: Optional[int] = None,
        success: bool,
    ) -> None:
        key = (int(dataref_id), None if index is None else int(index))
        with self._condition:
            self._rest_inflight.discard(key)
            if success and value is not None and math.isfinite(float(value)):
                self._rest_cache[key] = (
                    float(value),
                    time.monotonic(),
                )
                self._metrics["rest_fallbacks"] += 1
                self._rest_fallback_by_id[int(dataref_id)] += 1
            self._condition.notify_all()

    def note_rest_fallback(self, dataref_id: int) -> None:
        """Compatibility metric hook for older callers/tests."""
        ref_id = int(dataref_id)
        with self._lock:
            self._metrics["rest_fallbacks"] += 1
            self._rest_fallback_by_id[ref_id] += 1

    def cached_raw(self, dataref_id: int) -> Any:
        with self._lock:
            return self._values.get(int(dataref_id))

    def add_listener(self, callback: Any) -> int:
        """Register a read-only update listener and return its removal token."""
        if not callable(callback):
            raise TypeError("telemetry listener must be callable")
        with self._lock:
            token = int(self._next_listener_token)
            self._next_listener_token += 1
            self._listeners[token] = callback
            return token

    def remove_listener(self, token: int) -> None:
        with self._lock:
            self._listeners.pop(int(token), None)

    def raw_snapshot(
        self, dataref_ids: Optional[Iterable[int]] = None
    ) -> Dict[int, Any]:
        """Return a shallow raw-value snapshot for read-only display consumers."""
        with self._lock:
            if dataref_ids is None:
                return dict(self._values)
            result: Dict[int, Any] = {}
            for raw_id in dataref_ids:
                try:
                    ref_id = int(raw_id)
                except (TypeError, ValueError):
                    continue
                if ref_id in self._values:
                    result[ref_id] = self._values[ref_id]
            return result

    def read_numeric(
        self,
        dataref_id: int,
        *,
        index: Optional[int] = None,
        group: str = "dynamic.legacy",
        wait_seconds: Optional[float] = None,
    ) -> Optional[float]:
        """Return a distributed value or None so the caller can use REST fallback."""

        ref_id = int(dataref_id)
        self.ensure(ref_id, group=group)

        if wait_seconds is None:
            wait_seconds = self.first_value_wait_seconds
        wait_seconds = max(0.0, float(wait_seconds))
        deadline = time.monotonic() + wait_seconds

        with self._condition:
            while True:
                if ref_id in self._values and self.connected:
                    result = _numeric(self._values[ref_id], index)
                    if result is not None:
                        self._metrics["cache_reads"] += 1
                        return result

                if self._should_stop():
                    self._metrics["cache_misses"] += 1
                    return None

                # If the WebSocket is not connected yet, do not serialize
                # every device behind the full initial wait.  One early REST
                # read is allowed while the hub establishes itself.
                if not self.connected and self.last_message <= 0.0:
                    self._metrics["cache_misses"] += 1
                    return None

                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    self._metrics["cache_misses"] += 1
                    self._metrics["read_timeouts"] += 1
                    return None

                self._metrics["read_waits"] += 1
                self._condition.wait(timeout=min(remaining, 0.05))

    def snapshot_group(self, name: str) -> Dict[int, Any]:
        group = str(name)
        with self._lock:
            return {
                ref_id: self._values.get(ref_id)
                for ref_id in sorted(self._groups.get(group, ()))
            }

    def groups_for(self, dataref_id: int) -> Tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._id_groups.get(int(dataref_id), ())))

    def status(self) -> Dict[str, Any]:
        with self._lock:
            desired = len(self._desired)
            subscribed = len(self._subscribed)
            groups = {
                key: len(value)
                for key, value in sorted(self._groups.items())
            }
            metrics = dict(self._metrics)
            total_reads = (
                metrics["cache_reads"] + metrics["rest_fallbacks"]
            )
            hit_rate = (
                metrics["cache_reads"] / total_reads
                if total_reads
                else 0.0
            )
            top_fallbacks = sorted(
                self._rest_fallback_by_id.items(),
                key=lambda item: (-item[1], item[0]),
            )[:10]
            return {
                "api_version": self.api_version,
                "connected": bool(self.connected),
                "generation": int(self._generation),
                "desired_datarefs": desired,
                "subscribed_datarefs": subscribed,
                "rejected_datarefs": len(self._rejected_ids),
                "cached_values": len(self._values),
                "groups": groups,
                "last_message_age": (
                    None
                    if self.last_message <= 0.0
                    else max(0.0, time.monotonic() - self.last_message)
                ),
                "last_update_age": (
                    None
                    if self.last_update <= 0.0
                    else max(0.0, time.monotonic() - self.last_update)
                ),
                "error": str(self.error or ""),
                "metrics": metrics,
                "cache_hit_rate": hit_rate,
                "rest_fallback_top_ids": top_fallbacks,
            }

    def _request_id(self) -> int:
        with self._lock:
            result = int(self._next_req_id)
            self._next_req_id += 1
            return result

    def _send_subscription_batch(
        self,
        ws: Any,
        dataref_ids: Sequence[int],
        *,
        isolated: bool,
    ) -> None:
        batch = tuple(int(value) for value in dataref_ids)
        if not batch:
            return
        req_id = self._request_id()
        message = {
            "req_id": req_id,
            "type": "dataref_subscribe_values",
            "params": {
                "datarefs": [{"id": value} for value in batch],
            },
        }
        ws.send(json.dumps(message, separators=(",", ":")))
        with self._lock:
            self._subscription_requests_by_req[req_id] = (
                batch, bool(isolated)
            )
            self._metrics["subscription_requests"] += 1
            self._metrics["subscription_ids"] += len(batch)
            self._subscribed.update(batch)

    def _send_subscriptions(
        self,
        ws: Any,
        dataref_ids: Sequence[int],
    ) -> None:
        if not dataref_ids:
            return

        # Normal path: efficient bounded batches. If X-Plane rejects one batch
        # as a unit, _handle_subscription_result() retries those IDs
        # individually so one stale optional plugin DataRef cannot starve the
        # other valid values in its group.
        for offset in range(0, len(dataref_ids), 64):
            batch = tuple(
                int(value)
                for value in dataref_ids[offset:offset + 64]
                if int(value) not in self._rejected_ids
            )
            if batch:
                self._send_subscription_batch(
                    ws, batch, isolated=False
                )

    def _handle_subscription_result(
        self,
        ws: Any,
        message: Mapping[str, Any],
    ) -> None:
        try:
            req_id = int(message.get("req_id"))
        except (TypeError, ValueError):
            return

        with self._lock:
            record = self._subscription_requests_by_req.pop(
                req_id, None
            )
        if record is None:
            return

        batch, isolated = record
        if bool(message.get("success", False)):
            return

        with self._lock:
            self._subscribed.difference_update(batch)
            self.error = (
                str(message.get("error_message") or "")
                or str(message.get("error_code") or "")
                or "X-Plane subscription failed"
            )

        if len(batch) > 1 and not isolated:
            with self._lock:
                self._metrics["subscription_batch_failures"] += 1
            for ref_id in batch:
                self._send_subscription_batch(
                    ws, (ref_id,), isolated=True
                )
            return

        # One isolated ID failed. Leave it desired for diagnostics but do not
        # keep retrying it on every loop. A new simulator generation or a new
        # resolved ID will create a clean subscription attempt.
        with self._lock:
            self._rejected_ids.update(batch)
            self._metrics["subscription_rejected_ids"] += len(batch)

    def _take_pending(self) -> Tuple[int, ...]:
        with self._lock:
            pending = tuple(sorted(self._pending))
            self._pending.clear()
            return pending

    def _all_desired(self) -> Tuple[int, ...]:
        with self._lock:
            return tuple(sorted(self._desired))

    def _ingest_update(self, updates: Mapping[Any, Any]) -> int:
        if not isinstance(updates, Mapping):
            return 0
        now = time.monotonic()
        count = 0
        accepted: Dict[int, Any] = {}
        listeners = ()
        with self._condition:
            for raw_id, raw_value in updates.items():
                try:
                    ref_id = int(str(raw_id).strip())
                except (TypeError, ValueError):
                    continue
                if ref_id not in self._desired:
                    continue
                self._values[ref_id] = raw_value
                accepted[ref_id] = raw_value
                count += 1
            self.last_message = now
            if count:
                self.last_update = now
                self._metrics["updated_values"] += count
                listeners = tuple(self._listeners.values())
            self._metrics["update_messages"] += 1
            self._condition.notify_all()

        # Listener code is never called under the telemetry lock. Display
        # smoothing/render preparation can therefore consume updates without
        # delaying unrelated cache readers or subscription management.
        if accepted and listeners:
            payload = dict(accepted)
            for callback in listeners:
                try:
                    callback(payload, now)
                    with self._lock:
                        self._metrics["listener_callbacks"] += 1
                except Exception:
                    with self._lock:
                        self._metrics["listener_errors"] += 1
        return count

    def _mark_connected(self, ws: Any) -> None:
        with self._condition:
            self._ws = ws
            self.connected = True
            self.error = ""
            self._generation += 1
            self._values.clear()
            self._rest_cache.clear()
            self._rest_inflight.clear()
            self._subscription_requests_by_req.clear()
            self._rejected_ids.clear()
            self._subscribed.clear()
            self._pending = set(self._desired)
            self._metrics["ws_connects"] += 1
            self._condition.notify_all()

    def _mark_disconnected(self, message: str = "") -> None:
        with self._condition:
            was_connected = self.connected
            self._ws = None
            self.connected = False
            self._values.clear()
            self._subscribed.clear()
            self._pending = set(self._desired)
            if message:
                self.error = str(message)
            if was_connected:
                self._metrics["ws_disconnects"] += 1
            self._condition.notify_all()

    def _worker(self) -> None:
        ws_module = self.websocket_module
        if ws_module is None:
            self._mark_disconnected("websocket-client unavailable")
            return

        reconnect_delay = self.reconnect_min_seconds

        while not self._should_stop():
            ws = None
            try:
                ws = ws_module.create_connection(
                    self.url,
                    timeout=1.0,
                    enable_multithread=True,
                )
                ws.settimeout(self.receive_timeout_seconds)
                self._mark_connected(ws)
                self._send_subscriptions(ws, self._all_desired())
                reconnect_delay = self.reconnect_min_seconds

                while not self._should_stop():
                    if self._wake.is_set():
                        self._wake.clear()
                        self._send_subscriptions(ws, self._take_pending())

                    try:
                        raw = ws.recv()
                    except ws_module.WebSocketTimeoutException:
                        continue

                    if not raw:
                        continue

                    message = json.loads(raw)
                    message_type = message.get("type")

                    if message_type == "dataref_update_values":
                        self._ingest_update(message.get("data", {}))
                    elif message_type == "result":
                        self._handle_subscription_result(ws, message)
            except Exception as exc:
                self._mark_disconnected(str(exc))
                if not self._should_stop():
                    if self.external_stop is not None:
                        self.external_stop.wait(reconnect_delay)
                    else:
                        self._stop.wait(reconnect_delay)
                    reconnect_delay = min(
                        self.reconnect_max_seconds,
                        reconnect_delay * 2.0,
                    )
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass

        self._mark_disconnected("stopped")


__all__ = [
    "ResourceBackoffError",
    "ResourceFailure",
    "SharedXPlaneTelemetryHub",
    "XPlaneSessionResourceCache",
]
