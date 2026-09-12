"""Render every coded BB35/BB36 display page without opening hardware.

The PNG files produced here are QA snapshots only.  The live implementation
continues to draw native rectangles and text commands and never loads images.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.devices import nd_renderer, pfp_renderer, systems_renderer
from render_pfp_frame_png import PfpFrame


def _save(output: Path, name: str, draw) -> None:
    frame = PfpFrame()
    draw(frame)
    path = output / f"coded-{name}.png"
    frame.image.save(path, "PNG", optimize=True)
    print(f"{path} ({frame.fills} fills, {frame.texts} text runs)")


def _pfd_values() -> dict:
    return {
        "power": 1.0, "dc_standby_bus": 1.0,
        "ias": 164.0, "target_ias": 170.0, "target_ias_visible": 1.0,
        "altitude": 2440.0, "target_altitude": 3000.0,
        "vertical_speed": 820.0, "pitch": 2.6, "roll": -7.0,
        "heading": 274.0, "target_heading": 280.0,
        "baro": 29.92, "baro_hpa": 0.0, "baro_std": 0.0,
        "fd_pitch": 3.0, "fd_roll": -2.0, "fd_pitch_visible": 1.0,
        "fd_roll_visible": 1.0, "fd_command": 1.0,
        "fd_command_visible": 1.0, "land_mode": 0.0,
        "fma_speed": 3.0, "fma_lateral": 4.0, "fma_vertical": 5.0,
        "fma_lateral_armed": 1.0, "fma_vertical_armed": 5.0,
        "max_speed": 335.0, "min_speed": 122.0, "min_speed_show": 1.0,
        "max_maneuver_speed": 225.0, "max_maneuver_speed_show": 1.0,
        "min_maneuver_speed": 145.0, "min_maneuver_speed_show": 1.0,
        "speed_trend": 0.6, "flaps_speed": 190.0, "flap_lever": 0.25,
        "v1_speed": 142.0, "vr_speed": 147.0, "v2_speed": 153.0,
        "vref_speed": 138.0, "mach": 0.62, "radio_altitude": 420.0,
        "minimums": 200.0, "minimums_mode": 0.0,
        "field_elevation": 610.0, "slip_skid": 0.4,
        "localizer_deviation": -0.3, "glideslope_deviation": 0.2,
        "localizer_valid": 1.0, "glideslope_valid": 1.0,
        "approach_mode": 1.0, "nav_identifier": "IABC",
        "nav_frequency": 11030.0, "marker_outer": 1.0,
        "fpv_on": 1.0, "fpv_horizontal": 2.0, "fpv_vertical": -12.0,
        "stall_pitch": 11.0, "stall_pitch_show": 1.0,
        "runway_show": 1.0, "runway_x": -16.0, "runway_y": -28.0,
    }


def _nd_values() -> dict:
    return {
        "heading": 274.0, "track": 277.0, "target_heading": 280.0,
        "groundspeed": 246.0, "true_airspeed": 258.0,
        "wind_speed": 18.0, "wind_direction": 310.0,
        "latitude": 32.88, "longitude": -97.03,
        "map_mode": 2.0, "map_range_nm": 20.0,
        "ctr": 0.0, "wxr": 0.0, "terr": 0.0, "tfc": 1.0,
        "sta": 1.0, "wpt": 1.0, "arpt": 1.0, "data": 1.0,
        "route_lat": [32.90, 32.99, 33.10, 33.30],
        "route_lon": [-97.04, -97.11, -97.22, -97.41],
        "route_name": ["KDFW", "TTT", "JPOOL", "ADM"],
        "route_altitude": [0, 12000, 18000, 24000],
        "route_altitude2": [0, 0, 16000, 0],
        "route_altitude_type": [0, 2, 3, 1],
        "route_speed": [0, 250, 280, 0],
        "route_eta": [0, 13.20, 13.50, 14.25],
        "route_kind": [0, 1, 2, 3],
        "route_hold_time": [0, 1.0, 0, 0], "route_hold_distance": [0, 0, 0, 0],
        "next_waypoint_name": "JPOOL", "next_waypoint_distance": 8.4,
        "next_waypoint_eta": 13.50, "rnp": 0.30, "anp": 0.08,
        "altitude": 6200.0, "target_altitude": 10000.0,
        "vertical_speed": 1800.0, "roll": 12.0,
        "tcas_bearing": [-25.0, 18.0, 42.0],
        "tcas_distance": [6000.0, 3200.0, 12000.0],
        "tcas_altitude": [250.0, -120.0, 700.0],
        "tcas_vertical": [4.0, -3.0, 0.0], "tcas_ids": [1, 2, 3],
        "bearing_selector_1": 1.0, "bearing_selector_2": -1.0,
        "nav1_bearing": 22.0, "adf2_bearing": 280.0,
        "fuel_total": 4200.0, "eng_ff_0": 0.55, "eng_ff_1": 0.57,
        "database_stations": [(32.869, -97.040, "TTT", "VOR")],
        "database_waypoints": [(32.955, -96.950, "FINGR")],
        "database_airports": [(32.899, -97.040, "KDFW")],
    }


def _system_values() -> dict:
    return {
        "tat": 27.0, "thrust_mode": 1.0, "fuel_total": 7400.0,
        "target_n1_0": 100.7, "target_n1_1": 100.7,
        "eng_n1_0": 92.4, "eng_n1_1": 94.1,
        "eng_n2_0": 87.2, "eng_n2_1": 88.4,
        "eng_egt_0": 715.0, "eng_egt_1": 728.0,
        "eng_ff_0": 0.72, "eng_ff_1": 0.75,
        "eng_oil_pressure_0": 41.0, "eng_oil_pressure_1": 39.0,
        "eng_oil_temp_0": 104.0, "eng_oil_temp_1": 106.0,
        "eng_oil_qty_0": 0.82, "eng_oil_qty_1": 0.79,
        "eng_vibration_0": 0.8, "eng_vibration_1": 1.1,
        "eng_running_0": 1.0, "eng_running_1": 1.0,
        "eng_low_oil_0": 0.0, "eng_low_oil_1": 0.0,
        "hyd_qty_a": 85.0, "hyd_qty_b": 79.0,
        "hyd_press_a": 3000.0, "hyd_press_b": 2980.0,
        "brake_temp_lo": 0.3, "brake_temp_li": 0.3,
        "brake_temp_ri": 0.3, "brake_temp_ro": 0.3,
        "aileron_left": -0.25, "aileron_right": 0.25,
        "spoiler_left": 0.7, "spoiler_right": 0.45,
        "elevator_left": 0.15, "elevator_right": 0.15, "rudder": -0.2,
        "control_roll": 0.42, "control_pitch": -0.36, "control_yaw": 0.58,
        "left_brake_ratio": 0.22, "right_brake_ratio": 0.78,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    pfd = _pfd_values()
    nd = _nd_values()
    systems = _system_values()
    _save(args.out, "pfd-app", lambda frame: pfp_renderer.draw_live_pfd(frame, pfd))
    for name, values in (
        ("nd-map-20", nd),
        ("nd-map-640", {**nd, "map_range_nm": 640.0}),
        ("nd-plan-10", {**nd, "map_mode": 3.0, "map_range_nm": 10.0}),
        ("nd-plan-40", {**nd, "map_mode": 3.0, "map_range_nm": 40.0}),
        ("nd-vor", {**nd, "map_mode": 1.0, "nav_course": 275.0,
                    "nav_deviation": -0.5, "nav_frequency": 11330.0,
                    "nav_dme": 32780.0, "nav_to_from": 1.0}),
        ("nd-app", {**nd, "map_mode": 0.0, "nav_course": 275.0,
                    "nav_deviation": 0.3, "nav_vdeviation": -0.4,
                    "nav_frequency": 11030.0, "nav_dme": 17200.0,
                    "marker_outer": 1.0}),
        ("nd-vsd", {**nd, "vsd": 1.0,
                    "terrain_profile": [(-45 + i * 3, i / 30.0, -3000 + i * 190)
                                        for i in range(31)]}),
    ):
        _save(args.out, name, lambda frame, values=values: nd_renderer.draw_nd_frame(frame, values))
    for page in ("eng_pri", "mfd", "hyd"):
        _save(args.out, page, lambda frame, page=page: systems_renderer.draw_system_frame(frame, page, systems))
    _save(
        args.out,
        "hyd-controls-neutral",
        lambda frame: systems_renderer.draw_system_frame(
            frame,
            "hyd",
            {
                **systems,
                "control_roll": 0.0,
                "control_pitch": 0.0,
                "control_yaw": 0.0,
                "left_brake_ratio": 0.0,
                "right_brake_ratio": 0.0,
            },
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
