#!/usr/bin/env python3
"""Read-only clean-PC readiness report for MuslimSim."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muslimsim.hardware.windows_bootstrap import clean_pc_readiness, format_readiness


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = clean_pc_readiness(ROOT, include_sdl=False)
    print(json.dumps(report, indent=2) if args.json else format_readiness(report))
    return 0 if report["ready"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
