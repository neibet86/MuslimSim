"""Watch exactly what the PU FLT/LAND altitude windows gate on, live.

The PU shows its native ----- whenever the bridge decides no AC source is
confirmed, and exact Zibo numbers once it is.  That decision is made in
`bridge/final.py` from eight Zibo annunciators plus the APU running flag, and
when the panel reveals numbers at the wrong moment there is no way to see
which of those inputs caused it.

This prints two decisions side by side:

  CURRENT   the rule the bridge uses today -- the four transfer/source OFF
            annunciators being dark, plus a sticky "saw the OFF lamp lit once"
            latch per source.
  PROPOSED  positive source evidence only -- an AC source switch is ON and
            that source is actually available.

The reason for the second column: a dark OFF lamp is ambiguous.  It means
either "this bus has a source" or "nothing is driving this annunciator right
now".  On a cold aircraft with the APU running and the APU GEN switches still
off, all four read 0.000, so the current rule already believes both transfer
buses are fed and only the sticky latch is holding the dashes.

Run it, then do the sequence on the rig: battery on, APU start, APU GEN 1/2
on.  Every line is a change.  The line where the two columns disagree is the
bug, and the `-> NUMBERS` line is the instant the PU stops showing dashes.

It only reads.  It writes nothing to the aircraft, opens no serial port, and
touches no hardware, so it is safe to run beside a live bridge.
X-Plane must be running with the Web API enabled.

Usage:
    python tools/probe_pu_altitude_source.py
    python tools/probe_pu_altitude_source.py --log logs/pu_altitude_source.log
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_API_ROOT = "http://127.0.0.1:8086"

# Mirrors bridge/final.py PU_ALTITUDE_BUS_KEYS -- all four must be dark.
BUS_KEYS = ("trans_bus_1", "trans_bus_2", "source_off_1", "source_off_2")
# Mirrors bridge/final.py PU_ALTITUDE_SOURCE_KEYS.
SOURCE_KEYS = ("apu_gen_off", "gen_off_1", "gen_off_2", "ground_power")
MONITOR_KEYS = BUS_KEYS + SOURCE_KEYS

# The switch positions and availability flags the proposed rule uses.  These
# are not annunciators, so an unpowered annunciator bus cannot fake them.
EVIDENCE_KEYS = (
    "apu_gen1_pos",
    "apu_gen2_pos",
    "gen1_pos",
    "gen2_pos",
    "gpu_pos",
    "gen1_available",
    "gen2_available",
    "gpu_available",
    "apu_generator_on",
    "gpu_generator_on",
)

DATAREFS = {
    # --- the eight annunciators the current rule reads ---
    "trans_bus_1": "laminar/B738/annunciator/trans_bus_off1",
    "trans_bus_2": "laminar/B738/annunciator/trans_bus_off2",
    "source_off_1": "laminar/B738/annunciator/source_off1",
    "source_off_2": "laminar/B738/annunciator/source_off2",
    "apu_gen_off": "laminar/B738/annunciator/apu_gen_off_bus",
    "gen_off_1": "laminar/B738/annunciator/gen_off_bus1",
    "gen_off_2": "laminar/B738/annunciator/gen_off_bus2",
    "ground_power": "laminar/B738/annunciator/ground_power_avail",
    # --- APU running, shared by both rules ---
    "apu_running": "sim/cockpit2/electrical/APU_running",
    # --- positive source evidence ---
    "apu_gen1_pos": "laminar/B738/electrical/apu_gen1_pos",
    "apu_gen2_pos": "laminar/B738/electrical/apu_gen2_pos",
    "gen1_pos": "laminar/B738/electrical/gen1_pos",
    "gen2_pos": "laminar/B738/electrical/gen2_pos",
    "gpu_pos": "laminar/B738/electrical/gpu_pos",
    "gen1_available": "laminar/B738/electric/gen1_available",
    "gen2_available": "laminar/B738/electric/gen2_available",
    "gpu_available": "laminar/B738/gpu_available",
    "apu_generator_on": "sim/cockpit2/electrical/APU_generator_on",
    "gpu_generator_on": "sim/cockpit2/electrical/GPU_generator_on",
}

# Mirrors bridge/final.py PU_POWER_DATAREF_CANDIDATES, in the same order.
POWER_CANDIDATES = (
    ("dc_standby_bus", "laminar/B738/electric/dc_stdbus_status"),
    ("battery_on", "sim/cockpit2/electrical/battery_on"),
    ("avionics_on", "sim/cockpit/electrical/avionics_on"),
)
POWER_THRESHOLD = 0.5
APU_RUNNING_THRESHOLD = 0.5
SWITCH_THRESHOLD = 0.5


def http_json(url, timeout=4.0):
    request = urllib.request.Request(
        url, headers={"Accept": "application/json"}, method="GET"
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def detect_api_version(api_root):
    caps = http_json(api_root + "/api/capabilities")
    versions = caps.get("api", {}).get("versions", [])
    for preferred in ("v3", "v2", "v1"):
        if preferred in versions:
            return preferred
    raise RuntimeError("No supported Web API version. Capabilities: %r" % (caps,))


def resolve_dataref_id(api_root, api_version, name):
    query = urllib.parse.urlencode({"filter[name]": name, "limit": 100})
    try:
        payload = http_json(api_root + "/api/" + api_version + "/datarefs?" + query)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RuntimeError("DataRef not found: " + name)
        raise
    items = payload.get("data", [])
    if isinstance(items, dict):
        items = [items]
    for item in items:
        if isinstance(item, dict) and item.get("name") == name:
            return int(item["id"])
    raise RuntimeError("DataRef not found: " + name)


def unwrap_value(payload):
    data = payload.get("data") if isinstance(payload, dict) else payload
    if isinstance(data, list):
        return float(data[0]) if data else math.nan
    return float(data)


def read_dataref(api_root, api_version, ref_id):
    return unwrap_value(
        http_json(
            api_root + "/api/" + api_version + "/datarefs/"
            + str(ref_id) + "/value",
            timeout=0.35,
        )
    )


def light_is_on(value):
    """Zibo reports lamp brightness, so a lit lamp can be 0.10 -- not 0.5."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(numeric) and numeric > 0.01


