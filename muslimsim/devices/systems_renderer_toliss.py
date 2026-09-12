"""Code-native 640x480 ToLiss A320 ECAM lower-display synoptic pages.

Sibling to muslimsim/devices/systems_renderer.py (Boeing ENG PRI/MFD/HYD),
not a reskin of it: this is a fresh, Airbus-native page set (ENG, BLEED,
PRESS, COND, ELEC, HYD, FUEL, DOOR, WHEEL, APU, FCTL, CRUISE, STATUS) matching how a
real A320 lower ECAM actually organizes its system pages, driven by real
`AirbusFBW/*` datarefs (xplane_command_catalog.json, aircraft=="toliss") plus
explicitly documented generic X-Plane SDK fallbacks for engine summaries and
the permanent lower-SD row. Every value key this module reads
is a flat, already-indexed name built upstream in bridge/final.py from the
raw (possibly array-shaped) feed values in mcdu_bb36_toliss_paths.py's
TOLISS_MCDU_SECONDARY_DATAREFS - this module never talks to a dataref name.

Shares the PFD/ND/systems final-image differential contract (imported, not
reimplemented): a complete page is recorded in memory, only changed pixel
regions are emitted, and an occasional recovery frame repairs a missed USB
region. Also imports systems_renderer.py's generic (airplane-agnostic) gauge
primitives - `_arc`/`_vertical_bar`/`_wheel` - the same
block-stamping technique the Boeing pages and the ND compass already use.
Every widget layout, colour, and label below is new Airbus-specific code.

Gauge ranges and warn/danger thresholds throughout are illustrative
engineering estimates for visual scaling (the catalog carries no dataref
limit metadata), except where a real limit dataref is read dynamically (APU
EGT uses AirbusFBW/APUEGTLimit) - confirm against a live session and correct
fast, same discipline as every other first-pass renderer in this project.
"""

from __future__ import annotations

import math
import time
from typing import Any, Mapping, Tuple

from muslimsim.devices.pfp_renderer import (
    AMBER,
    BLACK,
    CYAN,
    FONT_CELL_HEIGHT,
    FONT_CELL_WIDTH,
    GREEN,
    HEIGHT,
    RED,
    WHITE,
    WIDTH,
    _clamp,
    _dirty_boxes,
    _draw_large_text as _draw_text,
    _emit_frame,
    _finite,
    _OpRecorder,
    _slot,
    FULL_REPAINT_SECONDS,
)
from muslimsim.devices.systems_renderer import (
    _arc,
    _fill,
    _line,
    _outline,
    _vertical_bar,
    _wheel,
)

ECAM_BG = BLACK                 # real ECAM background is black, not navy
DIM_GREY = (100, 106, 118)
PANEL_LINE = (58, 63, 74)
ECAM_BLUE = CYAN                 # see mcdu_bb36_toliss_paths.py's own "b"->
                                  # COLOR_CYAN judgment call for this project's
                                  # established Airbus-blue-as-cyan precedent
TOLISS_SAFE_LEFT = 34            # same physical bezel-masked strip as Boeing's
TOLISS_SAFE_RIGHT = 606          # SYSTEM_SAFE_LEFT/RIGHT - same hardware
TOLISS_SYSTEM_FULL_REPAINT_FRAMES = 600

# Column/row layout shared by every page's plain status/value table. Chosen
# generously (not packed to the pixel) so pages stay easy to extend safely.
_ROW_LEFT_X = 40
_ROW_RIGHT_X = 340
_ROW_LABEL_CELLS = 9
_ROW_VALUE_CELLS = 5
_ROW_VALUE_GAP_CELLS = 1

TOLISS_SYSTEM_PAGES: Tuple[str, ...] = (
    "eng", "bleed", "press", "cond", "elec", "hyd", "fuel",
    "door", "wheel", "apu", "fctl", "cruise", "status",
)

TOLISS_SYSTEM_COMMON_VALUE_KEYS: Tuple[str, ...] = (
    "ecam_tat", "ecam_sat", "ecam_gw", "ecam_utc",
)

# ---------------------------------------------------------------------------
# Flat value-key contract per page - what each draw function reads via
# values.get(...). Built upstream in bridge/final.py from the raw feed
# (mcdu_bb36_toliss_paths.TOLISS_MCDU_SECONDARY_DATAREFS), matching how
# systems_renderer.SYSTEM_PAGE_VALUE_KEYS documents the Boeing contract.
# ---------------------------------------------------------------------------
TOLISS_SYSTEM_PAGE_VALUE_KEYS = {
    "eng": (
        "eng_epr_0", "eng_epr_1", "eng_egt_0", "eng_egt_1",
        "eng_ff_0", "eng_ff_1", "eng_oilpress_0", "eng_oilpress_1",
        "eng_n1_0", "eng_n1_1", "eng_n2_0", "eng_n2_1",
        "eng_oiltemp_0", "eng_oiltemp_1", "eng_vib_0", "eng_vib_1",
        "eng_master_0", "eng_master_1",
    ),
    "bleed": (
        "bleed_press_l", "bleed_press_r", "bleed_ind_1", "bleed_ind_2",
        "bleed_hp_1", "bleed_hp_2", "bleed_switch_1", "bleed_switch_2",
        "bleed_apu_ind", "bleed_xbleed_ind", "bleed_intercon",
        "bleed_ground_hp", "bleed_ground_lp", "bleed_ram",
        "bleed_pack_switch_1", "bleed_pack_switch_2",
        "bleed_pack_temp_1", "bleed_pack_temp_2",
        "bleed_pack_outlet_1", "bleed_pack_outlet_2",
        "bleed_pack_pointer_1", "bleed_pack_pointer_2",
        "bleed_pack_flow_1", "bleed_pack_flow_2",
        "bleed_temp_1", "bleed_temp_2",
    ),
    "press": (
        "press_cabin_alt", "press_cabin_vs", "press_outflow",
        "press_outflow_aft", "press_mode", "press_mode_lights",
    ),
    "cond": (
        "cond_fwd_cabin_temp", "cond_aft_cabin_temp", "cond_fwd_cargo_temp",
        "cond_aft_cargo_temp", "cond_bulk_cargo_temp", "cond_vent_inlet",
        "cond_vent_extract", "cond_cargo_hot_air",
    ),
    "elec": (
        "elec_bat_v_0", "elec_bat_v_1", "elec_gen_1", "elec_gen_2",
        "elec_apu_gen", "elec_ext_pow", "elec_ac_tie",
        "elec_ac_bus_1", "elec_ac_bus_2", "elec_dc_bus_1", "elec_dc_bus_2",
    ),
    "hyd": (
        "hyd_press_g", "hyd_press_b", "hyd_press_y",
        "hyd_qty_g", "hyd_qty_b", "hyd_qty_y",
        "hyd_ptu_mode", "hyd_rat_mode", "hyd_y_elec_mode",
        "hyd_brake_accu", "hyd_altn_brake",
    ),
    "fuel": (
        "fuel_qty_l", "fuel_qty_ctr", "fuel_qty_r", "fuel_fob",
        "fuel_ff_0", "fuel_ff_1", "fuel_lp_valve_0", "fuel_lp_valve_1",
        "fuel_apu_ff", "fuel_extra_tanks",
    ),
    "door": (
        "door_pax_0", "door_pax_1", "door_pax_2", "door_pax_3",
        "door_cargo_0", "door_cargo_1", "door_bulk", "door_cockpit",
        "door_slides", "door_oxy_crew", "door_oxy_pax",
    ),
    "wheel": (
        "wheel_gear_l", "wheel_gear_n", "wheel_gear_r",
        "wheel_brake_temp_lo", "wheel_brake_temp_li",
        "wheel_brake_temp_ri", "wheel_brake_temp_ro",
        "wheel_brake_l", "wheel_brake_r", "wheel_park_brake",
        "wheel_autobrk_lo", "wheel_autobrk_med", "wheel_autobrk_max",
        "wheel_antiskid", "wheel_nws_avail", "wheel_spd_brake",
        "wheel_brake_fan",
    ),
    "apu": (
        "apu_avail", "apu_egt", "apu_egt_limit", "apu_n_pct", "apu_flap",
        "apu_master", "apu_starter", "apu_fire",
        "apu_bleed_switch", "apu_bleed_ind", "apu_bleed_press", "apu_ff",
    ),
    "fctl": (
        "fctl_spoiler_l", "fctl_spoiler_r", "fctl_pitch_trim",
        "fctl_yaw_trim", "fctl_rudder_avail",
        *(f"fctl_spoiler_{index}" for index in range(1, 11)),
        "fctl_aileron_l", "fctl_aileron_r",
        "fctl_elevator_l", "fctl_elevator_r", "fctl_rudder",
        "fctl_pitch_trim_deg", "fctl_yaw_trim_deg",
        "fctl_hyd_g", "fctl_hyd_b", "fctl_hyd_y",
        "fctl_rudder_avail_g", "fctl_rudder_avail_b",
        "fctl_rudder_avail_y",
    ),
    "cruise": (
        "cruise_oil_qty_0", "cruise_oil_qty_1",
        "cruise_vib_0", "cruise_vib_1",
        "cruise_ff_0", "cruise_ff_1",
        "cruise_cabin_alt", "cruise_cabin_vs", "cruise_delta_p",
        "cruise_fwd_temp", "cruise_aft_temp",
    ),
    "status": (
        "status_master_warn", "status_master_caut", "status_flight_phase",
        "status_ap_warn", "status_athr_warn", "status_retard_warn",
        "status_ospeed_warn",
    ),
}


