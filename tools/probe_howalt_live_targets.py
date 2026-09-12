"""Ask the running aircraft which HOWALT live targets actually exist.

Three D201/D203 controls have no verified aircraft target, so MuslimSim
deliberately refuses to guess one:

  * the D201 VHF3 window, which currently blanks rather than showing COM1;
  * the D203 XPNDR source switch, labelled ATC 1/2 in the aircraft;
  * the D203 ALT source switch, labelled ALT 1/2 in the aircraft.

Guessing a DataRef name for those is how a panel ends up confidently driving
the wrong thing, so this asks the simulator instead.  It also re-checks the
NAV commands the D201 lower encoders and transfer key already use, because
"the NAV knobs do nothing" and "these command names are not in this aircraft"
look identical from the cockpit.

The DataRef search pages the whole inventory and filters locally.  It does not
use `filter[name]`, which is an exact-match filter that returns HTTP 404 on a
partial name and so cannot be used to discover anything.

It only reads.  It writes nothing to the aircraft, opens no serial port and
touches no hardware, so it is safe to run beside a live bridge.  X-Plane must
be running, with the Web API enabled and the aircraft loaded.

Usage:
    py tools/probe_howalt_live_targets.py
    py tools/probe_howalt_live_targets.py --term vhf3 --term datalink
    py tools/probe_howalt_live_targets.py --log logs/howalt_live_targets.log
"""

from __future__ import annotations

import argparse
import importlib.util
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Sequence

PROJECT = Path(__file__).resolve().parents[1]

# Substring searches, grouped by the question each one answers.  These are
# search terms, not claims that any of them exist.
DATAREF_TERMS: Dict[str, Sequence[str]] = {
    "D201 VHF3 / third COM": ("vhf3", "vhf_3", "com3", "com_3", "datalink", "acars"),
    "D203 ATC (XPNDR) source 1/2": ("transponder_source", "xpdr_source",
                                    "xpndr_source", "atc_source", "transponder_su"),
    "D203 ALT source 1/2": ("alt_source", "altitude_source", "alt_su"),
    "Anything mentioning ATC or XPDR": ("/atc", "atc_", "_atc", "xpdr", "xpndr"),
    "Every Zibo toggle switch (ATC 1/2 and ALT 1/2 may be in here)":
        ("b738/toggle_switch/",),
    "Every Zibo knob and selector": ("b738/knob/", "b738/selector"),
    "Transponder, for reference": ("transponder",),
}

COMMAND_TERMS: Dict[str, Sequence[str]] = {
    "NAV commands the D201 already uses": (
        "nav1_standy_flip", "stby_nav1_coarse_up", "stby_nav1_coarse_down",
        "stby_nav1_fine_up", "stby_nav1_fine_down",
    ),
    "Zibo's own NAV controls": ("b738/push_button/switch_freq_nav",
                                "b738/knob/nav", "b738/comm/nav"),
    "D203 source select": ("transponder_source", "xpdr_source", "alt_source",
                           "b738/toggle_switch/"),
    "Zibo transponder, for reference": ("transponder_mode", "transponder_pos"),
}

MAX_DATAREFS = 200000
PAGE = 1000


