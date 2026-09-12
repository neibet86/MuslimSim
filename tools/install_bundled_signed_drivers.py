#!/usr/bin/env python3
"""Install only reviewed signed driver bundles embedded with MuslimSim.

No network download. No manufacturer cockpit application. No unsigned driver.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muslimsim.hardware.windows_bootstrap import (
    clean_pc_readiness,
    format_readiness,
    install_missing_signed_drivers,
)


def main() -> int:
    report = clean_pc_readiness(ROOT, include_sdl=False)
    print(format_readiness(report))
    print()
    result = install_missing_signed_drivers(ROOT, readiness=report)
    print(result["message"])
    for item in result.get("results", ()):
        print(
            f"{item.get('key')}: "
            f"{'OK' if item.get('ok') else 'NOT INSTALLED'} - "
            f"{item.get('message')}"
        )
    return 0 if result.get("ok") else 3


if __name__ == "__main__":
    raise SystemExit(main())
