"""Declarative MuslimSim hardware catalogue.

Only protocol details already present in the bridge/device drivers are listed
as implemented.  A physical control that has not been captured or a device
that has no driver stays visible as ``unknown``/``unimplemented``: the lab
must never turn a product name into a made-up HID map.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import FrozenSet, Iterable, Mapping, Optional, Tuple

# These two tables are the captured physical-key maps that the existing PFP
# and MCDU bridge paths already use.  Importing a map has no device side
# effect: both modules defer HID access until their managers are started.
try:  # pragma: no cover - source-only fallback is deliberately graceful
    from ..devices.pfp_bb35_separate_paths import PFP3_KEYS
except Exception:
    PFP3_KEYS = {}

try:  # pragma: no cover - source-only fallback is deliberately graceful
    from ..devices.mcdu_bb36 import MCDU_KEY_MAP
except Exception:
    MCDU_KEY_MAP = {}

try:  # pragma: no cover - optional device module must not block catalogue UI
    from ..devices.fcu_efis_ba01 import (
        FCU_EFIS_CONTROL_DEFINITIONS,
        FCU_EFIS_ZIBO_DEFAULT_ROLES,
    )
except Exception:
    FCU_EFIS_CONTROL_DEFINITIONS = ()
    FCU_EFIS_ZIBO_DEFAULT_ROLES = {}


INPUT_KINDS = frozenset({"button", "toggle", "rotary", "axis", "selector"})
OUTPUT_KINDS = frozenset({"led", "lamp", "display", "solenoid", "gauge"})


@dataclass(frozen=True)
class ControlSpec:
    """One known control surface on a device.

    ``raw`` is deliberately descriptive rather than executable.  It lets the
    diagnostic/UI show exactly which report bit, axis, serial field, or driver
    function established the control.  ``status`` is one of ``implemented``,
    ``unknown``, or ``unimplemented``.
    """

    key: str
    label: str
    kind: str
    direction: str
    raw: str
    status: str = "implemented"
    remappable: bool = False
    testable: bool = False
    choices: Tuple[str, ...] = ()
    notes: str = ""

    @property
    def is_input(self) -> bool:
        return self.direction in {"input", "bidirectional"}

    @property
    def is_output(self) -> bool:
        return self.direction in {"output", "bidirectional"}


@dataclass(frozen=True)
class DeviceSpec:
    key: str
    title: str
    transport: str
    identity: str
    driver: str
    status: str = "implemented"
    notes: str = ""
    controls: Tuple[ControlSpec, ...] = field(default_factory=tuple)
    aliases: Tuple[str, ...] = ()

    def control(self, key: str) -> Optional[ControlSpec]:
        return next((item for item in self.controls if item.key == key), None)


def _input(
    key: str,
    label: str,
    kind: str,
    raw: str,
    *,
    choices: Iterable[str] = (),
    status: str = "implemented",
    notes: str = "",
) -> ControlSpec:
    return ControlSpec(
        key, label, kind, "input", raw, status, status == "implemented", True,
        tuple(choices), notes,
    )


def _output(
    key: str,
    label: str,
    kind: str,
    raw: str,
    *,
    testable: bool = True,
    status: str = "implemented",
    notes: str = "",
) -> ControlSpec:
    return ControlSpec(
        key, label, kind, "output", raw, status, False, testable,
        (), notes,
    )


# BB70's contact report is deliberately discovered rather than assumed.  The
# passive driver emits names in this exact format only after an actual report
# delta is observed.  These dynamic controls are valid mapping sources, but
# never claim an Airbus role until the owner assigns the observed contact to a
# labelled visual button in Studio.
_ECAM32_CAPTURE_CONTROL = re.compile(r"^raw_r[0-9a-f]{2}_b[0-9]{2}_bit[0-7]$")


def runtime_control_by_key(device_key: str, control_key: str) -> Optional[ControlSpec]:
    """Return a static or a user-captured runtime control safely."""

    device = device_by_key(device_key)
    if device is None:
        return None
    known = device.control(control_key)
    if known is not None:
        return known
    if device.key == "ecam32" and _ECAM32_CAPTURE_CONTROL.fullmatch(str(control_key)):
        return ControlSpec(
            str(control_key), "Captured ECAM physical contact", "button", "input",
            "Observed BB70 HID report delta", "implemented", True, True,
            (), "This raw contact was observed from the connected BB70. Assign it to one A320 faceplate button before mapping it.",
        )
    return None


def _unknown_bits(prefix: str, count: int, known: Iterable[int], *, source: str) -> Tuple[ControlSpec, ...]:
    """Expose uncaptured descriptor bits without pretending they are usable."""

    used = {int(item) for item in known}
    return tuple(
        _input(
            f"{prefix}_{index}",
            f"Unmapped raw input {index}",
            "button",
            f"{source} bit {index}",
            status="unknown",
            notes="The raw bit exists in the current descriptor/reader, but no physical semantic mapping was captured.",
        )
        for index in range(count)
        if index not in used
    )


def _captured_keypad_controls(
    key_map: Mapping[int, Tuple[str, Optional[str]]],
    *,
    raw_name: str,
) -> Tuple[ControlSpec, ...]:
    """Make a remappable control for every input in a captured keypad map.

    ``key_N`` deliberately keeps the physical report identity stable.  The
    human-readable label and the original bridge role are kept separately in
    ``DEFAULT_ROLES`` below, so restoring a profile always returns the device
    to its proven pre-Studio behaviour.
    """

    return tuple(
        _input(
            f"key_{int(index)}",
            str(label),
            "button",
            f"{raw_name} HID report 0x01 bit {int(index)}",
            notes=(
                "Captured physical keypad map. The original bridge mapping "
                "remains active until this control is explicitly remapped."
            ),
        )
        for index, (label, _action) in sorted(key_map.items())
    )


# The BB62 map is the capture-verified PDC_CONTROLS table in
# devices/pdc_bb62.py.  Its output packet framing is known, but no selector
# meaning was captured, so it is expressly not an output control below.
_PDC_BUTTONS = (
    ("fpv", "FPV", 0), ("mtrs", "MTRS", 1), ("wxr", "WXR", 2),
    ("sta", "STA", 3), ("wpt", "WPT", 4), ("arpt", "ARPT", 5),
    ("data", "DATA", 6), ("pos", "POS", 7), ("terr", "TERR", 8),
    ("vor_adf_1_vor", "VOR/ADF 1 VOR", 9),
    ("vor_adf_1_off", "VOR/ADF 1 OFF", 10),
    ("vor_adf_1_adf", "VOR/ADF 1 ADF", 11),
    ("vor_adf_2_vor", "VOR/ADF 2 VOR", 12),
    ("vor_adf_2_off", "VOR/ADF 2 OFF", 13),
    ("vor_adf_2_adf", "VOR/ADF 2 ADF", 14),
    ("mins_reset", "MINS reset", 15), ("tfc", "TFC", 17),
    ("baro_std", "BARO STD", 18),
    ("mins_mode_radio", "MINS RADIO", 23),
    ("mins_mode_baro", "MINS BARO", 24),
    ("baro_mode_in", "BARO IN", 25),
    ("baro_mode_hpa", "BARO HPA", 26),
    ("mode_app", "MODE APP", 27), ("mode_vor", "MODE VOR", 28),
    ("mode_map", "MODE MAP", 29), ("mode_plan", "MODE PLAN", 30),
    ("range_5", "RANGE 5", 31), ("range_10", "RANGE 10", 32),
    ("range_20", "RANGE 20", 33), ("range_40", "RANGE 40", 34),
    ("range_80", "RANGE 80", 35), ("range_160", "RANGE 160", 36),
    ("range_320", "RANGE 320", 37),
    ("mins_knob_ccw", "MINS knob counter-clockwise", 39),
    ("mins_knob_cw", "MINS knob clockwise", 41),
    ("baro_knob_ccw", "BARO knob counter-clockwise", 42),
    ("baro_knob_cw", "BARO knob clockwise", 44),
)

_PDC_CONTROLS = tuple(
    _input(key, label, "rotary" if "knob" in key else "button", f"HID report 0x01 bit {bit}")
    for key, label, bit in _PDC_BUTTONS
) + (
    _input("raw_axis_x", "Raw axis X", "axis", "HID report 0x01 bytes 9..10", status="unknown",
           notes="Descriptor known; no semantic control was verified."),
    _input("raw_axis_y", "Raw axis Y", "axis", "HID report 0x01 bytes 11..12", status="unknown",
           notes="Descriptor known; no semantic control was verified."),
    _output("unmapped_vendor_output", "Vendor LED/LCD output", "display", "report 0x02 / 0xF0", testable=False,
            status="unknown", notes="Packet framing is known, selector meanings are not captured; writes are blocked."),
) + _unknown_bits("raw_bit", 64, (bit for _key, _label, bit in _PDC_BUTTONS), source="HID report 0x01")


# MUSLIMSIM_PDC_CANONICAL_BB61_BB52_V1_3
# Capture-verified fixed-side PDC semantic controls. These keys exactly match
# muslimsim.devices.pdc_bb61_bb52 event.control values.
_PDC_BB61_LEFT_CONTROLS = (
    _input("fpv", "FPV", "button", "BB61 HID report 0x01 bit 0"),
    _input("mtrs", "MTRS", "button", "BB61 HID report 0x01 bit 1"),
    _input("wxr", "WXR", "button", "BB61 HID report 0x01 bit 2"),
    _input("sta", "STA", "button", "BB61 HID report 0x01 bit 3"),
    _input("wpt", "WPT", "button", "BB61 HID report 0x01 bit 4"),
    _input("arpt", "ARPT", "button", "BB61 HID report 0x01 bit 5"),
    _input("data", "DATA", "button", "BB61 HID report 0x01 bit 6"),
    _input("pos", "POS", "button", "BB61 HID report 0x01 bit 7"),
    _input("terr", "TERR", "button", "BB61 HID report 0x01 bit 8"),
    _input("vor1", "VOR/ADF 1 selector", "selector",
           "BB61 HID report 0x01 bits 9..11 one-hot",
           choices=("VOR", "OFF", "ADF1")),
    _input("vor2", "VOR/ADF 2 selector", "selector",
           "BB61 HID report 0x01 bits 12..14 one-hot",
           choices=("VOR", "OFF", "ADF2")),
    _input("mins_rst", "MINS reset", "button", "BB61 HID report 0x01 bit 15"),
    _input("ctr", "CTR", "button", "BB61 HID report 0x01 bit 16"),
    _input("tfc", "TFC", "button", "BB61 HID report 0x01 bit 17"),
    _input("baro_std", "BARO STD", "button", "BB61 HID report 0x01 bit 18"),
    _input("mins_mode", "MINS RADIO / BARO", "selector",
           "BB61 HID report 0x01 bits 23..24 one-hot",
           choices=("RADIO", "BARO")),
    _input("baro_unit", "BARO IN / HPA", "selector",
           "BB61 HID report 0x01 bits 25..26 one-hot",
           choices=("IN", "HPA")),
    _input("map_mode", "MODE selector", "selector",
           "BB61 HID report 0x01 bits 27..30 one-hot",
           choices=("APP", "VOR", "MAP", "PLN")),
    _input("map_range", "RANGE selector", "selector",
           "BB61 HID report 0x01 bits 31..38 one-hot",
           choices=("5", "10", "20", "40", "80", "160", "320", "640")),
    _input("mins_dec", "MINS decrease", "rotary", "BB61 HID report 0x01 bit 39"),
    _input("mins_inc", "MINS increase", "rotary", "BB61 HID report 0x01 bit 41"),
    _input("baro_dec", "BARO decrease", "rotary", "BB61 HID report 0x01 bit 42"),
    _input("baro_inc", "BARO increase", "rotary", "BB61 HID report 0x01 bit 44"),
)

_PDC_BB52_RIGHT_CONTROLS = (
    _input("fpv", "FPV", "button", "BB52 HID report 0x01 bit 0"),
    _input("mtrs", "MTRS", "button", "BB52 HID report 0x01 bit 1"),
    _input("vsd", "VSD", "button", "BB52 HID report 0x01 bit 2"),
    _input("wxr", "WXR", "button", "BB52 HID report 0x01 bit 3"),
    _input("sta", "STA", "button", "BB52 HID report 0x01 bit 4"),
    _input("wpt", "WPT", "button", "BB52 HID report 0x01 bit 5"),
    _input("arpt", "ARPT", "button", "BB52 HID report 0x01 bit 6"),
    _input("data", "DATA", "button", "BB52 HID report 0x01 bit 7"),
    _input("pos", "POS", "button", "BB52 HID report 0x01 bit 8"),
    _input("terr", "TERR", "button", "BB52 HID report 0x01 bit 9"),
    _input("vor1", "VOR/ADF 1 selector", "selector",
           "BB52 HID report 0x01 bits 10..12 one-hot",
           choices=("VOR", "OFF", "ADF1")),
    _input("vor2", "VOR/ADF 2 selector", "selector",
           "BB52 HID report 0x01 bits 13..15 one-hot",
           choices=("VOR", "OFF", "ADF2")),
    _input("mins_rst", "MINS reset", "button", "BB52 HID report 0x01 bit 16"),
    _input("ctr", "CTR", "button", "BB52 HID report 0x01 bit 17"),
    _input("tfc", "TFC", "button", "BB52 HID report 0x01 bit 18"),
    _input("baro_std", "BARO STD", "button", "BB52 HID report 0x01 bit 19"),
    _input("range_dec", "RANGE decrease", "rotary", "BB52 HID report 0x01 bit 20"),
    _input("range_inc", "RANGE increase", "rotary", "BB52 HID report 0x01 bit 21"),
    _input("mins_mode", "MINS RADIO / BARO", "selector",
           "BB52 HID report 0x01 bits 24..25 one-hot",
           choices=("RADIO", "BARO")),
    _input("baro_unit", "BARO IN / HPA", "selector",
           "BB52 HID report 0x01 bits 26..27 one-hot",
           choices=("IN", "HPA")),
    _input("map_mode", "MODE selector", "selector",
           "BB52 HID report 0x01 bits 28..31 one-hot",
           choices=("APP", "VOR", "MAP", "PLN")),
    _input("mins_dec", "MINS decrease", "rotary", "BB52 HID report 0x01 bit 33"),
    _input("mins_inc", "MINS increase", "rotary", "BB52 HID report 0x01 bit 35"),
    _input("baro_dec", "BARO decrease", "rotary", "BB52 HID report 0x01 bit 37"),
    _input("baro_inc", "BARO increase", "rotary", "BB52 HID report 0x01 bit 39"),
)


_PAP3_COMMANDS = (
    ("n1", "N1", 0), ("speed", "SPEED", 1), ("vnav", "VNAV", 2),
    ("lvl_chg", "LVL CHG", 3), ("hdg_sel", "HDG SEL", 4),
    ("lnav", "LNAV", 5), ("vorloc", "VOR LOC", 6), ("app", "APP", 7),
    ("alt_hld", "ALT HLD", 8), ("vs", "V/S", 9), ("cmd_a", "CMD A", 10),
    ("cws_a", "CWS A", 11), ("cmd_b", "CMD B", 12), ("cws_b", "CWS B", 13),
    ("change_over", "C/O", 14), ("spd_intv", "SPD INTV", 15),
    ("alt_intv", "ALT INTV", 16), ("course_capt_dec", "CRS CAPT -", 17),
    ("course_capt_inc", "CRS CAPT +", 18), ("speed_dec", "SPD -", 19),
    ("speed_inc", "SPD +", 20), ("heading_dec", "HDG -", 21),
    ("heading_inc", "HDG +", 22), ("altitude_dec", "ALT -", 23),
    ("altitude_inc", "ALT +", 24), ("course_fo_dec", "CRS FO -", 25),
    ("course_fo_inc", "CRS FO +", 26), ("vs_dec", "V/S -", 38),
    ("vs_inc", "V/S +", 39),
)

_PAP3_CONTROLS = tuple(
    _input(key, label, "rotary" if key.endswith(("_dec", "_inc")) else "button", f"HID report 0x01 bit {bit}")
    for key, label, bit in _PAP3_COMMANDS
) + (
    _input("fd_capt", "Flight director captain", "toggle", "HID report 0x01 bit 27"),
    _input("fd_fo", "Flight director first officer", "toggle", "HID report 0x01 bit 29"),
    _input("ap_disconnect", "Autopilot disconnect", "toggle", "HID report 0x01 bits 31/32"),
    _input("bank_angle", "Bank angle selector", "selector", "HID report 0x01 bits 33..37",
           choices=("10", "15", "20", "25", "30")),
    _input("at_arm", "A/T ARM", "toggle", "HID report 0x01 bits 40/41"),
    _output("lcd", "Six native MCP numeric windows", "display", "0xF0 LCD transaction", notes="Numeric/segment display; free text is not a supported protocol feature."),
    _output("annunciators", "MCP annunciators", "led", "0x02 selectors 3..19"),
    _output("backlight", "Panel and LCD backlight", "led", "0x02 selectors 0..2"),
    _output("at_arm_solenoid", "Magnetic A/T ARM solenoid", "solenoid", "0x02 selector 0x1E",
            notes="Binary arm/release only. The protocol exposes no strength, endpoints, direction, or calibration control."),
) + _unknown_bits(
    "raw_bit", 48,
    tuple(bit for _key, _label, bit in _PAP3_COMMANDS) + (27, 29, 31, 32, 33, 34, 35, 36, 37, 40, 41),
    source="HID report 0x01",
)


_PU_LIGHTS = tuple(
    _output(f"lamp_{bit}", label, "lamp", f"COM5 P7 bit {bit}")
    for bit, label in (
        (0, "GPS"), (1, "IRS L ALIGN"), (2, "IRS L ON DC"), (3, "IRS R ALIGN"),
        (4, "IRS R ON DC"), (5, "FUEL CTR L"), (6, "FUEL CTR R"),
        (7, "FUEL 1 AFT"), (8, "FUEL 1 FWD"), (9, "FUEL 2 FWD"),
        (10, "FUEL 2 AFT"), (11, "YAW DAMPER"), (12, "GRD PWR AVAIL"),
        (13, "TRANSFER BUS 1"), (14, "TRANSFER BUS 2"), (15, "SOURCE OFF 1"),
        (16, "SOURCE OFF 2"), (17, "GEN OFF BUS 1"), (18, "APU GEN OFF BUS"),
        (19, "GEN OFF BUS 2"), (20, "APU MAINT"), (21, "APU LOW OIL"),
        (22, "APU FAULT"), (23, "APU OVERSPEED"), (24, "WINDOW HEAT L SIDE"),
        (25, "WINDOW HEAT L FWD"), (26, "WINDOW HEAT R FWD"),
        (27, "WINDOW HEAT R SIDE"), (28, "HYD ENG 1"), (29, "HYD ELEC 2"),
        (30, "HYD ELEC 1"), (31, "HYD ENG 2"),
    )
)

_PU_INPUT_CONTROLS = (
    _input("irs_left", "Left IRS mode selector", "selector", "PU SDL buttons 1..4", choices=("OFF", "ALIGN", "NAV", "ATT")),
    _input("irs_right", "Right IRS mode selector", "selector", "PU SDL buttons 5..8", choices=("OFF", "ALIGN", "NAV", "ATT")),
    _input("fuel_ctr_l", "Center fuel pump left", "toggle", "PU SDL button 9 (pressed = OFF)"),
    _input("fuel_ctr_r", "Center fuel pump right", "toggle", "PU SDL button 10 (pressed = OFF)"),
    _input("fuel_l_fwd", "Fuel pump 1 forward", "toggle", "PU SDL button 11 (pressed = OFF)"),
    _input("fuel_l_aft", "Fuel pump 1 aft", "toggle", "PU SDL button 12 (pressed = OFF)"),
    _input("fuel_r_aft", "Fuel pump 2 aft", "toggle", "PU SDL button 13 (pressed = OFF)"),
    _input("fuel_r_fwd", "Fuel pump 2 forward", "toggle", "PU SDL button 14 (pressed = OFF)"),
    _input("yaw_damper", "Yaw damper", "toggle", "PU SDL button 15 (pressed = OFF)"),
    _input("ground_power_off", "Ground power OFF", "button", "PU SDL button 16 (spring endpoint)"),
    _input("ground_power_on", "Ground power ON", "button", "PU SDL button 17 (spring endpoint)"),
    _input("gen1_off", "Generator 1 OFF", "button", "PU SDL button 18 (spring endpoint)"),
    _input("gen1_on", "Generator 1 ON", "button", "PU SDL button 19 (spring endpoint)"),
    _input("apu_gen1_off", "APU generator 1 OFF", "button", "PU SDL button 20 (spring endpoint)"),
    _input("apu_gen1_on", "APU generator 1 ON", "button", "PU SDL button 21 (spring endpoint)"),
    _input("apu_gen2_off", "APU generator 2 OFF", "button", "PU SDL button 22 (spring endpoint)"),
    _input("apu_gen2_on", "APU generator 2 ON", "button", "PU SDL button 23 (spring endpoint)"),
    _input("gen2_off", "Generator 2 OFF", "button", "PU SDL button 24 (spring endpoint)"),
    _input("gen2_on", "Generator 2 ON", "button", "PU SDL button 25 (spring endpoint)"),
    _input("wiper_selector", "Wiper selector", "selector", "PU SDL buttons 26..29", choices=("PARK", "INT", "LOW", "HIGH")),
    _input("window_heat_r_fwd", "Window heat right forward", "toggle", "PU SDL button 30 (pressed = OFF)"),
    _input("window_heat_l_fwd", "Window heat left forward", "toggle", "PU SDL button 31 (pressed = OFF)"),
    _input("window_heat_l_side", "Window heat left side", "toggle", "PU SDL button 32 (pressed = OFF)"),
    _input("window_heat_r_side", "Window heat right side", "toggle", "PU SDL button 33 (pressed = OFF)"),
    _input("probe_heat_capt", "Probe heat captain", "toggle", "PU SDL button 34 (pressed = OFF)"),
    _input("probe_heat_fo", "Probe heat first officer", "toggle", "PU SDL button 35 (pressed = OFF)"),
    _input("wing_anti_ice", "Wing anti-ice", "toggle", "PU SDL button 36 (pressed = OFF)"),
    _input("eng1_anti_ice", "Engine 1 anti-ice", "toggle", "PU SDL button 37 (pressed = OFF)"),
    _input("eng2_anti_ice", "Engine 2 anti-ice", "toggle", "PU SDL button 38 (pressed = OFF)"),
    _input("hyd_elec2", "Hydraulic electric pump 2", "toggle", "PU SDL button 39 (pressed = OFF)"),
    _input("hyd_elec1", "Hydraulic electric pump 1", "toggle", "PU SDL button 40 (pressed = OFF)"),
    _input("hyd_eng2", "Hydraulic engine pump 2", "toggle", "PU SDL button 41 (pressed = OFF)"),
    _input("hyd_eng1", "Hydraulic engine pump 1", "toggle", "PU SDL button 42 (pressed = OFF)"),
    _input(
        "battery_on", "DC/BAT switch", "toggle", "PU SDL button 43 (pressed = ON)",
        notes=(
            "Captured Stage-5 PU overhead switch. Pressed is BAT ON; released "
            "is BAT OFF. The existing Zibo/LevelUp bridge role remains active "
            "until this control is explicitly remapped."
        ),
    ),
    _input("no_smoking", "No-smoking sign", "selector", "PU SDL button 44 (OFF / ON; no AUTO detent)", choices=("OFF", "ON")),
    _input("fasten_belts", "Fasten-belts sign", "selector", "PU SDL buttons 45..46", choices=("OFF", "AUTO", "ON")),
    _input("l_pack", "Left pack selector", "selector", "PU SDL buttons 47..48", choices=("OFF", "AUTO", "HIGH")),
    _input("isolation_valve", "Isolation valve selector", "selector", "PU SDL buttons 49..50", choices=("CLOSE", "AUTO", "OPEN")),
    _input("r_pack", "Right pack selector", "selector", "PU SDL buttons 52 / 51", choices=("OFF", "AUTO", "HIGH")),
    _input("bleed_air_1", "Engine 1 bleed air", "toggle", "PU SDL button 53 (pressed = OFF)"),
    _input("bleed_air_apu", "APU bleed air", "toggle", "PU SDL button 54 (pressed = OFF)"),
    _input("bleed_air_2", "Engine 2 bleed air", "toggle", "PU SDL button 55 (pressed = OFF)"),
    _input("landing_light_left", "Landing light left", "toggle", "PU SDL button 56 (pressed = OFF)"),
    _input("landing_light_right", "Landing light right", "toggle", "PU SDL button 57 (pressed = OFF)"),
    _input("runway_turnoff_left", "Runway turnoff left", "toggle", "PU SDL button 58 (pressed = OFF)"),
    _input("runway_turnoff_right", "Runway turnoff right", "toggle", "PU SDL button 59 (pressed = OFF)"),
    _input("taxi_light", "Taxi light", "toggle", "PU SDL button 60 (pressed = OFF)"),
    _input("apu_start", "APU selector", "selector", "PU SDL buttons 61..62", choices=("OFF", "ON", "START")),
    _input("engine_start_1", "Engine 1 start selector", "selector", "PU SDL buttons 63..66", choices=("GRD", "OFF", "CONT", "FLT")),
    _input("ignition_source", "Engine ignition selector", "selector", "PU SDL buttons 67..68", choices=("IGN L", "BOTH", "IGN R")),
    _input("engine_start_2", "Engine 2 start selector", "selector", "PU SDL buttons 69..72", choices=("GRD", "OFF", "CONT", "FLT")),
    _input("logo_light", "Logo light", "toggle", "PU SDL button 73 (pressed = OFF)"),
    _input("position_lights", "Position / strobe lights", "selector", "PU SDL buttons 74..75", choices=("STEADY", "OFF", "STROBE & STEADY")),
    _input("beacon_light", "Anti-collision beacon", "toggle", "PU SDL button 76 (pressed = OFF)"),
    _input("wing_light", "Wing light", "toggle", "PU SDL button 77 (pressed = OFF)"),
    _input("flt_alt_cw", "FLT altitude clockwise", "rotary", "Raw Input byte 10 mask 0x40"),
    _input("flt_alt_ccw", "FLT altitude counter-clockwise", "rotary", "Raw Input byte 10 mask 0x20"),
    _input("land_alt_cw", "LAND altitude clockwise", "rotary", "Raw Input byte 11 mask 0x01"),
    _input("land_alt_ccw", "LAND altitude counter-clockwise", "rotary", "Raw Input byte 10 mask 0x80"),
    _input("panel_brightness", "Panel brightness", "axis", "SDL axis 0"),
)

_PU_CONTROLS = _PU_INPUT_CONTROLS + (
    _output("flt_altitude", "FLT altitude display", "display", "COM5 OVHD field"),
    _output("land_altitude", "LAND altitude display", "display", "COM5 OVHD field"),
    _output("apu_egt", "APU EGT gauge", "gauge", "COM5 P4"),
    _output("panel_backlight", "Panel brightness", "led", "COM5 P8 0..125"),
    _output("engine_start_retract", "Engine start auto-retract", "solenoid", "COM5 P1 timed pulse",
            notes="The confirmed control is a timed GRD-return pulse only. No motor endpoints, force, or direction protocol is present."),
) + _PU_LIGHTS + _unknown_bits(
    "raw_button", 78,
    tuple(range(1, 78)),
    source="PU SDL reader button",
)


_THROTTLE_CONTROLS = (
    _input("left_thrust", "Left thrust lever", "axis", "HID bytes 13..14 / SDL axis 3"),
    _input("right_thrust", "Right thrust lever", "axis", "HID bytes 15..16 / SDL axis 4"),
    _input("speedbrake", "Speedbrake", "axis", "HID bytes 19..20 / SDL axis 6"),
    _input("flap_axis", "Flap lever position", "axis", "HID bytes 21..22 / SDL axis 7"),
    _input("engine_1_idle", "ENG 1 start lever IDLE", "button", "HID bit 1"),
    _input("engine_1_cutoff", "ENG 1 start lever CUTOFF", "button", "HID bit 2"),
    _input("engine_2_idle", "ENG 2 start lever IDLE", "button", "HID bit 3"),
    _input("engine_2_cutoff", "ENG 2 start lever CUTOFF", "button", "HID bit 4"),
    _input(
        "aux_button_1", "Captured auxiliary button 1", "button", "B930 HID button 5",
        notes=(
            "Confirmed in light_throttle_engine fire light_lcd back light.pcapng. "
            "The report proves the contact but not its printed face label, so it is deliberately "
            "shown as AUX 1 and is fully remappable."
        ),
    ),
    _input(
        "aux_button_2", "Captured auxiliary button 2", "button", "B930 HID button 6",
        notes=(
            "Confirmed in light_throttle_engine fire light_lcd back light.pcapng. "
            "The report proves the contact but not its printed face label, so it is deliberately "
            "shown as AUX 2 and is fully remappable."
        ),
    ),
    _input("at_disconnect_left", "A/T disconnect left", "button", "HID bit 10"),
    _input("at_disconnect_right", "A/T disconnect right", "button", "HID bit 11"),
    _input(
        "trim_mode_cycle", "IGN/START knob push — next trim role", "button",
        "B930 HID bit 24",
        notes=(
            "Confirmed by MODE.pcapng: report byte 3 mask 0x80. In the ToLiss "
            "profile each press cycles PITCH and RUDDER without changing "
            "the separate CRANK/NORM/IGN-START engine-mode detents."
        ),
    ),
    _input("rudder_trim_reset", "Rudder trim reset", "button", "HID bit 25"),
    _input("rudder_trim_left", "Rudder trim left", "button", "HID bit 26",
           notes="Captured held contact. The existing bridge repeats the native rudder-trim-left command while it is held."),
    _input("rudder_trim_center", "Rudder trim centre contact", "button", "HID bit 27",
           notes="Captured centre contact. It is exposed for visual feedback and optional remapping; the established bridge does not assign it a default simulator action."),
    _input("rudder_trim_right", "Rudder trim right", "button", "HID bit 28",
           notes="Captured held contact. The existing bridge repeats the native rudder-trim-right command while it is held."),
    _input("parking_brake_off", "Parking brake OFF", "button", "HID bit 29"),
    _input("parking_brake_on", "Parking brake ON", "button", "HID bit 30"),
    _input("flaps_0", "Flaps 0", "button", "HID bit 35"),
    _input("flaps_5", "Flaps 5", "button", "HID bit 34"),
    _input("flaps_15", "Flaps 15", "button", "HID bit 33"),
    _input("flaps_25", "Flaps 25", "button", "HID bit 32"),
    _input("flaps_30", "Flaps 30", "button", "HID bit 31"),
    # Kept for profile migration only.  New faceplates use the five separate
    # captured detent contacts above so every physical flap position can be
    # selected and remapped independently.
    _input("flaps", "Flap detent (legacy group)", "selector", "HID bits 31..35", choices=("0", "5", "15", "25", "30"), status="unknown",
           notes="Superseded by separately captured Flaps 0/5/15/25/30 contacts."),
    # Profile-specific three-position selector: it remains the established
    # trim-role selector for the 737 profile, while ToLiss uses the three
    # actual Airbus engine-mode commands.  The ToLiss trim role is button 24.
    _input("trim_mode_crank", "Trim-role selector CRANK — pitch", "selector", "HID bit 7", choices=("PITCH",),
           notes="737: pitch-trim role. ToLiss: real engine-mode CRANK; trim role is cycled by the knob push (bit 24)."),
    _input("trim_mode_norm", "Trim-role selector NORM — rudder", "selector", "HID bit 8", choices=("RUDDER",),
           notes="737: rudder-trim role. ToLiss: real engine-mode NORM; trim role is cycled by the knob push (bit 24)."),
    _input("trim_mode_ign_start", "Trim-role selector IGN/START — aileron", "selector", "HID bit 9", choices=("AILERON",),
           notes="737: aileron-trim role. ToLiss: real engine-mode IGN/START; trim role is cycled by the knob push (bit 24)."),
    _output(
        "rudder_trim_display", "RUD TRIM numeric window", "display",
        "B930 captured F0 set-values + refresh reports",
        notes=(
            "Captured from the user's PAC while MobiFlight updated the physical RUD TRIM display. "
            "It accepts numeric L/R xx.x or positive pitch units plus the fixed captured-segment "
            "role labels PtCH/rUdr/ALrn; arbitrary text and other B930 display features remain unsupported."
        ),
    ),
    _output(
        "stab_trim_display", "RUD TRIM window as stabilizer units", "display",
        "B930 captured F0 set-values + refresh reports, unsigned",
        notes=(
            "The same physical window and the same two captured reports, written as a "
            "stabilizer-units readout for the hard-wired pitch-trim rocker: no L/R glyph, "
            "and 0.0-19.9 instead of the signed rudder scale. It needs its own control "
            "because every write is validated against this catalogue, so a window mode "
            "that is not declared here cannot be driven at all."
        ),
    ),
    _output(
        "throttle_backlight", "Throttle base backlight", "led",
        "B930 group 0x10 / LED channel 0",
        notes="Captured 0..255 brightness channel. This is the main throttle-base illumination.",
    ),
    _output(
        "flaps_airbrake_backlight", "Flaps / airbrake panel backlight", "led",
        "B930 group 0x01 / LED channel 0",
        notes="Captured 0..255 brightness channel for the attached PAC panel.",
    ),
    _output(
        "trim_display_backlight", "RUD TRIM numeric-display backlight", "led",
        "B930 group 0x01 / LED channel 2",
        notes="Captured 0..255 digital-tube/display brightness channel; it is not a general-purpose LCD writer.",
    ),
    _output(
        "engine_1_fault_light", "ENG 1 FAULT light", "lamp",
        "B930 group 0x10 / LED channel 3",
    ),
    _output(
        "engine_1_fire_light", "ENG 1 FIRE light", "lamp",
        "B930 group 0x10 / LED channel 4",
    ),
    _output(
        "engine_2_fault_light", "ENG 2 FAULT light", "lamp",
        "B930 group 0x10 / LED channel 5",
    ),
    _output(
        "engine_2_fire_light", "ENG 2 FIRE light", "lamp",
        "B930 group 0x10 / LED channel 6",
    ),
    _output(
        "vibration_motor_1", "Vibration motor 1", "gauge",
        "B930 group 0x10 / dynamic-vibration channel 14",
        notes="Captured 0..255 intensity channel. Studio uses a short test pulse and always returns it to zero.",
    ),
    _output(
        "vibration_motor_2", "Vibration motor 2", "gauge",
        "B930 group 0x10 / dynamic-vibration channel 16",
        notes="Captured 0..255 intensity channel. Studio uses a short test pulse and always returns it to zero.",
    ),
) + _unknown_bits(
    "raw_bit", 96,
    (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41),
    source="Throttle HID report",
)


# The combined FCU/EFIS unit is physically present as 4098:BA01.  The first
# twelve payload bytes have a source-verified FCU/L-EFIS/R-EFIS bitmap.  The
# rest of the report stays visible in diagnostics but is explicitly unknown
# and non-remappable; no unverified bit can accidentally fly the aircraft.
_FCU_EFIS_CONTROLS = tuple(
    _input(
        definition.key,
        definition.label,
        definition.kind,
        f"BA01 HID report 0x01 byte {1 + definition.bit // 8} bit {definition.bit % 8}",
        notes=(
            "Verified FCU/EFIS BA01 input. It uses its Zibo default until "
            "you save a remap in the active MuslimSim profile."
        ),
    )
    for definition in FCU_EFIS_CONTROL_DEFINITIONS
) + _unknown_bits(
    "unknown_bit", 63 * 8,
    (definition.bit for definition in FCU_EFIS_CONTROL_DEFINITIONS),
    source="BA01 HID report 0x01",
)
_FCU_EFIS_CONTROLS += (
    _output(
        "fcu_windows", "FCU speed / heading / altitude / V/S windows", "display",
        "BA01 documented F0 FCU value frames", notes=(
            "Four native FCU value windows. Studio mirrors the same values sent to the device; "
            "the BA01 input report does not provide display readback."
        ),
    ),
    _output(
        "captain_baro", "Captain EFIS BARO window", "display",
        "BA01 documented F0 EFIS-L value frames",
    ),
    _output(
        "first_officer_baro", "First-officer EFIS BARO window", "display",
        "BA01 documented F0 EFIS-R value frames",
    ),
    _output(
        "backlight", "FCU / EFIS panel and screen backlight", "led",
        "BA01 documented selector 0 / 1 brightness reports",
    ),
)


# The AGP is an Airbus A320-style panel.  These positions are the complete
# named input map published by the independent WinCtrl/ToLiss driver.  Keeping
# it in one table lets the live reader, Studio, profile migration, and practice
# cockpit agree on the exact physical contact without a user capture pass.
AGP_HID_CONTROL_MAP = {
    0: "brake_fan_on", 1: "brake_fan_off",
    2: "autobrake_low", 3: "autobrake_med", 4: "autobrake_max",
    5: "anti_skid_on", 6: "anti_skid_off",
    7: "rst_ccw", 8: "rst", 9: "rst_cw",
    10: "chr_left", 11: "chr_press", 12: "chr_right",
    13: "date_ccw", 14: "date_press", 15: "date_cw",
    16: "utc_gps", 17: "utc_int", 18: "utc_set",
    19: "timer_run", 20: "timer_stop", 21: "timer_reset",
    22: "terr_on_nd", 23: "gear_up", 24: "gear_down",
}

_AGP_CONTROLS = (
    _input("brake_fan_on", "BRK FAN ON", "toggle", "HID input index 0",
           notes="A320 brake-fan locking switch: ON."),
    _input("brake_fan_off", "BRK FAN OFF", "toggle", "HID input index 1",
           notes="A320 brake-fan locking switch: OFF."),
    _input("autobrake_low", "Autobrake LOW", "button", "HID input index 2",
           notes="A320 LOW autobrake selector."),
    _input("autobrake_med", "Autobrake MED", "button", "HID input index 3",
           notes="A320 MED autobrake selector."),
    _input("autobrake_max", "Autobrake MAX", "button", "HID input index 4",
           notes="A320 MAX autobrake selector."),
    _input("anti_skid_on", "A/SKID & N/W STRG ON", "toggle", "HID input index 5",
           notes="A320 anti-skid and nose-wheel-steering locking switch: ON."),
    _input("anti_skid_off", "A/SKID & N/W STRG OFF", "toggle", "HID input index 6",
           notes="A320 anti-skid and nose-wheel-steering locking switch: OFF."),
    _input("rst_ccw", "RST rotary counter-clockwise", "rotary", "HID counter bytes 21..22 / legacy contact 7",
           notes="Counter-authoritative. RADIO: native Zibo RTP fine down. NAV: selected MCP speed down."),
    _input("rst", "RST press / radio transfer", "button", "HID input index 8",
           notes="RADIO: selected Zibo RTP active/standby transfer. NAV: no native action."),
    _input("rst_cw", "RST rotary clockwise", "rotary", "HID counter bytes 21..22 / legacy contact 9",
           notes="Counter-authoritative. RADIO: native Zibo RTP fine up. NAV: selected MCP speed up."),
    _input("chr_left", "CHR rotary counter-clockwise", "rotary", "HID counter bytes 23..24 / legacy contact 10",
           notes="Counter-authoritative. RADIO: native Zibo RTP coarse down. NAV: selected MCP altitude down."),
    _input("chr_press", "CHR press", "button", "HID input index 11",
           notes="No factory RADIO/NAV action. Available for explicit user remap; never changes AGP mode."),
    _input("chr_right", "CHR rotary clockwise", "rotary", "HID counter bytes 23..24 / legacy contact 12",
           notes="Counter-authoritative. RADIO: native Zibo RTP coarse up. NAV: selected MCP altitude up."),
    _input("date_ccw", "SET rotary counter-clockwise", "rotary", "HID counter bytes 25..26 / legacy contact 13",
           notes="Counter-authoritative. RADIO: decrement selected octal squawk digit. NAV: selected MCP heading down."),
    _input("date_press", "SET press / ATC edit gesture", "button", "HID input index 14",
           notes="RADIO physical gesture: first long press enters edit on current digit; each later long press advances D1→D2→D3→D4→D1 and keeps flashing; short tap exits edit/stops flashing. NAV: no native action."),
    _input("date_cw", "SET rotary clockwise", "rotary", "HID counter bytes 25..26 / legacy contact 15",
           notes="Counter-authoritative. RADIO: increment selected octal squawk digit. NAV: selected MCP heading up."),
    _input("utc_gps", "VHF 1 selector", "selector", "HID input index 16", choices=("vhf1",),
           notes="RADIO: select VHF1. NAV: no native action."),
    _input("utc_int", "VHF 2 selector", "selector", "HID input index 17", choices=("vhf2",),
           notes="RADIO: select VHF2. NAV: no native action."),
    _input("utc_set", "VHF 3 selector", "selector", "HID input index 18", choices=("vhf3",),
           notes="RADIO: select Zibo VHF3 display. NAV: no native action."),
    _input("timer_run", "ATC selector RUN / STBY", "selector", "HID input index 19", choices=("run",),
           notes="RADIO: maintained RUN selects Zibo transponder STBY and briefly confirms Stby on ET before returning to squawk. Never changes AGP display mode."),
    _input("timer_stop", "ATC selector STP / ALT OFF", "selector", "HID input index 20", choices=("stop",),
           notes="RADIO: deliberate RUN→STP selects ALT OFF and briefly confirms ALoF on ET. Spring return after RST is ignored so logical ALT ON/TA/TA-RA persists."),
    _input("timer_reset", "ATC selector spring RST / NEXT", "selector", "HID input index 21", choices=("reset",),
           notes="RADIO: spring pulse cycles ALT ON→TA→TA/RA→ALT ON; each selection is briefly confirmed on ET, then squawk returns. Physical return to STP does not reset the logical mode."),
    _input("terr_on_nd", "TERR ON ND / RADIO-NAV mode", "toggle", "HID input index 22",
           notes="Dedicated AGP mode control. Every press toggles RADIO↔NAV; no other native AGP control may change mode."),
    _input("gear_up", "Landing gear UP contact", "toggle", "HID input index 23"),
    _input("gear_down", "Landing gear DOWN contact", "toggle", "HID input index 24"),
    _output("chr", "CHR display", "display", "HID 0xF0 digits 0..3"),
    _output("utc", "UTC display", "display", "HID 0xF0 digits 4..9"),
    _output("et", "ET display", "display", "HID 0xF0 digits 10..13"),
    _output(
        "display_mode", "RADIO/NAV mode", "display",
        "Bridge-owned mode request; physical TERR ON ND is the native owner",
        notes="Studio may request only 'radio' or 'navigation'.",
    ),
    _output("autobrake_lamps", "Autobrake lamps", "led", "AGP LED selectors"),
    _output("gear_lamps", "Landing-gear lamps", "led", "AGP LED selectors"),
) + tuple(
    _input(
        f"raw_bit_{index}",
        f"Unassigned AGP report contact {index}",
        "button",
        f"AGP HID report 0x01 input index {index}",
        status="unknown",
        notes="The published A320 panel uses input indices 0 through 24. This remaining report bit has no confirmed front-panel role.",
    )
    # The report decoder exposes 96 input bits (64 low + 32 high).  Keeping
    # the full range available to Capture means a rear/secondary contact is
    # not silently lost just because it lies past the first byte group.
    for index in range(96)
    if index not in AGP_HID_CONTROL_MAP
)


_DISPLAY_UNKNOWN_INPUT = _input(
    "keypad", "Keypad / page switch", "button", "driver-owned HID input",
    status="unknown", notes="The current bridge's separate path routers own this input; no complete semantic key map is stored here.",
)


# The device drivers already own these defaults.  They are declarative here
# purely so Studio can say what a control does *before* an owner changes it.
# A blank/default profile never routes through this table; it falls through to
# the existing bridge dispatcher, preserving working aircraft behaviour.
DEFAULT_ROLES: Mapping[str, Mapping[str, str]] = {
    "pap3_mag": {
        "n1": "Zibo MCP: N1", "speed": "Zibo MCP: SPEED", "vnav": "Zibo MCP: VNAV",
        "lvl_chg": "Zibo MCP: LVL CHG", "hdg_sel": "Zibo MCP: HDG SEL", "lnav": "Zibo MCP: LNAV",
        "vorloc": "Zibo MCP: VOR LOC", "app": "Zibo MCP: APP", "alt_hld": "Zibo MCP: ALT HLD",
        "vs": "Zibo MCP: V/S", "cmd_a": "Zibo MCP: CMD A", "cws_a": "Zibo MCP: CWS A",
        "cmd_b": "Zibo MCP: CMD B", "cws_b": "Zibo MCP: CWS B", "change_over": "Zibo MCP: C/O",
        "spd_intv": "Zibo MCP: SPD INTV", "alt_intv": "Zibo MCP: ALT INTV",
        "course_capt_dec": "Zibo MCP: captain course down", "course_capt_inc": "Zibo MCP: captain course up",
        "speed_dec": "Zibo MCP: speed down", "speed_inc": "Zibo MCP: speed up",
        "heading_dec": "Zibo MCP: heading down", "heading_inc": "Zibo MCP: heading up",
        "altitude_dec": "Zibo MCP: altitude down", "altitude_inc": "Zibo MCP: altitude up",
        "course_fo_dec": "Zibo MCP: first-officer course down", "course_fo_inc": "Zibo MCP: first-officer course up",
        "vs_dec": "Zibo MCP: vertical speed down", "vs_inc": "Zibo MCP: vertical speed up",
        "fd_capt": "Zibo MCP: captain flight director", "fd_fo": "Zibo MCP: first-officer flight director",
        "ap_disconnect": "Zibo MCP: autopilot disconnect", "bank_angle": "Zibo MCP: bank-angle selector",
        "at_arm": "Zibo MCP: autothrottle arm",
    },
    "pdc_bb62": {
        "fpv": "Zibo captain EFIS: FPV", "mtrs": "Zibo captain EFIS: MTRS",
        "wxr": "Zibo captain EFIS: WXR", "sta": "Zibo captain EFIS: STA",
        "wpt": "Zibo captain EFIS: WPT", "arpt": "Zibo captain EFIS: ARPT",
        "data": "Zibo captain EFIS: DATA", "pos": "Zibo captain EFIS: POS",
        "terr": "Zibo captain EFIS: TERR", "tfc": "Zibo captain EFIS: TFC",
        "mins_reset": "Zibo captain EFIS: MINS reset", "baro_std": "Zibo captain EFIS: BARO STD",
        "vor_adf_1_vor": "Zibo captain EFIS: VOR/ADF 1 VOR", "vor_adf_1_off": "Zibo captain EFIS: VOR/ADF 1 OFF",
        "vor_adf_1_adf": "Zibo captain EFIS: VOR/ADF 1 ADF", "vor_adf_2_vor": "Zibo captain EFIS: VOR/ADF 2 VOR",
        "vor_adf_2_off": "Zibo captain EFIS: VOR/ADF 2 OFF", "vor_adf_2_adf": "Zibo captain EFIS: VOR/ADF 2 ADF",
        "mins_mode_radio": "Zibo captain EFIS: MINS RADIO", "mins_mode_baro": "Zibo captain EFIS: MINS BARO",
        "baro_mode_in": "Zibo captain EFIS: BARO inches", "baro_mode_hpa": "Zibo captain EFIS: BARO hPa",
        "mode_app": "Zibo captain EFIS: APP mode", "mode_vor": "Zibo captain EFIS: VOR mode",
        "mode_map": "Zibo captain EFIS: MAP mode", "mode_plan": "Zibo captain EFIS: PLAN mode",
        "range_5": "Zibo captain EFIS: range 5", "range_10": "Zibo captain EFIS: range 10",
        "range_20": "Zibo captain EFIS: range 20", "range_40": "Zibo captain EFIS: range 40",
        "range_80": "Zibo captain EFIS: range 80", "range_160": "Zibo captain EFIS: range 160",
        "range_320": "Zibo captain EFIS: range 320", "mins_knob_ccw": "Zibo captain EFIS: MINS down",
        "mins_knob_cw": "Zibo captain EFIS: MINS up", "baro_knob_ccw": "Zibo captain EFIS: BARO down",
        "baro_knob_cw": "Zibo captain EFIS: BARO up",
    },
    "pdc_bb61_left": {
        "fpv": "Zibo captain EFIS: FPV",
        "mtrs": "Zibo captain EFIS: MTRS",
        "wxr": "Zibo captain EFIS: WXR",
        "sta": "Zibo captain EFIS: STA",
        "wpt": "Zibo captain EFIS: WPT",
        "arpt": "Zibo captain EFIS: ARPT",
        "data": "Zibo captain EFIS: DATA",
        "pos": "Zibo captain EFIS: POS",
        "terr": "Zibo captain EFIS: TERR",
        "vor1": "Zibo captain EFIS: VOR/ADF 1 selector",
        "vor2": "Zibo captain EFIS: VOR/ADF 2 selector",
        "mins_rst": "Zibo captain EFIS: MINS reset",
        "ctr": "Zibo captain EFIS: CTR",
        "tfc": "Zibo captain EFIS: TFC",
        "baro_std": "Zibo captain EFIS: BARO STD",
        "mins_mode": "Zibo captain EFIS: MINS RADIO/BARO",
        "baro_unit": "Zibo captain EFIS: BARO IN/HPA",
        "map_mode": "Zibo captain EFIS: MODE selector",
        "map_range": "Zibo captain EFIS: RANGE selector",
        "mins_dec": "Zibo captain EFIS: MINS down",
        "mins_inc": "Zibo captain EFIS: MINS up",
        "baro_dec": "Zibo captain EFIS: BARO down",
        "baro_inc": "Zibo captain EFIS: BARO up",
        "vsd": "Zibo captain EFIS: VSD",
        "range_dec": "Zibo captain EFIS: RANGE down",
        "range_inc": "Zibo captain EFIS: RANGE up",
    },
    "pdc_bb52_right": {
        "fpv": "Zibo first-officer EFIS: FPV",
        "mtrs": "Zibo first-officer EFIS: MTRS",
        "vsd": "Zibo first-officer EFIS: VSD",
        "wxr": "Zibo first-officer EFIS: WXR",
        "sta": "Zibo first-officer EFIS: STA",
        "wpt": "Zibo first-officer EFIS: WPT",
        "arpt": "Zibo first-officer EFIS: ARPT",
        "data": "Zibo first-officer EFIS: DATA",
        "pos": "Zibo first-officer EFIS: POS",
        "terr": "Zibo first-officer EFIS: TERR",
        "vor1": "Zibo first-officer EFIS: VOR/ADF 1 selector",
        "vor2": "Zibo first-officer EFIS: VOR/ADF 2 selector",
        "mins_rst": "Zibo first-officer EFIS: MINS reset",
        "ctr": "Zibo first-officer EFIS: CTR",
        "tfc": "Zibo first-officer EFIS: TFC",
        "baro_std": "Zibo first-officer EFIS: BARO STD",
        "range_dec": "Zibo first-officer EFIS: RANGE down",
        "range_inc": "Zibo first-officer EFIS: RANGE up",
        "mins_mode": "Zibo first-officer EFIS: MINS RADIO/BARO",
        "baro_unit": "Zibo first-officer EFIS: BARO IN/HPA",
        "map_mode": "Zibo first-officer EFIS: MODE selector",
        "mins_dec": "Zibo first-officer EFIS: MINS down",
        "mins_inc": "Zibo first-officer EFIS: MINS up",
        "baro_dec": "Zibo first-officer EFIS: BARO down",
        "baro_inc": "Zibo first-officer EFIS: BARO up",
    },
    "agp_bb80": {
        "brake_fan_on": "Brake fan ON", "brake_fan_off": "Brake fan OFF",
        "autobrake_low": "Autobrake LOW", "autobrake_med": "Autobrake MED",
        "autobrake_max": "Autobrake MAX",
        "anti_skid_on": "A/SKID & N/W STRG ON",
        "anti_skid_off": "A/SKID & N/W STRG OFF",
        "rst_ccw": "RADIO fine down / NAV speed down",
        "rst": "RADIO active/standby transfer",
        "rst_cw": "RADIO fine up / NAV speed up",
        "chr_left": "RADIO coarse down / NAV altitude down",
        "chr_press": "User-remappable press",
        "chr_right": "RADIO coarse up / NAV altitude up",
        "date_ccw": "RADIO selected ATC digit down / NAV heading down",
        "date_press": "RADIO long press enter/advance ATC digit; short tap exits edit",
        "date_cw": "RADIO selected ATC digit up / NAV heading up",
        "utc_gps": "RADIO VHF1 select",
        "utc_int": "RADIO VHF2 select",
        "utc_set": "RADIO VHF3 select",
        "timer_run": "RADIO ATC STBY",
        "timer_stop": "RADIO ATC ALT OFF / spring-return center",
        "timer_reset": "RADIO ATC next ALT ON/TA/TA-RA",
        "terr_on_nd": "Dedicated AGP RADIO/NAV mode toggle",
        "gear_up": "Landing gear UP", "gear_down": "Landing gear DOWN",
    },
    "winctrl_throttle": {
        "trim_mode_norm": "737 trim role: rudder",
        "trim_mode_crank": "Trim role: pitch",
        "trim_mode_ign_start": "Trim role: aileron",
        "trim_mode_cycle": "ToLiss: cycle pitch / rudder trim role",
        "rudder_trim_reset": "X-Plane: rudder trim centre",
        # The RUD TRIM rocker is hard-wired to the Zibo stabilizer trim wheel
        # and ignores the MODE trim-role selector.  The printed face label
        # still says RUD TRIM, so say plainly what it actually does.
        "rudder_trim_left": "Zibo: stabilizer trim NOSE DOWN while held",
        "rudder_trim_right": "Zibo: stabilizer trim NOSE UP while held",
    },
}

DEFAULT_ROLES = {
    **DEFAULT_ROLES,
    "fcu_32_efis": dict(FCU_EFIS_ZIBO_DEFAULT_ROLES),
    "pfp3n_bb35": {
        f"key_{int(index)}": (
            str(action).replace("__", "").replace("_", " ").title()
            if action and action.startswith("__")
            else (str(action) if action else "No original simulator action")
        )
        for index, (_label, action) in PFP3_KEYS.items()
    },
    "mcdu32_bb36": {
        f"key_{int(index)}": (
            str(action).replace("__", "").replace("_", " ").title()
            if action and action.startswith("__")
            else (str(action) if action else "No original simulator action")
        )
        for index, (_label, action) in MCDU_KEY_MAP.items()
    },
}

_PFP3N_CONTROLS = _captured_keypad_controls(PFP3_KEYS, raw_name="PFP3N BB35")
_MCDU32_CONTROLS = _captured_keypad_controls(MCDU_KEY_MAP, raw_name="MCDU32 BB36")

# Owner-supplied Moza preset files prove the configuration surface below.  The
# A210 capture additionally proves its standard joystick input collection; it
# remains separate so the AB6 does not inherit a protocol that was not
# captured from it.
_MOZA_BASE_CALIBRATION_CONTROLS = (
    _input(
        "axis_x", "X axis / roll calibration", "axis", "Moza preset axis X settings",
        status="unknown", notes="The supplied preset defines axis-X range, reversal and curve settings; its USB report position was not captured.",
    ),
    _input(
        "axis_y", "Y axis / pitch calibration", "axis", "Moza preset axis Y settings",
        status="unknown", notes="The supplied preset defines axis-Y range, reversal and curve settings; its USB report position was not captured.",
    ),
    _input(
        "axis_z", "Z axis / auxiliary calibration", "axis", "Moza preset axis Z settings",
        status="unknown", notes="The supplied preset defines axis-Z reversal and curve settings; its USB report position was not captured.",
    ),
    _output(
        "force_feedback_profile", "Force-feedback profile", "gauge", "Moza .preset values",
        testable=False, status="unimplemented", notes="Preset parameters are saved as a Studio profile. No Moza USB force-feedback protocol was supplied or inferred, so Studio does not send motor commands.",
    ),
)

_MOZA_A210_LIVE_CONTROLS = (
    _input("axis_x", "X / roll axis", "axis", "A210 report 01, unsigned 16-bit X"),
    _input("axis_y", "Y / pitch axis", "axis", "A210 report 01, unsigned 16-bit Y"),
    _input("axis_z", "Z axis", "axis", "A210 report 01, unsigned 16-bit Z"),
    _input("axis_rx", "Rx axis", "axis", "A210 report 01, unsigned 16-bit Rx"),
    _input("axis_ry", "Ry axis", "axis", "A210 report 01, unsigned 16-bit Ry"),
    _input("axis_rz", "Rz axis", "axis", "A210 report 01, unsigned 16-bit Rz"),
    _input("axis_slider", "Slider axis", "axis", "A210 report 01, unsigned 16-bit Slider"),
    _input("axis_dial", "Dial axis", "axis", "A210 report 01, unsigned 16-bit Dial"),
    _input("hat", "Hat switch", "selector", "A210 report 01, four-bit HID hat"),
) + tuple(
    _input(
        f"button_{number:03d}", f"Captured HID button {number:03d}", "button",
        f"A210 report 01, HID Button usage {number}",
        notes="The report proves this contact; its physical face label has not been guessed.",
    )
    for number in range(1, 129)
)


# MUSLIMSIM_MOZA_AB6_CAPTURE_V1
# Captured from the connected base by tools/capture_moza_ab6.py, not inherited
# from the A210 on the strength of the shared vendor id.  The AB6 returns a
# 1259-byte HID report descriptor whose SHA-256 is
# d6749e4488da932e7584bd5ec30d2e862c0c14b3f5841b9488f636e84edbdd15 - byte for
# byte the A210's own descriptor - and streams the same 34-byte report 01 at
# about 975 Hz.  The input collection is therefore proven identical, and the
# existing capture-proven A210 decode applies to it unchanged.
#
# A 30-second full-travel exercise on the owner's base (28669 frames) then
# established which of the eight declared axes the AB6 physically carries:
# X, Y, Slider and Dial each swept the complete 0..65535 range, while Z sat
# pinned at 32767 and Rx/Ry/Rz at 0 throughout.  The four are still catalogued,
# because the report field genuinely exists and decodes - they are marked as
# observed-idle rather than deleted on the strength of one session.
_MOZA_AB6_IDLE_AXIS_NOTE = (
    "Declared by the report descriptor and decoded, but a full-travel exercise "
    "of the base produced no motion on this axis. Present for a variant that "
    "uses it; do not map it without confirming it moves."
)
_MOZA_AB6_LIVE_CONTROLS = (
    _input("axis_x", "X / roll axis", "axis", "AB6 report 01, unsigned 16-bit X"),
    _input("axis_y", "Y / pitch axis", "axis", "AB6 report 01, unsigned 16-bit Y"),
    _input(
        "axis_z", "Z axis", "axis", "AB6 report 01, unsigned 16-bit Z",
        notes=_MOZA_AB6_IDLE_AXIS_NOTE,
    ),
    _input(
        "axis_rx", "Rx axis", "axis", "AB6 report 01, unsigned 16-bit Rx",
        notes=_MOZA_AB6_IDLE_AXIS_NOTE,
    ),
    _input(
        "axis_ry", "Ry axis", "axis", "AB6 report 01, unsigned 16-bit Ry",
        notes=_MOZA_AB6_IDLE_AXIS_NOTE,
    ),
    _input(
        "axis_rz", "Rz axis", "axis", "AB6 report 01, unsigned 16-bit Rz",
        notes=_MOZA_AB6_IDLE_AXIS_NOTE,
    ),
    _input("axis_slider", "Slider axis", "axis", "AB6 report 01, unsigned 16-bit Slider"),
    _input("axis_dial", "Dial axis", "axis", "AB6 report 01, unsigned 16-bit Dial"),
    _input("hat", "Hat switch", "selector", "AB6 report 01, four-bit HID hat"),
) + tuple(
    _input(
        f"button_{number:03d}", f"Captured HID button {number:03d}", "button",
        f"AB6 report 01, HID Button usage {number}",
        notes="The report proves this contact; its physical face label has not been guessed.",
    )
    for number in range(1, 129)
)


# MUSLIMSIM_TCA_BOEING_SINGLE_UNIT_CATALOG_V3
# ONE physical quadrant; the hardware switch changes its logical bank.
#
# Captured from the owner's unit on 2026-08-31 with
# ``tools/capture_tca_boeing_one_unit_both_banks.py`` -- the axis pass run
# twice and the button pass once, all on bank 1&2.
#
# Two things the capture settled that V2 had wrong:
#
# * The device declares six axes but carries three levers.  Axes 0, 1 and 2
#   never left their rest value in either run; the levers are on 3, 4 and 5,
#   left to right.  V2 described only axes 0..2, so the three real levers had
#   no catalogue entry at all.
# * V2 spelled its button keys zero-padded (``bank12_button_00``).  Nothing
#   ever looked those up: ``_tca_boeing_control_aliases()`` in bridge/final.py
#   tries ``bank12_button_4`` and twelve other unpadded spellings, so every
#   button lookup missed and no contact could route.
#
# Keys below therefore stay in the bridge's own alias spelling.  Renaming one
# silently disconnects that control from the simulator.
#
# No lever has a detent switch -- nothing closed during a full sweep of any of
# the three -- so reverse is the separate lever contact, not a below-idle band
# in the travel the way the WinCtrl URSA MINOR needs.
_TCA_BOEING_AXES = {
    0: ("Unused axis 0", "unimplemented",
        "Declared by the device, carries no lever. Rest +1.000, zero travel."),
    1: ("Unused axis 1", "unimplemented",
        "Declared by the device, carries no lever. Rest +1.000, zero travel."),
    2: ("Unused axis 2", "unimplemented",
        "Declared by the device, carries no lever. Rest 0.000, zero travel."),
    3: ("Left slide - Captain side", "implemented",
        "Captured -1.000..+1.000, rest +1.000. No detent switches."),
    4: ("Middle slide", "implemented",
        "Captured -1.000..+1.000, rest +1.000. No detent switches."),
    5: ("Right slide - First Officer side", "implemented",
        "Captured -1.000..+1.000, rest +1.000. No detent switches."),
}

_TCA_BOEING_BUTTONS = {
    0: ("Left slide button", "unknown",
        "Completes the 0/1/2 slide-button run and closed during discovery, "
        "but was not isolated by its own prompt."),
    1: ("Middle slide button", "implemented", "Captured directly."),
    2: ("Right slide button", "implemented", "Captured directly."),
    3: ("Left slide reverse lever", "unknown",
        "Completes the 3/4/5 reverser run and closed during discovery, but "
        "was not isolated by its own prompt."),
    4: ("Middle slide reverse lever", "implemented",
        "Captured directly. The owner confirmed the middle and right slides "
        "are the two that carry reverse levers."),
    5: ("Right slide reverse lever", "implemented", "Captured directly."),
    6: ("Side button 2", "implemented", "Captured directly."),
    7: ("Side button 3", "implemented", "Captured directly."),
    8: ("Side button 4", "implemented", "Captured directly."),
    9: ("Side button 1", "implemented",
        "Captured directly; first of the five in the owner's own order."),
    10: ("Side button 5", "implemented", "Captured directly."),
    11: ("Select knob position 1", "implemented",
         "Detented rotary. Captured sweep 11 -> 12 -> 13 and back."),
    12: ("Select knob position 2 (centre)", "implemented",
         "Detented rotary centre; seen twice per full sweep."),
    13: ("Select knob position 3", "implemented", "Detented rotary."),
    14: ("Top knob - counter-clockwise", "implemented",
         "Continuous encoder, direction-coded. 24 pulses in a CCW-only sweep."),
    15: ("Top knob - clockwise", "implemented",
         "Continuous encoder, direction-coded. 19 pulses in a CW-only sweep."),
    16: ("Knob pushbutton", "implemented", "Captured directly."),
}

# The owner confirmed that the same quadrant must remain usable after its
# physical 1&2 / 3&4 selector re-enumerates the controller.  SDL exposes that
# selection as a different product identity, not a different control layout:
# the central reader still receives the same six axes and 17 button indexes.
# Both identities are therefore bindable.  Only 1&2 keeps the captured Zibo
# defaults below; 3&4 receives no invented aircraft role and is user-mappable.
_TCA_BOEING_SECOND_BANK_NOTE = (
    "Same physical 6-axis / 17-button TCA interface after the selector "
    "re-enumerates it as engine bank 3&4. No default aircraft assignment is "
    "invented for this bank; choose its roles in Studio."
)


def _tca_boeing_one_unit_controls() -> Tuple[ControlSpec, ...]:
    controls = []
    for code, word in (("12", "1&2"), ("34", "3&4")):
        for index in sorted(_TCA_BOEING_AXES):
            label, status, note = _TCA_BOEING_AXES[index]
            controls.append(_input(
                f"bank{code}_axis_{index}", f"{word} {label}", "axis",
                f"SDL {word} axis {index}",
                status=status,
                notes=note if code == "12" else _TCA_BOEING_SECOND_BANK_NOTE,
            ))
        for index in sorted(_TCA_BOEING_BUTTONS):
            label, status, note = _TCA_BOEING_BUTTONS[index]
            controls.append(_input(
                f"bank{code}_button_{index}", f"{word} {label}", "button",
                f"SDL {word} button {index}",
                status=status,
                notes=note if code == "12" else _TCA_BOEING_SECOND_BANK_NOTE,
            ))
    return tuple(controls)


_TCA_BOEING_ONE_UNIT_CONTROLS = _tca_boeing_one_unit_controls()


# MUSLIMSIM_HOWALT_DIRECT_V1_CATALOG
# Capture-proven HOWALT runtime surface. These controls route through Studio;
# no simulator action is hard-coded in the serial drivers.
_MUSLIMRTP_D201_CONTROLS = (
    _input("vhf1", "VHF 1 select", "button", "D201 serial 7,VHF1,raw"),
    _input("vhf2", "VHF 2 select", "button", "D201 serial 7,VHF2,raw"),
    _input("vhf3", "VHF 3 select", "button", "D201 serial 7,VHF3,raw"),
    _input("hf1", "HF 1 select", "button", "D201 serial 7,HF1,raw"),
    _input("hf2", "HF 2 select", "button", "D201 serial 7,HF2,raw"),
    _input("am", "AM select", "button", "D201 serial 7,AM,raw"),
    _input("tfr1", "Transfer 1", "button", "D201 serial 7,TFR1,raw"),
    _input("tfr2", "Transfer 2", "button", "D201 serial 7,TFR2,raw"),
    _input("test1", "Test 1", "button", "D201 serial 7,TEST1,raw"),
    _input("test2", "Test 2", "button", "D201 serial 7,TEST2,raw"),
    _input("off", "Radio panel OFF", "button", "D201 serial 7,OFF,raw"),
    _input("bmq1", "BMQ1 encoder", "rotary", "D201 serial 6,BMQ1,event"),
    # MUSLIMSIM_HOWALT_V47_HFSENS_CATALOG
    _input("hf_sens_push", "HF SENS push", "button", "D201 pushable HF SENS centre; command-7 BMQ1/HFSENS is kept separate from command-6 encoder rotation"),
    _input("bmq2_1", "BMQ2-1 encoder", "rotary", "D201 serial 6,BMQ2-1,event"),
    _input("bmq2_2", "BMQ2-2 encoder", "rotary", "D201 serial 6,BMQ2-2,event"),
    _input("bmq3_1", "BMQ3-1 encoder", "rotary", "D201 serial 6,BMQ3-1,event"),
    _input("bmq3_2", "BMQ3-2 encoder", "rotary", "D201 serial 6,BMQ3-2,event"),
    _output("vhf1_led", "VHF 1 LED", "led", "D201 output index 0 / VHF1-L"),
    _output("vhf2_led", "VHF 2 LED", "led", "D201 output index 1 / VHF2-L"),
    _output("vhf3_led", "VHF 3 LED", "led", "D201 output index 2 / VHF3-L"),
    _output("hf1_led", "HF 1 LED", "led", "D201 output index 3 / HF1-L"),
    _output("hf2_led", "HF 2 LED", "led", "D201 output index 4 / HF2-L"),
    _output("am_led", "AM LED", "led", "D201 output index 5 / AM-L"),
    _output("backlight", "Panel backlight", "led", "D201 output index 6 / Back light"),
    _output("smg_1", "Radio display 1", "display", "D201 MAX7219 module 0 / SMG-1"),
    _output("smg_2", "Radio display 2", "display", "D201 MAX7219 module 1 / SMG-2"),
    _output("smg_3", "Radio display 3", "display", "D201 MAX7219 module 2 / SMG-3"),
    _output("smg_4", "Radio display 4", "display", "D201 MAX7219 module 3 / SMG-4"),
    _output("smg_1_brightness", "Display 1 brightness", "led", "D201 module 0 brightness 0..16"),
    _output("smg_2_brightness", "Display 2 brightness", "led", "D201 module 1 brightness 0..16"),
    _output("smg_3_brightness", "Display 3 brightness", "led", "D201 module 2 brightness 0..16"),
    _output("smg_4_brightness", "Display 4 brightness", "led", "D201 module 3 brightness 0..16"),
)

_MUSLIMATC_D203_CONTROLS = (
    _input("stby", "ATC STBY", "button", "D203 serial 7,STBY,raw"),
    _input("rptgoff", "ATC RPTG/OFF", "button", "D203 serial 7,RPTGOFF,raw"),
    _input("xpndr", "ATC XPNDR", "button", "D203 serial 7,XPNDR,raw"),
    _input("only", "ATC ONLY", "button", "D203 serial 7,ONLY,raw"),
    _input("atc_test", "ATC TEST", "button", "D203 serial 7,ATCTEST,raw"),
    _input("ta_ra", "ATC TA/RA", "button", "D203 serial 7,TA-RA,raw"),
    _input("xpn_1_2", "XPN 1/2 selector", "toggle", "D203 serial 7,XPN1-2,raw"),
    _input("alt_1_2", "ALT 1/2 selector", "toggle", "D203 serial 7,ALT1-2,raw"),
    _input("ident", "IDENT", "button", "D203 serial 7,IDENT,raw"),
    _input("bmq1_1", "Squawk encoder 1000", "rotary", "D203 serial 6,BMQ1-1,event"),
    _input("bmq1_2", "Squawk encoder 100", "rotary", "D203 serial 6,BMQ1-2,event"),
    _input("bmq2_1", "Squawk encoder 10", "rotary", "D203 serial 6,BMQ2-1,event"),
    _input("bmq2_2", "Squawk encoder 1", "rotary", "D203 serial 6,BMQ2-2,event"),
    _output("backlight", "Panel backlight", "led", "D203 output index 0 / Back light"),
    _output("fail_led", "FAIL LED", "led", "D203 output index 1 / FAIL-LED"),
    _output("xpndr2_led", "2 LED", "led", "D203 output index 2 / 2-LED"),
    _output("xpndr1_led", "1 LED", "led", "D203 output index 3 / 1-LED"),
    _output("atc_led", "ATC LED", "led", "D203 output index 4 / ATC-LED"),
    _output("squawk", "Squawk display", "display", "D203 MAX7219 module 0 / SMG"),
    _output("display_brightness", "Squawk display brightness", "led", "D203 module 0 brightness 0..16"),
)

ALL_HARDWARE: Tuple[DeviceSpec, ...] = (
    DeviceSpec(
        "muslimrtp_d201", "MUSLIMRTP • HOWALT D201 RTP", "USB serial",
        "VID 1A86 / PID 7523 • Hoowalt D201 RTP",
        "muslimsim.devices.muslimrtp_d201",
        notes=(
            "Direct 115200-baud runtime owner for the HOWALT D201 RTP. "
            "MobiFlight Connector is not part of the runtime path; Studio owns mapping and outputs."
        ),
        controls=_MUSLIMRTP_D201_CONTROLS,
        aliases=("muslimrtp", "d201", "howalt_d201_rtp"),
    ),
    DeviceSpec(
        "muslimatc_d203", "MUSLIMATC • HOWALT D203 ATC", "USB serial",
        "VID 1A86 / PID 7523 • Hoowalt D203 ATC",
        "muslimsim.devices.muslimatc_d203",
        notes=(
            "Direct 115200-baud runtime owner for the HOWALT D203 ATC. "
            "MobiFlight Connector is not part of the runtime path; Studio owns mapping and outputs."
        ),
        controls=_MUSLIMATC_D203_CONTROLS,
        aliases=("muslimatc", "d203", "howalt_d203_atc"),
    ),
    DeviceSpec(
        "fcu_32_efis", "WINCTRL 32 FCU + 32 EFIS L/R", "USB HID", "VID 4098 / PID BA01",
        "muslimsim.devices.fcu_efis_ba01", notes=(
            "Connected composite FCU/EFIS unit. FCU, captain EFIS, and first-officer EFIS "
            "controls use verified BA01 bit positions and Zibo defaults; every control can be remapped."
        ), controls=_FCU_EFIS_CONTROLS, aliases=("fcu32", "efis32l", "efis32r", "ba01"),
    ),
    DeviceSpec(
        "pdc_bb62", "WINCTRL 3N PDC / Airbus EFIS", "USB HID", "VID 4098 / PID BB62",
        "muslimsim.devices.pdc_bb62", notes="Reported by the connected unit as WINWING 3N PDC R.",
        controls=_PDC_CONTROLS, aliases=("efis3n", "winctrl_airbus_efis"),
    ),
    DeviceSpec(
        "pdc_bb61_left", "WINWING 3N PDC L", "USB HID", "VID 4098 / PID BB61",
        "muslimsim.devices.pdc_bb61_bb52",
        notes=(
            "Capture-verified fixed Captain/left Boeing PDC. Its maintained "
            "selectors and momentary controls use the owner-supplied BB61 capture."
        ),
        controls=_PDC_BB61_LEFT_CONTROLS,
        aliases=("bb61", "3n_pdc_l", "pdc3n_left"),
    ),
    DeviceSpec(
        "pdc_bb52_right", "WINWING 3M PDC R", "USB HID", "VID 4098 / PID BB52",
        "muslimsim.devices.pdc_bb61_bb52",
        notes=(
            "Capture-verified fixed First Officer/right Boeing PDC. RANGE is "
            "the capture-proven relative encoder."
        ),
        controls=_PDC_BB52_RIGHT_CONTROLS,
        aliases=("bb52", "3m_pdc_r", "pdc3m_right"),
    ),
    DeviceSpec(
        "pap3_mag", "WINCTRL 3N PAP3 MAG / MCP", "USB HID", "VID 4098 / PID BF0F",
        "muslimsim.devices.pap3_mcp", controls=_PAP3_CONTROLS,
    ),
    DeviceSpec(
        "pu_overhead", "PU Overhead", "Auto-discovered USB serial + SDL + Raw Input",
        "VID 3561 / PID 8561 • PU Korea overhead product identity",
        "bridge.final serial/SDL workers", controls=_PU_CONTROLS,
        notes=(
            "Made by PU Korea, not WinCtrl. Its COM number is a runtime locator "
            "resolved automatically from the supported product identity and is "
            "not persisted as configuration. It is also the only panel that "
            "one that does not hold an output state: its controller reverts to "
            "a lit default about a second after the last packet arrives, with "
            "the port still open. Measured 2026-09-01: the dark interval "
            "tracked the length of the stream rather than the port being "
            "open or closed. "
            "So no shutdown blackout can leave this panel dark; see "
            "DEVICE_REFERENCE.md."
        ),
    ),
    DeviceSpec(
        "tca_boeing", "Thrustmaster TCA Boeing Quadrant", "SDL / USB gaming controller",
        "ONE physical quadrant; Windows name switches between TCA Q Boeing 1&2 and TCA Q Boeing 3&4",
        "bridge.final SDL TCA worker", status="implemented",
        notes=(
            "One physical unit. Studio shows 1&2 and 3&4 together and highlights "
            "the active hardware bank. Bank 1&2 is captured: three levers on axes "
            "3/4/5 left to right, reverse levers on the middle and right slides, a "
            "three-position select knob, and a direction-coded continuous encoder. "
            "The same controls remain bindable when the selector re-enumerates "
            "the unit as bank 3&4. Only bank 1&2 has built-in aircraft defaults; "
            "bank 3&4 is intentionally left for the owner to map."
        ),
        controls=_TCA_BOEING_ONE_UNIT_CONTROLS,
        aliases=("tca q boeing 1&2", "tca q boeing 3&4", "tca quadrant boeing 1&2", "tca quadrant boeing 3&4"),
    ),
    DeviceSpec(
        "winctrl_throttle", "WINCTRL URSA Minor throttle", "USB HID / SDL", "VID 4098 / PID B930",
        "bridge.final WinCtrl axis worker", controls=_THROTTLE_CONTROLS,
    ),
    DeviceSpec(
        "winctrl_pedals", "WINCTRL Orion rudder pedals", "SDL", "controller name contains ORION COMBAT RUDDER PEDALS",
        "bridge.final pedal worker", controls=(
            _input("left_toe_brake", "Left toe brake", "axis", "SDL axis 0"),
            _input("right_toe_brake", "Right toe brake", "axis", "SDL axis 1"),
            _input("rudder", "Rudder", "axis", "SDL axis 2"),
        ),
    ),
    DeviceSpec(
        "moza_a210", "MOZA A210 Base + detachable yoke", "USB HID", "VID 346E / PID 1001",
        "muslimsim.devices.moza_a210 capture-proven HID reader", notes=(
            "The A210 remains one connected 34-byte HID input device while its yoke is removed or refitted. "
            "Studio therefore shows one base/yoke unit, never a duplicate yoke. The owner-supplied iFly B737 MAX "
            "and PMDG B777 presets provide its visual calibration profiles. Its captured joystick report supplies "
            "eight live axes, a hat, and 128 generic HID contacts; each is remappable, while unknown face legends "
            "remain deliberately numbered. No force-feedback output command is sent."
        ), controls=_MOZA_A210_LIVE_CONTROLS + _MOZA_BASE_CALIBRATION_CONTROLS[3:], aliases=("moza", "a210", "ay210", "moza a210"),
    ),
    DeviceSpec(
        "moza_a210_ffb", "MOZA AY210 Force Feedback Output", "USB HID + Serial", "VID 346E / PID 1001",
        "muslimsim.hardware.moza_ay210_ffb_engine + moza_ay210_ffb_protocol", notes=(
            "Real motor output, reverse-engineered without the MOZA SDK: a live USBPcap capture of the "
            "AY210's own serial debug log and HID writes, cross-checked against MOZA Cockpit's Basic "
            "Settings/Physics Model Settings sliders one change at a time. Spring, trim (CP-Offset), "
            "rumble, and constant-force effects are all physically confirmed, plus the seven-field "
            "Cockpit-equivalent 'physics' gain family (Spring/Damper/Inertia/Friction/Overall Intensity/"
            "Maximum Torque/Friction Compensation), each of which may be a static percentage or a "
            "live X-Plane-dataref-driven curve - something MOZA Cockpit itself cannot do. Shares the "
            "A210's VID/PID with the read-only axis reader (moza_a210) but owns a separate HID "
            "collection and the device's serial port, so both can run at once. Off unless the bridge is "
            "started with --moza-ffb; a graceful no-op with no AY210 connected."
        ), controls=(
            _output("spring_gain", "Spring", "gauge", "Table 7, Param 15 (0xAF)"),
            _output("damper", "Damper", "gauge", "Table 7, Param 16 (0xB0)"),
            _output("inertia", "Inertia", "gauge", "Table 7, Param 53 (0xB1)"),
            _output("friction", "Friction", "gauge", "Table 7, Param 54 (0xB2)"),
            _output("overall_intensity", "Overall Force Feedback Intensity", "gauge", "Table 7, Param 52 (0xAE)"),
            _output("max_torque", "Maximum Torque Output", "gauge", "Table 7, Param 100 (0xA9)"),
            _output("friction_compensation", "Friction Compensation Strength", "gauge", "Table 8, Param 65 (0xE1/0x16)"),
        ), aliases=("moza ffb", "ay210 ffb", "moza a210 force feedback", "moza a210 ffb"),
    ),
    DeviceSpec(
        "moza_ab6", "MOZA AB6 FFB Base", "USB HID", "VID 346E / PID 1002",
        "muslimsim.devices.moza_a210 capture-proven HID reader (shared report)", notes=(
            "Captured from the connected base rather than inherited from the A210: the AB6 returns a HID report "
            "descriptor byte-identical to the A210's and streams the same 34-byte report 01, so its eight 16-bit "
            "axes, four-bit hat and 128 generic HID contacts are proven, not assumed. A full-travel exercise then "
            "established that X, Y, Slider and Dial sweep the whole range while Z, Rx, Ry and Rz stay idle, and "
            "observed the hat plus 14 contacts. Each control is remappable, and unknown face legends remain "
            "deliberately numbered: the base prints no button names, so they are assigned in Studio rather than "
            "guessed here. The owner-supplied A320/MSFS 2024 preset "
            "still provides the visual force and flight-effect calibration values. This entry covers axis/button "
            "input only - see moza_ab6_ffb for the AB6's own real, captured force-feedback output path."
        ), controls=_MOZA_AB6_LIVE_CONTROLS + _MOZA_BASE_CALIBRATION_CONTROLS[3:],
        aliases=("moza ab6", "ab6", "moza ab6 ffb base"),
    ),
    DeviceSpec(
        "moza_ab6_ffb", "MOZA AB6 Force Feedback Output", "USB HID + Serial", "VID 346E / PID 1002",
        "muslimsim.hardware.moza_ay210_ffb_engine + moza_ay210_ffb_protocol (AB6_PROFILE)", notes=(
            "Real motor output, same engine as moza_a210_ffb pointed at a separate device profile: a live "
            "USBPcap capture of a full disconnect->reconnect cycle on the AB6 itself confirmed its own COM "
            "port, its own enable-latch write (value 0x00, vs. the AY210's 0x01), its full 227-frame connection "
            "setup burst, its 61-frame steady-state poll loop, and that it sends no active HID teardown on "
            "disconnect (confirmed empty - MOZA Cockpit relies on the poll loop simply stopping). Spring, trim, "
            "rumble, and constant-force effects reuse the same capture-proven Condition/Set-Periodic/Constant-"
            "Force report machinery as the AY210, since both devices share the identical HID report descriptor. "
            "Of the seven-field physics gain family, only Spring/Damper/Inertia/Friction (Table 7, Params 15/16/"
            "53/54) are confirmed shared with the AY210 (per moza_ab6_calibration_notes.md); Overall Intensity, "
            "Maximum Torque, and Friction Compensation were never byte-confirmed for the AB6, so this profile "
            "deliberately omits them rather than guess they share the AY210's addresses - the engine's own "
            "confirmed_physics_fields gate refuses to send them for this device. Shares the AB6's VID/PID with "
            "the read-only axis reader (moza_ab6) but owns a separate HID collection and the device's serial "
            "port, so both can run at once. Off unless the bridge is started with --moza-ab6-ffb; a graceful "
            "no-op with no AB6 connected."
        ), controls=(
            _output("spring_gain", "Spring", "gauge", "Table 7, Param 15 (0xAF)"),
            _output("damper", "Damper", "gauge", "Table 7, Param 16 (0xB0)"),
            _output("inertia", "Inertia", "gauge", "Table 7, Param 53 (0xB1)"),
            _output("friction", "Friction", "gauge", "Table 7, Param 54 (0xB2)"),
        ), aliases=("moza ab6 ffb", "ab6 ffb", "moza ab6 force feedback"),
    ),
    DeviceSpec(
        "agp_bb80", "WINCTRL 32 AGP Metal", "USB HID", "VID 4098 / PID BB80",
        "bridge.final AGP worker", controls=_AGP_CONTROLS,
    ),
    DeviceSpec(
        "pfp3n_bb35", "WINCTRL 3N PFP", "USB HID", "VID 4098 / PID BB35",
        "bridge.final BB35 PFD/FMC path", controls=_PFP3N_CONTROLS + (
            _output("screen", "640 x 480 PFP screen", "display", "native F0/F2 graphics",
                    notes="Practice mode uses the existing F2 character-page setup only; arbitrary graphics-plane injection remains unsupported."),
        ),
    ),
    DeviceSpec(
        "mcdu32_bb36", "WINCTRL 32 MCDU Captain", "USB HID", "VID 4098 / PID BB36",
        "bridge.final BB36 PFD/FMC path", controls=_MCDU32_CONTROLS + (
            _output("screen", "640 x 480 MCDU screen", "display", "native F0/F2 graphics",
                    notes="Practice mode uses the existing F2 character-page setup only; arbitrary graphics-plane injection remains unsupported."),
        ),
    ),
    DeviceSpec(
        "ecam32", "WINCTRL 32 ECAM", "USB HID", "VID 4098 / PID BB70",
        "muslimsim.devices.ecam32 capture-proven input / wake / lamp driver", notes=(
            "BB70 key contacts are still learned before receiving an Airbus face-button name. "
            "Ecam.pcapng verifies its 12-byte input report, panel wake keepalive, and individual "
            "indicator addresses 04 through 11. back light.pcapng additionally verifies two separate "
            "yellow panel-backlight channels (00 and 01); all other output channels stay blocked."
        ),
        controls=(
            _input("raw_capture", "Captured physical contacts", "button", "runtime BB70 report deltas", status="unknown", notes="Appears as concrete raw controls only after a real BB70 report changes."),
            _output("panel_wake", "Panel wake / keepalive", "led", "BB70 02 01 keepalive", notes="Captured 500 ms host keepalive. It wakes the connected ECAM without changing any lamp state."),
            _output("panel_backlight", "Yellow panel backlight", "led", "BB70 02 70 BB / selector 49, channels 00 + 01", notes="Captured full-brightness write to both yellow faceplate illumination zones. This is separate from every selected-button indicator."),
            _output("panel_backlight_1", "Yellow panel backlight — zone 1", "led", "BB70 02 70 BB 00 00 03 49 00 brightness", notes="Captured 0..255 brightness channel. Use only when independently tuning the first physical yellow-light zone."),
            _output("panel_backlight_2", "Yellow panel backlight — zone 2", "led", "BB70 02 70 BB 00 00 03 49 01 brightness", notes="Captured 0..255 brightness channel. Use only when independently tuning the second physical yellow-light zone."),
            _output("button_backlight", "All captured ECAM button lamps", "led", "BB70 02 70 BB / selector 49", notes="Test-only all-on/all-off for the fourteen captured lamp addresses. It does not claim a physical face-button order."),
        ) + tuple(
            _output(
                f"led_{index:02x}", f"Captured ECAM lamp {index:02X}", "led",
                f"BB70 02 70 BB 00 00 03 49 {index:02X} state",
                notes="Capture-proven individual BB70 lamp address; its physical legend remains user-assigned unless a contact/lamp pair was recorded.",
            )
            for index in range(0x04, 0x12)
        ),
    ),
)


# >>> MUSLIMSIM PDC CLEAN CANONICAL V1 >>>
_PDC_BB61_LEFT_CONTROLS_CLEAN_V1 = (
    _input("fpv", "FPV", "button", "BB61 HID button 1"),
    _input("mtrs", "MTRS", "button", "BB61 HID button 2"),
    _input("wxr", "WXR", "button", "BB61 HID button 3"),
    _input("sta", "STA", "button", "BB61 HID button 4"),
    _input("wpt", "WPT", "button", "BB61 HID button 5"),
    _input("arpt", "ARPT", "button", "BB61 HID button 6"),
    _input("data", "DATA", "button", "BB61 HID button 7"),
    _input("pos", "POS", "button", "BB61 HID button 8"),
    _input("terr", "TERR", "button", "BB61 HID button 9"),
    _input("vor1", "VOR/ADF 1 selector", "selector", "BB61 buttons 10/11/12", choices=("VOR", "OFF", "ADF1")),
    _input("vor2", "VOR/ADF 2 selector", "selector", "BB61 buttons 13/14/15", choices=("VOR", "OFF", "ADF2")),
    _input("mins_rst", "MINS reset", "button", "BB61 HID button 16"),
    _input("ctr", "CTR", "button", "BB61 HID button 17"),
    _input("tfc", "TFC", "button", "BB61 HID button 18"),
    _input("baro_std", "BARO STD", "button", "BB61 HID button 19"),
    _input("mins_mode", "MINS RADIO/BARO", "selector", "BB61 buttons 25/24", choices=("RADIO", "BARO")),
    _input("baro_unit", "BARO IN/HPA", "selector", "BB61 buttons 27/26", choices=("IN", "HPA")),
    _input("map_mode", "MODE APP/VOR/MAP/PLN", "selector", "BB61 buttons 28..31", choices=("APP", "VOR", "MAP", "PLN")),
    _input("map_range", "RANGE", "selector", "BB61 buttons 32..39", choices=("5", "10", "20", "40", "80", "160", "320", "640")),
    _input("mins_dec", "MINS decrease", "rotary",
           "BB61 two-stage detent: rest 41, detent 40, past the notch 20"),
    _input("mins_inc", "MINS increase", "rotary",
           "BB61 two-stage detent: rest 41, detent 42, past the notch 21"),
    _input("baro_dec", "BARO decrease", "rotary",
           "BB61 two-stage detent: rest 44, detent 43, past the notch 22"),
    _input("baro_inc", "BARO increase", "rotary",
           "BB61 two-stage detent: rest 44, detent 45, past the notch 23"),
    # MUSLIMSIM_PDC_FIXED_BACKLIGHT_V51
    _output(
        "panel_backlight", "Panel backlight", "led",
        "BB61 02 60 BB 00 00 03 49 00 brightness",
        notes="Owner capture proves continuous 0..255 brightness on channel 00; value 0 is OFF.",
    ),
)


# The Captain role accepts BB61 and BB51. Preserve every old key so existing
# profiles remain valid; add only the independently verified 3M-only inputs.
_PDC_BB61_LEFT_CONTROLS_CLEAN_V1 += (
    _input("vsd", "VSD (3M)", "button", "BB51 owner capture: HID button 3"),
    _input("range_dec", "RANGE decrease (3M)", "rotary", "BB51 owner capture: HID button 21"),
    _input("range_inc", "RANGE increase (3M)", "rotary", "BB51 owner capture: HID button 22"),
)

_PDC_BB52_RIGHT_CONTROLS_CLEAN_V1 = (
    _input("fpv", "FPV", "button", "BB52 HID button 1"),
    _input("mtrs", "MTRS", "button", "BB52 HID button 2"),
    _input("vsd", "VSD", "button", "BB52 HID button 3"),
    _input("wxr", "WXR", "button", "BB52 HID button 4"),
    _input("sta", "STA", "button", "BB52 HID button 5"),
    _input("wpt", "WPT", "button", "BB52 HID button 6"),
    _input("arpt", "ARPT", "button", "BB52 HID button 7"),
    _input("data", "DATA", "button", "BB52 HID button 8"),
    _input("pos", "POS", "button", "BB52 HID button 9"),
    _input("terr", "TERR", "button", "BB52 HID button 10"),
    _input("vor1", "VOR/ADF 1 selector", "selector", "BB52 buttons 11/12/13", choices=("VOR", "OFF", "ADF1")),
    _input("vor2", "VOR/ADF 2 selector", "selector", "BB52 buttons 14/15/16", choices=("VOR", "OFF", "ADF2")),
    _input("mins_rst", "MINS reset", "button", "BB52 HID button 17"),
    _input("ctr", "CTR", "button", "BB52 HID button 18"),
    _input("tfc", "TFC", "button", "BB52 HID button 19"),
    _input("baro_std", "BARO STD", "button", "BB52 HID button 20"),
    _input("range_dec", "RANGE decrease", "rotary", "BB52 HID button 21"),
    _input("range_inc", "RANGE increase", "rotary", "BB52 HID button 22"),
    _input("mins_mode", "MINS RADIO/BARO", "selector", "BB52 buttons 26/25", choices=("RADIO", "BARO")),
    _input("baro_unit", "BARO IN/HPA", "selector", "BB52 buttons 28/27", choices=("IN", "HPA")),
    _input("map_mode", "MODE APP/VOR/MAP/PLN", "selector", "BB52 buttons 29..32", choices=("APP", "VOR", "MAP", "PLN")),
    _input("mins_dec", "MINS decrease", "rotary",
           "BB52 two-stage detent: rest 35, detent 34, past the notch 33"),
    _input("mins_inc", "MINS increase", "rotary",
           "BB52 two-stage detent: rest 35, detent 36, past the notch 37"),
    _input("baro_dec", "BARO decrease", "rotary",
           "BB52 two-stage detent: rest 39, detent 38, past the notch 23"),
    _input("baro_inc", "BARO increase", "rotary",
           "BB52 two-stage detent: rest 39, detent 40, past the notch 24"),
    _output(
        "panel_backlight", "Panel backlight", "led",
        "BB52 02 50 BB 00 00 03 49 00 brightness",
        notes="Owner capture proves continuous 0..255 brightness on channel 00; value 0 is OFF.",
    ),
)

DEFAULT_ROLES = {
    **DEFAULT_ROLES,
    "pdc_bb61_left": {
        "fpv": "Zibo captain EFIS: FPV", "mtrs": "Zibo captain EFIS: MTRS",
        "wxr": "Zibo captain EFIS: WXR", "sta": "Zibo captain EFIS: STA",
        "wpt": "Zibo captain EFIS: WPT", "arpt": "Zibo captain EFIS: ARPT",
        "data": "Zibo captain EFIS: DATA", "pos": "Zibo captain EFIS: POS",
        "terr": "Zibo captain EFIS: TERR", "vor1": "Zibo captain EFIS: VOR/ADF 1",
        "vor2": "Zibo captain EFIS: VOR/ADF 2", "mins_rst": "Zibo captain EFIS: MINS reset",
        "ctr": "Zibo captain EFIS: CTR", "tfc": "Zibo captain EFIS: TFC",
        "baro_std": "Zibo captain EFIS: BARO STD", "mins_mode": "Zibo captain EFIS: MINS mode",
        "baro_unit": "Zibo captain EFIS: BARO units", "map_mode": "Zibo captain EFIS: MODE",
        "map_range": "Zibo captain EFIS: RANGE", "mins_dec": "Zibo captain EFIS: MINS down",
        "mins_inc": "Zibo captain EFIS: MINS up", "baro_dec": "Zibo captain EFIS: BARO down",
        "baro_inc": "Zibo captain EFIS: BARO up",
    },
    "pdc_bb52_right": {
        "fpv": "Zibo first-officer EFIS: FPV", "mtrs": "Zibo first-officer EFIS: MTRS",
        "vsd": "Zibo first-officer EFIS: VSD", "wxr": "Zibo first-officer EFIS: WXR",
        "sta": "Zibo first-officer EFIS: STA", "wpt": "Zibo first-officer EFIS: WPT",
        "arpt": "Zibo first-officer EFIS: ARPT", "data": "Zibo first-officer EFIS: DATA",
        "pos": "Zibo first-officer EFIS: POS", "terr": "Zibo first-officer EFIS: TERR",
        "vor1": "Zibo first-officer EFIS: VOR/ADF 1", "vor2": "Zibo first-officer EFIS: VOR/ADF 2",
        "mins_rst": "Zibo first-officer EFIS: MINS reset", "ctr": "Zibo first-officer EFIS: CTR",
        "tfc": "Zibo first-officer EFIS: TFC", "baro_std": "Zibo first-officer EFIS: BARO STD",
        "range_dec": "Zibo first-officer EFIS: RANGE down", "range_inc": "Zibo first-officer EFIS: RANGE up",
        "mins_mode": "Zibo first-officer EFIS: MINS mode", "baro_unit": "Zibo first-officer EFIS: BARO units",
        "map_mode": "Zibo first-officer EFIS: MODE", "mins_dec": "Zibo first-officer EFIS: MINS down",
        "mins_inc": "Zibo first-officer EFIS: MINS up", "baro_dec": "Zibo first-officer EFIS: BARO down",
        "baro_inc": "Zibo first-officer EFIS: BARO up",
    },
}


# MUSLIMSIM_TCA_BOEING_DEFAULT_RULES_V1
#
# ``DEFAULT_ROLES`` above is descriptive only: a device with no saved binding
# falls through to the bridge's own dispatcher, which already knows what that
# hardware does.  The TCA Boeing quadrant has no such dispatcher -- the bridge
# tracks it for display and deliberately routes nothing -- so "no saved
# binding" meant "does nothing at all".
#
# These are executable defaults for exactly that case.  ``HardwareLab._binding``
# consults this table only when the active profile has no explicit entry for
# the control, so the existing precedence is unchanged and honoured:
#
#     saved user binding  >  this table  >  bridge dispatcher / nothing
#
# Rebinding a lever in Studio writes a profile entry, which wins from then on.
# "Restore this profile" clears those entries and these rules return.
#
# Axis scaling: SDL reports each lever -1.000..+1.000 resting at +1.000, while
# the binding sink computes ``(1 - raw) * scale``.  ``invert`` with a 0.5 scale
# therefore maps rest -> 0.0 and the far end of travel -> 1.0.  Rest meaning
# 0.0 is deliberate: idle thrust, speedbrake retracted, flaps up.  That is the
# safe end whichever way round the levers are physically oriented.
#
# The owner's rules for a single quadrant: left slide is the airbrake, right
# slide is the flaps, and the middle slide drives every engine.  The all-engine
# throttle target is engine-count agnostic, so the middle slide is correct on a
# twin and on a four without branching.
DEFAULT_BINDINGS: Mapping[str, Mapping[str, Mapping[str, object]]] = {
    "tca_boeing": {
        "bank12_axis_3": {
            "kind": "dataref",
            "target": "laminar/B738/flt_ctrls/speedbrake_lever",
            "invert": True, "scale": 0.5,
        },
        "bank12_axis_4": {
            "kind": "dataref",
            "target": "sim/cockpit2/engine/actuators/throttle_ratio_all",
            "invert": True, "scale": 0.5,
        },
        "bank12_axis_5": {
            "kind": "dataref",
            "target": "laminar/B738/flt_ctrls/flap_lever",
            "invert": True, "scale": 0.5,
        },
        # A button reports 1 on press and 0 on release, so no invert: the
        # lever drives its reverser to 1.0 held and back to 0.0 released.
        "bank12_button_4": {
            "kind": "dataref",
            "target": "laminar/B738/flt_ctrls/reverse_lever1",
            "scale": 1.0,
        },
        "bank12_button_5": {
            "kind": "dataref",
            "target": "laminar/B738/flt_ctrls/reverse_lever2",
            "scale": 1.0,
        },
    },
}


ALL_HARDWARE = tuple(
    device for device in ALL_HARDWARE
    if device.key not in {"pdc_bb61_left", "pdc_bb52_right"}
) + (
    DeviceSpec(
        "pdc_bb61_left", "WINWING 3N PDC L", "USB HID", "VID 4098 / PID BB61",
        "muslimsim.devices.pdc_bb61_bb52", controls=_PDC_BB61_LEFT_CONTROLS_CLEAN_V1,
        notes="Capture-proven fixed Captain/left PDC.", aliases=("bb61", "3n_pdc_l"),
    ),
    DeviceSpec(
        "pdc_bb52_right", "WINWING 3M PDC R", "USB HID", "VID 4098 / PID BB52",
        "muslimsim.devices.pdc_bb61_bb52", controls=_PDC_BB52_RIGHT_CONTROLS_CLEAN_V1,
        notes="Capture-proven fixed First-Officer/right PDC.", aliases=("bb52", "3m_pdc_r"),
    ),
)
# <<< MUSLIMSIM PDC CLEAN CANONICAL V1 <<<

def device_by_key(key: str) -> Optional[DeviceSpec]:
    wanted = str(key).strip().lower()
    for device in ALL_HARDWARE:
        if wanted == device.key or wanted in device.aliases:
            return device
    try:
        from muslimsim.hardware.device_profiles import community_device_by_key
        return community_device_by_key(wanted)
    except Exception:
        pass
    return None


def catalogue_snapshot() -> Mapping[str, object]:
    """Return JSON-ready device/control metadata for the loopback channel."""

    all_devices = list(ALL_HARDWARE)
    all_roles: Mapping[str, Mapping[str, str]] = DEFAULT_ROLES
    try:
        from muslimsim.hardware.device_profiles import (
            load_community_hardware, community_default_roles,
        )
        community_hw = load_community_hardware()
        if community_hw:
            existing_keys = {d.key for d in ALL_HARDWARE}
            all_devices = all_devices + [d for d in community_hw if d.key not in existing_keys]
        community_roles = community_default_roles()
        if community_roles:
            merged = dict(all_roles)
            merged.update(community_roles)
            all_roles = merged
    except Exception:
        pass

    return {
        "schema": 1,
        "devices": [
            {
                "key": device.key,
                "title": device.title,
                "transport": device.transport,
                "identity": device.identity,
                "driver": device.driver,
                "status": device.status,
                "notes": device.notes,
                "aliases": list(device.aliases),
                "controls": [
                    {
                        "key": control.key,
                        "label": control.label,
                        "kind": control.kind,
                        "direction": control.direction,
                        "raw": control.raw,
                        "status": control.status,
                        "remappable": control.remappable,
                        "testable": control.testable,
                        "choices": list(control.choices),
                        "notes": control.notes,
                        "default_role": all_roles.get(device.key, {}).get(control.key, ""),
                    }
                    for control in device.controls
                ],
            }
            for device in all_devices
        ],
    }

# MUSLIMSIM_AGP_RADIO_NAV_V2_CATALOG

# MUSLIMSIM_AGP_RADIO_NAV_V2_2_CATALOG

# MUSLIMSIM_AGP_RADIO_NAV_V2_3_CATALOG
