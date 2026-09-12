"""Render ToLiss coded-display pages offline without opening any hardware."""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "tools"))

from muslimsim.devices import nd_renderer_toliss as nd
from muslimsim.devices import pfp_renderer_toliss as pfd
from muslimsim.devices import systems_renderer_toliss as systems
import render_pfp_frame_png as emulator
from test_toliss_displays import _load_bridge, _nd_values, _pfd_values


def _save(name: str, renderer, values: dict, output: Path) -> None:
    frame = emulator.PfpFrame()
    renderer(frame, values)
    path = output / name
    frame.image.save(path, "PNG", optimize=True)
    print(
        f"{path.name}: {frame.fills} fills, {frame.texts} text cells, "
        f"{frame.primitives} primitives"
    )


class _DisplayDevice:
    def write(self, report) -> int:
        return len(report)


def _system_values() -> dict:
    values = {
        key: 1.0
        for keys in systems.TOLISS_SYSTEM_PAGE_VALUE_KEYS.values()
        for key in keys
    }
    values.update({
        "ecam_tat": 18.0, "ecam_sat": 12.0,
        "ecam_gw": 68000.0, "ecam_utc": 13 * 3600.0 + 22 * 60.0,
        "eng_epr_0": 1.24, "eng_epr_1": 1.25,
        "eng_egt_0": 590.0, "eng_egt_1": 602.0,
        "eng_n1_0": 84.3, "eng_n1_1": 84.7,
        "eng_n2_0": 91.2, "eng_n2_1": 91.4,
        "eng_ff_0": 860.0, "eng_ff_1": 875.0,
        "eng_oilpress_0": 72.0, "eng_oilpress_1": 70.0,
        "eng_oiltemp_0": 94.0, "eng_oiltemp_1": 96.0,
        "hyd_press_g": 3000.0, "hyd_press_b": 2980.0, "hyd_press_y": 3010.0,
        "hyd_qty_g": 86.0, "hyd_qty_b": 82.0, "hyd_qty_y": 84.0,
        "fuel_qty_l": 3200.0, "fuel_qty_ctr": 1400.0,
        "fuel_qty_r": 3150.0, "fuel_fob": 7750.0,
        "apu_egt": 540.0, "apu_egt_limit": 700.0, "apu_n_pct": 99.5,
        "press_cabin_alt": 6200.0, "press_cabin_vs": 250.0,
        "press_outflow": 42.0, "cond_fwd_cabin_temp": 23.0,
        "cond_aft_cabin_temp": 24.0, "cond_fwd_cargo_temp": 18.0,
        "cond_aft_cargo_temp": 17.0, "cond_bulk_cargo_temp": 16.0,
        "wheel_brake_temp_lo": 210.0, "wheel_brake_temp_li": 225.0,
        "wheel_brake_temp_ri": 218.0, "wheel_brake_temp_ro": 205.0,
        "fctl_pitch_trim_deg": 1.3, "fctl_yaw_trim_deg": -0.2,
        "fctl_aileron_l": -0.42, "fctl_aileron_r": 0.42,
        "fctl_elevator_l": -0.18, "fctl_elevator_r": -0.18,
        "fctl_rudder": 0.30,
        "fctl_hyd_g": 3000.0, "fctl_hyd_b": 2980.0, "fctl_hyd_y": 3010.0,
        "cruise_oil_qty_0": 0.82, "cruise_oil_qty_1": 0.80,
        "cruise_vib_0": 0.7, "cruise_vib_1": 0.8,
        "cruise_ff_0": 860.0, "cruise_ff_1": 875.0,
        "cruise_cabin_alt": 6200.0, "cruise_cabin_vs": 250.0,
        "cruise_delta_p": 7.8, "cruise_fwd_temp": 23.0,
        "cruise_aft_temp": 24.0,
    })
    for index, deployed in enumerate((0.0, 0.18, 0.42, 0.75, 0.28), start=1):
        values[f"fctl_spoiler_{index}"] = deployed
        values[f"fctl_spoiler_{index + 5}"] = deployed
    return values