def _load_bridge() -> Any:
    path = PROJECT / "bridge" / "final.py"
    if not path.exists():
        raise SystemExit(f"Bridge engine not found: {path}")
    spec = importlib.util.spec_from_file_location("_howalt_probe_bridge", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _all_datarefs(bridge: Any, version: str) -> List[Dict[str, Any]]:
    """Page the whole DataRef inventory; filtering happens locally."""
    total: int | None = None
    try:
        payload = bridge.http_json(
            f"{bridge.API_ROOT}/api/{version}/datarefs/count", timeout=5.0
        )
        data = payload.get("data") if isinstance(payload, dict) else payload
        total = max(0, min(MAX_DATAREFS, int(data)))
    except Exception:
        total = None

    items: List[Dict[str, Any]] = []
    start = 0
    while start < MAX_DATAREFS:
        query = urllib.parse.urlencode({"start": start, "limit": PAGE})
        try:
            payload = bridge.http_json(
                f"{bridge.API_ROOT}/api/{version}/datarefs?{query}", timeout=15.0
            )
        except Exception as exc:
            if start == 0:
                raise RuntimeError(f"DataRef listing failed: {exc}") from exc
            break
        chunk = payload.get("data", []) if isinstance(payload, dict) else []
        if isinstance(chunk, dict):
            chunk = [chunk]
        if not isinstance(chunk, list) or not chunk:
            break
        items.extend(c for c in chunk if isinstance(c, dict))
        start += len(chunk)
        if len(chunk) < PAGE:
            break
        if total is not None and start >= total:
            break
    return items


def _value_of(bridge: Any, version: str, ref_id: int) -> str:
    try:
        return f"{bridge.read_dataref(version, ref_id, timeout=0.5):g}"
    except TypeError:
        try:
            return f"{bridge.read_dataref(version, ref_id):g}"
        except Exception:
            return "?"
    except Exception:
        return "?"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--term", action="append", default=[],
                        help="extra substring to search for (repeatable)")
    parser.add_argument("--max-hits", type=int, default=250,
                        help="most matches to print per group (default 250)")
    parser.add_argument("--log", default="", help="also write this report to a file")
    args = parser.parse_args(argv)

    lines: List[str] = []

    def say(text: str = "") -> None:
        print(text)
        lines.append(text)

    bridge = _load_bridge()
    try:
        version = bridge.detect_api_version()
    except Exception as exc:
        raise SystemExit(
            f"Could not reach the X-Plane Web API at {bridge.API_ROOT}: {exc}\n"
            "Start X-Plane, load the aircraft, and enable the Web API."
        )
    say(f"X-Plane Web API {version} at {bridge.API_ROOT}")
    try:
        say(f"Aircraft: {bridge._read_active_aircraft_path(version)}")
    except Exception:
        say("Aircraft: unknown")
    say()

    say("=" * 70)
    say("DATAREFS")
    say("=" * 70)
    try:
        refs = _all_datarefs(bridge, version)
    except Exception as exc:
        say(f"    ! {exc}")
        refs = []
    say(f"    {len(refs)} DataRefs in the loaded aircraft")

    groups = dict(DATAREF_TERMS)
    if args.term:
        groups["Extra terms"] = tuple(args.term)

    index = [(str(r.get("name", "")).lower(), r) for r in refs]
    for title, terms in groups.items():
        say(f"\n{title}")
        low = [t.lower() for t in terms]
        hits = sorted(
            {name: item for name, item in index if any(t in name for t in low)}.items()
        )
        if not hits:
            say("    (nothing matched - this aircraft publishes no such DataRef)")
            continue
        for name, item in hits[: args.max_hits]:
            ref_id = item.get("id")
            flag = "rw" if item.get("is_writable") else "ro"
            value = _value_of(bridge, version, int(ref_id)) if ref_id is not None else "?"
            say(f"    {flag}  {item.get('name')}  = {value}")
        if len(hits) > args.max_hits:
            say(f"    ... and {len(hits) - args.max_hits} more (raise --max-hits)")

    say()
    say("=" * 70)
    say("COMMANDS")
    say("=" * 70)
    try:
        commands = bridge._muslimsim_list_live_commands(version)
    except Exception as exc:
        say(f"    ! command inventory unavailable: {exc}")
        commands = []
    say(f"    {len(commands)} commands in the loaded aircraft\n")
    names = [str(c.get("name", "")) for c in commands]
    for title, terms in COMMAND_TERMS.items():
        say(f"{title}")
        low = [t.lower() for t in terms]
        hits = sorted({n for n in names if any(t in n.lower() for t in low)})
        if hits:
            for name in hits[: args.max_hits]:
                say(f"    {name}")
            if len(hits) > args.max_hits:
                say(f"    ... and {len(hits) - args.max_hits} more")
        else:
            say("    (nothing matched)")
        say()

    say("Read-only probe finished.  Nothing was written to the aircraft.")

    if args.log:
        out = Path(args.log)
        if not out.is_absolute():
            out = PROJECT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nSaved to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
