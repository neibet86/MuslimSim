"""Offline guards for BUG-32/33/34/35/38 ToLiss coded displays."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import struct
import sys
import tempfile
import threading
from types import SimpleNamespace


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.devices import mcdu_bb36_toliss_paths as paths
from muslimsim.devices import nd_renderer_toliss as nd
from muslimsim.devices import pfp_renderer_toliss as pfd
from muslimsim.devices import systems_renderer_toliss as systems
from muslimsim.devices.toliss_route_autosave import parse_toliss_qps_route
from muslimsim.devices import pfp_right_strip_tiles as shape_glyphs
from muslimsim.devices.pfp_bank_line_font import pfd_number_glyph_rectangles


def _load_bridge():
    source = PROJECT / "bridge" / "final.py"
    spec = importlib.util.spec_from_file_location("_toliss_display_bridge_test", source)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _CountingDevice:
    def __init__(self) -> None:
        self.reports = 0

    def write(self, report) -> int:
        self.reports += 1
        return len(report)


class _FeedStub:
    def start(self) -> None:
        return None

    def secondary_snapshot(self):
        return {}, False


class _PoweredFeedStub(_FeedStub):
    def secondary_snapshot(self):
        return {"elec_bat_volts": [28.0, 28.0], "ref_ac_buses": [115.0]*5,
                "ref_du_brightness": [.8]*8, "ref_du_selftest": [0.0]*8}, True

    def mcdu_snapshot(self):
        lines, colours = paths._standby_toliss_page()
        return lines, colours, True


class _UnpoweredFeedStub(_PoweredFeedStub):
    def secondary_snapshot(self):
        return {"elec_bat_volts": [0.0, 0.0]}, True


class _ClosableDevice:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _SystemsCapture:
    def __init__(self) -> None:
        self.features = set()
        self.texts = []

    def colour(self, *_args) -> None:
        return None

    def fill(self, *_args) -> None:
        return None

    def text(self, _x, _y, value, *_args) -> None:
        self.texts.append(str(value).strip())

    def record_feature(self, name: str) -> None:
        self.features.add(str(name))


def _pfd_values() -> dict:
    return {
        "ias_valid": 1.0, "alt_valid": 1.0,
        "att_valid": 1.0, "hdg_valid": 1.0,
        "ias": 250.0, "mach": 0.62, "altitude": 24500.0,
        "pitch": 3.5, "roll": -8.0, "vertical_speed": 800.0,
        "drift_angle": 2.0, "flight_path_angle": 2.5,
        "fd_pitch_cmd": 2.0, "fd_roll_cmd": -5.0, "fd_on": 1.0,
        "ap_on": 1.0, "athr_on": 1.0, "athr_thrust_mode": 4.0,
        "fma1_green": ("MACH" + " " * 4 + "ALT CRZ" + " " * 2 + "NAV").ljust(32),
        "fma1_blue": " " * 32,
        "fma1_white": (" " * 28 + "AP1").ljust(32),
        "fma2_blue": " " * 32,
        "fma2_magenta": " " * 32,
        "fma2_white": " " * 26 + "1 FD 2",
        "fma3_amber": " " * 32,
        "fma3_blue": " " * 32,
        "fma3_white": " " * 27 + "A/THR",
        "alpha_floor": 0.0, "target_speed": 260.0,
        "target_altitude": 30000.0, "target_altitude_type": 1.0,
        "target_heading": 275.0, "heading": 268.0,
        "v_ls": 172.0, "v_max": 340.0, "v_sw": 158.0,
        "v_green_dot": 210.0,
        "v1": 238.0, "v_r": 245.0, "v2": 252.0,
        "show_to_speeds": 1.0,
        "v_f": 265.0, "v_s": 275.0,
        "v_vfe_next": 215.0, "v_alpha_max": 150.0, "v_aprot": 165.0,
        "baro_std": 0.0, "baro_unit": 1.0, "baro_value": 1013.0,
        "ils_on": 1.0, "ils_freq": 109.5, "loc_dev": 0.2,
        "gs_dev": -0.3, "dme_distance": 12.4, "landing_elev": 610.0,
        "lateral_accel": 0.1,
    }


def _nd_values() -> dict:
    return {
        "heading": 268.0, "own_lat": 32.88, "own_lon": -97.03,
        "mode": 3.0, "range_index": 1.0,
        "map_available": 1.0, "heading_valid": 1.0,
        "gps_primary_message": 1.0,
        "ground_speed": 154.0, "true_air_speed": 162.0,
        "wind_available": 1.0, "wind_direction": 310.0, "wind_speed": 18.0,
        "waypoint_distance": 12.4,
        "route_lat": [32.90, 32.89, 32.71, 33.60],
        "route_lon": [-97.04, -97.05, -97.05, -98.90],
        "route_alt": [0, 12000, 18000, 24000],
        "route_ids": ["KDFW", "JPOOL", "ACTON", "KLAS"],
        "route_breaks": [False, False, False, False],
        "route_no_wp": 4.0, "route_to_wp": 1.0, "route_dashed": 0.0,
        "wpt_id": "JPOOL",
        "bearing1_selector": 2.0, "bearing2_selector": 2.0,
        "vor1_bearing": 250.0, "vor2_bearing": 300.0,
        "adf1_bearing": 90.0, "adf2_bearing": 90.0,
        "vor1_valid": 1.0, "vor2_valid": 1.0,
        "adf1_valid": 0.0, "adf2_valid": 0.0,
        "vor1_id": "CVE", "vor2_id": "TTT",
        "adf1_id": "", "adf2_id": "",
        "vor1_dme": 6.7, "vor2_dme": 1.1,
        "ils_loc": 0.2, "ils_crs": 250.0, "ils_on": 1.0,
        "show_arpt": 1.0, "show_wpt": 1.0, "show_vord": 1.0,
    }


def _reports(bridge, renderer, values: dict, canvas=None):
    device = _CountingDevice() if canvas is None else canvas.device
    canvas = bridge._PfpNativeCanvas(device) if canvas is None else canvas
    before = device.reports
    renderer(canvas, values)
    canvas.command(0x103)
    return device.reports - before, canvas


def main() -> int:
    pfd.assert_layout_contract()
    nd.assert_layout_contract()
    systems.assert_layout_contract()

    pfd_refs = paths.TOLISS_MCDU_SECONDARY_DATAREFS["pfd"]
    nd_refs = paths.TOLISS_MCDU_SECONDARY_DATAREFS["nd"]
    common_refs = paths.TOLISS_MCDU_SECONDARY_DATAREFS["ecam_common"]
    fctl_refs = paths.TOLISS_MCDU_SECONDARY_DATAREFS["fctl"]
    assert pfd_refs["ias_valid"] == "AirbusFBW/CaptIASValid"
    assert pfd_refs["alt_valid"] == "AirbusFBW/CaptALTValid"
    assert pfd_refs["att_valid"] == "AirbusFBW/CaptATTValid"
    assert pfd_refs["hdg_valid"] == "AirbusFBW/CaptHDGValid"
    assert pfd_refs["heading"] == "AirbusFBW/HDGCapt"
    assert pfd_refs["target_heading"] == "AirbusFBW/APHDG_Capt"
    assert pfd_refs["v1"] == "toliss_airbus/performance/V1"
    assert pfd_refs["v2"] == "toliss_airbus/performance/V2"
    assert pfd_refs["v_r"] == "toliss_airbus/pfdoutputs/general/VR_value"
    assert pfd_refs["v_s"] == "toliss_airbus/pfdoutputs/general/VS_value"
    assert pfd_refs["v_f"] == "toliss_airbus/pfdoutputs/general/VF_value"
    assert pfd_refs["v_vfe_next"] == "toliss_airbus/pfdoutputs/general/VFENext_value"
    assert pfd_refs["v_max"] == "toliss_airbus/pfdoutputs/general/VMax_value"
    assert pfd_refs["show_to_speeds"] == "toliss_airbus/pfdoutputs/general/show_to_speeds"
    assert pfd_refs["fma1_green"] == "AirbusFBW/FMA1g"
    assert pfd_refs["fma2_blue"] == "AirbusFBW/FMA2b"
    assert pfd_refs["fma3_amber"] == "AirbusFBW/FMA3a"
    assert pfd.FMA_HEIGHT == 87
    assert 35 <= pfd.HEADING_TAPE.height <= 45
    assert pfd.SPEED_TAPE.width == 56
    assert pfd.ALTITUDE_TAPE.width == 56
    assert pfd.ALT_SCALE_X == pfd.ALTITUDE_TAPE.right - 2
    assert pfd.ALTITUDE_WINDOW.x >= pfd.ALTITUDE_TAPE.x
    assert pfd.ALTITUDE_WINDOW.right == pfd.ALT_SCALE_X
    assert pfd.ALT_DRUM_BOX.x == pfd.ALT_SCALE_X
    assert pfd.ALT_DRUM_BOX.right > pfd.ALTITUDE_TAPE.right
    assert pfd.MACH_TEXT.rect.right == pfd.SPEED_TAPE.right
    assert pfd.PRESEL_MACH_TEXT.rect.right == pfd.SPEED_TAPE.right
    assert pfd.BARO_TEXT.rect.right == pfd.ALT_DRUM_BOX.right
    assert pfd.LANDING_ELEV_TEXT.rect.right == pfd.ALT_DRUM_BOX.right
    assert pfd.DME_TEXT.rect.right == pfd.ALT_DRUM_BOX.right
    assert pfd.VS_WEDGE.width <= 30
    assert pfd._attitude_row_span(pfd.ATTITUDE.y)[0] > pfd._attitude_row_span(pfd.TAPE_CENTER_Y)[0]
    assert nd_refs["nd_map_available"] == "AirbusFBW/CaptMAPAvail"
    assert nd_refs["nd_gps_primary_message"] == "AirbusFBW/GPSPrimMessCapt"
    assert nd_refs["nd_ground_speed"] == "AirbusFBW/GSCapt"
    assert nd_refs["nd_true_air_speed"] == "AirbusFBW/TASCapt"
    assert nd_refs["nd_route_dashed"] == "AirbusFBW/FlightPlanDashed"
    assert nd_refs["nd_aircraft_path"] == "sim/aircraft/view/acf_relative_path"
    assert nd_refs["nd_bearing1_selector"] == "ckpt/fcu/adf1Left/anim"
    assert nd_refs["nd_bearing2_selector"] == "ckpt/fcu/adf2Left/anim"
    assert nd_refs["nd_vor_bearings"] == "AirbusFBW/VORBearingArray"
    assert nd_refs["nd_ndb_bearings"] == "AirbusFBW/NDBBearingArray"
    assert {"nd_vor1_id", "nd_vor2_id", "nd_adf1_id", "nd_adf2_id"}.issubset(
        set(paths.TOLISS_ND_TEXT_KEYS)
    )
    assert "nd_aircraft_path" in paths.TOLISS_ND_TEXT_KEYS
    assert nd._airbus_heading_label(270.0) == "27"
    assert nd._airbus_heading_label(0.0) == "0"
    assert nd.PPOS_LABEL.rect.right == nd.HEADER_SAFE_RIGHT
    assert nd.RANGE_LABEL.rect.right == nd.HEADER_SAFE_RIGHT
    assert nd.HEADER_SAFE_RIGHT <= nd.X_SAFE_RIGHT - 10

    altitude_reference = {
        **_pfd_values(),
        "altitude": 33000.0,
        "target_altitude": 33000.0,
        "target_altitude_type": 1.0,
    }
    altitude_capture = pfd._CaptureCanvas()
    pfd.draw_toliss_pfd_frame(altitude_capture, altitude_reference)
    assert {
        "ALTITUDE_AMBER_HAMMER",
        "ALTITUDE_OPEN_MAIN_CRADLE",
        "ALTITUDE_OUTBOARD_DRUM_BOX",
        "ALTITUDE_CYAN_TARGET_BOX",
        "ALTITUDE_20FT_ROLLING_DRUM",
        "AIRBUS_NARROW_SPEED_DATUM",
        "AIRBUS_FULL_5DEG_PITCH_LADDER",
        "AIRBUS_STEPPED_AIRCRAFT_REFERENCE",
    }.issubset(altitude_capture.features)
    assert {">335", ">325", "330", "00", "80", "20"}.issubset(
        set(altitude_capture.texts)
    )

    altitude_ops = pfd._OpRecorder()
    pfd.draw_toliss_pfd_frame(altitude_ops, altitude_reference)
    assert any(
        op[0] == "f" and op[1] == pfd.WHITE
        and op[2:6] == (
            pfd.ALT_SCALE_X, pfd.ALTITUDE_TAPE.y, 2, pfd.ALTITUDE_TAPE.height,
        )
        for op in altitude_ops.ops
    )
    assert any(op[0] == "t" and op[6] == pfd.PFD_TINY_FONT_ID for op in altitude_ops.ops)
    assert any(
        op[0] == "t" and op[5] == "330"
        and op[6] == pfd.PFD_ALTITUDE_LARGE_FONT_ID
        for op in altitude_ops.ops
    )
    assert not any(
        op[0] == "f" and op[1] == pfd.AMBER
        and op[2] == pfd.ALTITUDE_WINDOW.x and op[4] == 2
        and op[5] == pfd.ALTITUDE_WINDOW.height
        for op in altitude_ops.ops
    )

    rolling_ops = pfd._OpRecorder()
    pfd.draw_toliss_pfd_frame(
        rolling_ops, {**altitude_reference, "altitude": 33010.0, "target_altitude": 33010.0},
    )
    exact_zero_y = [
        op[4] for op in altitude_ops.ops
        if op[0] == "t" and op[6] == pfd.PFD_TINY_FONT_ID and op[5] == "0"
    ]
    rolling_zero_y = [
        op[4] for op in rolling_ops.ops
        if op[0] == "t" and op[6] == pfd.PFD_TINY_FONT_ID and op[5] == "0"
    ]
    assert exact_zero_y != rolling_zero_y

    next_hundred = pfd._CaptureCanvas()
    pfd.draw_toliss_pfd_frame(
        next_hundred, {**altitude_reference, "altitude": 33100.0, "target_altitude": 33100.0},
    )
    assert "331" in next_hundred.texts

    assert common_refs == {
        "ecam_tat": "sim/weather/aircraft/temperature_leadingedge_deg_c",
        "ecam_sat": "sim/weather/aircraft/temperature_ambient_deg_c",
        "ecam_gw": "sim/flightmodel/weight/m_total",
        "ecam_utc": "sim/time/zulu_time_sec",
    }
    assert tuple(fctl_refs[f"fctl_spoiler_{index}"] for index in range(1, 11)) == tuple(
        f"anim/spoiler/{index}" for index in range(1, 11)
    )
    assert fctl_refs["fctl_aileron_l"] == "anim/aileronLeft"
    assert fctl_refs["fctl_aileron_r"] == "anim/aileronRight"
    assert fctl_refs["fctl_elevator_l"] == "anim/elevatorLeft"
    assert fctl_refs["fctl_elevator_r"] == "anim/elevatorRight"
    assert fctl_refs["fctl_rudder"] == "anim/rudder"
    expected_bb36_pages = (
        "pfd", "nd", "eng", "bleed", "press", "cond", "elec", "hyd",
        "fuel", "door", "wheel", "apu", "fctl", "cruise", "status",
    )
    assert paths.TOLISS_DISPLAY_PAGE_ORDER == expected_bb36_pages
    assert systems.TOLISS_SYSTEM_PAGES == expected_bb36_pages[2:]

    expected_bb35_pages = (paths.TOLISS_CDU_PAGE, *expected_bb36_pages)
    assert paths.TOLISS_BB35_DISPLAY_PAGE_ORDER == expected_bb35_pages
    assert paths.BB35_TOLISS_SLASH_INDEX == 69
    assert paths.TolissDisplayFeed is paths._TolissMcduFeed
    fanout = paths._reverse_dataref_ids({
        "pfd_heading": 41, "nd_heading": 41, "other": 72,
    })
    assert fanout == {"41": ["pfd_heading", "nd_heading"], "72": ["other"]}

    bb35 = paths.TolissBB35DisplayPath(
        open_pfd=lambda: (None, None), draw_worker=lambda *args: None,
        blackout=lambda *args: None, feed=_FeedStub(), refresh_interval=0.1,
    )
    assert bb35.get_display_page() == paths.TOLISS_CDU_PAGE
    for expected_page in expected_bb36_pages:
        bb35._cycle_display_page()
        assert bb35.get_display_page() == expected_page
    bb35._cycle_display_page()
    assert bb35.get_display_page() == paths.TOLISS_CDU_PAGE
    bb35.request_page("bleed")
    assert bb35.get_display_page() == "bleed"
    bb35.request_page("not-a-page")
    assert bb35.get_display_page() == "bleed"

    blackout_calls = []
    bb36 = paths.TolissBB36MirrorPath(
        open_pfd=lambda: (None, None), draw_worker=lambda *args: None,
        content_drawer=lambda *args: None, api_root="http://127.0.0.1:8086",
        api_version="v2", feed=_FeedStub(), refresh_interval=0.1,
        blackout=lambda device, canvas: blackout_calls.append((device, canvas)),
    )
    device = _ClosableDevice()
    canvas = object()
    bb36.device, bb36.canvas = device, canvas
    assert bb36.get_display_page() == paths.TOLISS_CDU_PAGE
    for expected_page in expected_bb36_pages:
        bb36._cycle_display_page()
        assert bb36.get_display_page() == expected_page
    bb36._cycle_display_page()
    assert bb36.get_display_page() == "pfd"
    bb36._toggle_cdu_page()
    assert bb36.get_display_page() == paths.TOLISS_CDU_PAGE
    bb36._toggle_cdu_page()
    assert bb36.get_display_page() == "pfd"
    bb36.stop()
    assert blackout_calls == [(device, canvas)] and device.closed

    mirror_off_blackouts = []
    mirror_off_static_draws = []
    bb36_dark = paths.TolissBB36MirrorPath(
        open_pfd=lambda: (None, None), draw_worker=lambda *args: None,
        content_drawer=lambda *args: mirror_off_static_draws.append(args),
        api_root="http://127.0.0.1:8086", api_version="v2",
        feed=_FeedStub(), refresh_interval=0.1, mirror_enabled=False,
        blackout=lambda device, canvas: mirror_off_blackouts.append((device, canvas)),
        show_static_when_mirror_off=False,
    )
    dark_device = _ClosableDevice()
    dark_canvas = object()
    bb36_dark.device, bb36_dark.canvas = dark_device, dark_canvas
    bb36_dark._draw_mirror_off_state()
    assert mirror_off_blackouts == [(dark_device, dark_canvas)]
    assert not mirror_off_static_draws

    bridge = _load_bridge()
    assert bridge.MCDU_PFD_FONT_FILENAME.endswith("font2-3-4-5-6-8.xpwwf")

    # BB35 must use its own brightness authority while rendering live CDU
    # content. This test exercises only the worker's drawing route; the
    # separate BUG-39 keypad guard covers BB35's physical MCDU commands.
    bb35_cdu_calls = []
    bb35_stop = threading.Event()
    original_cdu_draw = bridge._toliss_draw_mcdu_content
    original_invalidate = bridge._toliss_invalidate_display_canvas
    try:
        def _capture_bb35_cdu(*args, **kwargs):
            bb35_cdu_calls.append((args, kwargs))
            bb35_stop.set()

        bridge._toliss_draw_mcdu_content = _capture_bb35_cdu
        bridge._toliss_invalidate_display_canvas = lambda _canvas: None
        bridge._toliss_bb35_display_output_worker(
            object(), object(), _PoweredFeedStub(), 0.0,
            bb35_stop, {}, threading.Lock(), lambda: paths.TOLISS_CDU_PAGE,
        )
    finally:
        bridge._toliss_draw_mcdu_content = original_cdu_draw
        bridge._toliss_invalidate_display_canvas = original_invalidate
    assert len(bb35_cdu_calls) == 1
    assert bb35_cdu_calls[0][1]["display_id"] == "BB35"

    bb35_system_calls = []
    bb35_stop = threading.Event()
    from muslimsim.devices import toliss_sd_image
    original_image_pages = toliss_sd_image.PAGE_IDS
    deadline = threading.Timer(2.0, bb35_stop.set)
    original_system_draw = bridge._toliss_draw_mcdu_secondary
    original_invalidate = bridge._toliss_invalidate_display_canvas
    try:
        # This assertion tests the legacy numerical fallback. Do not let a
        # concurrently running simulator's shared image bypass its spy.
        toliss_sd_image.PAGE_IDS = {}
        deadline.start()
        def _capture_bb35_system(*args, **kwargs):
            bb35_system_calls.append((args, kwargs))
            bb35_stop.set()

        bridge._toliss_draw_mcdu_secondary = _capture_bb35_system
        bridge._toliss_invalidate_display_canvas = lambda _canvas: None
        bridge._toliss_bb35_display_output_worker(
            object(), object(), _PoweredFeedStub(), 0.0,
            bb35_stop, {}, threading.Lock(), lambda: "fctl",
        )
    finally:
        deadline.cancel()
        toliss_sd_image.PAGE_IDS = original_image_pages
        bridge._toliss_draw_mcdu_secondary = original_system_draw
        bridge._toliss_invalidate_display_canvas = original_invalidate
    assert len(bb35_system_calls) == 1
    assert bb35_system_calls[0][1]["display_id"] == "BB35"

    bb35_blackouts = []
    bb35_stop = threading.Event()
    original_blackout = bridge._toliss_blackout_display
    original_invalidate = bridge._toliss_invalidate_display_canvas
    try:
        def _capture_bb35_blackout(*args):
            bb35_blackouts.append(args)
            bb35_stop.set()

        bridge._toliss_blackout_display = _capture_bb35_blackout
        bridge._toliss_invalidate_display_canvas = lambda _canvas: None
        bridge._toliss_bb35_display_output_worker(
            object(), object(), _UnpoweredFeedStub(), 0.0,
            bb35_stop, {}, threading.Lock(), lambda: paths.TOLISS_CDU_PAGE,
        )
    finally:
        bridge._toliss_blackout_display = original_blackout
        bridge._toliss_invalidate_display_canvas = original_invalidate
    assert len(bb35_blackouts) == 1
    assert bb35_blackouts[0][2] == "BB35"

    bridge_source = (PROJECT / "bridge" / "final.py").read_text(encoding="utf-8")
    assert "_open_pfp_pfd_display(\n                        MCDU_PFD_FONT_FILENAME," in bridge_source
    assert 'for router_key in ("router", "bb35_router")' in bridge_source
    assert "for router in routers:" in bridge_source

    translated = bridge._toliss_pfd_values({
        "v1": [138.0], "v_r": [145.0], "v2": [150.0],
        "v_s": [205.0], "show_to_speeds": [1.0],
        "fma1_green": "SPEED",
        "fma2_blue": "        ALT",
        "fma3_white": "                           A/THR",
    })
    assert translated["v1"] == 138.0
    assert translated["v_r"] == 145.0
    assert translated["v2"] == 150.0
    assert translated["v_s"] == 205.0
    assert translated["show_to_speeds"] == 1.0
    assert translated["fma1_green"] == "SPEED"
    assert translated["fma2_blue"].strip() == "ALT"
    assert translated["fma3_white"].strip() == "A/THR"
    assert set(translated) == set(pfd.TOLISS_PFD_VALUE_KEYS)

    translated_nd = bridge._toliss_nd_values({
        "nd_route_dashed": [1.0],
        "nd_waypoint_course": [89.7],
        "nd_waypoint_distance": [3.2],
        "nd_bearing1_selector": [2.0],
        "nd_bearing2_selector": [0.0],
        "nd_vor_bearings": [82.5, 183.4],
        "nd_ndb_bearings": [91.0, 271.0],
        "nd_vor1_valid": [1.0], "nd_vor2_valid": [1.0],
        "nd_adf1_valid": [0.0], "nd_adf2_valid": [1.0],
        "nd_vor1_id": "CVE", "nd_vor2_id": "TTT",
        "nd_adf1_id": "", "nd_adf2_id": "NDB",
        "nd_vor1_dme": [6.7], "nd_vor2_dme": [1.1],
    })
    assert translated_nd["route_dashed"] == 1.0
    assert translated_nd["waypoint_course"] == 89.7
    assert translated_nd["route_active_leg_fallback"] is True
    assert translated_nd["vor1_bearing"] == 82.5
    assert translated_nd["vor2_bearing"] == 183.4
    assert translated_nd["adf2_bearing"] == 271.0
    assert translated_nd["vor1_id"] == "CVE"
    assert set(translated_nd) == set(nd.TOLISS_ND_VALUE_KEYS)

    # BUG-47: ToLiss's QPS autosave is a bounded record stream.  Find the
    # latitude/longitude/name triplet structurally, keep all fixes after a
    # blank discontinuity, and expose the break before the resumed segment.
    def qps_record(record_id, element_size, count, capacity, payload):
        assert len(payload) == element_size * count
        return struct.pack("<4I", record_id, element_size, count, capacity) + payload

    route_names = ("DEP", "FIRST", "ACTIVE", "", "RESUME", "NEXT", "DEST", "MISSED")
    route_lats = (32.0, 32.1, 32.2, 0.0, 32.4, 32.5, 32.6, 32.7)
    route_lons = (-97.0, -96.9, -96.8, 0.0, -96.6, -96.5, -96.4, -96.3)
    name_payload = b"".join(name.encode("ascii").ljust(10, b"\0") for name in route_names)
    qps_blob = b"".join((
        qps_record(1, 4, 1, 4, struct.pack("<f", 123.0)),
        qps_record(2, 4, 8, 16, struct.pack("<8f", *route_lats)),
        qps_record(3, 4, 8, 16, struct.pack("<8f", *route_lons)),
        qps_record(4, 10, 8, 16, name_payload),
    ))
    with tempfile.TemporaryDirectory() as directory:
        qps_path = Path(directory) / "A321_AUTOSAVED_SITUATION.qps"
        qps_path.write_bytes(qps_blob)
        qps_route = parse_toliss_qps_route(qps_path, "ACTIVE")
    assert qps_route is not None
    assert qps_route.active_index == 2
    assert qps_route.waypoint_ids[4:] == ("RESUME", "NEXT", "DEST", "MISSED")
    assert qps_route.break_before[4] is True
    assert nd._route_leg_broken({"route_breaks": qps_route.break_before}, 2, 4)
    assert not nd._route_leg_broken({"route_breaks": qps_route.break_before}, 4, 5)

    saved_route_reader = bridge._muslimsim_read_toliss_autosaved_route
    bridge._muslimsim_read_toliss_autosaved_route = lambda _aircraft, _active: SimpleNamespace(
        latitudes=qps_route.latitudes,
        longitudes=qps_route.longitudes,
        waypoint_ids=qps_route.waypoint_ids,
        break_before=qps_route.break_before,
        active_index=qps_route.active_index,
    )
    try:
        translated_full_route = bridge._toliss_nd_values({
            "nd_aircraft_path": "Aircraft/ToLissA321/a321.acf",
            "nd_wpt_id": "ACTIVE",
        })
    finally:
        bridge._muslimsim_read_toliss_autosaved_route = saved_route_reader
    assert translated_full_route["route_active_leg_fallback"] is False
    assert translated_full_route["route_to_wp"] == 2.0
    assert translated_full_route["route_breaks"][4] is True

    translated_fctl = bridge._toliss_ecam_system_values("fctl", {
        **{f"fctl_spoiler_{index}": [index / 10.0] for index in range(1, 11)},
        "fctl_aileron_l": [-0.4], "fctl_aileron_r": [0.4],
        "fctl_elevator_l": [-0.2], "fctl_elevator_r": [-0.2],
        "fctl_rudder": [0.3], "fctl_pitch_trim": [1.3],
        "fctl_yaw_trim": [-0.7], "fctl_hyd_press": [3000.0, 2990.0, 3010.0],
        "fctl_rudder_avail": [1.0, 1.0, 1.0],
    })
    assert translated_fctl["fctl_spoiler_1"] == 0.1
    assert translated_fctl["fctl_spoiler_10"] == 1.0
    assert translated_fctl["fctl_aileron_l"] == -0.4
    assert translated_fctl["fctl_elevator_r"] == -0.2
    assert translated_fctl["fctl_rudder"] == 0.3
    assert translated_fctl["fctl_pitch_trim_deg"] == 1.3
    assert translated_fctl["fctl_hyd_y"] == 3010.0
    assert set(translated_fctl) == set(systems.TOLISS_SYSTEM_PAGE_VALUE_KEYS["fctl"])
    assert bridge._toliss_ecam_common_values({
        "ecam_tat": [18.0], "ecam_sat": [12.0],
        "ecam_gw": [68000.0], "ecam_utc": [48120.0],
    }) == {
        "ecam_tat": 18.0, "ecam_sat": 12.0,
        "ecam_gw": 68000.0, "ecam_utc": 48120.0,
    }
    translated_cruise = bridge._toliss_ecam_system_values("cruise", {
        "cruise_oil_qty": [0.82, 0.80],
        "cruise_vib": [0.7, 0.8],
        "cruise_ff": [860.0, 875.0],
        "cruise_cabin_alt": [6200.0], "cruise_cabin_vs": [250.0],
        "cruise_delta_p": [7.8], "cruise_fwd_temp": [23.0],
        "cruise_aft_temp": [24.0],
    })
    assert translated_cruise["cruise_oil_qty_0"] == 0.82
    assert translated_cruise["cruise_oil_qty_1"] == 0.80
    assert translated_cruise["cruise_delta_p"] == 7.8
    assert set(translated_cruise) == set(systems.TOLISS_SYSTEM_PAGE_VALUE_KEYS["cruise"])

    fctl_values = {
        **translated_fctl,
        "ecam_tat": 18.0, "ecam_sat": 12.0,
        "ecam_gw": 68000.0, "ecam_utc": 48120.0,
    }
    fctl_capture = _SystemsCapture()
    systems.draw_toliss_system_frame(fctl_capture, "fctl", fctl_values)
    assert {
        "AIRBUS_ECAM_HEADER", "AIRBUS_ECAM_PERMANENT_DATA",
        "FCTL_TEN_SPOILERS", "FCTL_AILERONS", "FCTL_ELEVATORS",
        "FCTL_RUDDER",
    }.issubset(fctl_capture.features)
    assert "NO AILERON POSITION DATAREF" not in fctl_capture.texts
    assert {"F/CTL", "SPD BRK", "L AIL", "R AIL", "L ELEV", "R ELEV", "RUD"}.issubset(
        set(fctl_capture.texts)
    )

    cruise_capture = _SystemsCapture()
    systems.draw_toliss_system_frame(cruise_capture, "cruise", {
        **{key: 1.0 for key in systems.TOLISS_SYSTEM_PAGE_VALUE_KEYS["cruise"]},
        "ecam_tat": 18.0, "ecam_sat": 12.0,
        "ecam_gw": 68000.0, "ecam_utc": 48120.0,
    })
    assert {"AIRBUS_CRUISE_PAGE", "AIRBUS_ECAM_PERMANENT_DATA"}.issubset(
        cruise_capture.features
    )

    # The Airbus lower-SD permanent data strip belongs to every system page,
    # not only F/CTL and CRUISE.  Guard this centrally so future pages cannot
    # appear on BB36 without the shared TAT/SAT/GW/UTC line.
    for page in systems.TOLISS_SYSTEM_PAGES:
        capture = _SystemsCapture()
        systems.draw_toliss_system_frame(capture, page, {
            **{key: 1.0 for key in systems.TOLISS_SYSTEM_PAGE_VALUE_KEYS[page]},
            "ecam_tat": 18.0, "ecam_sat": 12.0,
            "ecam_gw": 68000.0, "ecam_utc": 48120.0,
        })
        assert {"AIRBUS_ECAM_HEADER", "AIRBUS_ECAM_PERMANENT_DATA"}.issubset(
            capture.features
        ), page

    # The three moving symbols must remain native glyphs rather than falling
    # back to multi-command rectangle mosaics.  They are isolated to unused
    # slot-3 characters and therefore cannot alter normal numeric typography.
    assert shape_glyphs.DEVIATION_DIAMOND_CHARACTER == "y"
    assert shape_glyphs.SPEED_RING_CHARACTER == "z"
    assert shape_glyphs.SPEED_TRIANGLE_CHARACTER == "~"
    for character in ("y", "z", "~"):
        assert pfd_number_glyph_rectangles(character), character

    takeoff = pfd._CaptureCanvas()
    pfd.draw_toliss_pfd_frame(takeoff, {
        **_pfd_values(),
        "ias": 135.0, "v1": 138.0, "v_r": 145.0, "v2": 150.0,
        "v_f": 0.0, "v_s": 0.0, "v_green_dot": 0.0,
        "v_vfe_next": 0.0, "show_to_speeds": 1.0,
    })
    assert {"V1", "VR", "V2"}.issubset(takeoff.features)
    no_takeoff = pfd._CaptureCanvas()
    pfd.draw_toliss_pfd_frame(no_takeoff, {
        **_pfd_values(),
        "ias": 135.0, "v1": 138.0, "v_r": 145.0, "v2": 150.0,
        "show_to_speeds": 0.0,
    })
    assert not {"V1", "VR", "V2"}.intersection(no_takeoff.features)

    ils = pfd._CaptureCanvas()
    pfd.draw_toliss_pfd_frame(ils, _pfd_values())
    assert ils.features.count("ILS_DEVIATION_DIAMOND") == 2

    # VMax is already ToLiss's active minimum of VMO/MMO/VFE/VLE/VLO.  Prove
    # that changing this one input moves a real red/black strip rather than
    # leaving behind a fixed Studio overspeed limit.
    def maximum_band_bottom(v_max: float) -> int:
        recorder = pfd._OpRecorder()
        pfd.draw_toliss_pfd_frame(
            recorder,
            {
                **_pfd_values(),
                "ias": 200.0,
                "v_max": v_max,
                "v_ls": 0.0,
                "v_sw": 0.0,
                "v_alpha_max": 0.0,
                "v_aprot": 0.0,
                "show_to_speeds": 0.0,
                "v_f": 0.0,
                "v_s": 0.0,
                "v_green_dot": 0.0,
                "v_vfe_next": 0.0,
            },
        )
        band = [
            op for op in recorder.ops
            if op[0] == "f"
            and op[2] == pfd.SPEED_BAND_X
            and op[4] == pfd.SPEED_BAND_WIDTH
            and op[1] in {pfd.RED, pfd.BLACK}
        ]
        assert any(op[1] == pfd.RED for op in band)
        assert any(op[1] == pfd.BLACK for op in band)
        return max(op[3] + op[5] for op in band)

    assert maximum_band_bottom(230.0) < maximum_band_bottom(215.0)

    pfd_full, pfd_canvas = _reports(bridge, pfd.draw_live_toliss_pfd, _pfd_values())
    moving = _pfd_values()
    moving.update({"ias": 251.0, "altitude": 24520.0, "roll": -7.5})
    pfd_delta, _ = _reports(bridge, pfd.draw_live_toliss_pfd, moving, pfd_canvas)

    nd_full, nd_canvas = _reports(bridge, nd.draw_live_toliss_nd, _nd_values())
    turning = _nd_values()
    turning["heading"] = 268.5
    nd_delta, _ = _reports(bridge, nd.draw_live_toliss_nd, turning, nd_canvas)
    assert pfd_delta < pfd_full
    assert nd_delta < nd_full
    # The calibrated A321 artwork adds the real 5-degree ladder, bilateral
    # labels, stepped aircraft reference and split altitude drum.  Full-page
    # recovery remains below one SD-page burst; normal motion stays differential.
    assert pfd_full <= 350, f"ToLiss PFD recovery burst regressed to {pfd_full} reports"
    assert pfd_delta <= 260, f"ToLiss PFD motion burst regressed to {pfd_delta} reports"
    assert nd_full <= 450, f"ToLiss ND recovery burst regressed to {nd_full} reports"
    assert nd_delta <= 375, f"ToLiss ND turn burst regressed to {nd_delta} reports"

    # Every BB36 ECAM page must remain bounded even when the project doubles.
    # The renderer emits only dirty regions after this recovery frame; F/CTL
    # gets an explicit moving-surface guard because it is the busiest live page.
    system_values = {
        key: 1.0
        for keys in systems.TOLISS_SYSTEM_PAGE_VALUE_KEYS.values()
        for key in keys
    }
    system_values.update({
        "ecam_tat": 18.0, "ecam_sat": 12.0,
        "ecam_gw": 68000.0, "ecam_utc": 48120.0,
        **translated_fctl,
    })
    system_reports = {}
    system_canvases = {}
    for page in systems.TOLISS_SYSTEM_PAGES:
        reports, page_canvas = _reports(
            bridge,
            lambda target, current, page=page: systems.draw_live_toliss_system_page(
                target, page, current,
            ),
            system_values,
        )
        system_reports[page] = reports
        system_canvases[page] = page_canvas
    busiest_page = max(system_reports, key=system_reports.get)
    assert system_reports[busiest_page] <= 400, (
        f"ToLiss {busiest_page.upper()} recovery burst regressed to "
        f"{system_reports[busiest_page]} reports"
    )
    # BUG-40 adds the reference computer brackets, hydraulic boxes and curved
    # rudder pointer. Measured 255 full/113 moving vs the old 229/79, still below
    # the existing 400-report SD limit. Keep a narrow budget for the new art.
    assert system_reports["fctl"] <= 270, (
        f"ToLiss F/CTL recovery burst regressed to {system_reports['fctl']} reports"
    )
    moving_fctl = dict(system_values)
    moving_fctl.update({
        "fctl_aileron_l": 0.2, "fctl_aileron_r": -0.2,
        "fctl_elevator_l": 0.25, "fctl_elevator_r": 0.25,
        "fctl_rudder": -0.3, "fctl_spoiler_3": 0.7,
    })
    fctl_delta, _ = _reports(
        bridge,
        lambda target, current: systems.draw_live_toliss_system_page(
            target, "fctl", current,
        ),
        moving_fctl,
        system_canvases["fctl"],
    )
    assert fctl_delta < system_reports["fctl"]
    assert fctl_delta <= 125, f"ToLiss F/CTL motion burst regressed to {fctl_delta} reports"

    invalid_pfd = pfd._CaptureCanvas()
    pfd.draw_toliss_pfd_frame(
        invalid_pfd,
        {
            **_pfd_values(),
            "ias_valid": 0.0, "alt_valid": 0.0,
            "att_valid": 0.0, "hdg_valid": 0.0,
        },
    )
    assert {"SPD", "ATT", "ALT", "V/S", "HDG"}.issubset(invalid_pfd.texts)
    assert {
        "INVALID_SPEED_SHAPE", "INVALID_ATTITUDE_SHAPE",
        "INVALID_ALTITUDE_SPLIT_SHAPE", "INVALID_VS_TAPERED_SHAPE",
        "INVALID_HEADING_SHAPE",
    }.issubset(invalid_pfd.features)

    native_fma = pfd._CaptureCanvas()
    pfd.draw_toliss_pfd_frame(native_fma, {
        **_pfd_values(),
        "fma1_green": "SPEED   G/S     LOC             AP1 ",
        "fma2_blue": "        ALT                     ",
        "fma2_white": "                           1FD2 ",
        "fma3_white": "                           A/THR",
    })
    assert "NATIVE_TOLISS_FMA" in native_fma.features

    invalid = nd._CaptureCanvas()
    nd.draw_toliss_nd_frame(
        invalid,
        {**_nd_values(), "map_available": 0.0, "gps_primary_message": 2.0},
    )
    assert {"HDG", "MAP NOT AVAIL", "GPS PRIMARY LOST"}.issubset(invalid.texts)
    assert invalid.texts.count("---") >= 2

    # LS selection must not inject an ILS/VOR deviation scale into ARC mode.
    arc_ls = nd._OpRecorder()
    arc_no_ls = nd._OpRecorder()
    nd.draw_toliss_nd_frame(arc_ls, _nd_values())
    nd.draw_toliss_nd_frame(arc_no_ls, {**_nd_values(), "ils_on": 0.0})
    assert arc_ls.ops == arc_no_ls.ops

    # The real active plan is green in NAV/ARC/PLAN and becomes dashed only
    # when ToLiss says it is no longer being followed.  VOR1/ADF1 is the
    # single pointer and VOR2/ADF2 the double pointer; PLAN suppresses both.
    for mode in (2.0, 3.0, 4.0):
        capture = nd._CaptureCanvas()
        nd.draw_toliss_nd_frame(capture, {**_nd_values(), "mode": mode})
        assert "FLIGHT_PLAN_SOLID" in capture.features
    bearings = nd._CaptureCanvas()
    nd.draw_toliss_nd_frame(bearings, {**_nd_values(), "mode": 2.0})
    assert {"BEARING_SINGLE", "BEARING_DOUBLE"}.issubset(bearings.features)
    assert {"VOR1", "CVE", "6.7NM", "VOR2", "TTT", "1.1NM"}.issubset(bearings.texts)
    dashed = nd._CaptureCanvas()
    nd.draw_toliss_nd_frame(dashed, {**_nd_values(), "route_dashed": 1.0})
    assert "FLIGHT_PLAN_DASHED" in dashed.features
    # BUG-46: installed ToLiss A321 1.8 has no flightplan coordinate arrays.
    # WPT course/distance must still draw the live active leg and identifier.
    fallback = nd._CaptureCanvas()
    nd.draw_toliss_nd_frame(fallback, {
        **_nd_values(), "route_lat": (), "route_lon": (), "route_alt": (),
        "route_no_wp": math.nan, "route_to_wp": math.nan,
        "route_active_leg_fallback": True,
        "waypoint_course": 89.7, "waypoint_distance": 3.2,
        "wpt_id": "INTCPT",
    })
    assert "FLIGHT_PLAN_SOLID" in fallback.features
    assert any(text.startswith("INTCPT") for text in fallback.texts)
    plan = nd._CaptureCanvas()
    nd.draw_toliss_nd_frame(plan, {**_nd_values(), "mode": 4.0})
    assert not {"BEARING_SINGLE", "BEARING_DOUBLE"}.intersection(plan.features)

    source = (PROJECT / "bridge" / bridge.PFP_PFD_FONT_FILENAME).read_bytes()
    combined = (PROJECT / "bridge" / bridge.MCDU_PFD_FONT_FILENAME).read_bytes()
    assert combined.startswith(source) and len(combined) > len(source)
    pfd_font_device = _CountingDevice()
    combined_font_device = _CountingDevice()
    pfd_packets = bridge._pfp_upload_font(
        pfd_font_device, bridge.PFP_PFD_FONT_FILENAME,
    )
    combined_packets = bridge._pfp_upload_font(
        combined_font_device, bridge.MCDU_PFD_FONT_FILENAME,
    )
    assert pfd_packets == pfd_font_device.reports
    assert combined_packets == combined_font_device.reports
    assert combined_packets > pfd_packets

    print(
        "ToLiss display BUG-32/33/34/35/38 checks passed: "
        f"PFD {pfd_full} full/{pfd_delta} moving reports; "
        f"ND {nd_full} full/{nd_delta} turning; "
        f"ECAM max {busiest_page.upper()} {system_reports[busiest_page]}, "
        f"F/CTL {system_reports['fctl']} full/{fctl_delta} moving reports."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
