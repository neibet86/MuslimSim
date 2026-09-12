#!/usr/bin/env python3
"""MuslimSim BB36 path for a ToLiss Airbus MCDU (VID 0x4098 / PID 0xBB36).

Mirrors the architecture proven in ``mcdu_bb36_separate_paths.py`` (one
persistent native-F0 BB36 session; PERIOD x3 and SLASH x2 physical gestures
switch the graphical page shown on that same session) without touching that
file. Zibo/LevelUp is a 24x14 character-grid FMC with a Boeing PFD/ND/ENG
PRI/MFD/HYD secondary set; ToLiss is a real Airbus MCDU (``AirbusFBW/MCDU1*``)
with no EXEC key and its own PFD-output/engine dataref set, so the two paths
share only the physical protocol (imported from ``mcdu_bb36.py``) and the
tap-gesture detectors (imported from ``mcdu_bb36_separate_paths.py`` - both
are generic, stateless-except-for-their-own-timers classes with no Zibo
coupling).

Key dispatch is always live (regardless of which page is on screen) because
this is a dedicated MCDU keypad, not a general Hardware Lab macro board - see
``TolissBB36MirrorPath._key_command_worker``. The live screen mirror (CDU
content + PFD/engine secondary pages) can be turned off independently via the
persisted toggle in this file. With it off, only key dispatch runs: standalone
lab callers may retain the historical static page, while the production bridge
fails closed to a black LCD because no live worker remains to prove aircraft
electrical power.

BB35 uses the same command loop with its own captured keypad map, queue and
local page gestures. Both physical keypads address the mirrored captain MCDU1.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple
from .toliss_ecam_telemetry import DATAREFS as ECAM_AUDITED_DATAREFS, TEXT_KEYS as ECAM_TEXT_KEYS
from .toliss_ecam_telemetry import PAGE_EXTRA_KEYS as ECAM_EXTRA_KEYS, POWER_KEYS as ECAM_POWER_KEYS

try:
    import websocket
except ImportError:
    websocket = None

# Reuse the proven BB36 firmware protocol byte-for-byte: geometry, packet
# builders, colour codes, REST id resolvers, and the WS value decoders. None
# of this is Boeing-specific.
from .mcdu_bb36 import (
    MCDU_COLUMNS,
    MCDU_ROWS,
    COLOR_AMBER,
    COLOR_CYAN,
    COLOR_GREEN,
    COLOR_MAGENTA,
    COLOR_WHITE,
    COLOR_YELLOW,
    COLOR_GREY,
    _normalize_24,
    _button_bits,
    _resolve_dataref_id,
    _resolve_command_id,
)
# The tap-gesture detectors are pure timers around a callback - no Zibo
# state - reused as literal instances, including their own tap-count/gap
# constants, so a triple-PERIOD/double-SLASH on this device times out
# identically to the Zibo path.
from .mcdu_bb36_separate_paths import (
    _TriplePeriodDetector,
    _DoubleSlashDetector,
    _open_bb36,
    BB36_SECRET_GAP,
    BB36_DISPLAY_SLASH_GAP,
)

def _toliss_decode_text(value: Any, *, fixed_columns: bool = False) -> str:
    """Decode one WS dataref value to text - a corrected local copy of
    mcdu_bb36.py's _ws_decode_text/_decode_possible_base64_text, NOT an
    edit to that shared file (Zibo's own FMC path must stay untouched).

    Keeps the shared version's own safeguard (only trust a base64 decode
    when the result is mostly printable text, so a short plain-text value
    that merely LOOKS like valid base64 - e.g. a 4-character ICAO code -
    doesn't get corrupted) but fixes one real bug in it: the original
    treats a successfully-decoded EMPTY string as "untrustworthy" (`decoded
    and ...` is falsy for "") and falls back to returning the RAW UNDECODED
    base64 text instead. This device's data shape hits that constantly -
    each MCDU1 row has up to 7 colour channels and most are legitimately
    blank for any given line. Confirmed live: this produced a literal
    "AA==" (base64 of one null byte) prefix on every content row, and a
    full row of "A" characters (base64 of an all-null longer buffer) on
    the scratchpad row. Fixed by trusting an empty decode as the correct,
    final answer rather than falling back to raw base64 garbage.
    """
    if fixed_columns:
        # SD colour layers are fixed columns; embedded NULs are empty cells,
        # not the end of the whole row as they are in CDU strings.
        if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
            value = value[0]
        if isinstance(value, str):
            try:
                value = base64.b64decode(value.encode("ascii"), validate=True)
            except (UnicodeEncodeError, ValueError, binascii.Error):
                return value.replace("\x00", " ")
        if isinstance(value, list) and all(isinstance(item, int) for item in value):
            value = bytes(max(0, min(255, item)) for item in value)
        if isinstance(value, (bytes, bytearray)):
            return bytes(value).decode("utf-8", errors="replace").replace("\x00", " ")
        return ""
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).split(b"\x00", 1)[0].decode("utf-8", errors="replace")
    if isinstance(value, list):
        if value and all(isinstance(item, int) for item in value):
            raw = bytes(max(0, min(255, int(item))) for item in value)
            return raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
        if len(value) == 1:
            return _toliss_decode_text(value[0])
        return ""
    if not isinstance(value, str):
        return str(value)
    stripped = value.rstrip("\x00")
    if not stripped:
        return ""
    try:
        raw = base64.b64decode(stripped.encode("ascii"), validate=True)
        decoded = raw.split(b"\x00", 1)[0].decode("utf-8", errors="strict")
    except (UnicodeEncodeError, UnicodeDecodeError, ValueError, binascii.Error):
        return stripped
    if not decoded:
        return ""
    printable = sum(1 for char in decoded if char.isprintable() or char == " ")
    return decoded if printable / len(decoded) >= 0.90 else stripped


BB36_TOLISS_PERIOD_INDEX = 41   # same physical key as Zibo's PERIOD x3 gesture
BB36_TOLISS_SLASH_INDEX = 70    # same physical key as Zibo's SLASH x2 gesture
BB36_TOLISS_MIN_REFRESH_SECONDS = 0.080
BB36_TOLISS_WS_RECONNECT_SECONDS = 0.50

TOLISS_CDU_PAGE = "cdu"
# "pfd" is a real graphical PFD (muslimsim.devices.pfp_renderer_toliss, Part E
# step 2). "nd" is a real graphical Navigation Display
# (muslimsim.devices.nd_renderer_toliss, Part E step 3 - this task). Every
# page after it is a real ECAM lower-display synoptic page drawn by
# muslimsim.devices.systems_renderer_toliss - see that module's
# TOLISS_SYSTEM_PAGES tuple, which this order must stay in sync with.
TOLISS_DISPLAY_PAGE_ORDER = (
    "pfd", "nd", "eng", "bleed", "press", "cond", "elec", "hyd", "fuel",
    "door", "wheel", "apu", "fctl", "cruise", "status",
)

# ---------------------------------------------------------------------------
# Key map. Same 74 hardware indices as MCDU_KEY_MAP (mcdu_bb36.py), retargeted
# to real AirbusFBW/MCDU1* commands (xplane_command_catalog.json, aircraft ==
# "toliss", 218 MCDU1* commands). The physical legend was silkscreened for a
# Boeing 737 CDU (WinCtrl's "HARDWARE_MCDU"); several positions have no clean
# 1:1 Airbus meaning and are flagged below - confirm against a live BB36 +
# ToLiss session and correct fast, per this project's own "prove, don't
# guess" rule.
# ---------------------------------------------------------------------------
TOLISS_MCDU_KEY_MAP: Dict[int, Tuple[str, Optional[str]]] = {
    0: ("LSK1L", "AirbusFBW/MCDU1LSK1L"), 1: ("LSK2L", "AirbusFBW/MCDU1LSK2L"),
    2: ("LSK3L", "AirbusFBW/MCDU1LSK3L"), 3: ("LSK4L", "AirbusFBW/MCDU1LSK4L"),
    4: ("LSK5L", "AirbusFBW/MCDU1LSK5L"), 5: ("LSK6L", "AirbusFBW/MCDU1LSK6L"),
    6: ("LSK1R", "AirbusFBW/MCDU1LSK1R"), 7: ("LSK2R", "AirbusFBW/MCDU1LSK2R"),
    8: ("LSK3R", "AirbusFBW/MCDU1LSK3R"), 9: ("LSK4R", "AirbusFBW/MCDU1LSK4R"),
    10: ("LSK5R", "AirbusFBW/MCDU1LSK5R"), 11: ("LSK6R", "AirbusFBW/MCDU1LSK6R"),
    # Boeing legend "DIR -> LEGS" dual-labels one key; Airbus DIR TO is the
    # natural single-function match.
    12: ("DIR -> LEGS", "AirbusFBW/MCDU1DirTo"),
    13: ("PROG", "AirbusFBW/MCDU1Prog"),
    14: ("PERF -> N1 LIMIT", "AirbusFBW/MCDU1Perf"),
    15: ("INIT -> INIT REF", "AirbusFBW/MCDU1Init"),
    # Boeing's 737 FMC has no DATA key (None in MCDU_KEY_MAP); the Airbus
    # MCDU does, so this physical position gains a real function under ToLiss.
    16: ("DATA", "AirbusFBW/MCDU1Data"),
    # JUDGMENT CALL: Boeing's EXEC key has no Airbus MCDU equivalent - no
    # catalogued AirbusFBW/MCDU1Exec* exists (a real A320 MCDU has no EXEC
    # key at all; flight-plan changes are confirmed via LSK INSERT instead).
    # Left unassigned rather than guessing a wrong target.
    17: ("EMPTY TOP RIGHT -> EXEC", None),
    # Real Airbus key, not a synthetic dataref write like Boeing's
    # __brightness_up__: ToLiss/AirbusFBW ship an actual command for it.
    18: ("BRIGHTNESS UP", "AirbusFBW/MCDU1KeyBright"),
    19: ("F-PLN -> LEGS", "AirbusFBW/MCDU1Fpln"),
    20: ("RAD NAV", "AirbusFBW/MCDU1RadNav"),
    21: ("FUEL PRED", "AirbusFBW/MCDU1FuelPred"),
    22: ("SEC F-PLN -> RTE", "AirbusFBW/MCDU1SecFpln"),
    23: ("ATC COMM", "AirbusFBW/MCDU1ATC"),
    24: ("MENU", "AirbusFBW/MCDU1Menu"),
    25: ("BRIGHTNESS DOWN", "AirbusFBW/MCDU1KeyDim"),
    26: ("AIRPORT -> DEP/ARR", "AirbusFBW/MCDU1Airport"),
    # JUDGMENT CALL: Boeing's FIX key has no catalogued Airbus MCDU1Fix*
    # command either. Left unassigned.
    27: ("EMPTY BOTTOM LEFT -> FIX", None),
    # JUDGMENT CALL: these four physical positions (PREV PAGE / PAGE UP /
    # NEXT PAGE / PAGE DOWN) only make sense on this hardware as a 4-way
    # slew diamond - Airbus MCDU1SlewUp/Down/Left/Right map onto exactly
    # four keys, while Boeing only ever used two of them (PREV/NEXT PAGE)
    # and left PAGE UP/DOWN unassigned (None in MCDU_KEY_MAP). The up/down
    # vs left/right physical orientation guessed here (UP=top, DOWN=bottom,
    # PREV=left, NEXT=right) needs a live check.
    28: ("PREV PAGE", "AirbusFBW/MCDU1SlewLeft"),
    29: ("PAGE UP", "AirbusFBW/MCDU1SlewUp"),
    30: ("NEXT PAGE", "AirbusFBW/MCDU1SlewRight"),
    31: ("PAGE DOWN", "AirbusFBW/MCDU1SlewDown"),
    32: ("1", "AirbusFBW/MCDU1Key1"), 33: ("2", "AirbusFBW/MCDU1Key2"),
    34: ("3", "AirbusFBW/MCDU1Key3"), 35: ("4", "AirbusFBW/MCDU1Key4"),
    36: ("5", "AirbusFBW/MCDU1Key5"), 37: ("6", "AirbusFBW/MCDU1Key6"),
    38: ("7", "AirbusFBW/MCDU1Key7"), 39: ("8", "AirbusFBW/MCDU1Key8"),
    40: ("9", "AirbusFBW/MCDU1Key9"),
    # Also the PERIOD x3 gesture index - TolissBB36MirrorPath defers single/
    # double taps back to this normal KeyDecimal action; only a genuine
    # triple tap is consumed as the page-toggle gesture.
    41: (".", "AirbusFBW/MCDU1KeyDecimal"),
    42: ("0", "AirbusFBW/MCDU1Key0"),
    43: ("+/-", "AirbusFBW/MCDU1KeyPM"),
    44: ("A", "AirbusFBW/MCDU1KeyA"), 45: ("B", "AirbusFBW/MCDU1KeyB"),
    46: ("C", "AirbusFBW/MCDU1KeyC"), 47: ("D", "AirbusFBW/MCDU1KeyD"),
    48: ("E", "AirbusFBW/MCDU1KeyE"), 49: ("F", "AirbusFBW/MCDU1KeyF"),
    50: ("G", "AirbusFBW/MCDU1KeyG"), 51: ("H", "AirbusFBW/MCDU1KeyH"),
    52: ("I", "AirbusFBW/MCDU1KeyI"), 53: ("J", "AirbusFBW/MCDU1KeyJ"),
    54: ("K", "AirbusFBW/MCDU1KeyK"), 55: ("L", "AirbusFBW/MCDU1KeyL"),
    56: ("M", "AirbusFBW/MCDU1KeyM"), 57: ("N", "AirbusFBW/MCDU1KeyN"),
    58: ("O", "AirbusFBW/MCDU1KeyO"), 59: ("P", "AirbusFBW/MCDU1KeyP"),
    60: ("Q", "AirbusFBW/MCDU1KeyQ"), 61: ("R", "AirbusFBW/MCDU1KeyR"),
    62: ("S", "AirbusFBW/MCDU1KeyS"), 63: ("T", "AirbusFBW/MCDU1KeyT"),
    64: ("U", "AirbusFBW/MCDU1KeyU"), 65: ("V", "AirbusFBW/MCDU1KeyV"),
    66: ("W", "AirbusFBW/MCDU1KeyW"), 67: ("X", "AirbusFBW/MCDU1KeyX"),
    68: ("Y", "AirbusFBW/MCDU1KeyY"), 69: ("Z", "AirbusFBW/MCDU1KeyZ"),
    # Also the SLASH x2 gesture index - same deferred-tap treatment as
    # PERIOD above, so a single "/" still reaches the MCDU (unlike Zibo's
    # BB36 path, where a lone slash press is currently swallowed entirely).
    70: ("/", "AirbusFBW/MCDU1KeySlash"),
    71: ("SPACE", "AirbusFBW/MCDU1KeySpace"),
    # Real Airbus "overfly" waypoint key - a direct match, not a guess.
    72: ("OVERFLY -> DEL", "AirbusFBW/MCDU1KeyOverfly"),
    73: ("CLR", "AirbusFBW/MCDU1KeyClear"),
}

# ---------------------------------------------------------------------------
# CDU content mirror datarefs: AirbusFBW/MCDU1<row><colour-channel>, the real
# ToLiss/AirbusFBW rendering convention (source: dualznz/toliss-a430-datarefs,
# also catalogued in xplane_command_catalog.json). 7 colour channels per
# label/content row; title/scratchpad rows expose only the channels that
# realistically apply to them.
#
# JUDGMENT CALL (flagged for live confirmation): the exact colour a channel
# letter renders as. "w/g/a/m/y" read unambiguously as white/green/amber/
# magenta/yellow. "b" is mapped to cyan - older Airbus documentation calls
# the CDU's light-blue "blue" where Boeing calls the same shade "cyan", and
# Boeing's own compose function in mcdu_bb36.py already uses COLOR_CYAN for
# this role. "s" has no obvious avionics-colour meaning (there is no red
# channel in this dataref set at all) and is mapped to COLOR_GREY as a
# distinct placeholder pending a live check of what it actually renders.
#
# JUDGMENT CALL: "scont<N><ch>" and "stitle<ch>" are composed as an overlay
# on top of "cont<N><ch>"/"title<ch>" (non-space characters only, matching
# the L/S/I/M layering mcdu_bb36.py's _compose_zibo_page already uses for
# Boeing) rather than as separate rows - there are only 14 physical rows on
# this glass and cont/label/title already account for all of them, so scont/
# stitle must share a row with something. Confirm this is really a same-row
# secondary string (e.g. a small-font annotation) and not something else.
TOLISS_MCDU_COLOR_CHANNELS: Tuple[str, ...] = ("a", "b", "g", "m", "s", "w", "y")
_TOLISS_TITLE_CHANNELS: Tuple[str, ...] = ("b", "g", "s", "w", "y")
_TOLISS_STITLE_CHANNELS: Tuple[str, ...] = ("b", "g", "w", "y")
_TOLISS_SCRATCHPAD_CHANNELS: Tuple[str, ...] = ("a", "w")

TOLISS_MCDU_CONTENT_DATAREFS: Dict[str, str] = {}
for _ch in _TOLISS_TITLE_CHANNELS:
    TOLISS_MCDU_CONTENT_DATAREFS[f"title_{_ch}"] = f"AirbusFBW/MCDU1title{_ch}"
for _ch in _TOLISS_STITLE_CHANNELS:
    TOLISS_MCDU_CONTENT_DATAREFS[f"stitle_{_ch}"] = f"AirbusFBW/MCDU1stitle{_ch}"
for _line in range(1, 7):
    for _ch in TOLISS_MCDU_COLOR_CHANNELS:
        TOLISS_MCDU_CONTENT_DATAREFS[f"label{_line}_{_ch}"] = f"AirbusFBW/MCDU1label{_line}{_ch}"
        TOLISS_MCDU_CONTENT_DATAREFS[f"cont{_line}_{_ch}"] = f"AirbusFBW/MCDU1cont{_line}{_ch}"
        TOLISS_MCDU_CONTENT_DATAREFS[f"scont{_line}_{_ch}"] = f"AirbusFBW/MCDU1scont{_line}{_ch}"
for _ch in _TOLISS_SCRATCHPAD_CHANNELS:
    TOLISS_MCDU_CONTENT_DATAREFS[f"sp_{_ch}"] = f"AirbusFBW/MCDU1sp{_ch}"

# ---------------------------------------------------------------------------
# Secondary graphical-page datarefs. The current PFD/ND uses ToLiss's
# purpose-built `toliss_airbus/pfdoutputs/*` mirror values together with its
# exact captain-side `AirbusFBW/*` indications and validity flags. Generic
# simulator refs remain only where ToLiss publishes no add-on equivalent
# (own-ship position and a few defensive engine fallbacks). Field layout and
# array indexing still require the normal live-session confirmation.
# ---------------------------------------------------------------------------
TOLISS_MCDU_SECONDARY_DATAREFS: Dict[str, Dict[str, str]] = {
    "pfd": {
        "pitch": "toliss_airbus/pfdoutputs/captain/pitch_angle",
        "roll": "toliss_airbus/pfdoutputs/captain/roll_angle",
        "vs": "toliss_airbus/pfdoutputs/captain/vertical_speed",
        "drift": "toliss_airbus/pfdoutputs/captain/drift_angle",
        "fpa": "toliss_airbus/pfdoutputs/captain/flight_path_angle",
        "ap_alt_target": "toliss_airbus/pfdoutputs/general/ap_alt_target_value",
        "ap_alt_target_type": "toliss_airbus/pfdoutputs/general/ap_alt_target_type",
        "ap_alt_ref": "toliss_airbus/pfdoutputs/general/ap_altitude_reference",
        "ap_speed": "toliss_airbus/pfdoutputs/general/ap_speed_value",
        "ap_engaged": "toliss_airbus/pfdoutputs/general/ap_engage_boxed",
        "fd_engaged": "toliss_airbus/pfdoutputs/general/fd_engage_boxed",
        "athr_engaged": "toliss_airbus/pfdoutputs/general/athr_engage_boxed",
        "athr_mode": "toliss_airbus/pfdoutputs/general/athr_thrust_mode",
        # ToLiss exposes the three FMA rows as full-width, already-positioned
        # colour layers.  Using these native strings preserves every active
        # and armed mode the aircraft itself presents instead of maintaining
        # an incomplete Studio enum table.
        "fma1_green": "AirbusFBW/FMA1g",
        "fma1_blue": "AirbusFBW/FMA1b",
        "fma1_white": "AirbusFBW/FMA1w",
        "fma2_blue": "AirbusFBW/FMA2b",
        "fma2_magenta": "AirbusFBW/FMA2m",
        "fma2_white": "AirbusFBW/FMA2w",
        "fma3_amber": "AirbusFBW/FMA3a",
        "fma3_blue": "AirbusFBW/FMA3b",
        "fma3_white": "AirbusFBW/FMA3w",
        "v_ls": "toliss_airbus/pfdoutputs/general/VLS_value",
        "v_max": "toliss_airbus/pfdoutputs/general/VMax_value",
        "v_sw": "toliss_airbus/pfdoutputs/general/VSW_value",
        "v_green_dot": "toliss_airbus/pfdoutputs/general/VGreenDot_value",
        # Take-off speeds entered/computed on the ToLiss PERF TO page.  V1
        # and V2 are not part of the pfdoutputs block, while VR has a
        # display-ready pfdoutputs value below.  Keep all three distinct:
        # the Airbus PFD presents V1 as "1", VR as a cyan circle and V2 as
        # the magenta target triangle rather than collapsing them into one
        # generic speed bug.
        "v1": "toliss_airbus/performance/V1",
        "v2": "toliss_airbus/performance/V2",
        "v_r": "toliss_airbus/pfdoutputs/general/VR_value",
        "ils_freq": "toliss_airbus/pfdoutputs/general/ils_frequency",
        "ils_type": "toliss_airbus/pfdoutputs/general/ils_type",
        "dme_distance": "toliss_airbus/pfdoutputs/general/dme_distance",
        "landing_elev": "toliss_airbus/pfdoutputs/general/landing_elev",
        # -------------------------------------------------------------------
        # Added for Part E step 2 (pfp_renderer_toliss.py, the graphical PFD
        # page - previously "pfd" only fed Part D's plain text-row mirror).
        # Every name below was individually re-verified against
        # xplane_command_catalog.json with aircraft=="toliss" for this task
        # (not trusted from the plan's own list secondhand).
        # -------------------------------------------------------------------
        "ias": "AirbusFBW/IASCapt",
        "mach": "AirbusFBW/MachCapt",
        "altitude": "AirbusFBW/ALTCapt",
        # Native captain-source validity flags.  These are distinct from a
        # WebSocket disconnect: explicit zero means the powered Airbus PFD
        # must show its red SPD/ALT/ATT/HDG failure presentation.
        "ias_valid": "AirbusFBW/CaptIASValid",
        "alt_valid": "AirbusFBW/CaptALTValid",
        "att_valid": "AirbusFBW/CaptATTValid",
        "hdg_valid": "AirbusFBW/CaptHDGValid",
        "fd_pitch_cmd": "toliss_airbus/pfdoutputs/general/fd1_pitch_cmd",
        "fd_roll_cmd": "toliss_airbus/pfdoutputs/general/fd1_roll_cmd",
        "alpha_floor": "toliss_airbus/pfdoutputs/general/alpha_floor_mode",
        "v_vfe_next": "toliss_airbus/pfdoutputs/general/VFENext_value",
        "v_f": "toliss_airbus/pfdoutputs/general/VF_value",
        "v_s": "toliss_airbus/pfdoutputs/general/VS_value",
        "v_alpha_max": "toliss_airbus/pfdoutputs/general/VAlphaMax_value",
        "v_aprot": "toliss_airbus/pfdoutputs/general/VAProt_value",
        # ToLiss owns the phase/configuration logic deciding when the PERF
        # TO markers belong on the tape.  An explicit zero must therefore
        # hide them; Studio must not infer take-off phase from IAS or gear.
        "show_to_speeds": "toliss_airbus/pfdoutputs/general/show_to_speeds",
        "climb_cas_presel": "toliss_airbus/pfdoutputs/general/climb_cas_presel",
        "cruise_cas_presel": "toliss_airbus/pfdoutputs/general/cruise_cas_presel",
        "cruise_mach_presel": "toliss_airbus/pfdoutputs/general/cruise_mach_presel",
        "ils_slope": "toliss_airbus/pfdoutputs/general/ils_slope",
        "ils_on_capt": "AirbusFBW/ILSonCapt",
        # Raw needle deviations (-1..1 full-scale, same convention assumed
        # for both) rather than ILSCourseDev, which is FCU course-knob-
        # relative and not what a raw LOC/G-S deviation scale should show.
        "loc_raw": "AirbusFBW/ILS1LocRaw",
        "gs_raw": "AirbusFBW/ILS1GSRaw",
        "lateral_accel": "toliss_airbus/pfdoutputs/general/lateral_acceleration",
        "baro_std_capt": "AirbusFBW/BaroStdCapt",
        "baro_unit_capt": "AirbusFBW/BaroUnitCapt",
        # JUDGMENT CALL: no AirbusFBW captain baro VALUE dataref is
        # catalogued at all (only the Std/Unit flags above and a knob-
        # rotation ratio) - the standby-instrument setting is used as a
        # proxy. Confirm live that the ISI and captain baro settings track
        # together; see pfp_renderer_toliss.py's own comment on this key.
        "baro_value": "AirbusFBW/ISIBaroSetting",
        "target_heading": "AirbusFBW/APHDG_Capt",
        "heading": "AirbusFBW/HDGCapt",
    },
    # -----------------------------------------------------------------------
    # "nd" feeds the real Navigation Display (nd_renderer_toliss.py, Part E
    # step 3). Real per-waypoint route source: toliss_airbus/flightplan/* -
    # array shape/indexing NOT documented in the catalog metadata (no length
    # or type info exists there at all), flagged for live confirmation same
    # as every other array in this table. Real EFIS mode/range rotaries
    # (AirbusFBW/NDmodeCapt/NDrangeCapt) and overlay toggles (NDShow*Capt/
    # WXRonND1/TerrainSelectedND1) - all individually re-verified against
    # xplane_command_catalog.json with aircraft=="toliss" for this task.
    # -----------------------------------------------------------------------
    "nd": {
        # CONFIRMED GAP: ToLiss publishes native captain heading and validity,
        # but not a separate add-on own-ship latitude/longitude pair. A
        # route-relative map is impossible without position, so only those
        # two coordinates use simulator-level state. The heading ID is shared
        # deliberately with PFD and fanned out to both local keys downstream.
        "nd_heading": "AirbusFBW/HDGCapt",
        "nd_own_lat": "sim/flightmodel/position/latitude",
        "nd_own_lon": "sim/flightmodel/position/longitude",
        # Text path used only to select the matching ToLiss situation
        # autosave.  The route reader remains GET/file-read only.
        "nd_aircraft_path": "sim/aircraft/view/acf_relative_path",
        "nd_heading_valid": "AirbusFBW/CaptHDGValid",
        "nd_map_available": "AirbusFBW/CaptMAPAvail",
        "nd_gps_primary_message": "AirbusFBW/GPSPrimMessCapt",
        "nd_ground_speed": "AirbusFBW/GSCapt",
        "nd_true_air_speed": "AirbusFBW/TASCapt",
        "nd_wind_available": "AirbusFBW/WindDataAvailableCapt",
        "nd_wind_direction": "AirbusFBW/WindDirCapt",
        "nd_wind_speed": "AirbusFBW/WindSpdCapt",
        "nd_waypoint_distance": "AirbusFBW/WPT_Dist",
        "nd_waypoint_course": "AirbusFBW/WPT_Crs",
        # JUDGMENT CALL: enum order for both rotaries is not documented in
        # the catalog (no enum metadata at all) - see nd_renderer_toliss.py's
        # own _ND_MODE_LABELS/_ND_RANGE_TABLE comments for the guessed order.
        "nd_mode": "AirbusFBW/NDmodeCapt",
        "nd_range": "AirbusFBW/NDrangeCapt",
        # These legacy toliss_airbus/flightplan arrays are absent from the
        # installed A321 1.8 catalogue. They remain optional for versions that
        # publish them; WPT_Crs/WPT_Dist supplies the active-leg fallback.
        "nd_route_lat": "toliss_airbus/flightplan/latitude",
        "nd_route_lon": "toliss_airbus/flightplan/longitude",
        "nd_route_alt": "toliss_airbus/flightplan/altitude",
        "nd_route_no_wp": "toliss_airbus/flightplan/no_wp",
        # JUDGMENT CALL: treated as a 0-based index into the latitude/
        # longitude arrays - confirm live (see nd_renderer_toliss.py's
        # _draw_route comment on this same field).
        "nd_route_to_wp": "toliss_airbus/flightplan/current_to_waypoint",
        # ToLiss marks the active route dashed while the aircraft is in a
        # selected lateral mode and no longer following it.  This is the
        # exact state shown in the ToLiss tutorial; keep it as route styling,
        # not as a guessed change of plan colour.
        "nd_route_dashed": "AirbusFBW/FlightPlanDashed",
        # Text-shaped datarefs (see TOLISS_ND_TEXT_KEYS below) - decoded via
        # the same _toliss_decode_text base64/byte-array path already
        # proven for the CDU content channels, not _decode_numeric.
        "nd_wpt_id": "AirbusFBW/WPT_ID",
        "nd_departure_icao": "toliss_airbus/flightplan/departure_icao",
        "nd_destination_icao": "toliss_airbus/flightplan/destination_icao",
        # Captain EFIS bearing-source selectors.  ToLiss's own knobs.obj and
        # live writable datarefs establish the absolute enum 0=ADF, 1=OFF,
        # 2=VOR.  Bearing arrays and validity/identifier outputs are native
        # ToLiss sources; NAV1 is the single needle, NAV2 the double needle.
        "nd_bearing1_selector": "ckpt/fcu/adf1Left/anim",
        "nd_bearing2_selector": "ckpt/fcu/adf2Left/anim",
        "nd_vor_bearings": "AirbusFBW/VORBearingArray",
        "nd_ndb_bearings": "AirbusFBW/NDBBearingArray",
        "nd_vor1_valid": "AirbusFBW/VOR1IDValid",
        "nd_vor2_valid": "AirbusFBW/VOR2IDValid",
        "nd_adf1_valid": "AirbusFBW/ADF1IDValid",
        "nd_adf2_valid": "AirbusFBW/ADF2IDValid",
        "nd_vor1_id": "AirbusFBW/VOR1ID",
        "nd_vor2_id": "AirbusFBW/VOR2ID",
        "nd_adf1_id": "AirbusFBW/ADF1ID",
        "nd_adf2_id": "AirbusFBW/ADF2ID",
        "nd_vor1_dme": "sim/cockpit2/radios/indicators/nav1_dme_distance_nm",
        "nd_vor2_dme": "sim/cockpit2/radios/indicators/nav2_dme_distance_nm",
        # Raw LOC-style deviation + selected course + on/off - real, shares
        # meaning with "pfd"'s own loc_raw/ils_on_capt keys under separate
        # local names (required: see the collision check below).
        "nd_ils_loc": "AirbusFBW/ILS1LocRaw",
        "nd_ils_crs": "AirbusFBW/ILSCrs",
        "nd_ils_on": "AirbusFBW/ILSonCapt",
        # EFIS control-panel overlay toggles - real, all confirmed in the
        # catalog. Shown as on/off annunciations only (no ToLiss dataref
        # carries the actual weather/terrain/navaid map content itself).
        "nd_show_arpt": "AirbusFBW/NDShowARPTCapt",
        "nd_show_cstr": "AirbusFBW/NDShowCSTRCapt",
        "nd_show_vord": "AirbusFBW/NDShowVORDCapt",
        "nd_show_wpt": "AirbusFBW/NDShowWPTCapt",
        "nd_show_ndb": "AirbusFBW/NDShowNDBCapt",
        "nd_show_wxr": "AirbusFBW/WXRonND1",
        "nd_show_terr": "AirbusFBW/TerrainSelectedND1",
    },
    # Permanent data printed along the bottom of Airbus SD pages.  These are
    # subscribed once and shared by every ECAM renderer; they are not a
    # selectable page and therefore do not belong in TOLISS_DISPLAY_PAGE_ORDER.
    "ecam_common": {
        "ecam_tat": "sim/weather/aircraft/temperature_leadingedge_deg_c",
        "ecam_sat": "sim/weather/aircraft/temperature_ambient_deg_c",
        "ecam_gw": "sim/flightmodel/weight/m_total",
        "ecam_utc": "sim/time/zulu_time_sec",
    },
    # BUG-40: independently named supplemental inputs for the reference SD
    # drawings. Never interpret SD* drawing enums as physical units.
    "ecam_reference": ECAM_AUDITED_DATAREFS,
    # -----------------------------------------------------------------------
    # "eng" and every page below feed the real ECAM synoptic pages
    # (systems_renderer_toliss.py), superseding Part D's old ENG text-mirror
    # body. All target real "AirbusFBW/" rows (xplane_command_catalog.json,
    # aircraft=="toliss") except the four explicitly-flagged generic X-Plane
    # SDK fallbacks in "eng". _TolissMcduFeed flattens every page dict below
    # into ONE secondary_values dict keyed by these strings, so every key is
    # deliberately prefixed with its page name to guarantee no two pages
    # collide there - keep that convention when adding more.
    #
    # None of these were sized/shaped by the catalog (it carries no
    # array-length metadata for any of them), so every array index used at
    # render time is a JUDGMENT CALL grounded in real A320 system layout
    # (e.g. 3 hydraulic systems in G/B/Y order, 2 engines) rather than a
    # confirmed field map - read defensively (_toliss_secondary_element in
    # final.py) and correct fast after a live check.
    # -----------------------------------------------------------------------
    "eng": {
        "eng_egt": "AirbusFBW/ENGEGTArray",
        "eng_ff": "AirbusFBW/ENGFuelFlowArray",
        # Miscategorized under "Air Cond/Pressurization" in the catalog - a
        # cataloguing quirk, not a hint about the dataref's real meaning.
        "eng_oilpress": "AirbusFBW/ENGOilPressArray",
        "eng_epr": "AirbusFBW/ENGEPRArray",
        "eng_target_n1": "AirbusFBW/ENGTLASettingN1",
        "eng_target_epr": "AirbusFBW/THRRatingEPR",
        "eng_mode": "AirbusFBW/ENGModeArray",
        "eng_fadec": "AirbusFBW/FADECStateArray",
        "eng_master1": "AirbusFBW/ENG1MasterSwitch",
        "eng_master2": "AirbusFBW/ENG2MasterSwitch",
        # CONFIRMED GAP (catalog searched exhaustively): no N1%, N2%,
        # oil-temperature, or vibration dataref exists under ToLiss's own
        # "AirbusFBW/" tag. "AirbusFBW/anim/ENGN1Speed" exists but is an
        # animation-only needle-position value (the "anim/" namespace drives
        # 3D cockpit needle sweep, not a calibrated instrument reading), so
        # it is deliberately NOT used here. Per the owner's explicit decision
        # this session, these four fall back to generic, non-ToLiss-tagged
        # core X-Plane SDK datarefs instead - confirm against a live session
        # that ToLiss's own engine model actually feeds these arrays
        # correctly before trusting them.
        "eng_gen_n1": "sim/cockpit2/engine/indicators/N1_percent",
        "eng_gen_n2": "sim/cockpit2/engine/indicators/N2_percent",
        "eng_gen_oiltemp": "sim/cockpit2/engine/indicators/oil_temperature_deg_C",
        "eng_gen_vib": "sim/cockpit2/engine/indicators/engine_vibration",
    },
    "bleed": {
        "bleed_press_l": "AirbusFBW/LeftBleedPress",
        "bleed_press_r": "AirbusFBW/RightBleedPress",
        # ToLiss publishes absolute psia; the SD shows gauge PSI after local
        # ambient pressure is subtracted by toliss_ecam_telemetry.
        "bleed_ambient_pressure_pa": "sim/weather/aircraft/barometer_current_pas",
        # ENG*BleedInd is a confirmed stale zero in the running A321.  These
        # two native engine facts constrain the guarded fallback; neither
        # pressure nor the overhead switch can establish an engine source.
        "bleed_engine_running": "sim/flightmodel/engine/ENGN_running",
        "bleed_intercon": "AirbusFBW/BleedIntercon",
        "bleed_ground_hp": "AirbusFBW/GroundHPAir",
        "bleed_ground_lp": "AirbusFBW/GroundLPAir",
        "bleed_ind_1": "AirbusFBW/ENG1BleedInd",
        "bleed_ind_2": "AirbusFBW/ENG2BleedInd",
        "bleed_hp_1": "AirbusFBW/ENG1HPBleedInd",
        "bleed_hp_2": "AirbusFBW/ENG2HPBleedInd",
        "bleed_switch_1": "AirbusFBW/ENG1BleedSwitch",
        "bleed_switch_2": "AirbusFBW/ENG2BleedSwitch",
        "bleed_apu_ind": "AirbusFBW/APUBleedInd",
        "bleed_xbleed_ind": "AirbusFBW/XBleedInd",
        "bleed_pack1_switch": "AirbusFBW/Pack1Switch",
        "bleed_pack2_switch": "AirbusFBW/Pack2Switch",
        "bleed_pack1_temp": "AirbusFBW/Pack1Temp",
        "bleed_pack2_temp": "AirbusFBW/Pack2Temp",
        # Native 0.8..1.2 flow-pointer scale, not kg/s and not percent.
        "bleed_pack1_flow": "AirbusFBW/Pack1Flow",
        "bleed_pack2_flow": "AirbusFBW/Pack2Flow",
    },
    "press": {
        # CabinAlt is catalogued under "Autopilot/FCU" - another cataloguing
        # quirk; the name and unit (feet) are unambiguous.
        "press_cabin_alt": "AirbusFBW/CabinAlt",
        "press_cabin_vs": "AirbusFBW/CabinVS",
        "press_outflow": "AirbusFBW/OutflowValve",
        "press_outflow_aft": "AirbusFBW/OutFlowValveAft",
        "press_mode": "AirbusFBW/CabPressMode",
        "press_mode_lights": "AirbusFBW/CabPressModeLights",
    },
    "cond": {
        "cond_fwd_cabin_temp": "AirbusFBW/CabinZone1Temperature_degC",
        "cond_aft_cabin_temp": "AirbusFBW/CabinZone2Temperature_degC",
        "cond_fwd_cargo_temp": "AirbusFBW/FwdCargoTemp",
        "cond_aft_cargo_temp": "AirbusFBW/AftCargoTemp",
        "cond_bulk_cargo_temp": "AirbusFBW/BulkCargoTemp",
        "cond_vent_inlet": "AirbusFBW/VentInletValve",
        "cond_vent_extract": "AirbusFBW/VentExtractValve",
        "cond_cargo_hot_air": "AirbusFBW/CargoHotAir",
        "cond_cockpit_trim": "AirbusFBW/CockpitTrim",
        "cond_zone1_trim": "AirbusFBW/Zone1Trim",
        "cond_zone2_trim": "AirbusFBW/Zone2Trim",
    },
    "elec": {
        # BatVolts is actual battery voltage. OHP switches are NOT generator
        # output indications. The audited adapter suppresses those guesses.
        "elec_bat_volts": "AirbusFBW/BatVolts",
        "elec_ohp": "AirbusFBW/ElecOHPArray",
        "elec_ac_cross": "AirbusFBW/SDACCrossConnect",
        "elec_ext_pow": "AirbusFBW/SDExtPowBox",
    },
    "hyd": {
        # Real A320 order: Green, Blue, Yellow.
        "hyd_press": "AirbusFBW/HydSysPressArray",
        "hyd_qty": "AirbusFBW/HydSysQtyArray",
        "hyd_ptu_mode": "AirbusFBW/HydPTUMode",
        "hyd_rat_mode": "AirbusFBW/HydRATMode",
        "hyd_y_elec_mode": "AirbusFBW/HydYElecMode",
        "hyd_brake_accu": "AirbusFBW/BrakeAccu",
        "hyd_altn_brake": "AirbusFBW/AltnBrake",
    },
    "fuel": {
        # SDFUEL is a scalar page selector, not quantities. The audited
        # adapter reads the A321's installed tank layout via ref_fuel_mass.
        "fuel_ff": "AirbusFBW/ENGFuelFlowArray",
        "fuel_lp_valve": "AirbusFBW/ENGFuelLPValveArray",
        "fuel_apu_ff": "AirbusFBW/APUFuelFlow",
        "fuel_extra_tanks": "AirbusFBW/FuelNumExtraTanks",
        # "Write" in the name suggests an init-time override; treat the
        # readback as FOB but confirm it tracks live fuel burn.
        "fuel_fob": "AirbusFBW/WriteFOB",
    },
    "door": {
        # JUDGMENT CALL: PaxDoorArray/CargoDoorArray element order guessed
        # from real A320 door layout (pax: L1/R1/L2/R2; cargo: FWD/AFT).
        "door_pax": "AirbusFBW/PaxDoorArray",
        "door_cargo": "AirbusFBW/CargoDoorArray",
        "door_bulk": "AirbusFBW/BulkDoor",
        "door_clg": "AirbusFBW/CLGDoor",
        "door_cockpit": "AirbusFBW/CockpitDoorLockState",
        "door_slides": "AirbusFBW/PaxDoorSlidesDeployRatio",
        "door_oxy_crew": "AirbusFBW/CrewOxyMask",
        "door_oxy_pax": "AirbusFBW/PaxOxyMask",
    },
    "wheel": {
        "wheel_gear_lever": "AirbusFBW/GearLever",
        "wheel_gear_l": "AirbusFBW/LeftGearInd",
        "wheel_gear_n": "AirbusFBW/NoseGearInd",
        "wheel_gear_r": "AirbusFBW/RightGearInd",
        "wheel_brake_temp": "AirbusFBW/BrakeTemperatureArray",
        "wheel_tire_pressure": "AirbusFBW/TirePressureArray",
        "wheel_brake_l": "AirbusFBW/TotLeftBrake",
        "wheel_brake_r": "AirbusFBW/TotRightBrake",
        "wheel_park_brake": "AirbusFBW/ParkBrake",
        "wheel_autobrk_lo": "AirbusFBW/AutoBrkLo",
        "wheel_autobrk_med": "AirbusFBW/AutoBrkMed",
        "wheel_autobrk_max": "AirbusFBW/AutoBrkMax",
        "wheel_antiskid": "AirbusFBW/NWSnAntiSkid",
        "wheel_nws_avail": "AirbusFBW/NWSAvail",
        "wheel_spd_brake": "AirbusFBW/SpdBrakeDeployed",
        "wheel_brake_fan": "AirbusFBW/BrakeFan",
    },
    "apu": {
        "apu_avail": "AirbusFBW/APUAvail",
        "apu_egt": "AirbusFBW/APUEGT",
        "apu_egt_limit": "AirbusFBW/APUEGTLimit",
        "apu_n_pct": "AirbusFBW/APUN",
        "apu_flap": "AirbusFBW/APUFlapOpenRatio",
        "apu_master": "AirbusFBW/APUMaster",
        "apu_starter": "AirbusFBW/APUStarter",
        "apu_fire": "AirbusFBW/APUOnFire",
        "apu_bleed_switch": "AirbusFBW/APUBleedSwitch",
        "apu_bleed_ind": "AirbusFBW/APUBleedInd",
        "apu_ff": "AirbusFBW/APUFuelFlow",
    },
    "fctl": {
        # SDSpoilerArray carries the ToLiss SD status codes.  The scalar
        # anim/* values below are the actual surface animation positions used
        # by both installed ToLiss A320 and A321 object models.  They were
        # also resolved/read through the live X-Plane API on 2026-09-09.
        "fctl_spoilers": "AirbusFBW/SDSpoilerArray",
        **{
            f"fctl_spoiler_{index}": f"anim/spoiler/{index}"
            for index in range(1, 11)
        },
        "fctl_aileron_l": "anim/aileronLeft",
        "fctl_aileron_r": "anim/aileronRight",
        "fctl_elevator_l": "anim/elevatorLeft",
        "fctl_elevator_r": "anim/elevatorRight",
        "fctl_rudder": "anim/rudder",
        "fctl_hyd_press": "AirbusFBW/HydSysPressArray",
        "fctl_rudder_avail": "AirbusFBW/RudderAvailArray",
        "fctl_pitch_trim": "AirbusFBW/PitchTrimPosition",
        "fctl_yaw_trim": "AirbusFBW/YawTrimPosition",
    },
    # CRUISE is the twelfth normal Airbus SD system page.  It has no manual
    # selector on the ECP, but belongs in BB36's complete page cycle.
    "cruise": {
        "cruise_oil_qty": "sim/cockpit2/engine/indicators/oil_quantity_ratio",
        "cruise_vib": "sim/cockpit2/engine/indicators/engine_vibration",
        "cruise_ff": "AirbusFBW/ENGFuelFlowArray",
        "cruise_cabin_alt": "AirbusFBW/CabinAlt",
        "cruise_cabin_vs": "AirbusFBW/CabinVS",
        "cruise_delta_p": "AirbusFBW/CabinDeltaP",
        "cruise_fwd_temp": "AirbusFBW/CabinZone1Temperature_degC",
        "cruise_aft_temp": "AirbusFBW/CabinZone2Temperature_degC",
    },
    "status": {
        # The real STATUS page is a scrolling failure-message list; no
        # message-text dataref is catalogued, so this page renders a
        # warning/caution summary annunciator from real light/flag
        # datarefs instead of fabricating message text - see this page's
        # comment in systems_renderer_toliss.py.
        "status_master_warn": "AirbusFBW/MasterWarn",
        "status_master_caut": "AirbusFBW/MasterCaut",
        "status_flight_phase": "AirbusFBW/ECAMFlightPhase",
        "status_ap_warn": "AirbusFBW/APWarning",
        "status_athr_warn": "AirbusFBW/ATHROffWarning",
        "status_retard_warn": "AirbusFBW/RetardWarning",
        "status_ospeed_warn": "AirbusFBW/OSpeedWarning",
    },
}

# Secondary keys that carry TEXT (a char-array dataref, same shape as the CDU
# content channels) rather than a number.  The historical public name is kept
# because callers already import it, but it now includes native PFD FMA colour
# layers as well as ND identifiers.  _TolissMcduFeed._worker routes these
# through _toliss_decode_text instead of _decode_numeric.
TOLISS_ND_TEXT_KEYS: Tuple[str, ...] = (
    "nd_wpt_id", "nd_departure_icao", "nd_destination_icao", "nd_aircraft_path",
    "nd_vor1_id", "nd_vor2_id", "nd_adf1_id", "nd_adf2_id",
    "fma1_green", "fma1_blue", "fma1_white",
    "fma2_blue", "fma2_magenta", "fma2_white",
    "fma3_amber", "fma3_blue", "fma3_white",
)

# Sanity check at import time: _TolissMcduFeed flattens every page dict above
# into one secondary_values dict, so two pages accidentally sharing a raw key
# would silently overwrite each other's live data with no visible error.
_TOLISS_SECONDARY_KEY_OWNER: Dict[str, str] = {}
for _page_name, _page_data in TOLISS_MCDU_SECONDARY_DATAREFS.items():
    for _raw_key in _page_data:
        _prior = _TOLISS_SECONDARY_KEY_OWNER.get(_raw_key)
        if _prior is not None and _prior != _page_name:
            raise RuntimeError(
                f"TOLISS_MCDU_SECONDARY_DATAREFS key collision: {_raw_key!r} "
                f"used by both {_prior!r} and {_page_name!r}"
            )
        _TOLISS_SECONDARY_KEY_OWNER[_raw_key] = _page_name
del _page_name, _page_data, _raw_key, _prior

# ---------------------------------------------------------------------------
# CDU content composition (F0 native-canvas 24x14 grid; same geometry the
# Boeing graphical-FMC page uses).
# ---------------------------------------------------------------------------
_TOLISS_MCDU_COLOR_MAP: Dict[str, int] = {
    "a": COLOR_AMBER,
    "b": COLOR_CYAN,
    "g": COLOR_GREEN,
    "m": COLOR_MAGENTA,
    "s": COLOR_GREY,
    "w": COLOR_WHITE,
    "y": COLOR_YELLOW,
}


def _toliss_overlay_row(
    text: str,
    colours: Tuple[int, ...],
    values: Mapping[str, str],
    prefix: str,
    channels: Tuple[str, ...],
) -> Tuple[str, Tuple[int, ...]]:
    """Layer every non-space channel string for one row onto a base row."""
    chars = list(_normalize_24(text))
    colour_list = list(colours)
    for channel in channels:
        overlay = _normalize_24(values.get(f"{prefix}_{channel}", ""))
        colour = _TOLISS_MCDU_COLOR_MAP[channel]
        for index, char in enumerate(overlay):
            if char != " ":
                chars[index] = char
                colour_list[index] = colour
    return "".join(chars), tuple(colour_list)


def _compose_toliss_mcdu_page(values: Mapping[str, str]):
    """Build the 14-row ToLiss MCDU1 page from resolved content dataref text."""
    lines = [" " * MCDU_COLUMNS for _ in range(MCDU_ROWS)]
    colours = [tuple([COLOR_WHITE] * MCDU_COLUMNS) for _ in range(MCDU_ROWS)]

    text, row_colours = _toliss_overlay_row(
        "", tuple([COLOR_WHITE] * MCDU_COLUMNS), values, "title", _TOLISS_TITLE_CHANNELS,
    )
    text, row_colours = _toliss_overlay_row(
        text, row_colours, values, "stitle", _TOLISS_STITLE_CHANNELS,
    )
    lines[0] = text
    colours[0] = row_colours

    for number in range(1, 7):
        label_row = 1 + (number - 1) * 2
        content_row = label_row + 1

        label_text, label_colours = _toliss_overlay_row(
            "", tuple([COLOR_WHITE] * MCDU_COLUMNS), values,
            f"label{number}", TOLISS_MCDU_COLOR_CHANNELS,
        )
        lines[label_row] = label_text
        colours[label_row] = label_colours

        content_text, content_colours = _toliss_overlay_row(
            "", tuple([COLOR_WHITE] * MCDU_COLUMNS), values,
            f"cont{number}", TOLISS_MCDU_COLOR_CHANNELS,
        )
        content_text, content_colours = _toliss_overlay_row(
            content_text, content_colours, values,
            f"scont{number}", TOLISS_MCDU_COLOR_CHANNELS,
        )
        lines[content_row] = content_text
        colours[content_row] = content_colours

    scratch_text, scratch_colours = _toliss_overlay_row(
        "", tuple([COLOR_WHITE] * MCDU_COLUMNS), values, "sp", _TOLISS_SCRATCHPAD_CHANNELS,
    )
    lines[13] = scratch_text
    colours[13] = scratch_colours

    return tuple(lines), tuple(colours)


def _standby_toliss_page():
    """Static page shown before the first real MCDU1 title/content arrives."""
    lines = [" " * MCDU_COLUMNS for _ in range(MCDU_ROWS)]
    colours = [tuple([COLOR_WHITE] * MCDU_COLUMNS) for _ in range(MCDU_ROWS)]

    def place(row: int, text: str, colour: int) -> None:
        text = str(text)[:MCDU_COLUMNS]
        start = max(0, (MCDU_COLUMNS - len(text)) // 2)
        padded = (" " * start + text).ljust(MCDU_COLUMNS)[:MCDU_COLUMNS]
        lines[row] = padded
        colours[row] = tuple(
            colour if padded[column] != " " else COLOR_WHITE
            for column in range(MCDU_COLUMNS)
        )

    place(0, "MUSLIMSIM", COLOR_MAGENTA)
    place(3, "TOLISS MCDU", COLOR_AMBER)
    place(5, "WAITING FOR SIMULATOR", COLOR_WHITE)
    place(11, "DEVELOPED BY", COLOR_WHITE)
    place(12, "MUSLIMSIM", COLOR_MAGENTA)

    return tuple(lines), tuple(colours)


def _keys_only_page():
    """Shown when the owner has turned the live screen mirror off."""
    lines = [" " * MCDU_COLUMNS for _ in range(MCDU_ROWS)]
    colours = [tuple([COLOR_WHITE] * MCDU_COLUMNS) for _ in range(MCDU_ROWS)]

    def place(row: int, text: str, colour: int) -> None:
        text = str(text)[:MCDU_COLUMNS]
        start = max(0, (MCDU_COLUMNS - len(text)) // 2)
        padded = (" " * start + text).ljust(MCDU_COLUMNS)[:MCDU_COLUMNS]
        lines[row] = padded
        colours[row] = tuple(
            colour if padded[column] != " " else COLOR_WHITE
            for column in range(MCDU_COLUMNS)
        )

    place(0, "MUSLIMSIM", COLOR_MAGENTA)
    place(5, "KEYS ACTIVE", COLOR_GREEN)
    place(7, "LIVE DISPLAY OFF", COLOR_AMBER)
    place(13, "ENABLE IN STUDIO", COLOR_WHITE)

    return tuple(lines), tuple(colours)


# ---------------------------------------------------------------------------
# Persisted "live mirror enabled" toggle. Exact atomic-write idiom used by
# ffb_profiles.save_active_profile_name / final.py's
# _save_moza_a210_axis_slots: schema-versioned, fail-open on read error,
# write via a .tmp file + os.replace.
# ---------------------------------------------------------------------------
TOLISS_MCDU_MIRROR_SIDECAR_FILENAME = "mcdu_toliss_mirror_enabled.json"


def load_mirror_enabled(path: Path, default: bool = True) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping) or int(payload.get("schema", 0)) != 1:
            return default
        value = payload.get("enabled")
        return bool(value) if isinstance(value, bool) else default
    except (FileNotFoundError, OSError, ValueError, TypeError):
        return default


def save_mirror_enabled(path: Path, enabled: bool) -> None:
    payload = {"schema": 1, "enabled": bool(enabled)}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except OSError as exc:
        print(f"WARNING: could not persist ToLiss MCDU mirror toggle: {exc}")


def _reverse_dataref_ids(dataref_ids: Mapping[str, int]) -> Dict[str, list[str]]:
    """Return every local consumer for each physical X-Plane dataref id.

    PFD and ND intentionally share native ToLiss sources such as HDGCapt and
    CaptHDGValid. A one-to-one reverse dictionary drops one local consumer
    and leaves its display frozen, so the reverse side must remain a fan-out
    list.
    """
    result: Dict[str, list[str]] = {}
    for key, ref_id in dataref_ids.items():
        result.setdefault(str(int(ref_id)), []).append(key)
    return result


_DISPLAY_SNAPSHOT_KEYS = {
    page: tuple(sorted(set(ECAM_POWER_KEYS)
        | set(TOLISS_MCDU_SECONDARY_DATAREFS.get(page, {}))
        | set(ECAM_EXTRA_KEYS.get(page, ()))
        | (set(TOLISS_MCDU_SECONDARY_DATAREFS["ecam_common"]) | {"ias_valid"}
           if page not in ("pfd", "nd", "cdu") else set())))
    for page in (TOLISS_CDU_PAGE,) + TOLISS_DISPLAY_PAGE_ORDER
}


class _TolissMcduFeed:
    """One WebSocket subscription for MCDU1 content + PFD/engine mirror data.

    Both data sets are read together (one connection, one subscription) since
    they share the same refresh cadence need and this keeps the ToLiss path
    to one data thread, matching _BB36GraphicalFMCFeed's standalone-thread
    fallback mode rather than Boeing's shared telemetry hub (that hub is
    wired to Boeing-only dataref tables and is not a generic reusable piece).
    """

    def __init__(self, api_root: str, api_version: str) -> None:
        self.api_root = str(api_root).rstrip("/")
        self.api_version = str(api_version)
        self.stop_evt = threading.Event()
        self.lock = threading.Lock()
        self.content_values: Dict[str, str] = {}
        self.secondary_values: Dict[str, Any] = {}
        self.connected = False
        self.error = ""
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.thread is not None and self.thread.is_alive():
            return
        self.stop_evt.clear()
        self.thread = threading.Thread(
            target=self._worker, name="BB36-TOLISS-MCDU-FEED", daemon=True,
        )
        self.thread.start()

    def stop(self) -> None:
        self.stop_evt.set()
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=1.5)
        self.thread = None
        with self.lock:
            self.connected = False
            self.content_values = {}
            self.secondary_values = {}

    def mcdu_snapshot(self) -> Tuple[Tuple[str, ...], Tuple[Tuple[int, ...], ...], bool]:
        with self.lock:
            values = dict(self.content_values)
            connected = self.connected
        lines, colours = _compose_toliss_mcdu_page(values)
        return lines, colours, connected

    def secondary_snapshot(self) -> Tuple[Dict[str, Any], bool]:
        with self.lock:
            return dict(self.secondary_values), self.connected

    def page_snapshot(self, page: str) -> Tuple[Dict[str, Any], bool]:
        keys = _DISPLAY_SNAPSHOT_KEYS.get(page, ECAM_POWER_KEYS)
        with self.lock:
            return {key:self.secondary_values[key] for key in keys if key in self.secondary_values}, self.connected

    @staticmethod
    def _decode_numeric(value: Any) -> Any:
        if isinstance(value, list):
            decoded = []
            for item in value:
                try:
                    decoded.append(float(item))
                except (TypeError, ValueError):
                    decoded.append(float("nan"))
            return decoded
        try:
            return float(value)
        except (TypeError, ValueError):
            return float("nan")

    def _worker(self) -> None:
        if websocket is None:
            return

        while not self.stop_evt.is_set():
            ws = None
            try:
                content_ids: Dict[str, int] = {}
                for key, name in TOLISS_MCDU_CONTENT_DATAREFS.items():
                    try:
                        content_ids[key] = _resolve_dataref_id(
                            self.api_root, self.api_version, name,
                        )
                    except Exception:
                        pass

                secondary_ids: Dict[str, int] = {}
                resolved_names: Dict[str, int] = {}
                for page_data in TOLISS_MCDU_SECONDARY_DATAREFS.values():
                    for key, name in page_data.items():
                        try:
                            if name not in resolved_names:
                                resolved_names[name] = _resolve_dataref_id(
                                    self.api_root, self.api_version, name,
                                )
                            secondary_ids[key] = resolved_names[name]
                        except Exception:
                            pass

                if "title_w" not in content_ids:
                    raise RuntimeError(
                        "required ToLiss MCDU1 title dataref unavailable"
                    )

                id_to_content_key = {
                    str(int(ref_id)): key for key, ref_id in content_ids.items()
                }
                # One physical dataref can intentionally feed more than one
                # page-local key (for example HDGCapt and CaptHDGValid feed
                # both PFD and ND).  A one-to-one reverse dict silently kept
                # only the last key and froze the other display.
                id_to_secondary_keys = _reverse_dataref_ids(secondary_ids)

                ws = websocket.create_connection(
                    f"ws://127.0.0.1:8086/api/{self.api_version}",
                    timeout=1.0,
                    enable_multithread=True,
                )
                ws.settimeout(0.10)
                subscriptions = [
                    {"id": ref_id}
                    for ref_id in sorted({
                        int(item)
                        for item in list(content_ids.values()) + list(secondary_ids.values())
                    })
                ]
                ws.send(json.dumps({
                    "req_id": 9460,
                    "type": "dataref_subscribe_values",
                    "params": {"datarefs": subscriptions},
                }, separators=(",", ":")))

                with self.lock:
                    self.content_values.clear()
                    self.secondary_values.clear()
                    self.connected = True
                    self.error = ""

                while not self.stop_evt.is_set():
                    try:
                        raw = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue
                    if not raw:
                        raise ConnectionError("ToLiss telemetry WebSocket closed")

                    message = json.loads(raw)
                    if message.get("type") != "dataref_update_values":
                        continue
                    updates = message.get("data", {})
                    if not isinstance(updates, dict):
                        continue

                    with self.lock:
                        for raw_id, value in updates.items():
                            id_key = str(raw_id).strip()
                            content_key = id_to_content_key.get(id_key)
                            if content_key is not None:
                                self.content_values[content_key] = _toliss_decode_text(value)
                                continue
                            secondary_keys = id_to_secondary_keys.get(id_key, ())
                            for secondary_key in secondary_keys:
                                if secondary_key in TOLISS_ND_TEXT_KEYS or secondary_key in ECAM_TEXT_KEYS:
                                    self.secondary_values[secondary_key] = _toliss_decode_text(
                                        value, fixed_columns=secondary_key.startswith("ref_status_"))
                                else:
                                    self.secondary_values[secondary_key] = self._decode_numeric(value)
                        self.connected = True

            except Exception as exc:
                with self.lock:
                    self.connected = False
                    self.content_values.clear()
                    self.secondary_values.clear()
                    self.error = f"{type(exc).__name__}: {exc}"
                if not self.stop_evt.is_set():
                    self.stop_evt.wait(BB36_TOLISS_WS_RECONNECT_SECONDS)
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass

        with self.lock:
            self.connected = False


# Public name used by the BB35 and BB36 display owners.  The implementation
# remains one shared WebSocket/subscription regardless of how many LCDs view it.
TolissDisplayFeed = _TolissMcduFeed


class TolissBB36MirrorPath:
    """One persistent BB36 F0 session for the ToLiss MCDU: keys + optional mirror.

    Key dispatch (real AirbusFBW/MCDU1* commands) always runs. The CDU
    content mirror and PFD/engine secondary pages run only while
    ``mirror_enabled`` is set. Toggling it off stops this display's draw
    thread and shows one static page; a feed shared with BB35 remains owned
    by the bridge rather than being stopped underneath the other display.
    """

    def __init__(
        self,
        *,
        open_pfd: Callable[[], Tuple[Any, Any]],
        draw_worker: Callable[..., None],
        content_drawer: Callable[
            [Any, Any, Tuple[str, ...], Tuple[Tuple[int, ...], ...]], None
        ],
        api_root: str,
        api_version: str,
        refresh_interval: float,
        mirror_enabled: bool = True,
        diagnose: bool = False,
        feed: Optional[_TolissMcduFeed] = None,
        blackout: Optional[Callable[[Any, Any], None]] = None,
        show_static_when_mirror_off: bool = True,
    ) -> None:
        self.open_pfd = open_pfd
        self.draw_worker = draw_worker
        # Same F0 text renderer + brightness authority draw_worker uses for
        # the live "cdu" page; reused directly for the one-shot static pages
        # below (standby / keys-only) so there is exactly one place that
        # knows how to paint a 14-row grid onto this hardware and light it.
        self.content_drawer = content_drawer
        self.api_root = str(api_root).rstrip("/")
        self.api_version = str(api_version)
        self.refresh_interval = max(
            BB36_TOLISS_MIN_REFRESH_SECONDS, float(refresh_interval),
        )
        self.diagnose = diagnose

        self.device = None
        self.input_device = None
        self.canvas = None
        self.stop_evt = threading.Event()

        self.key_reader: Optional[threading.Thread] = None
        self.key_command_worker: Optional[threading.Thread] = None
        self.key_queue: "queue.Queue[Tuple[str, int]]" = queue.Queue()

        self.feed: Optional[_TolissMcduFeed] = feed
        self._owns_feed = feed is None
        self.blackout = blackout
        self.show_static_when_mirror_off = bool(show_static_when_mirror_off)
        self.mirror_thread: Optional[threading.Thread] = None
        self.mirror_stop_evt = threading.Event()
        self.mirror_lock = threading.Lock()
        self._mirror_enabled = bool(mirror_enabled)

        self.display_page_lock = threading.Lock()
        self.display_page = TOLISS_CDU_PAGE

        self.simulator_connected = threading.Event()
        self.simulator_connected.set()

        self.status: Dict[str, Any] = {
            "frames": 0, "error": None, "live": False, "connected": False,
            "mirror_enabled": self._mirror_enabled,
        }
        self.status_lock = threading.Lock()

    # -- gestures -----------------------------------------------------
    def get_display_page(self) -> str:
        with self.display_page_lock:
            return self.display_page

    def request_page(self, page: str) -> None:
        """Jump straight to one page - the external-trigger counterpart to
        the physical SLASH x2 cycle gesture. Used by the bridge to keep the
        BB36 screen in sync with a real cockpit control that already picks
        a specific ECAM page (the ECAM32 panel's own page-select buttons),
        so pressing e.g. BLEED on the physical ECAM panel also shows the
        BLEED synoptic here rather than requiring a separate manual cycle.
        A no-op for an unknown page name rather than an error, since this
        is called from a generic control-name lookup that may not always
        resolve to one of this router's own pages.
        """
        if page not in TOLISS_DISPLAY_PAGE_ORDER:
            return
        with self.display_page_lock:
            self.display_page = page

    def _cycle_display_page(self) -> None:
        with self.display_page_lock:
            current = self.display_page
            if current == TOLISS_CDU_PAGE:
                self.display_page = TOLISS_DISPLAY_PAGE_ORDER[0]
            else:
                try:
                    index = TOLISS_DISPLAY_PAGE_ORDER.index(current)
                except ValueError:
                    index = 0
                self.display_page = TOLISS_DISPLAY_PAGE_ORDER[
                    (index + 1) % len(TOLISS_DISPLAY_PAGE_ORDER)
                ]
            page = self.display_page
        print(f"BB36 TOLISS DISPLAY -> {page.upper()} (SLASH x2)")

    def _toggle_cdu_page(self) -> None:
        with self.display_page_lock:
            if self.display_page == TOLISS_CDU_PAGE:
                self.display_page = TOLISS_DISPLAY_PAGE_ORDER[0]
            else:
                self.display_page = TOLISS_CDU_PAGE
            page = self.display_page
        print(f"BB36 TOLISS SECRET: PERIOD x3 -> {page.upper()}")

    # -- mirror enable/disable -----------------------------------------
    def get_mirror_enabled(self) -> bool:
        with self.mirror_lock:
            return self._mirror_enabled

    def set_mirror_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        with self.mirror_lock:
            if enabled == self._mirror_enabled:
                return
            self._mirror_enabled = enabled
        with self.status_lock:
            self.status["mirror_enabled"] = enabled
        if enabled:
            self._start_mirror()
        else:
            self._stop_mirror()
            self._draw_mirror_off_state()

    def _draw_mirror_off_state(self) -> None:
        """Leave a safe production screen when live power authority is absent.

        Standalone/lab callers retain the historical keys-only page by
        default.  The production bridge opts out because a disabled mirror
        has no running telemetry worker to prove aircraft electrical power;
        in that case the only fail-closed output is a black LCD.
        """
        if self.show_static_when_mirror_off or self.blackout is None:
            self._draw_static_once(_keys_only_page())
            return
        if self.canvas is None or self.device is None:
            return
        try:
            self.blackout(self.device, self.canvas)
        except Exception as exc:
            if self.diagnose:
                print(f"BB36 TOLISS mirror-off blackout failed: {exc}")

    def _draw_static_once(self, page: Tuple[Tuple[str, ...], Tuple[Tuple[int, ...], ...]]) -> None:
        if self.canvas is None or self.device is None:
            return
        try:
            lines, colours = page
            self.content_drawer(self.device, self.canvas, lines, colours)
        except Exception as exc:
            if self.diagnose:
                print(f"BB36 TOLISS static page draw failed: {exc}")

    def _start_mirror(self) -> None:
        if self.canvas is None:
            return
        if self.feed is None:
            self.feed = _TolissMcduFeed(self.api_root, self.api_version)
            self._owns_feed = True
        self.feed.start()
        if self.mirror_thread is not None and self.mirror_thread.is_alive():
            return
        self.mirror_stop_evt.clear()
        self.mirror_thread = threading.Thread(
            target=self.draw_worker,
            args=(
                self.device, self.canvas, self.feed, self.refresh_interval,
                self.mirror_stop_evt, self.status, self.status_lock, self.get_display_page,
            ),
            name="BB36-TOLISS-MIRROR",
            daemon=True,
        )
        self.mirror_thread.start()

    def _stop_mirror(self) -> None:
        self.mirror_stop_evt.set()
        if self.feed is not None and self._owns_feed:
            self.feed.stop()
        thread = self.mirror_thread
        self.mirror_thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.5)

    # -- key dispatch (always live) --------------------------------------
    def _key_reader(self) -> None:
        """Read raw HID reports and queue every edge, unfiltered.

        Gesture counting (PERIOD x3 / SLASH x2) happens entirely in
        _key_command_worker, which is the one place that also knows whether
        a partial tap sequence needs to be replayed as normal keystrokes -
        see that method's docstring. Detecting gestures here too, as Boeing's
        BB36PFDPath does for its "not viewing FMC" case, would fire the
        toggle twice for one triple-tap.
        """
        reader = self.input_device or self.device
        if reader is None:
            return

        previous = None

        while not self.stop_evt.is_set():
            try:
                report = reader.read(128)
            except Exception:
                if self.stop_evt.is_set():
                    return
                # Only the dedicated handle is ever reopened here - never
                # self.device, matching BB36PFDPath's own "keypad faults are
                # recoverable input failures, not display failures" rule.
                if reader is self.input_device and self.input_device is not self.device:
                    try:
                        reader.close()
                    except Exception:
                        pass
                    self.stop_evt.wait(0.20)
                    try:
                        reader = _open_bb36()
                        self.input_device = reader
                        previous = None
                    except Exception:
                        reader = self.input_device or self.device
                else:
                    self.stop_evt.wait(0.20)
                continue

            if not report:
                self.stop_evt.wait(0.001)
                continue

            bits = _button_bits(bytes(report))
            if bits is None:
                continue
            if previous is None:
                previous = bits
                continue

            changed = previous ^ bits
            for index in range(96):
                mask = 1 << index
                if not changed & mask:
                    continue
                edge = "press" if bits & mask else "release"
                self.key_queue.put((edge, index))
            previous = bits

    def _key_command_worker(
        self,
        *,
        key_map: Mapping[int, Tuple[str, Optional[str]]] = TOLISS_MCDU_KEY_MAP,
        period_index: int = BB36_TOLISS_PERIOD_INDEX,
        slash_index: int = BB36_TOLISS_SLASH_INDEX,
        panel_name: str = "BB36",
        command_status: Optional[Callable[[bool, str], None]] = None,
        release_on_close: bool = False,
    ) -> None:
        """Drain the key queue and fire real MCDU1 commands. Always runs.

        Reuses _TriplePeriodDetector/_DoubleSlashDetector as the actual tap
        counters (same instances, same BB36_SECRET_GAP/BB36_DISPLAY_SLASH_GAP
        timing as the Zibo path), wrapped with deferred dispatch: a tap
        sequence that goes stale (gap expires) or is interrupted by another
        key replays as that many normal keystrokes instead of being silently
        dropped, so a single "." or "/" still reaches the aircraft - unlike
        the Zibo BB36 path, where a lone SLASH press is currently swallowed.
        """
        period_detector = _TriplePeriodDetector(self._toggle_cdu_page)
        slash_detector = _DoubleSlashDetector(self._cycle_display_page)
        detectors = {
            period_index: period_detector,
            slash_index: slash_detector,
        }
        gesture_gap = {
            period_index: BB36_SECRET_GAP,
            slash_index: BB36_DISPLAY_SLASH_GAP,
        }
        req_counter = [8000]
        active_commands = set()

        def send(ws: Any, payload: Dict[str, Any]) -> None:
            ws.send(json.dumps(payload, separators=(",", ":")))

        def next_req() -> int:
            req_counter[0] += 1
            return req_counter[0]

        def command_phase(ws: Any, command_id: int, active: bool) -> None:
            send(ws, {
                "req_id": next_req(),
                "type": "command_set_is_active",
                "params": {"commands": [{"id": int(command_id), "is_active": bool(active)}]},
            })
            if release_on_close:
                if active:
                    active_commands.add(command_id)
                else:
                    active_commands.discard(command_id)

        def flush_stale(ws: Any, commands: Dict[str, int], index: int) -> None:
            detector = detectors[index]
            count = detector.count
            if not count:
                return
            action = key_map[index][1]
            command_id = commands.get(action) if action else None
            if command_id is not None:
                for _ in range(count):
                    command_phase(ws, command_id, True)
                    command_phase(ws, command_id, False)
            detector.count = 0

        while not self.stop_evt.is_set():
            if websocket is None:
                if command_status is not None:
                    command_status(False, "websocket-client is unavailable")
                self.stop_evt.wait(1.0)
                continue
            if not self.simulator_connected.is_set():
                try:
                    while True:
                        self.key_queue.get_nowait()
                except queue.Empty:
                    pass
                self.stop_evt.wait(BB36_TOLISS_WS_RECONNECT_SECONDS)
                continue

            ws = None
            try:
                commands: Dict[str, int] = {}
                missing_commands = []
                for _label, action in key_map.values():
                    if not action or action in commands:
                        continue
                    try:
                        commands[action] = _resolve_command_id(
                            self.api_root, self.api_version, action,
                        )
                    except Exception:
                        missing_commands.append(action)

                ws = websocket.create_connection(
                    f"ws://127.0.0.1:8086/api/{self.api_version}",
                    timeout=1.0,
                    enable_multithread=True,
                )
                ws.settimeout(0.01)
                if command_status is not None:
                    command_status(True, (
                        "Missing ToLiss commands: " + ", ".join(missing_commands)
                        if missing_commands else ""
                    ))

                while not self.stop_evt.is_set() and self.simulator_connected.is_set():
                    now = time.monotonic()
                    for gesture_index, detector in detectors.items():
                        if detector.count and now - detector.last > gesture_gap[gesture_index]:
                            flush_stale(ws, commands, gesture_index)

                    processed = 0
                    while processed < 128:
                        try:
                            edge, index = self.key_queue.get_nowait()
                        except queue.Empty:
                            break
                        processed += 1
                        index = int(index)

                        if index in detectors:
                            if edge != "press":
                                continue
                            detector = detectors[index]
                            current = time.monotonic()
                            if detector.count and current - detector.last > gesture_gap[index]:
                                # Gap since the last tap expired before this
                                # one arrived: detector.press() is about to
                                # silently reset the count, so replay the
                                # stale taps as normal keystrokes first.
                                flush_stale(ws, commands, index)
                            detector.press()  # increments count; fires and
                            # resets to 0 at the trigger tap-count on its own
                            continue

                        # Any other key ends an in-progress PERIOD/SLASH tap
                        # sequence early, same as Boeing's behaviour.
                        if edge == "press":
                            for gesture_index in detectors:
                                flush_stale(ws, commands, gesture_index)

                        mapping = key_map.get(index)
                        if mapping is None:
                            continue
                        _label, action = mapping
                        if action is None:
                            continue
                        command_id = commands.get(action)
                        if command_id is None:
                            continue
                        command_phase(ws, command_id, edge == "press")
                        if edge == "press" and self.diagnose:
                            print(f"{panel_name} TOLISS key {index:02d} {_label} -> {action}")

                    try:
                        ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue

            except Exception as exc:
                if command_status is not None:
                    command_status(False, f"{type(exc).__name__}: {exc}")
                if self.diagnose and not self.stop_evt.is_set():
                    print(f"{panel_name} TOLISS key command reconnect: {exc}")
                self.stop_evt.wait(BB36_TOLISS_WS_RECONNECT_SECONDS)
            finally:
                if ws is not None:
                    if release_on_close:
                        for command_id in tuple(active_commands):
                            try:
                                command_phase(ws, command_id, False)
                            except Exception:
                                break
                        active_commands.clear()
                    try:
                        ws.close()
                    except Exception:
                        pass

    # -- lifecycle --------------------------------------------------------
    def set_simulator_connected(self, connected: bool) -> None:
        if connected:
            self.simulator_connected.set()
        else:
            self.simulator_connected.clear()

    def start(self) -> None:
        self.stop_evt.clear()
        self.device, self.canvas = self.open_pfd()

        try:
            self.input_device = _open_bb36()
        except Exception as exc:
            self.input_device = self.device
            print(
                "WARNING: BB36 ToLiss dedicated keypad handle unavailable; "
                f"using shared fallback: {type(exc).__name__}: {exc}"
            )

        self.key_reader = threading.Thread(
            target=self._key_reader, name="BB36-TOLISS-KEYS", daemon=True,
        )
        self.key_command_worker = threading.Thread(
            target=self._key_command_worker, name="BB36-TOLISS-KEY-CMDS", daemon=True,
        )
        self.key_reader.start()
        self.key_command_worker.start()

        if self._mirror_enabled:
            self._start_mirror()
        else:
            self._draw_mirror_off_state()

        print(
            "BB36 TOLISS MCDU armed: keys always live; "
            f"mirror {'ON' if self._mirror_enabled else 'OFF'}; "
            "PERIOD x3 toggles CDU/PFD, SLASH x2 cycles PFD/ENG."
        )

    def stop(self, *, final: bool = False) -> None:
        self.stop_evt.set()
        self._stop_mirror()

        if self.key_reader is not None:
            self.key_reader.join(timeout=1.0)
        if self.key_command_worker is not None:
            self.key_command_worker.join(timeout=1.25)

        if self.input_device is not None and self.input_device is not self.device:
            try:
                self.input_device.close()
            except Exception:
                pass

        if self.device is not None and self.canvas is not None and self.blackout is not None:
            try:
                self.blackout(self.device, self.canvas)
            except Exception:
                pass

        if self.device is not None:
            try:
                self.device.close()
            except Exception:
                pass

        self.device = None
        self.input_device = None
        self.canvas = None
        self.key_reader = None
        self.key_command_worker = None

    def service_snapshot(self) -> Dict[str, Any]:
        with self.status_lock:
            status = dict(self.status)
        status["page"] = self.get_display_page()
        status["state"] = "running" if self.device is not None else "waiting"
        return status


BB35_TOLISS_PERIOD_INDEX = 38
BB35_TOLISS_SLASH_INDEX = 69
# Captured PFP3N positions, not BB36 positions: digits start at 29, letters
# at 41, and the last row is SPACE/DEL/SLASH/CLR. All targets are existing
# ToLiss MCDU1 commands. Boeing-only legends receive the documented Airbus
# page shortcuts below; EXEC opens DIR TO, never simulates an Airbus INSERT.
TOLISS_BB35_KEY_MAP: Dict[int, Tuple[str, Optional[str]]] = {
    **{index: TOLISS_MCDU_KEY_MAP[index] for index in range(12)},
    12: ("INIT REF -> INIT", "AirbusFBW/MCDU1Init"),
    13: ("RTE -> F-PLN", "AirbusFBW/MCDU1Fpln"),
    14: ("CLB -> PERF", "AirbusFBW/MCDU1Perf"),
    15: ("CRZ -> FUEL PRED", "AirbusFBW/MCDU1FuelPred"),
    16: ("DES -> PROG", "AirbusFBW/MCDU1Prog"),
    17: ("BRT -", "AirbusFBW/MCDU1KeyDim"),
    18: ("BRT +", "AirbusFBW/MCDU1KeyBright"),
    19: ("MENU", "AirbusFBW/MCDU1Menu"),
    20: ("LEGS -> F-PLN", "AirbusFBW/MCDU1Fpln"),
    21: ("DEP/ARR -> AIRPORT", "AirbusFBW/MCDU1Airport"),
    22: ("HOLD -> SEC F-PLN", "AirbusFBW/MCDU1SecFpln"),
    23: ("PROG", "AirbusFBW/MCDU1Prog"),
    24: ("EXEC -> DIR TO", "AirbusFBW/MCDU1DirTo"),
    25: ("N1 LIMIT -> DATA", "AirbusFBW/MCDU1Data"),
    26: ("FIX -> RAD NAV", "AirbusFBW/MCDU1RadNav"),
    27: ("PREV PAGE", "AirbusFBW/MCDU1SlewLeft"),
    28: ("NEXT PAGE", "AirbusFBW/MCDU1SlewRight"),
    **{index: TOLISS_MCDU_KEY_MAP[index + 3] for index in range(29, 67)},
    67: ("SPACE", "AirbusFBW/MCDU1KeySpace"),
    68: ("DEL -> OVERFLY", "AirbusFBW/MCDU1KeyOverfly"),
    69: ("/", "AirbusFBW/MCDU1KeySlash"),
    70: ("CLR", "AirbusFBW/MCDU1KeyClear"),
}
TOLISS_BB35_DISPLAY_PAGE_ORDER = (
    TOLISS_CDU_PAGE,
    *TOLISS_DISPLAY_PAGE_ORDER,
)


class TolissBB35DisplayPath:
    """Persistent ToLiss coded-display and optional MCDU keypad owner for BB35.

    BB35 shares the one ToLiss feed with BB36, but owns its own HID handle,
    canvas, differential history and draw thread. Its own captured keypad can
    control the mirrored captain MCDU without a connected BB36. A double press
    of the physical BB35 slash key cycles CDU, PFD,
    ND and the complete authored ECAM deck without importing any Boeing route
    or command map.
    """

    def __init__(
        self,
        *,
        open_pfd: Callable[[], Tuple[Any, Any]],
        draw_worker: Callable[..., None],
        blackout: Callable[[Any, Any], None],
        feed: _TolissMcduFeed,
        refresh_interval: float,
        diagnose: bool = False,
        api_root: Optional[str] = None,
        api_version: str = "v2",
        input_sink: Optional[Callable[[int, str], None]] = None,
    ) -> None:
        self.open_pfd = open_pfd
        self.draw_worker = draw_worker
        self.blackout = blackout
        self.feed = feed
        self.refresh_interval = max(
            BB36_TOLISS_MIN_REFRESH_SECONDS, float(refresh_interval),
        )
        self.diagnose = bool(diagnose)
        self.api_root = str(api_root or "").rstrip("/")
        self.api_version = str(api_version)
        self.input_sink = input_sink
        self.key_queue: "queue.Queue[Tuple[str, int]]" = queue.Queue()
        self.key_command_thread: Optional[threading.Thread] = None
        self.simulator_connected = threading.Event()
        self.simulator_connected.set()
        self.device = None
        self.canvas = None
        self.stop_evt = threading.Event()
        self.reader_thread: Optional[threading.Thread] = None
        self.output_thread: Optional[threading.Thread] = None
        self.display_page_lock = threading.Lock()
        self.display_page = TOLISS_BB35_DISPLAY_PAGE_ORDER[0]
        self.status: Dict[str, Any] = {
            "frames": 0, "error": None, "live": False, "connected": False,
        }
        self.status_lock = threading.Lock()

    def get_display_page(self) -> str:
        with self.display_page_lock:
            return self.display_page

    def request_page(self, page: str) -> None:
        """Select a known page directly from an external ECAM page button."""
        if page not in TOLISS_BB35_DISPLAY_PAGE_ORDER:
            return
        with self.display_page_lock:
            self.display_page = page

    def _cycle_display_page(self) -> None:
        with self.display_page_lock:
            current = self.display_page
            try:
                index = TOLISS_BB35_DISPLAY_PAGE_ORDER.index(current)
            except ValueError:
                index = 0
            self.display_page = TOLISS_BB35_DISPLAY_PAGE_ORDER[
                (index + 1) % len(TOLISS_BB35_DISPLAY_PAGE_ORDER)
            ]
            page = self.display_page
        print(f"BB35 TOLISS DISPLAY -> {page.upper()} (SLASH x2)")

    def _reader(self) -> None:
        previous: Optional[int] = None
        pressed_here = 0
        slash = _DoubleSlashDetector(self._cycle_display_page)
        while not self.stop_evt.is_set():
            try:
                report = self.device.read(128) if self.device is not None else []
            except Exception as exc:
                with self.status_lock:
                    self.status["error"] = f"{type(exc).__name__}: {exc}"
                self.stop_evt.wait(0.20)
                continue
            if not report:
                self.stop_evt.wait(0.002)
                continue
            bits = _button_bits(bytes(report))
            if bits is None:
                continue
            if previous is None:
                previous = bits
                continue
            changed = previous ^ bits
            while changed:
                mask = changed & -changed
                changed ^= mask
                index = mask.bit_length() - 1
                if index not in TOLISS_BB35_KEY_MAP:
                    continue
                edge = "press" if bits & mask else "release"
                if self.input_sink is not None:
                    try:
                        self.input_sink(index, edge)
                    except Exception as exc:
                        with self.status_lock:
                            self.status["input_error"] = str(exc)
                if self.api_root:
                    if edge == "press":
                        pressed_here |= mask
                        self.key_queue.put((edge, index))
                    elif pressed_here & mask:
                        pressed_here &= ~mask
                        self.key_queue.put((edge, index))
                elif index == BB35_TOLISS_SLASH_INDEX and edge == "press":
                    # Preserve the standalone display-only caller contract.
                    slash.press()
            previous = bits

    def _toggle_cdu_page(self) -> None:
        with self.display_page_lock:
            self.display_page = (
                "pfd" if self.display_page == TOLISS_CDU_PAGE else TOLISS_CDU_PAGE
            )
        print(f"BB35 TOLISS SECRET: PERIOD x3 -> {self.get_display_page().upper()}")

    def _key_command_worker(self) -> None:
        # Reuse the established command/gesture loop, with BB35's captured
        # positions and this panel's own queue, stop event and page callbacks.
        TolissBB36MirrorPath._key_command_worker(
            self, key_map=TOLISS_BB35_KEY_MAP,
            period_index=BB35_TOLISS_PERIOD_INDEX,
            slash_index=BB35_TOLISS_SLASH_INDEX, panel_name="BB35",
            command_status=self._set_keypad_status, release_on_close=True,
        )

    def _set_keypad_status(self, connected: bool, error: str) -> None:
        with self.status_lock:
            self.status["keypad_connected"] = bool(connected)
            self.status["keypad_error"] = str(error) or None

    def start(self) -> None:
        self.stop_evt.clear()
        # A restarted owner must never replay keystrokes from its old session.
        while not self.key_queue.empty():
            try:
                self.key_queue.get_nowait()
            except queue.Empty:
                break
        self.feed.start()
        self.device, self.canvas = self.open_pfd()
        self.reader_thread = threading.Thread(
            target=self._reader, name="BB35-TOLISS-KEYS", daemon=True,
        )
        self.output_thread = threading.Thread(
            target=self.draw_worker,
            args=(
                self.device, self.canvas, self.feed, self.refresh_interval,
                self.stop_evt, self.status, self.status_lock,
                self.get_display_page,
            ),
            name="BB35-TOLISS-DISPLAY",
            daemon=True,
        )
        self.reader_thread.start()
        if self.api_root:
            self.key_command_thread = threading.Thread(
                target=self._key_command_worker,
                name="BB35-TOLISS-KEY-CMDS", daemon=True,
            )
            self.key_command_thread.start()
        self.output_thread.start()
        print(
            "BB35 TOLISS display armed: CDU/PFD/ND/ECAM, "
            f"keypad {'ON' if self.api_root else 'display-only'}; "
            "SLASH x2 changes page, PERIOD x3 toggles CDU/PFD."
        )

    def stop(self, *, final: bool = False) -> None:
        self.stop_evt.set()
        if self.reader_thread is not None:
            self.reader_thread.join(timeout=1.0)
        if self.key_command_thread is not None:
            self.key_command_thread.join(timeout=1.25)
        if self.output_thread is not None:
            self.output_thread.join(timeout=1.5)
        if self.device is not None and self.canvas is not None:
            try:
                self.blackout(self.device, self.canvas)
            except Exception:
                pass
        if self.device is not None:
            try:
                self.device.close()
            except Exception:
                pass
        self.device = None
        self.canvas = None
        self.reader_thread = None
        self.key_command_thread = None
        self.output_thread = None
        self._set_keypad_status(False, "")

    def service_snapshot(self) -> Dict[str, Any]:
        with self.status_lock:
            result = dict(self.status)
        result["page"] = self.get_display_page()
        result["state"] = "running" if self.device is not None else "waiting"
        return result
