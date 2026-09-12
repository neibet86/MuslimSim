"""Check every dataref and command the PDC binds to against the aircraft.

The PDC's control map comes from the hardware -- `tools/probe_pdc_bb62.py`
watches which bit moves when a control is operated, so it cannot be wrong
about the panel.  The Zibo names it writes to cannot be captured that way,
and a name that does not exist fails silently: the control simply does
nothing, with no clue as to why.

This resolves all of them against the running aircraft and says which are
real.  Run it after a Zibo update, or whenever a PDC control is dead.

One name is worth knowing about: the minimums entries use
`EFIS_control/cpt/`, with no `a`, while their siblings use
`EFIS_control/capt/`.  That is Zibo's own spelling, confirmed here, not a
typo to be tidied away.

It only reads.  It writes nothing to the aircraft and opens no hardware.
X-Plane must be running with the Web API enabled.

Usage:
    python tools/probe_pdc_datarefs.py
    python tools/probe_pdc_datarefs.py --api-root http://127.0.0.1:8086
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

DEFAULT_API_ROOT = "http://127.0.0.1:8086"
DEFAULT_API_VERSION = "v2"


def _exists(api_root: str, api_version: str, kind: str, name: str):
    """True/False if the endpoint answered, None if it could not be reached."""
    query = urllib.parse.urlencode({"filter[name]": name, "limit": 100})
    url = f"{api_root}/api/{api_version}/{kind}?{query}"

    try:
        request = urllib.request.Request(
            url, headers={"Accept": "application/json"}, method="GET"
        )

        with urllib.request.urlopen(request, timeout=4.0) as response:
            payload = json.loads(response.read().decode("utf-8"))

    except Exception:
        return None

    items = payload.get("data", [])

    if isinstance(items, dict):
        items = [items]

    return any(
        isinstance(item, dict) and item.get("name") == name for item in items
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-root", default=DEFAULT_API_ROOT)
    parser.add_argument("--api-version", default=DEFAULT_API_VERSION)
    args = parser.parse_args()

    api_root = str(args.api_root).rstrip("/")

    try:
        from muslimsim.devices.pdc_bb62 import (
            PDC_ZIBO_COMMANDS,
            PDC_ZIBO_EFIS_DATAREFS,
        )
    except Exception as exc:
        print(f"Could not import the PDC module: {exc}")
        return 2

    groups = (
        ("DATAREFS", "datarefs", PDC_ZIBO_EFIS_DATAREFS),
        ("COMMANDS", "commands", PDC_ZIBO_COMMANDS),
    )

    unreachable = 0
    missing = []

    for title, kind, table in groups:
        print(f"\n{title}")

        for key, name in table.items():
            found = _exists(api_root, args.api_version, kind, name)

            if found is None:
                unreachable += 1
                mark = "NO API"
            elif found:
                mark = "ok"
            else:
                mark = "MISSING"
                missing.append((key, name))

            print(f"  {mark:<8} {key:<12} {name}")

    print()

    if unreachable:
        print(f"{unreachable} lookups could not reach {api_root}.")
        print("Is X-Plane running with its Web API enabled?")
        return 2

    if not missing:
        total = sum(len(table) for _, _, table in groups)
        print(f"All {total} names exist on this aircraft.")
        return 0

    print(f"{len(missing)} names do not exist -- these controls stay inert:")

    for key, name in missing:
        print(f"    {key:<12} {name}")

    print()
    print("A missing name usually means the aircraft is not Zibo, or Zibo")
    print("renamed it.  Search the new name and update the table in")
    print("muslimsim/devices/pdc_bb62.py.")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
