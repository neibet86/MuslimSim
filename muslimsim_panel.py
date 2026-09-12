#!/usr/bin/env python3
"""Desktop entry point for the simulator-independent MuslimSim hardware lab."""

from __future__ import annotations

import argparse
import json

from muslimsim.gui.studio import MuslimSimStudio
from muslimsim.hardware.lab import HardwareLab
from muslimsim.hardware.profiles import HardwareProfileStore
from muslimsim.gui.supervisor import default_profile_path


def main() -> int:
    parser = argparse.ArgumentParser(description="MuslimSim Hardware Laboratory")
    parser.add_argument("--check", action="store_true", help="Run catalog/profile checks without opening a window")
    parser.add_argument(
        "--readiness",
        action="store_true",
        help="Print clean-PC runtime/Windows driver readiness without opening Studio.",
    )
    parser.add_argument(
        "--readiness-json",
        action="store_true",
        help="Print clean-PC readiness as JSON without opening Studio.",
    )
    parser.add_argument(
        "--bootstrap-drivers",
        action="store_true",
        help=(
            "Install only missing reviewed local signed INF bundles embedded "
            "with MuslimSim; never downloads or installs cockpit applications."
        ),
    )
    args = parser.parse_args()

    if args.readiness or args.readiness_json or args.bootstrap_drivers:
        from muslimsim.hardware.windows_bootstrap import (
            clean_pc_readiness,
            format_readiness,
            install_missing_signed_drivers,
        )
        report = clean_pc_readiness()
        if args.readiness_json:
            print(json.dumps(report, indent=2))
        else:
            print(format_readiness(report))
        if args.bootstrap_drivers:
            print()
            result = install_missing_signed_drivers(readiness=report)
            print(result.get("message", ""))
            for item in result.get("results", ()):
                print(
                    f"  {item.get('key')}: "
                    f"{'OK' if item.get('ok') else 'NOT INSTALLED'} - "
                    f"{item.get('message')}"
                )
            return 0 if result.get("ok") else 3
        return 0 if report.get("ready") else 3
    if args.check:
        store = HardwareProfileStore(default_profile_path())
        store.load()
        result = HardwareLab(store).self_test()
        if not result["ok"]:
            print("Hardware lab check failed: " + "; ".join(result["errors"]))
            return 2
        print(f"Hardware lab check passed: {result['devices']} device definitions validated.")
        return 0
    MuslimSimStudio().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
