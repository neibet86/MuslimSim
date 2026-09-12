#!/usr/bin/env python3
"""Offline contract checks for Performance Phase B shared display telemetry.

No X-Plane, HID, serial, SDL, or network socket is opened.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muslimsim.simulator.xplane_telemetry import SharedXPlaneTelemetryHub


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_bridge():
    spec = importlib.util.spec_from_file_location(
        "_muslimsim_phase_b_bridge_test", ROOT / "bridge" / "final.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    checks = 0
    bridge = load_bridge()

    # Central Phase-A hub in deterministic offline mode. We directly ingest
    # updates instead of starting a socket thread.
    raw = SharedXPlaneTelemetryHub(
        "v3", websocket_module=None, first_value_wait_seconds=0.0
    )
    raw.connected = True
    raw._generation = 1
    bridge._SHARED_XPLANE_TELEMETRY = raw

    pfd_ids = {
        "ias": 101,
        "heading": 102,
    }
    secondary_ids = {
        "groundspeed": (103, None),
        "eng_n1": (104, "array"),
    }

    # Two physical display consumers must acquire ONE smoothing instance.
    smooth1, key1 = bridge._acquire_smooth_telemetry(
        "v3", pfd_ids, secondary_ids
    )
    smooth2, key2 = bridge._acquire_smooth_telemetry(
        "v3", pfd_ids, secondary_ids
    )
    check(smooth1 is smooth2, "BB35/BB36 did not share one smooth hub")
    check(key1 == key2, "identical display maps produced different pool keys")
    pool = bridge._smooth_telemetry_pool_status()
    check(pool["instances"] == 1, f"unexpected pool instances: {pool}")
    check(pool["references"] == 2, f"unexpected pool refs: {pool}")
    checks += 4

    groups = raw.status()["groups"]
    check(groups.get("pfd.graphical.shared") == 4,
          f"shared graphical group wrong: {groups}")
    checks += 1

    # One raw update feeds the one smoother and therefore both displays.
    raw._ingest_update({
        "101": 250.0,
        "102": 91.0,
        "103": 120.0,
        "104": [55.0, 56.0],
    })
    snap1 = smooth1.snapshot(("ias", "heading", "groundspeed", "eng_n1_0", "eng_n1_1"))
    snap2 = smooth2.snapshot(("ias", "heading", "groundspeed", "eng_n1_0", "eng_n1_1"))
    for key in ("ias", "heading", "groundspeed", "eng_n1_0", "eng_n1_1"):
        check(math.isfinite(snap1[key]), f"{key} not populated")
        check(abs(snap1[key] - snap2[key]) < 1e-9,
              f"shared display snapshots diverged for {key}")
        checks += 2

    check(smooth1.healthy(), "shared smoother not healthy after initial update")
    checks += 1

    # Session generation must clear former-aircraft smoothed values before a
    # new X-Plane connection is allowed to show them.
    raw.invalidate("offline test")
    raw.connected = True
    stale = smooth1.snapshot(("ias",))
    check(math.isnan(stale["ias"]), "old-aircraft smoothed IAS survived generation reset")
    checks += 1
    raw._ingest_update({"101": 201.0, "102": 180.0, "103": 0.0, "104": [10.0, 11.0]})
    fresh = smooth1.snapshot(("ias",))
    check(math.isfinite(fresh["ias"]), "new-generation value did not repopulate")
    checks += 1

    # Reference-counted teardown: one display can restart without killing the
    # shared data source still used by the other display.
    bridge._release_smooth_telemetry(key1)
    pool = bridge._smooth_telemetry_pool_status()
    check(pool["instances"] == 1 and pool["references"] == 1,
          f"first release killed shared smoother: {pool}")
    checks += 1
    bridge._release_smooth_telemetry(key2)
    pool = bridge._smooth_telemetry_pool_status()
    check(pool["instances"] == 0 and pool["references"] == 0,
          f"last release leaked shared smoother: {pool}")
    checks += 1

    # BB36 graphical FMC must also use the central raw cache when present and
    # must not create its former dedicated WebSocket worker thread.
    original_resolver = bridge.resolve_dataref_id
    id_map = {}
    try:
        def fake_resolve(api_version, name, **kwargs):
            if name not in id_map:
                id_map[name] = 2000 + len(id_map)
            return id_map[name]

        bridge.resolve_dataref_id = fake_resolve
        feed = bridge._BB36GraphicalFMCFeed("v3", shared_source=raw)
        feed.start()
        check(feed.thread is None, "shared BB36 FMC feed still created a worker thread")
        check("line00_l" in feed.resolved and "entry" in feed.resolved,
              "BB36 shared FMC refs did not resolve")
        checks += 2
        raw.connected = True
        line_id = feed.resolved["line00_l"]
        entry_id = feed.resolved["entry"]
        raw._ingest_update({
            str(line_id): [84, 69, 83, 84],   # TEST
            str(entry_id): [65, 66, 67],      # ABC
        })
        values, connected = feed._shared_values()
        check(values.get("line00_l") == "TEST", f"FMC line decode wrong: {values.get('line00_l')!r}")
        check(values.get("entry") == "ABC", f"FMC entry decode wrong: {values.get('entry')!r}")
        check(connected, "shared FMC feed did not report central connection")
        check(raw.status()["groups"].get("bb36.fmc", 0) >= 2,
              "BB36 FMC group was not registered")
        checks += 4
        feed.stop()
    finally:
        bridge.resolve_dataref_id = original_resolver

    # ND route/TCAS/text caches can consume non-numeric raw values through the
    # same central distribution service.
    raw.connected = True
    raw.ensure(777, group="pfd.nd.traffic")
    raw._ingest_update({"777": [1, 2, 3]})
    check(
        bridge._cockpit_shared_raw_value("v3", 777, "pfd.nd.traffic") == [1, 2, 3],
        "display raw-array cache did not use shared hub",
    )
    checks += 1

    # The telemetry listener API must deliver outside-cache consumers without
    # spawning another simulator connection.
    events = []
    token = raw.add_listener(lambda updates, now: events.append(dict(updates)))
    raw.ensure(888, group="test.listener")
    raw._ingest_update({"888": 9.0})
    raw.remove_listener(token)
    check(events and events[-1].get(888) == 9.0, "central listener distribution failed")
    checks += 1

    # Source-level ownership checks.
    source = (ROOT / "bridge" / "final.py").read_text(encoding="utf-8")
    telemetry_source = (ROOT / "muslimsim" / "simulator" / "xplane_telemetry.py").read_text(encoding="utf-8")
    for token in (
        "_acquire_smooth_telemetry(",
        "_release_smooth_telemetry(smooth_pool_key)",
        'shared_source=_SHARED_XPLANE_TELEMETRY',
        '"pfd.graphical.shared"',
        '"bb36.fmc"',
        '"pfd.nd.route"',
        '"pfd.nd.traffic"',
        '"pfd.text"',
    ):
        check(token in source, f"Phase B bridge wiring missing: {token}")
        checks += 1

    for forbidden in (
        "def set_dataref",
        "def activate_command",
        "import pygame",
        "import hid",
    ):
        check(forbidden not in telemetry_source,
              f"shared telemetry crossed hardware/write ownership: {forbidden}")
        checks += 1

    print(f"Shared PFD/BB36 display telemetry Phase B: {checks} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