class TolissSystemsLayoutError(RuntimeError):
    """A ToLiss ECAM page primitive left the physical LCD."""


def _text(
    canvas: Any,
    x: int,
    y: int,
    value: str,
    colour: Tuple[int, int, int] = WHITE,
    width_cells: int | None = None,
    align: str = "left",
    background: Tuple[int, int, int] = ECAM_BG,
) -> None:
    value = str(value)
    cells = width_cells if width_cells is not None else max(1, len(value))
    _draw_text(
        canvas,
        _slot("toliss systems text", int(x), int(y), int(cells) * FONT_CELL_WIDTH, align),
        value[:cells], colour, background,
    )


def _center(canvas: Any, x: int, y: int, value: str,
            colour: Tuple[int, int, int] = WHITE, cells: int | None = None,
            background: Tuple[int, int, int] = ECAM_BG) -> None:
    value = str(value)
    width = cells if cells is not None else max(1, len(value))
    _text(canvas, int(x - width * FONT_CELL_WIDTH / 2), y, value,
          colour, width, "center", background)


def _fmt(value: Any, decimals: int = 0, fallback: str = "---") -> str:
    if not _finite(value):
        return fallback
    if decimals <= 0:
        return str(int(round(float(value))))
    return f"{float(value):.{decimals}f}"


def _ratio_to_percent(value: Any) -> Any:
    """Some ToLiss quantity datarefs read as a 0..1 ratio, others 0..100.

    JUDGMENT CALL (same defensive guess Boeing's own _draw_hyd already makes
    for AirbusFBW/hyd_qty_*): treat anything <= 1.5 as a ratio.
    """
    if _finite(value) and abs(float(value)) <= 1.5:
        return float(value) * 100.0
    return value


def _feature(canvas: Any, name: str) -> None:
    recorder = getattr(canvas, "record_feature", None)
    if callable(recorder):
        recorder(str(name))


