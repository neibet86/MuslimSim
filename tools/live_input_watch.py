#!/usr/bin/env python3
"""
Watch physical control input arriving at the bridge, live.

Read-only: it asks the running bridge for status and prints controls whose
value changed. Use it to prove the hardware->bridge half works, separately
from whether Studio is drawing it.

    py tools/live_input_watch.py            watch everything
    py tools/live_input_watch.py moza tca   only devices matching these words
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from muslimsim.platform.locator import read_locator
from muslimsim.control.client import ControlClient, ControlClientError


def main() -> None:
    filters = [a.lower() for a in sys.argv[1:]]
    loc = read_locator()
    if not loc:
        raise SystemExit("Bridge is not running (no locator). Start MuslimSim Studio first.")
    client = ControlClient(int(loc["port"]), str(loc["token"]), timeout=8.0)
    print(f"bridge pid {loc.get('pid')} port {loc.get('port')} — move a control. Ctrl+C to stop.\n")

    seen: dict[tuple[str, str], object] = {}
    first = True
    while True:
        try:
            lab = client.request("status").get("lab") or {}
        except ControlClientError as exc:
            print(f"  [control channel] {exc}")
            time.sleep(1.0)
            continue
        for device, controls in sorted((lab.get("inputs") or {}).items()):
            if filters and not any(f in device.lower() for f in filters):
                continue
            for control, sample in sorted(controls.items()):
                if not isinstance(sample, dict):
                    continue
                value = sample.get("value")
                key = (device, control)
                if key in seen and seen[key] == value:
                    continue
                if not first:
                    print(f"  {time.strftime('%H:%M:%S')}  {device:<18} {control:<22} = {value}")
                seen[key] = value
        if first:
            print(f"  baseline captured: {len(seen)} controls being tracked\n")
            first = False
        time.sleep(0.1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped.")
