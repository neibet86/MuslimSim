"""Show one display-only MuslimSim PFD preview on the WinCtrl PFP screen.

This opens only the PFP display HID device.  It does not connect to X-Plane,
open COM5, change throttle, send a switch command, or write to any simulator
DataRef.  Close PU CONNECT MSFS first so it does not own the PFP screen.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.core.engine import _load_engine


NORMAL = {
    "ias": 175.0,
    "altitude": 2400.0,
    "vertical_speed": 600.0,
    "pitch": 5.0,
    "roll": -12.5,
    "heading": 320.0,
    "target_ias": 200.0,
    "target_heading": 350.0,
    "target_altitude": 2800.0,
    "target_ias_is_mach": 0.0,
    "target_ias_visible": 1.0,
    "baro": 29.92,
    "baro_hpa": 0.0,
    "baro_std": 0.0,
    "fd_pitch": 2.5,
    "fd_roll": -5.0,
    "fd_pitch_visible": 1.0,
    "fd_roll_visible": 1.0,
    "fd_command": 2.0,
    "fd_command_visible": 1.0,
    "land_mode": 0.0,
    "fma_speed": 4.0,
    "fma_lateral": 3.0,
    "fma_vertical": 9.0,
}


APPROACH = {
    **NORMAL,
    "ias": 141.0,
    "altitude": 1800.0,
    "vertical_speed": -700.0,
    "pitch": -1.0,
    "roll": -2.0,
    "heading": 90.0,
    "target_ias": 145.0,
    "target_heading": 92.0,
    "target_altitude": 2000.0,
    "fma_speed": 3.0,
    "fma_lateral": 2.0,
    "fma_vertical": 5.0,
    "land_mode": 2.0,
}


def scenario_values(name: str) -> dict[str, float]:
    if name == "offline":
        return {}
    if name == "bands":
        # Real Zibo band values, read from the running aircraft with
        # tools/probe_speed_datarefs.py, on an approach with flaps out.
        return {
            **NORMAL, "ias": 172.0, "altitude": 2400.0, "vertical_speed": -700.0,
            "pitch": 1.0, "roll": 0.0, "heading": 320.0, "target_ias": 165.0,
            "min_speed": 147.5, "min_speed_show": 1.0,
            "min_maneuver_speed": 153.3, "min_maneuver_speed_show": 1.0,
            "max_maneuver_speed": 220.0, "max_maneuver_speed_show": 1.0,
            "max_speed": 230.0, "max_speed_show": 1.0,
            "flaps_speed": 205.0, "vref_speed": 152.0, "flap_lever": 0.625,
            "speed_trend": -3.4,
        }
    if name == "takeoff-bugs":
        # V-speeds set in the FMC, flaps 5, accelerating through 120 kt.
        return {
            **NORMAL, "ias": 120.0, "altitude": 40.0, "vertical_speed": 0.0,
            "pitch": 0.5, "roll": 0.0, "heading": 320.0, "target_ias": 160.0,
            "min_speed": 96.0, "min_speed_show": 1.0,
            "min_maneuver_speed": 104.0, "min_maneuver_speed_show": 1.0,
            "max_maneuver_speed": 245.0, "max_maneuver_speed_show": 1.0,
            "max_speed": 255.0, "max_speed_show": 1.0,
            "v1_speed": 138.0, "vr_speed": 142.0, "v2_speed": 148.0,
            "flaps_speed": 190.0, "flap_lever": 0.375, "speed_trend": 4.5,
        }
    if name == "zero":
        # Everything at rest: a level horizon, no bank, zero on every scale.
        return {
            **NORMAL, "ias": 0.0, "altitude": 0.0, "vertical_speed": 0.0, "pitch": 0.0,
            "roll": 0.0, "heading": 0.0, "target_ias": 0.0, "target_altitude": 0.0,
            "target_heading": 0.0,
        }
    if name == "extreme":
        # Every scale at its limit at once, which is where a zone that cannot
        # hold its own longest label shows up.
        return {
            **NORMAL, "ias": 999.0, "altitude": 41000.0, "vertical_speed": 6000.0,
            "pitch": 25.0, "roll": -45.0, "heading": 359.0, "target_ias": 999.0,
            "target_altitude": 41000.0, "target_heading": 180.0, "baro_hpa": 1.0,
            "minimums": 39000.0,
        }
    if name == "below-sea-level":
        # An aerodrome below sea level, descending hard, on radio minimums.
        return {
            **NORMAL, "ias": 140.0, "altitude": -200.0, "vertical_speed": -6000.0,
            "pitch": -25.0, "roll": 45.0, "heading": 90.0, "target_altitude": 100.0,
            "minimums": 50.0, "minimums_is_radio": 1.0, "radio_altitude": 20.0,
        }
    if name == "minimums":
        # Barometric minimums set and still above them: green reference and a
        # green pointer on the altitude tape.
        return {**APPROACH, "minimums": 1500.0, "minimums_is_radio": 0.0}
    if name == "minimums-reached":
        # At or below the setting: the same indications turn amber.
        return {
            **APPROACH,
            "altitude": 1460.0,
            "minimums": 1500.0,
            "minimums_is_radio": 0.0,
            "baro_hpa": 1.0,
        }
    if name == "radio-minimums":
        # A radio height cannot be shown on a barometric tape, so the
        # reference is annunciated as text only.
        return {
            **APPROACH,
            "altitude": 900.0,
            "radio_altitude": 380.0,
            "minimums": 200.0,
            "minimums_is_radio": 1.0,
            "baro_std": 0.0,
        }
    if name == "high":
        return {
            **NORMAL,
            "ias": 282.0,
            "altitude": 28000.0,
            "vertical_speed": -1800.0,
            "pitch": -3.0,
            "roll": 18.0,
            "heading": 5.0,
            "target_ias": 0.78,
            "target_heading": 350.0,
            "target_altitude": 30000.0,
            "target_ias_is_mach": 1.0,
            "baro": 29.92,
            "baro_hpa": 1.0,
            "fma_speed": 6.0,
            "fma_lateral": 1.0,
            "fma_vertical": 4.0,
            "land_mode": 2.0,
        }
    if name == "low":
        return {
            **NORMAL,
            "ias": 140.0,
            "altitude": 615.0,
            "vertical_speed": 300.0,
            "pitch": 2.0,
            "roll": 0.0,
            "heading": 90.0,
            "target_ias": 145.0,
            "target_heading": 95.0,
            "target_altitude": 1000.0,
            "baro_std": 0.0,
            "fma_speed": 3.0,
            "fma_lateral": 2.0,
            "fma_vertical": 5.0,
        }
    return dict(NORMAL)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=("normal", "high", "low", "offline", "minimums", "minimums-reached",
                 "radio-minimums", "zero", "extreme", "below-sea-level",
                 "bands", "takeoff-bugs"),
        default="normal",
        help="PFD condition to show (default: normal).",
    )
    args = parser.parse_args()
    bridge = _load_engine()
    device = None
    try:
        device, canvas = bridge._open_pfp_pfd_display()
        bridge._pfp_write_graphical_pfd(device, canvas, scenario_values(args.scenario))
    finally:
        if device is not None:
            device.close()
    print(f"MuslimSim display-only PFD preview sent: {args.scenario}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