def switch_on(value):
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(numeric) and numeric >= SWITCH_THRESHOLD


def buses_ready(values):
    """True only when all four transfer/source OFF lamps are dark."""
    for key in BUS_KEYS:
        try:
            value = float(values[key])
        except (KeyError, TypeError, ValueError):
            return False
        if not math.isfinite(value) or light_is_on(value):
            return False
    return True


class Emitter:
    def __init__(self, log_path):
        self.handle = None
        if log_path:
            self.handle = open(log_path, "a", encoding="utf-8")

    def __call__(self, text):
        stamp = _dt.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        line = stamp + "  " + text
        print(line, flush=True)
        if self.handle is not None:
            self.handle.write(line + "\n")
            self.handle.flush()

    def close(self):
        if self.handle is not None:
            self.handle.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-root", default=DEFAULT_API_ROOT)
    ap.add_argument("--api-version", default=None)
    ap.add_argument("--interval", type=float, default=0.10)
    ap.add_argument("--log", default=None, help="also append output to this file")
    a = ap.parse_args()

    api_root = a.api_root.rstrip("/")
    say = Emitter(a.log)

    try:
        api_version = a.api_version or detect_api_version(api_root)
    except Exception as exc:
        print(
            "Cannot reach the X-Plane Web API at " + api_root + ": " + str(exc),
            file=sys.stderr,
        )
        say.close()
        return 1

    say("PU altitude source probe -- read only -- " + api_root + " " + api_version)

    ids = {}
    for key, name in DATAREFS.items():
        try:
            ids[key] = resolve_dataref_id(api_root, api_version, name)
        except Exception as exc:
            say("UNRESOLVED %-18s %s  (%s)" % (key, name, exc))

    power_key = None
    power_id = None
    for key, name in POWER_CANDIDATES:
        try:
            power_id = resolve_dataref_id(api_root, api_version, name)
            power_key = key
            break
        except Exception:
            continue
    if power_id is None:
        say("No PU aircraft-power dataref resolved; treating as unpowered.")
    else:
        say("Aircraft power source: " + str(power_key))

    say("Do the sequence now: BAT ON -> APU START -> APU GEN 1/2 ON")
    say("-" * 78)

    # The same sticky latches the bridge keeps today.
    confirmed = False
    saw = {
        "apu_gen_off": False,
        "gen_off_1": False,
        "gen_off_2": False,
        "ground_power": False,
    }
    last_signature = None
    disagreements = 0

    all_keys = MONITOR_KEYS + EVIDENCE_KEYS + ("apu_running",)

    try:
        while True:
            values = {}
            for key in all_keys:
                if key not in ids:
                    values[key] = math.nan
                    continue
                try:
                    values[key] = read_dataref(api_root, api_version, ids[key])
                except Exception:
                    values[key] = math.nan

            powered = False
            if power_id is not None:
                try:
                    raw = read_dataref(api_root, api_version, power_id)
                    powered = math.isfinite(raw) and raw >= POWER_THRESHOLD
                except Exception:
                    powered = False

            apu_raw = values.get("apu_running", math.nan)
            apu_running = bool(
                math.isfinite(apu_raw) and apu_raw >= APU_RUNNING_THRESHOLD
            )

            # ---------- CURRENT rule, as bridge/final.py computes it ----------
            if not powered:
                confirmed = False
                for k in saw:
                    saw[k] = False
                core_ready = False
                connected = {
                    "apu": False, "gen1": False, "gen2": False, "grd": False,
                }
            else:
                core_ready = buses_ready(values)
                apu_gen_off = light_is_on(values.get("apu_gen_off", math.nan))
                gen1_off = light_is_on(values.get("gen_off_1", math.nan))
                gen2_off = light_is_on(values.get("gen_off_2", math.nan))
                grd_avail = light_is_on(values.get("ground_power", math.nan))

                if apu_gen_off:
                    saw["apu_gen_off"] = True
                if gen1_off:
                    saw["gen_off_1"] = True
                if gen2_off:
                    saw["gen_off_2"] = True
                if grd_avail:
                    saw["ground_power"] = True

                connected = {
                    "apu": bool(
                        apu_running and core_ready
                        and saw["apu_gen_off"] and not apu_gen_off
                    ),
                    "gen1": bool(
                        core_ready and saw["gen_off_1"] and not gen1_off
                    ),
                    "gen2": bool(
                        core_ready and saw["gen_off_2"] and not gen2_off
                    ),
                    "grd": bool(
                        core_ready and saw["ground_power"] and not grd_avail
                    ),
                }

                if not core_ready:
                    confirmed = False
                elif any(connected.values()):
                    confirmed = True

            current_powered = bool(core_ready and confirmed)

            # ---------- PROPOSED rule: positive source evidence only ----------
            apu_gen_selected = (
                switch_on(values.get("apu_gen1_pos", math.nan))
                or switch_on(values.get("apu_gen2_pos", math.nan))
            )
            proposed = {
                "apu": bool(apu_gen_selected and apu_running),
                "gen1": bool(
                    switch_on(values.get("gen1_pos", math.nan))
                    and switch_on(values.get("gen1_available", math.nan))
                ),
                "gen2": bool(
                    switch_on(values.get("gen2_pos", math.nan))
                    and switch_on(values.get("gen2_available", math.nan))
                ),
                "grd": bool(
                    switch_on(values.get("gpu_pos", math.nan))
                    and switch_on(values.get("gpu_available", math.nan))
                ),
            }
            proposed_powered = bool(powered and any(proposed.values()))

            signature = (
                powered, apu_running, core_ready, confirmed, current_powered,
                proposed_powered,
                tuple(light_is_on(values.get(k, math.nan)) for k in MONITOR_KEYS),
                tuple(switch_on(values.get(k, math.nan)) for k in EVIDENCE_KEYS),
                tuple(connected[k] for k in ("apu", "gen1", "gen2", "grd")),
                tuple(proposed[k] for k in ("apu", "gen1", "gen2", "grd")),
            )
            if signature != last_signature:
                last_signature = signature
                cur_why = ",".join(
                    n for n in ("apu", "gen1", "gen2", "grd") if connected[n]
                ) or "none"
                pro_why = ",".join(
                    n for n in ("apu", "gen1", "gen2", "grd") if proposed[n]
                ) or "none"
                flag = ""
                if current_powered != proposed_powered:
                    disagreements += 1
                    flag = "   <<< RULES DISAGREE"
                say(
                    "CURRENT  %-8s core_bus_ready=%d confirmed=%d via=%s"
                    % (
                        "NUMBERS" if current_powered else "DASHES",
                        core_ready, confirmed, cur_why,
                    )
                )
                say(
                    "PROPOSED %-8s power=%d apu_run=%d via=%s%s"
                    % (
                        "NUMBERS" if proposed_powered else "DASHES",
                        powered, apu_running, pro_why, flag,
                    )
                )
                say(
                    "   lamps  "
                    + " ".join(
                        "%s=%.3f" % (k, values.get(k, math.nan))
                        for k in MONITOR_KEYS
                    )
                )
                say(
                    "   switch "
                    + " ".join(
                        "%s=%.0f" % (k, values.get(k, math.nan))
                        for k in EVIDENCE_KEYS
                    )
                )
                say(
                    "   saw    "
                    + " ".join("%s=%d" % (k, saw[k]) for k in sorted(saw))
                )
                say("")

            time.sleep(max(0.02, a.interval))
    except KeyboardInterrupt:
        say("stopped after %d disagreement(s) between the two rules"
            % disagreements)
        return 0
    finally:
        say.close()


if __name__ == "__main__":
    raise SystemExit(main())
