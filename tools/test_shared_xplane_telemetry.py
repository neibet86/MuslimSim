#!/usr/bin/env python3
"""Offline performance/contract checks for MuslimSim shared X-Plane telemetry.

No simulator, network socket, HID, serial, or SDL device is opened.
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muslimsim.simulator.xplane_telemetry import (
    ResourceBackoffError,
    SharedXPlaneTelemetryHub,
    XPlaneSessionResourceCache,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class FakeSocket:
    def __init__(self) -> None:
        self.sent = []
        self.closed = False

    def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))

    def close(self) -> None:
        self.closed = True


def load_bridge():
    spec = importlib.util.spec_from_file_location(
        "_muslimsim_shared_telemetry_bridge_test",
        ROOT / "bridge" / "final.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    checks = 0

    # ------------------------------------------------------------------
    # Session resource registry: one positive REST resolve becomes a hit.
    # ------------------------------------------------------------------
    cache = XPlaneSessionResourceCache(
        base_retry_seconds=0.25,
        max_retry_seconds=2.0,
    )
    check(cache.get("dataref", "v3", "foo") is None, "empty cache returned id")
    checks += 1
    cache.before_resolve("dataref", "v3", "foo", now=10.0)
    cache.remember("dataref", "v3", "foo", 123)
    check(cache.get("dataref", "v3", "foo") == 123, "positive DataRef cache failed")
    checks += 1

    cache.failure(
        "command", "v3", "missing", RuntimeError("not ready"), now=20.0
    )
    try:
        cache.before_resolve("command", "v3", "missing", now=20.1)
    except ResourceBackoffError:
        pass
    else:
        raise AssertionError("failed command resolution did not back off")
    checks += 1
    cache.before_resolve("command", "v3", "missing", now=20.3)
    checks += 1

    old_generation = cache.generation
    cache.new_generation()
    check(cache.generation == old_generation + 1, "resource generation did not move")
    check(cache.get("dataref", "v3", "foo") is None, "new generation retained old id")
    checks += 2

    # ------------------------------------------------------------------
    # Shared telemetry distribution: one cached value serves many readers.
    # ------------------------------------------------------------------
    hub = SharedXPlaneTelemetryHub(
        "v3",
        websocket_module=None,
        first_value_wait_seconds=0.0,
    )
    hub.connected = True
    hub.register_group("pu.core", (101, 102))
    hub.register_group("agp.radio_nav", (102, 103))

    check(hub._ingest_update({"101": 12.5, "102": [4, 5, 6], "103": 7.25}) == 3,
          "update ingest count wrong")
    checks += 1
    check(hub.read_numeric(101, wait_seconds=0.0) == 12.5, "scalar cache read failed")
    checks += 1
    check(hub.read_numeric(102, index=1, wait_seconds=0.0) == 5.0,
          "array-index cache read failed")
    checks += 1

    for _ in range(1000):
        value = hub.read_numeric(101, wait_seconds=0.0)
        if value != 12.5:
            raise AssertionError("repeated cache distribution changed value")
    status = hub.status()
    check(status["metrics"]["cache_reads"] >= 1002,
          "1000 repeated consumers were not served from cache")
    check(status["metrics"]["rest_fallbacks"] == 0,
          "cache-only performance test unexpectedly used REST")
    checks += 2

    check(status["groups"]["pu.core"] == 2, "PU group count wrong")
    check(status["groups"]["agp.radio_nav"] == 2, "AGP group count wrong")
    checks += 2

    # Whole-array policy: subscription descriptor contains only id, never
    # sparse index state that would need unsubscribe/resubscribe ordering.
    socket = FakeSocket()
    hub._send_subscriptions(socket, [101, 102, 103])
    check(len(socket.sent) == 1, "small subscription should be one request")
    sent = socket.sent[0]
    check(sent["type"] == "dataref_subscribe_values", "wrong WS request type")
    check(
        sent["params"]["datarefs"] == [{"id": 101}, {"id": 102}, {"id": 103}],
        "subscription descriptors are not whole-DataRef ids",
    )
    checks += 3

    # One invalid ID must not poison the whole batch. A failed normal batch is
    # automatically retried as isolated one-ID subscriptions.
    failed_req_id = int(sent["req_id"])
    hub._handle_subscription_result(
        socket,
        {
            "req_id": failed_req_id,
            "type": "result",
            "success": False,
            "error_code": "invalid_dataref_id",
        },
    )
    isolated = socket.sent[1:]
    check(len(isolated) == 3, "failed subscription batch was not isolated")
    check(
        all(len(item["params"]["datarefs"]) == 1 for item in isolated),
        "isolated retry still bundled multiple DataRefs",
    )
    checks += 2

    # Reject one isolated ID and ensure diagnostics retain the failure without
    # repeatedly resubscribing it.
    first_isolated_req = int(isolated[0]["req_id"])
    rejected_id = isolated[0]["params"]["datarefs"][0]["id"]
    hub._handle_subscription_result(
        socket,
        {
            "req_id": first_isolated_req,
            "type": "result",
            "success": False,
            "error_code": "invalid_dataref_id",
        },
    )
    check(rejected_id in hub._rejected_ids, "bad isolated DataRef was not quarantined")
    check(hub.status()["rejected_datarefs"] >= 1, "rejected DataRef missing from status")
    checks += 2

    # Invalidation must never return old aircraft state.
    hub.invalidate("test disconnect")
    check(hub.cached_raw(101) is None, "disconnect retained stale telemetry")
    checks += 1

    # REST fallback broker: one caller fetches, later callers reuse, and a
    # second fetch cannot hammer the same ID inside the bounded interval.
    action, cached = hub.begin_rest_fallback(
        777, reuse_seconds=0.5, min_request_interval=0.25
    )
    check(action == "fetch" and cached is None, "first REST fallback did not get fetch ticket")
    hub.finish_rest_fallback(777, 55.0, success=True)
    action, cached = hub.begin_rest_fallback(
        777, reuse_seconds=0.5, min_request_interval=0.25
    )
    check(action == "value" and cached == 55.0, "fresh REST fallback result was not reused")
    checks += 2

    # Force cached value old while keeping the request interval active.
    key = (777, None)
    with hub._lock:
        value, _when = hub._rest_cache[key]
        hub._rest_cache[key] = (value, 0.0)
        hub._rest_last_request[key] = __import__("time").monotonic()
    action, cached = hub.begin_rest_fallback(
        777, reuse_seconds=0.0, min_request_interval=10.0
    )
    check(action == "skip" and cached is None, "REST fallback rate limit did not suppress duplicate fetch")
    checks += 1

    # ------------------------------------------------------------------
    # Bridge facade: existing read_dataref callers transparently use hub.
    # ------------------------------------------------------------------
    bridge = load_bridge()

    class FacadeHub:
        api_version = "v3"
        first_value_wait_seconds = 0.0

        def __init__(self, scalar, array):
            self.scalar = scalar
            self.array = array
            self.fallbacks = 0
            self._fallback_value = None

        def read_numeric(self, dataref_id, *, index=None, group="", wait_seconds=0.0):
            if index is None:
                return self.scalar
            return self.array[index]

        def begin_rest_fallback(self, dataref_id, *, index=None):
            if self._fallback_value is not None:
                return "value", self._fallback_value
            return "fetch", None

        def finish_rest_fallback(self, dataref_id, value, *, index=None, success=False):
            if success:
                self.fallbacks += 1
                self._fallback_value = float(value)

        def note_rest_fallback(self, dataref_id):
            self.fallbacks += 1

    facade = FacadeHub(42.5, [1.0, 8.0, 3.0])
    bridge._SHARED_XPLANE_TELEMETRY = facade

    original_scalar_rest = bridge._read_dataref_rest
    original_index_rest = bridge._read_dataref_index_rest
    try:
        bridge._read_dataref_rest = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("scalar REST should not run on cache hit")
        )
        bridge._read_dataref_index_rest = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("array REST should not run on cache hit")
        )
        check(bridge.read_dataref("v3", 9001) == 42.5,
              "bridge scalar facade ignored shared hub")
        check(bridge.read_dataref_index("v3", 9002, 1) == 8.0,
              "bridge array facade ignored shared hub")
        checks += 2
    finally:
        bridge._read_dataref_rest = original_scalar_rest
        bridge._read_dataref_index_rest = original_index_rest

    # REST fallback remains available if the hub has no initial value.
    facade.scalar = None
    facade._fallback_value = None
    bridge._read_dataref_rest = lambda *a, **k: 3.25
    try:
        check(bridge.read_dataref("v3", 9003) == 3.25,
              "REST fallback disappeared")
        check(facade.fallbacks == 1, "REST fallback metric was not recorded")
        checks += 2
    finally:
        bridge._read_dataref_rest = original_scalar_rest

    # ------------------------------------------------------------------
    # Bridge resource resolver: identical successful names hit REST once.
    # ------------------------------------------------------------------
    bridge._XPLANE_RESOURCE_CACHE = XPlaneSessionResourceCache()
    calls = {"count": 0}
    original_http = bridge.http_json

    def fake_http(url, *args, **kwargs):
        calls["count"] += 1
        if "/datarefs?" in url:
            return {"data": [{"id": 321, "name": "sim/test/value"}]}
        if "/commands?" in url:
            return {"data": [{"id": 654, "name": "sim/test/command"}]}
        raise AssertionError(url)

    bridge.http_json = fake_http
    try:
        check(bridge.resolve_dataref_id("v3", "sim/test/value") == 321,
              "DataRef resolver first lookup failed")
        check(bridge.resolve_dataref_id("v3", "sim/test/value") == 321,
              "DataRef resolver cache hit failed")
        check(bridge.resolve_command_id("v3", "sim/test/command") == 654,
              "command resolver first lookup failed")
        check(bridge.resolve_command_id("v3", "sim/test/command") == 654,
              "command resolver cache hit failed")
        check(calls["count"] == 2,
              f"resource cache used {calls['count']} REST searches instead of 2")
        checks += 5
    finally:
        bridge.http_json = original_http

    # Explicit refresh must bypass the positive cache for existing 404 recovery
    # helpers rather than returning a stale ID forever.
    calls["count"] = 0
    bridge.http_json = fake_http
    try:
        bridge._XPLANE_RESOURCE_CACHE.remember(
            "dataref", "v3", "sim/test/value", 111
        )
        check(
            bridge.resolve_dataref_id(
                "v3", "sim/test/value", refresh=True
            ) == 321,
            "explicit DataRef refresh returned stale cached id",
        )
        check(calls["count"] == 1, "explicit refresh did not reach resolver REST")
        checks += 2
    finally:
        bridge.http_json = original_http

    # Source integration / ownership boundary.
    source = (ROOT / "bridge" / "final.py").read_text(encoding="utf-8")
    for token in (
        "_start_shared_xplane_telemetry(api_version, stop_evt)",
        '_telemetry_register_group("pu.core", ids)',
        '"pu.annunciators"',
        '"fcu_efis.display"',
        '"winctrl.throttle.feedback"',
        '"agp.radio_nav"',
        '"pfd.shared_inputs"',
        "--diagnose-telemetry",
    ):
        check(token in source, f"bridge shared-telemetry wiring missing: {token}")
        checks += 1

    # Writers must remain writers; the new simulator module must contain no
    # bridge set_dataref/activate_command ownership.
    telemetry_source = (
        ROOT / "muslimsim" / "simulator" / "xplane_telemetry.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("def set_dataref", "def activate_command", "import pygame", "import hid"):
        check(forbidden not in telemetry_source,
              f"telemetry layer crossed ownership boundary: {forbidden}")
        checks += 1

    print(f"Shared X-Plane telemetry: {checks} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
