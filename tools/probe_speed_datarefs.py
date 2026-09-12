"""Ask the running X-Plane which speed-band datarefs this aircraft publishes.

The PFD's speed-awareness bands - the red barber poles, the amber minimum
manoeuvre band, and the flap manoeuvring bugs - are only safe to draw from the
aircraft's own numbers.  Guessing a dataref name would either draw nothing or,
far worse, draw a band at a speed that is not the aeroplane's.

This tool reads X-Plane's own dataref catalogue over the Web API the bridge
already uses, lists everything that looks like a speed limit or a flap
setting, and shows what each one currently reads.  Run it with the aircraft
loaded and it will name the exact datarefs to wire up.

It only reads.  It writes nothing to the simulator and touches no hardware.

Usage:
    python tools/probe_speed_datarefs.py
    python tools/probe_speed_datarefs.py --match vref --match flap
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.core.engine import _load_engine

# What the PFD needs, and the words the aircraft is likely to use for it.
WANTED = (
    ("maximum speed (VMO/MMO barber pole)", ("vmo", "mmo", "max_speed", "maxspeed", "vne", "overspeed")),
    ("minimum speed (stick shaker / red band)", ("vls", "min_speed", "minspeed", "stick", "shaker", "vs_", "stall")),
    ("minimum manoeuvre (amber band)", ("manouver", "maneuver", "manoeuvre", "min_man", "amber")),
    ("flap manoeuvring speeds", ("flap_speed", "flaps_speed", "vfe", "flap_manouver", "flap_maneuver")),
    ("reference speeds", ("vref", "v1", "vr_", "v2_", "vspeed", "v_speed")),
    ("flap position", ("flap_lever", "flap_handle", "flap_ratio", "flap_deploy")),
    ("speed tape extras", ("speed_tape", "speed_bug", "spd_bug", "trend")),
)


def catalogue(bridge, api_version: str) -> list[dict]:
    """Every dataref the simulator is currently publishing."""
    payload = bridge.http_json(f"{bridge.API_ROOT}/api/{api_version}/datarefs")
    items = payload.get("data", [])
    return [item for item in items if isinstance(item, dict) and item.get("name")]


def value_of(bridge, api_version: str, item: dict) -> str:
    try:
        raw = bridge.http_json(
            f"{bridge.API_ROOT}/api/{api_version}/datarefs/{int(item['id'])}/value"
        )
        data = raw.get("data") if isinstance(raw, dict) else raw
        if isinstance(data, list):
            return "[" + ", ".join(f"{float(entry):g}" for entry in data[:8]) + "]"
        return f"{float(data):g}"
    except Exception as error:  # a write-only or non-numeric dataref is fine
        return f"({type(error).__name__})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--match", action="append", default=[],
                        help="Extra keyword to search for; repeatable.")
    parser.add_argument("--all-b738", action="store_true",
                        help="List every laminar/B738 dataref instead of filtering.")
    args = parser.parse_args()

    bridge = _load_engine()
    try:
        api_version = bridge.detect_api_version()
    except Exception as error:
        print("X-Plane's Web API did not answer on 127.0.0.1:8086.")
        print(f"  {type(error).__name__}: {error}")
        print("Start X-Plane with the aircraft loaded, then run this again.")
        return 1

    print(f"X-Plane Web API {api_version}")
    items = catalogue(bridge, api_version)
    print(f"{len(items)} datarefs published\n")

    if args.all_b738:
        for item in sorted(items, key=lambda entry: entry["name"]):
            if item["name"].startswith("laminar/B738"):
                print(f"  {item['name']}")
        return 0

    seen: set[str] = set()
    for heading, keywords in WANTED:
        matches = [
            item for item in items
            if any(word in item["name"].lower() for word in keywords)
            and ("laminar" in item["name"] or "sim/aircraft" in item["name"]
                 or "sim/cockpit" in item["name"] or "sim/flightmodel" in item["name"])
        ]
        print(f"{heading}:")
        if not matches:
            print("  nothing found")
        for item in sorted(matches, key=lambda entry: entry["name"])[:14]:
            marker = " " if item["name"] not in seen else "*"
            seen.add(item["name"])
            print(f" {marker} {item['name']:<62} = {value_of(bridge, api_version, item)}")
        print()

    for word in args.match:
        matches = [item for item in items if word.lower() in item["name"].lower()]
        print(f"matching {word!r}:")
        for item in sorted(matches, key=lambda entry: entry["name"])[:30]:
            print(f"   {item['name']:<62} = {value_of(bridge, api_version, item)}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
