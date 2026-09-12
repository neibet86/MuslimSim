#!/usr/bin/env python3
"""Read X-Plane's real yoke_roll_ratio/yoke_pitch_ratio values directly,
with timestamps, independent of the bridge or Studio.

Three targeted write-side fixes to the MOZA A210 routing (an X-Plane
joystick override, a fixed-rate write timer, and a tolerance floor fix for
that timer) have all failed to change a reported "chacke very very tiny
movement i concider chacking not movement" while watching X-Plane's own 3D
yoke model - even after a full X-Plane and Studio restart. Reasoning about
the bridge's write path further without new evidence would just be another
guess, so this instead reads the actual DataRef values X-Plane is holding,
straight from its Web API, on a plain timer - no bridge internals, no HID,
nothing this script could get wrong the same way.

Run this ALONGSIDE the normal bridge (it only does read-only GETs, so it
cannot interfere with anything). While it is running, move the yoke slowly,
the same tiny movement that showed the problem. The printed/CSV sequence of
timestamped values is the ground truth: if it climbs in a smooth staircase
of small steps, the bridge's write is fine and the choppiness must be
downstream (X-Plane/Zibo's own rendering of the value); if it holds flat for
stretches and then jumps, the write itself is still not smooth and the
bridge needs another look.

Usage:
    python tools/probe_moza_yoke_dataref.py [--seconds 15] [--interval 0.02] [--csv out.csv]

Requires X-Plane running with its Web API reachable at 127.0.0.1:8086 (the
same one the bridge uses). Does not require the bridge to be running,
though testing the real symptom means running both together.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request

API_ROOT = "http://127.0.0.1:8086"
DATAREF_NAMES = {
    "roll": "sim/joystick/yoke_roll_ratio",
    "pitch": "sim/joystick/yoke_pitch_ratio",
}


def http_json(url: str, timeout: float = 2.0):
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "MuslimSim-Probe/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def detect_api_version() -> str:
    caps = http_json(f"{API_ROOT}/api/capabilities")
    versions = caps.get("api", {}).get("versions", [])
    for preferred in ("v3", "v2", "v1"):
        if preferred in versions:
            return preferred
    raise RuntimeError(f"No supported X-Plane Web API version found. Capabilities: {caps}")


def resolve_dataref_id(api_version: str, name: str) -> int:
    query = urllib.parse.urlencode({"filter[name]": name, "limit": 100})
    payload = http_json(f"{API_ROOT}/api/{api_version}/datarefs?{query}")
    items = payload.get("data", [])
    if isinstance(items, dict):
        items = [items]
    for item in items:
        if isinstance(item, dict) and item.get("name") == name:
            return int(item["id"])
    raise RuntimeError(f"DataRef not found: {name}")


def read_dataref(api_version: str, dataref_id: int) -> float:
    payload = http_json(f"{API_ROOT}/api/{api_version}/datarefs/{dataref_id}/value", timeout=1.0)
    return float(payload["data"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=15.0, help="How long to capture (default: 15)")
    parser.add_argument("--interval", type=float, default=0.02, help="Seconds between polls (default: 0.02, ~50Hz)")
    parser.add_argument("--csv", default=None, help="Optional path to also write a CSV of every sample")
    args = parser.parse_args()

    try:
        api_version = detect_api_version()
    except Exception as exc:
        print(f"Could not reach X-Plane's Web API at {API_ROOT}: {exc}", file=sys.stderr)
        return 1

    ids = {}
    for key, name in DATAREF_NAMES.items():
        try:
            ids[key] = resolve_dataref_id(api_version, name)
            print(f"{key:5s} -> id {ids[key]} -> {name}")
        except Exception as exc:
            print(f"WARNING: could not resolve {name}: {exc}", file=sys.stderr)

    if not ids:
        print("Nothing resolved; is X-Plane actually running with an aircraft loaded?", file=sys.stderr)
        return 1

    csv_file = open(args.csv, "w", encoding="utf-8") if args.csv else None
    if csv_file:
        csv_file.write("elapsed_s," + ",".join(ids.keys()) + "\n")

    print(f"\nPolling every {args.interval*1000:.0f} ms for {args.seconds:.0f} s. Move the yoke now.\n")
    start = time.monotonic()
    last_values = {key: None for key in ids}
    try:
        while time.monotonic() - start < args.seconds:
            tick_start = time.monotonic()
            elapsed = tick_start - start
            values = {}
            for key, ref_id in ids.items():
                try:
                    values[key] = read_dataref(api_version, ref_id)
                except Exception as exc:
                    values[key] = None
                    print(f"  [{elapsed:6.3f}s] {key} read failed: {exc}")
            changed = any(
                last_values[key] is None or values[key] is None or abs(values[key] - last_values[key]) > 1e-6
                for key in ids
            )
            if changed:
                parts = " ".join(f"{key}={values[key]:+.5f}" for key in ids if values[key] is not None)
                print(f"[{elapsed:7.3f}s] {parts}")
            if csv_file:
                csv_file.write(
                    f"{elapsed:.4f}," + ",".join(
                        "" if values[key] is None else f"{values[key]:.6f}" for key in ids
                    ) + "\n"
                )
            last_values = values
            remaining = args.interval - (time.monotonic() - tick_start)
            if remaining > 0:
                time.sleep(remaining)
    except KeyboardInterrupt:
        pass
    finally:
        if csv_file:
            csv_file.close()
            print(f"\nWrote every sample to {args.csv}")

    print("\nDone. A smooth staircase of small steps means the write is fine and the")
    print("choppiness is downstream (X-Plane/Zibo's own rendering). Long flat stretches")
    print("followed by a jump means the write itself is still not smooth.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