def _save_mcdu(output: Path) -> None:
    """Exercise the exact ToLiss 24x14/23x29 physical MCDU painter."""
    bridge = _load_bridge()
    emulator.FONT_RESOURCE = PROJECT / "bridge" / bridge.MCDU_PFD_FONT_FILENAME
    frame = emulator.PfpFrame()
    glyphs, size = emulator._load_font_glyphs(2)
    frame._glyphs[2] = glyphs
    frame._font_sizes[2] = size

    lines = (
        "         INIT       23",
        " CO RTE        FROM/TO ",
        " MSIM01        KDFW/KIAH",
        " ALTN/CO RTE   INIT     ",
        " ----/-------- REQUEST* ",
        " FLT NBR       IRS INIT>",
        " MS3201                 ",
        "                        ",
        " COST INDEX        WIND>",
        " 25                TROPO",
        " CRZ FL/TEMP       36090",
        " FL350/-54       GND TEMP",
        "                   +18  ",
        "                        ",
    )
    lines = tuple(line[:24].ljust(24) for line in lines)
    colours = tuple(tuple([None] * 24) for _ in lines)
    bridge._toliss_draw_mcdu_content(_DisplayDevice(), frame, lines, colours)
    path = output / "mcdu-native-grid.png"
    frame.image.save(path, "PNG", optimize=True)
    print(f"{path.name}: native slot-2 {size[0]}x{size[1]} glyph grid")


def main() -> int:
    output = PROJECT / "PNG" / "toliss-display-preview"
    output.mkdir(parents=True, exist_ok=True)

    normal_pfd = _pfd_values()
    invalid_pfd = {
        **normal_pfd,
        "ias_valid": 0.0,
        "alt_valid": 0.0,
        "att_valid": 0.0,
        "hdg_valid": 0.0,
    }
    normal_nd = _nd_values()

    _save("pfd-normal.png", pfd.draw_toliss_pfd_frame, normal_pfd, output)
    _save(
        "pfd-takeoff-speeds.png", pfd.draw_toliss_pfd_frame,
        {
            **normal_pfd,
            "roll": 0.0,
            "ias": 135.0,
            "v1": 138.0,
            "v_r": 145.0,
            "v2": 150.0,
            "show_to_speeds": 1.0,
            "v_f": 195.0,
            "v_s": 0.0,
            "v_green_dot": 0.0,
            "ils_on": 0.0,
        },
        output,
    )
    _save(
        "pfd-approach-ils.png", pfd.draw_toliss_pfd_frame,
        {
            **normal_pfd,
            "roll": 0.0,
            "ias": 165.0,
            "v_max": 177.0,
            "v1": 0.0,
            "v_r": 0.0,
            "v2": 0.0,
            "show_to_speeds": 0.0,
            "v_f": 0.0,
            "v_s": 170.0,
            "v_green_dot": 0.0,
            "loc_dev": -0.35,
            "gs_dev": 0.25,
            "ils_on": 1.0,
        },
        output,
    )
    _save(
        "pfd-clean-limit.png", pfd.draw_toliss_pfd_frame,
        {
            **normal_pfd,
            "roll": 0.0,
            "ias": 335.0,
            "v_max": 340.0,
            "show_to_speeds": 0.0,
            "v_f": 0.0,
            "v_s": 0.0,
            "v_vfe_next": 0.0,
            "ils_on": 0.0,
        },
        output,
    )
    _save("pfd-invalid.png", pfd.draw_toliss_pfd_frame, invalid_pfd, output)
    _save("nd-arc.png", nd.draw_toliss_nd_frame, normal_nd, output)
    _save(
        "nd-plan.png", nd.draw_toliss_nd_frame,
        {**normal_nd, "mode": 4.0, "range_index": 2.0}, output,
    )
    _save(
        "nd-invalid.png", nd.draw_toliss_nd_frame,
        {**normal_nd, "map_available": 0.0, "gps_primary_message": 2.0},
        output,
    )
    system_values = _system_values()
    for page in systems.TOLISS_SYSTEM_PAGES:
        _save(
            f"ecam-{page}.png",
            lambda frame, values, page=page: systems.draw_toliss_system_frame(
                frame, page, values,
            ),
            system_values,
            output,
        )
    _save_mcdu(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