def _header(canvas: Any, title: str, accent: Tuple[int, int, int] = ECAM_BLUE) -> None:
    _fill(canvas, 0, 0, WIDTH, HEIGHT, ECAM_BG)
    _center(canvas, WIDTH // 2, 5, title, WHITE, max(6, len(title)))
    underline_width = max(70, len(title) * FONT_CELL_WIDTH)
    _fill(canvas, (WIDTH - underline_width) // 2, 34, underline_width, 2, accent)
    _feature(canvas, "AIRBUS_ECAM_HEADER")


def _signed_temperature(value: Any) -> str:
    if not _finite(value):
        return "---"
    return f"{float(value):+03.0f}"


def _draw_permanent_data(canvas: Any, values: Mapping[str, Any]) -> None:
    """Airbus SD bottom row: TAT, SAT, gross weight and UTC."""
    _fill(canvas, 0, 446, WIDTH, HEIGHT - 446, ECAM_BG)
    _fill(canvas, TOLISS_SAFE_LEFT, 446, TOLISS_SAFE_RIGHT - TOLISS_SAFE_LEFT, 2, PANEL_LINE)
    _text(canvas, 34, 451, "TAT", ECAM_BLUE, 3)
    _text(canvas, 85, 451, _signed_temperature(values.get("ecam_tat")), GREEN, 4)
    _text(canvas, 170, 451, "SAT", ECAM_BLUE, 3)
    _text(canvas, 221, 451, _signed_temperature(values.get("ecam_sat")), GREEN, 4)
    _text(canvas, 310, 451, "GW", ECAM_BLUE, 2)
    gw = _fmt(values.get("ecam_gw"), 0)
    _text(canvas, 344, 451, gw, GREEN if gw != "---" else AMBER, 6)
    _text(canvas, 464, 451, "UTC", ECAM_BLUE, 3)
    utc = values.get("ecam_utc")
    if _finite(utc):
        total_minutes = int(float(utc) // 60.0) % (24 * 60)
        clock = f"{total_minutes // 60:02d}H{total_minutes % 60:02d}"
    else:
        clock = "--H--"
    _text(canvas, 515, 451, clock, GREEN if _finite(utc) else AMBER, 5)
    _feature(canvas, "AIRBUS_ECAM_PERMANENT_DATA")


def _dial(
    canvas: Any,
    cx: int,
    cy: int,
    value: Any,
    vmin: float,
    vmax: float,
    label: str,
    radius: int = 50,
    decimals: int = 0,
    warn_low: float | None = None,
    warn_high: float | None = None,
    danger_low: float | None = None,
    danger_high: float | None = None,
) -> None:
    """Round Airbus-style gauge: coloured arc sweep + needle + centred value."""
    start, end = 140.0, 400.0
    _arc(canvas, cx, cy, radius, start, end, DIM_GREY, 3)
    for tick in range(5):
        angle = math.radians(start + (end - start) * tick / 4.0)
        inner = radius - 9
        _line(
            canvas,
            cx + inner * math.cos(angle), cy + inner * math.sin(angle),
            cx + radius * math.cos(angle), cy + radius * math.sin(angle),
            WHITE, 2,
        )
    known = _finite(value)
    v = float(value) if known else 0.0
    fraction = _clamp((v - vmin) / max(1e-6, vmax - vmin), 0.0, 1.0) if known else 0.0
    colour = GREEN
    if known:
        if (danger_low is not None and v <= danger_low) or (danger_high is not None and v >= danger_high):
            colour = RED
        elif (warn_low is not None and v <= warn_low) or (warn_high is not None and v >= warn_high):
            colour = AMBER
    _arc(canvas, cx, cy, radius, start, end, colour, 4, fraction)
    if known:
        angle = math.radians(start + (end - start) * fraction)
        _line(canvas, cx, cy, cx + (radius - 10) * math.cos(angle),
              cy + (radius - 10) * math.sin(angle), WHITE, 3)
    _center(canvas, cx, cy - 15, _fmt(value, decimals), WHITE, 6)
    _center(canvas, cx, cy + 14, label, ECAM_BLUE, max(3, len(label)))


def _switch_text(value: Any, on_text: str = "ON", off_text: str = "OFF",
                  unknown: str = "---") -> str:
    if not _finite(value):
        return unknown
    return on_text if float(value) >= 0.5 else off_text


def _switch_colour(value: Any, on_colour: Tuple[int, int, int] = GREEN,
                    off_colour: Tuple[int, int, int] = DIM_GREY,
                    unknown_colour: Tuple[int, int, int] = AMBER) -> Tuple[int, int, int]:
    if not _finite(value):
        return unknown_colour
    return on_colour if float(value) >= 0.5 else off_colour


def _switch_row(canvas: Any, x: int, y: int, label: str, value: Any,
                 on_text: str = "ON", off_text: str = "OFF",
                 on_colour: Tuple[int, int, int] = GREEN) -> None:
    _text(canvas, x, y, label[:_ROW_LABEL_CELLS], DIM_GREY, _ROW_LABEL_CELLS)
    text = _switch_text(value, on_text, off_text)
    colour = _switch_colour(value, on_colour)
    _text(
        canvas,
        x + (_ROW_LABEL_CELLS + _ROW_VALUE_GAP_CELLS) * FONT_CELL_WIDTH,
        y,
        text,
        colour,
        _ROW_VALUE_CELLS,
    )


def _value_row(canvas: Any, x: int, y: int, label: str, value: Any,
                decimals: int = 0, unit: str = "", colour: Tuple[int, int, int] = WHITE) -> None:
    _text(canvas, x, y, label[:_ROW_LABEL_CELLS], DIM_GREY, _ROW_LABEL_CELLS)
    text = _fmt(value, decimals)
    if unit and text != "---":
        text = text + unit
    _text(
        canvas,
        x + (_ROW_LABEL_CELLS + _ROW_VALUE_GAP_CELLS) * FONT_CELL_WIDTH,
        y,
        text,
        colour,
        _ROW_VALUE_CELLS,
    )


# ---------------------------------------------------------------------------
# ENG - EPR primary + N1 secondary (per the plan's approved generic-fallback
# gap), EGT, FF, oil pressure (all real ToLiss arrays), oil temp/vibration
# (generic X-Plane SDK fallback, flagged in the dataref table upstream).
# ---------------------------------------------------------------------------
def _draw_eng(canvas: Any, values: Mapping[str, Any]) -> None:
    _header(canvas, "ENG")
    for index, cx in ((0, 160), (1, 480)):
        master = values.get(f"eng_master_{index}")
        label = f"ENG{index + 1} MASTER"
        colour = GREEN if _finite(master) and float(master) >= 0.5 else (
            RED if _finite(master) else AMBER
        )
        _center(canvas, cx, 44, label, colour, max(3, len(label)))
        _dial(canvas, cx, 160, values.get(f"eng_epr_{index}"), 0.9, 1.7, "EPR",
              50, 2, warn_high=1.55, danger_high=1.65)
        _dial(canvas, cx, 255, values.get(f"eng_egt_{index}"), 0.0, 1000.0, "EGT",
              42, 0, warn_high=650.0, danger_high=950.0)

    # Fixed row geometry: label column centred at x=320 (spans roughly
    # 252..388), value columns clear of it on both sides with a margin -
    # keeps every row's opaque 29px-tall text cell from touching its
    # neighbour (rows are 30px apart) or the label column.
    rows = (
        ("N1 %", "eng_n1", 1),          # generic X-Plane fallback
        ("N2 %", "eng_n2", 1),          # generic X-Plane fallback
        ("FF KG/H", "eng_ff", 0),
        ("OIL PSI", "eng_oilpress", 0),
        ("OIL TEMP", "eng_oiltemp", 0),  # generic X-Plane fallback
        ("VIB", "eng_vib", 1),          # generic X-Plane fallback
    )
    for row_index, (label, prefix, decimals) in enumerate(rows):
        # Six rows must finish above the permanent SD data strip at y=446.
        y = 267 + row_index * 29
        _center(canvas, 320, y, label, ECAM_BLUE, 8)
        _text(canvas, 163, y, _fmt(values.get(f"{prefix}_0"), decimals), WHITE, 5, "right")
        _text(canvas, 392, y, _fmt(values.get(f"{prefix}_1"), decimals), WHITE, 5)


# ---------------------------------------------------------------------------
# BLEED - engine bleed pressure (real dials), valve/switch indications, pack
# temp/flow bars, cross-bleed and APU bleed status.
# ---------------------------------------------------------------------------
def _draw_bleed(canvas: Any, values: Mapping[str, Any]) -> None:
    _header(canvas, "BLEED")
    for index, cx, press_key in ((0, 160, "bleed_press_l"), (1, 480, "bleed_press_r")):
        _center(canvas, cx, 46, f"ENG{index + 1}", ECAM_BLUE, 6)
        _dial(canvas, cx, 140, values.get(press_key), 0.0, 60.0, "PSI", 54, 0, warn_high=50.0)

    _center(canvas, 320, 92, "X BLEED", WHITE, 8)
    xbleed = values.get("bleed_xbleed_ind")
    _center(canvas, 320, 122, _switch_text(xbleed, "OPEN", "SHUT"), _switch_colour(xbleed), 5)
    _center(canvas, 320, 212, "APU BLEED", AMBER, 10)
    apu_bleed = values.get("bleed_apu_ind")
    _center(canvas, 320, 242, _switch_text(apu_bleed, "OPEN", "SHUT"), _switch_colour(apu_bleed), 5)

    rows_left = (
        ("E1 VALVE", "bleed_ind_1", True, "OPEN", "SHUT"),
        ("E1 HP", "bleed_hp_1", True, "OPEN", "SHUT"),
        ("E1 SW", "bleed_switch_1", True, "ON", "OFF"),
        ("PACK1 SW", "bleed_pack_switch_1", True, "ON", "OFF"),
        ("PACK1 TEMP", "bleed_pack_temp_1", False, "", ""),
        ("PACK1 FLOW", "bleed_pack_flow_1", False, "", ""),
    )
    rows_right = (
        ("E2 VALVE", "bleed_ind_2", True, "OPEN", "SHUT"),
        ("E2 HP", "bleed_hp_2", True, "OPEN", "SHUT"),
        ("E2 SW", "bleed_switch_2", True, "ON", "OFF"),
        ("PACK2 SW", "bleed_pack_switch_2", True, "ON", "OFF"),
        ("PACK2 TEMP", "bleed_pack_temp_2", False, "", ""),
        ("PACK2 FLOW", "bleed_pack_flow_2", False, "", ""),
    )
    for x0, rows in ((_ROW_LEFT_X, rows_left), (_ROW_RIGHT_X, rows_right)):
        for row_index, (label, key, is_switch, on_text, off_text) in enumerate(rows):
            # Keep the final PACK FLOW row clear of the permanent data strip.
            y = 265 + row_index * 29
            if is_switch:
                _switch_row(canvas, x0, y, label, values.get(key), on_text, off_text)
            else:
                decimals = 2 if "FLOW" in label else 0
                _value_row(canvas, x0, y, label, values.get(key), decimals)


# ---------------------------------------------------------------------------
# PRESS - cabin altitude / cabin V/S dials, outflow valve, pressurization
# mode. All real AirbusFBW/* datarefs.
# ---------------------------------------------------------------------------
def _draw_press(canvas: Any, values: Mapping[str, Any]) -> None:
    _header(canvas, "PRESS")
    _dial(canvas, 160, 150, values.get("press_cabin_alt"), 0.0, 12000.0, "CAB ALT",
          58, 0, warn_high=8000.0, danger_high=9550.0)
    _dial(canvas, 480, 150, values.get("press_cabin_vs"), -2000.0, 2000.0, "CAB V/S",
          58, 0)
    _vertical_bar(canvas, 311, 96, 108, values.get("press_outflow"), 0.0, 100.0, WHITE)
    _center(canvas, 320, 212, "OFV " + _fmt(values.get("press_outflow"), 0) + "%", WHITE, 12)

    _value_row(canvas, _ROW_LEFT_X, 300, "MODE", values.get("press_mode"))
    _value_row(canvas, _ROW_LEFT_X, 330, "MODE LT", values.get("press_mode_lights"))
    _value_row(canvas, _ROW_RIGHT_X, 300, "OFV AFT", values.get("press_outflow_aft"), 0, "%")


# ---------------------------------------------------------------------------
# COND - cabin/cargo zone temperatures (real) plus vent/heat switches.
# ---------------------------------------------------------------------------
def _draw_cond(canvas: Any, values: Mapping[str, Any]) -> None:
    _header(canvas, "COND")
    _center(canvas, 160, 60, "FWD CABIN", ECAM_BLUE, 10)
    _vertical_bar(canvas, 151, 84, 130, values.get("cond_fwd_cabin_temp"), 0.0, 40.0, WHITE, amber_above=30.0)
    _center(canvas, 160, 222, _fmt(values.get("cond_fwd_cabin_temp"), 0) + " C", WHITE, 8)

    _center(canvas, 480, 60, "AFT CABIN", ECAM_BLUE, 10)
    _vertical_bar(canvas, 471, 84, 130, values.get("cond_aft_cabin_temp"), 0.0, 40.0, WHITE, amber_above=30.0)
    _center(canvas, 480, 222, _fmt(values.get("cond_aft_cabin_temp"), 0) + " C", WHITE, 8)

    _value_row(canvas, _ROW_LEFT_X, 280, "FWD CRGO", values.get("cond_fwd_cargo_temp"), 0, "C")
    _value_row(canvas, _ROW_LEFT_X, 310, "AFT CRGO", values.get("cond_aft_cargo_temp"), 0, "C")
    _value_row(canvas, _ROW_LEFT_X, 340, "BULK CRGO", values.get("cond_bulk_cargo_temp"), 0, "C")
    _switch_row(canvas, _ROW_RIGHT_X, 280, "VENT IN", values.get("cond_vent_inlet"), "OPEN", "SHUT")
    _switch_row(canvas, _ROW_RIGHT_X, 310, "VENT OUT", values.get("cond_vent_extract"), "OPEN", "SHUT")
    _switch_row(canvas, _ROW_RIGHT_X, 340, "CRGO HEAT", values.get("cond_cargo_hot_air"), "ON", "OFF")


# ---------------------------------------------------------------------------
# ELEC - battery voltage (real), generator/bus-tie/ext-power status (real
# switch array, index order guessed), AC/DC bus readout (SDELEC/SDELECDC,
# best-effort - see mcdu_bb36_toliss_paths.py's own comment on this page).
# ---------------------------------------------------------------------------
def _draw_elec(canvas: Any, values: Mapping[str, Any]) -> None:
    _header(canvas, "ELEC")
    _value_row(canvas, _ROW_LEFT_X, 60, "BAT1", values.get("elec_bat_v_0"), 1, "V")
    _value_row(canvas, _ROW_LEFT_X, 90, "BAT2", values.get("elec_bat_v_1"), 1, "V")
    _value_row(canvas, _ROW_LEFT_X, 120, "AC BUS1", values.get("elec_ac_bus_1"), 0)
    _value_row(canvas, _ROW_LEFT_X, 150, "AC BUS2", values.get("elec_ac_bus_2"), 0)
    _value_row(canvas, _ROW_LEFT_X, 180, "DC BUS1", values.get("elec_dc_bus_1"), 0)
    _value_row(canvas, _ROW_LEFT_X, 210, "DC BUS2", values.get("elec_dc_bus_2"), 0)

    _switch_row(canvas, _ROW_RIGHT_X, 60, "GEN1", values.get("elec_gen_1"), "AVAIL", "OFF")
    _switch_row(canvas, _ROW_RIGHT_X, 90, "GEN2", values.get("elec_gen_2"), "AVAIL", "OFF")
    _switch_row(canvas, _ROW_RIGHT_X, 120, "APU GEN", values.get("elec_apu_gen"), "AVAIL", "OFF")
    _switch_row(canvas, _ROW_RIGHT_X, 150, "EXT PWR", values.get("elec_ext_pow"), "AVAIL", "OFF")
    _switch_row(canvas, _ROW_RIGHT_X, 180, "BUS TIE", values.get("elec_ac_tie"), "AUTO", "OFF")


# ---------------------------------------------------------------------------
# HYD - Green/Blue/Yellow system pressure (real dials) + reservoir quantity
# (real bars) + PTU/RAT/electric-pump mode rows. Brake temps live on WHEEL,
# not duplicated here, matching the real A320's own HYD/WHEEL page split.
# ---------------------------------------------------------------------------
def _draw_hyd(canvas: Any, values: Mapping[str, Any]) -> None:
    _header(canvas, "HYD")
    systems = (("G", 110, GREEN), ("B", 320, ECAM_BLUE), ("Y", 530, AMBER))
    for index, (name, cx, colour) in enumerate(systems):
        press = values.get(f"hyd_press_{name.lower()}")
        qty = _ratio_to_percent(values.get(f"hyd_qty_{name.lower()}"))
        _dial(canvas, cx, 110, press, 0.0, 3500.0, name, 44, 0, warn_low=1450.0)
        _vertical_bar(canvas, cx - 9, 172, 70, qty, 0.0, 100.0, colour, amber_below=75.0)
        _text(canvas, cx - 34, 246, _fmt(qty, 0) + "%", WHITE, 8, "center")

    _switch_row(canvas, _ROW_LEFT_X, 300, "PTU", values.get("hyd_ptu_mode"))
    _switch_row(canvas, _ROW_LEFT_X, 330, "RAT", values.get("hyd_rat_mode"))
    _switch_row(canvas, _ROW_LEFT_X, 360, "Y ELEC PMP", values.get("hyd_y_elec_mode"))
    _value_row(canvas, _ROW_RIGHT_X, 300, "BRK ACCU", values.get("hyd_brake_accu"), 0)
    _switch_row(canvas, _ROW_RIGHT_X, 330, "ALTN BRK", values.get("hyd_altn_brake"))


# ---------------------------------------------------------------------------
# FUEL - tank quantity bars (SDFUEL, judgment-call index order), FOB,
# per-engine fuel flow (real, shared with the ENG page's dataref), LP valves.
# ---------------------------------------------------------------------------
def _draw_fuel(canvas: Any, values: Mapping[str, Any]) -> None:
    _header(canvas, "FUEL")
    tanks = (("L", 101, values.get("fuel_qty_l")), ("CTR", 311, values.get("fuel_qty_ctr")),
             ("R", 521, values.get("fuel_qty_r")))
    for label, x, value in tanks:
        _vertical_bar(canvas, x, 60, 140, value, 0.0, 10000.0, GREEN, amber_below=1000.0)
        _center(canvas, x + 9, 210, label + " TANK", ECAM_BLUE, 8)
        _center(canvas, x + 9, 240, _fmt(value, 0), WHITE, 6)

    _center(canvas, 320, 280, "FOB " + _fmt(values.get("fuel_fob"), 0), GREEN, 14)

    _value_row(canvas, _ROW_LEFT_X, 310, "E1 FF", values.get("fuel_ff_0"), 0)
    _switch_row(canvas, _ROW_LEFT_X, 340, "E1 LP VLV", values.get("fuel_lp_valve_0"), "OPEN", "SHUT")
    _value_row(canvas, _ROW_LEFT_X, 370, "APU FF", values.get("fuel_apu_ff"), 0)
    _value_row(canvas, _ROW_RIGHT_X, 310, "E2 FF", values.get("fuel_ff_1"), 0)
    _switch_row(canvas, _ROW_RIGHT_X, 340, "E2 LP VLV", values.get("fuel_lp_valve_1"), "OPEN", "SHUT")
    _value_row(canvas, _ROW_RIGHT_X, 370, "XTRA TKS", values.get("fuel_extra_tanks"), 0)


# ---------------------------------------------------------------------------
# DOOR - pax/cargo door + slide status as a simple fuselage synoptic, plus
# crew/pax oxygen mask status.
# ---------------------------------------------------------------------------
def _draw_door(canvas: Any, values: Mapping[str, Any]) -> None:
    _header(canvas, "DOOR / OXY")
    _center(canvas, WIDTH // 2, 46, "1 = FWD PAIR   2 = AFT PAIR", DIM_GREY, 27)

    door_positions = (
        ("L1", 160, 90, values.get("door_pax_0")),
        ("R1", 420, 90, values.get("door_pax_1")),
        ("L2", 160, 222, values.get("door_pax_2")),
        ("R2", 420, 222, values.get("door_pax_3")),
    )
    for label, x, y, value in door_positions:
        colour = _switch_colour(value, on_colour=RED, off_colour=GREEN)
        _outline(canvas, x - 30, y, 60, 26, colour, 2)
        text = f"{label} {_switch_text(value, 'OPEN', 'SHUT')}"
        _center(canvas, x, y + 30, text, colour, max(3, len(text)))

    _outline(canvas, 100, 168, 440, 44, PANEL_LINE, 2)

    _value_row(canvas, _ROW_LEFT_X, 310, "FWD CRGO", values.get("door_cargo_0"))
    _value_row(canvas, _ROW_LEFT_X, 340, "AFT CRGO", values.get("door_cargo_1"))
    _switch_row(canvas, _ROW_LEFT_X, 370, "BULK", values.get("door_bulk"), "OPEN", "SHUT")
    _switch_row(canvas, _ROW_LEFT_X, 400, "CREW OXY", values.get("door_oxy_crew"))
    _switch_row(canvas, _ROW_RIGHT_X, 310, "COCKPIT", values.get("door_cockpit"), "LOCK", "UNLK")
    _value_row(canvas, _ROW_RIGHT_X, 340, "SLIDES", values.get("door_slides"), 0, "%")
    _switch_row(canvas, _ROW_RIGHT_X, 370, "PAX OXY", values.get("door_oxy_pax"))


# ---------------------------------------------------------------------------
# WHEEL - gear position lights, 4-wheel brake temps (reusing systems_
# renderer's Boeing-proven _wheel widget), brake pressure/park/autobrake.
# ---------------------------------------------------------------------------
def _draw_wheel(canvas: Any, values: Mapping[str, Any]) -> None:
    _header(canvas, "WHEEL")
    for label, x, value in (
        ("L", 220, values.get("wheel_gear_l")),
        ("NOSE", 320, values.get("wheel_gear_n")),
        ("R", 420, values.get("wheel_gear_r")),
    ):
        colour = _switch_colour(value, on_colour=GREEN, off_colour=RED)
        _outline(canvas, x - 24, 56, 48, 30, colour, 2)
        _center(canvas, x, 64, _switch_text(value, "DN", "UP"), colour, 3)
        _center(canvas, x, 94, label, DIM_GREY, max(1, len(label)))

    # Reused as-is from systems_renderer.py (never modified - see module
    # docstring). NOTE: its own two temp labels are spaced 56px apart but
    # each can render up to 68px wide (4 opaque cells), so a double/triple-
    # digit temperature pair can visually touch - a pre-existing trait of
    # the shared widget, not something introduced by this page.
    _wheel(canvas, 160, 210, values.get("wheel_brake_temp_lo"),
           values.get("wheel_brake_temp_li"), "L")
    _wheel(canvas, 480, 210, values.get("wheel_brake_temp_ri"),
           values.get("wheel_brake_temp_ro"), "R")

    _value_row(canvas, _ROW_LEFT_X, 300, "BRK PRESS L", values.get("wheel_brake_l"), 0)
    _value_row(canvas, _ROW_RIGHT_X, 300, "BRK PRESS R", values.get("wheel_brake_r"), 0)
    _switch_row(canvas, _ROW_LEFT_X, 330, "PARK BRK", values.get("wheel_park_brake"), on_colour=RED)
    _switch_row(canvas, _ROW_RIGHT_X, 330, "ANTISKID", values.get("wheel_antiskid"))
    _switch_row(canvas, _ROW_LEFT_X, 360, "AUTO LO", values.get("wheel_autobrk_lo"))
    _switch_row(canvas, _ROW_RIGHT_X, 360, "AUTO MED", values.get("wheel_autobrk_med"))
    _switch_row(canvas, _ROW_LEFT_X, 390, "AUTO MAX", values.get("wheel_autobrk_max"))
    _switch_row(canvas, _ROW_RIGHT_X, 390, "NWS AVAIL", values.get("wheel_nws_avail"))
    _switch_row(canvas, _ROW_LEFT_X, 415, "SPD BRK", values.get("wheel_spd_brake"), on_colour=AMBER)
    _switch_row(canvas, _ROW_RIGHT_X, 415, "BRK FAN", values.get("wheel_brake_fan"))


# ---------------------------------------------------------------------------
# APU - EGT (real, dynamic red limit from AirbusFBW/APUEGTLimit) + N% (real)
# dials, avail/master/starter/bleed/fire status.
# ---------------------------------------------------------------------------
def _draw_apu(canvas: Any, values: Mapping[str, Any]) -> None:
    _header(canvas, "APU")
    egt_limit = values.get("apu_egt_limit")
    danger_egt = float(egt_limit) if _finite(egt_limit) else 700.0
    _dial(canvas, 160, 150, values.get("apu_egt"), 0.0, 800.0, "EGT", 58, 0,
          warn_high=danger_egt - 50.0, danger_high=danger_egt)
    _dial(canvas, 480, 150, values.get("apu_n_pct"), 0.0, 110.0, "N %", 58, 0,
          warn_high=100.0, danger_high=105.0)

    avail = values.get("apu_avail")
    _center(canvas, 320, 110, _switch_text(avail, "AVAIL", "---"), _switch_colour(avail), 8)

    _switch_row(canvas, _ROW_LEFT_X, 260, "MASTER", values.get("apu_master"))
    _switch_row(canvas, _ROW_LEFT_X, 290, "STARTER", values.get("apu_starter"))
    _value_row(canvas, _ROW_LEFT_X, 320, "FUEL FLOW", values.get("apu_ff"), 0)
    _value_row(canvas, _ROW_LEFT_X, 350, "FLAP", values.get("apu_flap"), 0, "%")
    _switch_row(canvas, _ROW_RIGHT_X, 260, "BLEED SW", values.get("apu_bleed_switch"))
    _switch_row(canvas, _ROW_RIGHT_X, 290, "BLEED IND", values.get("apu_bleed_ind"), "OPEN", "SHUT")
    _switch_row(canvas, _ROW_RIGHT_X, 320, "FIRE", values.get("apu_fire"), on_colour=RED)


# ---------------------------------------------------------------------------
# FCTL - Airbus SD flight-control synoptic.  The moving indications below use
# the exact anim/* values that drive the installed ToLiss A320/A321 exterior
# surfaces, not the input axis and not a guessed left/right summary.
# ---------------------------------------------------------------------------
def _surface_ratio(value: Any) -> float | None:
    if not _finite(value):
        return None
    return _clamp(float(value), -1.0, 1.0)


def _draw_vertical_surface(
    canvas: Any, x: int, top: int, bottom: int, value: Any, *, marker_left: bool,
) -> None:
    _line(canvas, x, top, x, bottom, WHITE, 2)
    centre = (top + bottom) // 2
    for y in (top, centre, bottom):
        _line(canvas, x - 7, y, x + 7, y, WHITE, 2)
    ratio = _surface_ratio(value)
    if ratio is None:
        _center(canvas, x, centre - 14, "X", AMBER, 1)
        return
    marker_y = int(round(centre - ratio * (bottom - top) * 0.46))
    if marker_left:
        _line(canvas, x - 19, marker_y, x - 2, marker_y, GREEN, 4)
        _line(canvas, x - 5, marker_y - 6, x, marker_y, GREEN, 2)
        _line(canvas, x - 5, marker_y + 6, x, marker_y, GREEN, 2)
    else:
        _line(canvas, x + 2, marker_y, x + 19, marker_y, GREEN, 4)
        _line(canvas, x + 5, marker_y - 6, x, marker_y, GREEN, 2)
        _line(canvas, x + 5, marker_y + 6, x, marker_y, GREEN, 2)


def _draw_spoiler(canvas: Any, x: int, value: Any, number: int) -> None:
    ratio = _surface_ratio(value)
    deployed = max(0.0, ratio if ratio is not None else 0.0)
    baseline = 108
    tip = int(round(baseline - deployed * 30.0))
    colour = GREEN if ratio is not None else AMBER
    _line(canvas, x, baseline, x, tip, colour, 3)
    if deployed > 0.015:
        _line(canvas, x, tip, x - 5, tip + 7, colour, 2)
        _line(canvas, x, tip, x + 5, tip + 7, colour, 2)
    _center(canvas, x, 112, str(number), colour, 1)


def _trim_text(value: Any) -> str:
    if not _finite(value):
        return "---"
    amount = float(value)
    direction = "UP" if amount > 0.05 else "DN" if amount < -0.05 else ""
    return f"{abs(amount):.1f}{direction}"


def _hyd_colour(value: Any) -> Tuple[int, int, int]:
    if not _finite(value):
        return AMBER
    return GREEN if float(value) >= 1450.0 else AMBER


def _draw_fctl(canvas: Any, values: Mapping[str, Any]) -> None:
    _header(canvas, "F/CTL")
    _center(canvas, 320, 42, "SPD BRK", WHITE, 7)

    # Wing planform and the ten real spoiler panels (1..5 left, 1..5 right).
    _line(canvas, 104, 108, 292, 92, WHITE, 2)
    _line(canvas, 292, 92, 320, 103, WHITE, 2)
    _line(canvas, 320, 103, 348, 92, WHITE, 2)
    _line(canvas, 348, 92, 536, 108, WHITE, 2)
    _line(canvas, 104, 146, 292, 136, WHITE, 2)
    _line(canvas, 292, 136, 348, 136, WHITE, 2)
    _line(canvas, 348, 136, 536, 146, WHITE, 2)
    _line(canvas, 104, 108, 104, 146, WHITE, 2)
    _line(canvas, 536, 108, 536, 146, WHITE, 2)
    for number, x in enumerate((132, 168, 204, 240, 276), start=1):
        _draw_spoiler(canvas, x, values.get(f"fctl_spoiler_{number}"), number)
    for number, x in enumerate((364, 400, 436, 472, 508), start=1):
        _draw_spoiler(canvas, x, values.get(f"fctl_spoiler_{number + 5}"), number)
    _feature(canvas, "FCTL_TEN_SPOILERS")

    # Ailerons flank the wing, with actual left and right ToLiss positions.
    _draw_vertical_surface(canvas, 82, 154, 256, values.get("fctl_aileron_l"), marker_left=False)
    _draw_vertical_surface(canvas, 558, 154, 256, values.get("fctl_aileron_r"), marker_left=True)
    _center(canvas, 82, 262, "L AIL", WHITE, 5)
    _center(canvas, 558, 262, "R AIL", WHITE, 5)
    _feature(canvas, "FCTL_AILERONS")

    # The computer names are fixed page labels.  No green availability is
    # invented because this ToLiss build publishes no ELAC/SEC status array.
    _center(canvas, 235, 158, "ELAC", ECAM_BLUE, 4)
    _center(canvas, 235, 187, "1  2", WHITE, 4)
    _center(canvas, 405, 158, "SEC", ECAM_BLUE, 3)
    _center(canvas, 405, 187, "1 2 3", WHITE, 5)

    # Hydraulic pressure letters match the real F/CTL page colour logic.
    for label, x, key in (
        ("G", 286, "fctl_hyd_g"), ("B", 320, "fctl_hyd_b"),
        ("Y", 354, "fctl_hyd_y"),
    ):
        _center(canvas, x, 158, label, _hyd_colour(values.get(key)), 1)

    _center(canvas, 320, 216, "PITCH TRIM", ECAM_BLUE, 10)
    _center(canvas, 320, 245, _trim_text(values.get("fctl_pitch_trim_deg")), GREEN, 7)

    # Horizontal stabilizer, elevators and the centre fuselage/rudder.
    _line(canvas, 150, 302, 290, 286, WHITE, 2)
    _line(canvas, 290, 286, 350, 286, WHITE, 2)
    _line(canvas, 350, 286, 490, 302, WHITE, 2)
    _line(canvas, 150, 322, 290, 310, WHITE, 2)
    _line(canvas, 290, 310, 350, 310, WHITE, 2)
    _line(canvas, 350, 310, 490, 322, WHITE, 2)
    _line(canvas, 150, 302, 150, 322, WHITE, 2)
    _line(canvas, 490, 302, 490, 322, WHITE, 2)
    _draw_vertical_surface(canvas, 126, 286, 370, values.get("fctl_elevator_l"), marker_left=False)
    _draw_vertical_surface(canvas, 514, 286, 370, values.get("fctl_elevator_r"), marker_left=True)
    _center(canvas, 126, 374, "L ELEV", WHITE, 6)
    _center(canvas, 514, 374, "R ELEV", WHITE, 6)
    _feature(canvas, "FCTL_ELEVATORS")

    _line(canvas, 320, 282, 320, 390, WHITE, 2)
    _line(canvas, 282, 405, 358, 405, WHITE, 2)
    for x in (282, 320, 358):
        _line(canvas, x, 399, x, 411, WHITE, 2)
    rudder = _surface_ratio(values.get("fctl_rudder"))
    if rudder is None:
        _center(canvas, 320, 391, "X", AMBER, 1)
    else:
        marker_x = int(round(320 + rudder * 34.0))
        _fill(canvas, marker_x - 4, 397, 8, 16, GREEN)
    _center(canvas, 320, 414, "RUD", WHITE, 3)
    _text(canvas, 382, 405, "TRIM", ECAM_BLUE, 4)
    _text(canvas, 450, 405, _trim_text(values.get("fctl_yaw_trim_deg")), GREEN, 7)
    _feature(canvas, "FCTL_RUDDER")


# ---------------------------------------------------------------------------
# CRUISE - the automatic Airbus SD cruise page.  It combines the engine oil/
# vibration summary with cabin pressure and temperature information.
# ---------------------------------------------------------------------------
def _draw_cruise(canvas: Any, values: Mapping[str, Any]) -> None:
    _header(canvas, "CRUISE")
    _center(canvas, 320, 44, "ENG", WHITE, 3)
    _center(canvas, 165, 72, "1", WHITE, 1)
    _center(canvas, 475, 72, "2", WHITE, 1)
    for row, label, key, decimals, unit in (
        (105, "OIL QTY", "cruise_oil_qty", 0, "%"),
        (139, "VIB", "cruise_vib", 1, ""),
        (173, "FF", "cruise_ff", 0, ""),
    ):
        _center(canvas, 320, row, label, ECAM_BLUE, 7)
        left = values.get(f"{key}_0")
        right = values.get(f"{key}_1")
        if key == "cruise_oil_qty":
            left, right = _ratio_to_percent(left), _ratio_to_percent(right)
        _text(canvas, 112, row, _fmt(left, decimals) + (unit if _finite(left) else ""), GREEN, 6, "right")
        _text(canvas, 426, row, _fmt(right, decimals) + (unit if _finite(right) else ""), GREEN, 6)

    _fill(canvas, 80, 211, 480, 2, PANEL_LINE)
    _center(canvas, 320, 224, "AIR", WHITE, 3)
    _value_row(canvas, 70, 258, "CAB ALT", values.get("cruise_cabin_alt"), 0)
    _value_row(canvas, 70, 292, "CAB V/S", values.get("cruise_cabin_vs"), 0)
    _value_row(canvas, 350, 258, "DELTA P", values.get("cruise_delta_p"), 1)
    _value_row(canvas, 70, 344, "FWD CAB", values.get("cruise_fwd_temp"), 0, "C", GREEN)
    _value_row(canvas, 350, 344, "AFT CAB", values.get("cruise_aft_temp"), 0, "C", GREEN)
    _feature(canvas, "AIRBUS_CRUISE_PAGE")


# ---------------------------------------------------------------------------
# STATUS - the real page is a scrolling failure-message list; no message-
# text dataref exists in the catalog, so this renders a warning/caution
# summary annunciator from real master-warn/caution + individual flag
# datarefs instead of fabricating message text.
# ---------------------------------------------------------------------------
def _draw_status(canvas: Any, values: Mapping[str, Any]) -> None:
    _header(canvas, "STATUS")
    warn = values.get("status_master_warn")
    caut = values.get("status_master_caut")
    if _finite(warn) and float(warn) >= 0.5:
        banner, colour = "WARNING", RED
    elif _finite(caut) and float(caut) >= 0.5:
        banner, colour = "CAUTION", AMBER
    elif _finite(warn) or _finite(caut):
        banner, colour = "NORMAL", GREEN
    else:
        banner, colour = "---", DIM_GREY
    _fill(canvas, 200, 70, 240, 60, colour if colour != DIM_GREY else PANEL_LINE)
    _center(canvas, 320, 88, banner, BLACK if colour != DIM_GREY else WHITE, 10)

    phase = values.get("status_flight_phase")
    _center(canvas, 320, 156, "FLIGHT PHASE " + _fmt(phase, 0), WHITE, 20)

    # No message-list dataref is catalogued for ToLiss (searched
    # exhaustively) - a real flag summary instead of guessed message text.
    _text(canvas, _ROW_LEFT_X, 200, "NO MESSAGE LIST DATAREF EXISTS", DIM_GREY)
    _text(canvas, _ROW_LEFT_X, 230, "SHOWING REAL FLAGS, NOT TEXT", DIM_GREY)

    _switch_row(canvas, _ROW_LEFT_X, 280, "AP OFF", values.get("status_ap_warn"), on_colour=RED)
    _switch_row(canvas, _ROW_LEFT_X, 310, "A/THR OFF", values.get("status_athr_warn"), on_colour=RED)
    _switch_row(canvas, _ROW_RIGHT_X, 280, "RETARD", values.get("status_retard_warn"), on_colour=AMBER)
    _switch_row(canvas, _ROW_RIGHT_X, 310, "OVERSPEED", values.get("status_ospeed_warn"), on_colour=RED)


_PAGE_HANDLERS = {
    "eng": _draw_eng,
    "bleed": _draw_bleed,
    "press": _draw_press,
    "cond": _draw_cond,
    "elec": _draw_elec,
    "hyd": _draw_hyd,
    "fuel": _draw_fuel,
    "door": _draw_door,
    "wheel": _draw_wheel,
    "apu": _draw_apu,
    "fctl": _draw_fctl,
    "cruise": _draw_cruise,
    "status": _draw_status,
}


def draw_toliss_system_frame(canvas: Any, page: str, values: Mapping[str, Any]) -> None:
    page = str(page).strip().lower()
    from . import toliss_ecam_synoptics as reference
    if page in reference.HANDLERS:
        reference.draw(canvas, page, values)
        reference.permanent_data(canvas, values)
        return
    handler = _PAGE_HANDLERS.get(page)
    if handler is None:
        _header(canvas, "DISPLAY PAGE ERROR", AMBER)
        return
    handler(canvas, values)
    # The lower SD's permanent data line is common to every Airbus system
    # page.  Keep it in the dispatcher so a new page cannot silently omit it.
    reference.permanent_data(canvas, values)


def draw_live_toliss_system_page(canvas: Any, page: str, values: Mapping[str, Any]) -> bool:
    """Emit changed regions for one ECAM page; return True if it drew."""
    page = str(page).strip().lower()
    recorder = _OpRecorder()
    draw_toliss_system_frame(recorder, page, values)
    operations = recorder.ops
    state = getattr(canvas, "_muslimsim_toliss_systems_state", None)
    now = time.monotonic()
    stale = (
        state is None
        or state[0] != page
        or now - state[2] > FULL_REPAINT_SECONDS
        or state[3] >= TOLISS_SYSTEM_FULL_REPAINT_FRAMES
    )
    if stale:
        boxes = [(0, 0, WIDTH, HEIGHT)]
        sequence = 0
    else:
        boxes = _dirty_boxes(operations, state[1])
        sequence = state[3] + 1
    _emit_frame(canvas, operations, boxes)
    try:
        canvas._muslimsim_toliss_systems_state = (page, operations, now, sequence)
    except AttributeError:
        pass
    return bool(boxes)


def invalidate(canvas: Any) -> None:
    try:
        del canvas._muslimsim_toliss_systems_state
    except (AttributeError, TypeError):
        pass


class _BoundsCanvas:
    def colour(self, _red: int, _green: int, _blue: int) -> None:
        return None

    def fill(self, x: int, y: int, width: int, height: int) -> None:
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > WIDTH or y + height > HEIGHT:
            raise TolissSystemsLayoutError(f"fill outside display: {(x, y, width, height)}")

    def text(self, x: int, y: int, value: str, _foreground, _background, _font_id) -> None:
        if x < 0 or y < 0 or x + len(value) * FONT_CELL_WIDTH > WIDTH or y + FONT_CELL_HEIGHT > HEIGHT:
            raise TolissSystemsLayoutError(f"text outside display: {(x, y, value)!r}")


def assert_layout_contract() -> None:
    sample = {
        "ecam_tat": 18.0, "ecam_sat": 12.0,
        "ecam_gw": 68000.0, "ecam_utc": 13 * 3600.0 + 27 * 60.0,
    }
    for page, keys in TOLISS_SYSTEM_PAGE_VALUE_KEYS.items():
        for index, key in enumerate(keys):
            sample[key] = 10.0 + index * 3.5

    for page in TOLISS_SYSTEM_PAGES:
        draw_toliss_system_frame(_BoundsCanvas(), page, sample)

    # Nothing connected yet: every value missing/NaN.
    for page in TOLISS_SYSTEM_PAGES:
        draw_toliss_system_frame(_BoundsCanvas(), page, {})

    # Extreme finite values (a runaway sensor, a full tank, a stuck gauge)
    # must still clamp to the dial/bar geometry rather than overshoot it.
    extreme = {key: 999999.0 for keys in TOLISS_SYSTEM_PAGE_VALUE_KEYS.values() for key in keys}
    for page in TOLISS_SYSTEM_PAGES:
        draw_toliss_system_frame(_BoundsCanvas(), page, extreme)

    negative = {key: -999999.0 for keys in TOLISS_SYSTEM_PAGE_VALUE_KEYS.values() for key in keys}
    for page in TOLISS_SYSTEM_PAGES:
        draw_toliss_system_frame(_BoundsCanvas(), page, negative)

    unknown_page = _BoundsCanvas()
    draw_toliss_system_frame(unknown_page, "not-a-real-page", sample)


__all__ = (
    "TOLISS_SYSTEM_PAGES", "TOLISS_SYSTEM_COMMON_VALUE_KEYS",
    "TOLISS_SYSTEM_PAGE_VALUE_KEYS",
    "assert_layout_contract", "draw_live_toliss_system_page",
    "draw_toliss_system_frame", "invalidate",
)
