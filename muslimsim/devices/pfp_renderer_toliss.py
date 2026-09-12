"""Code-native 640x480 ToLiss A320 Primary Flight Display (PFD).

Sibling to muslimsim/devices/pfp_renderer.py (Boeing 737 PFD), not a reskin
of it: fresh Airbus-native geometry (speed tape with V1/VR/V2, S/F/green-dot,
VLS/VMAX/VFE-next and alpha-protection indications, altitude tape with a QNH/STD window, an
attitude sphere with a fixed aircraft reference, FD single-cue cross-pointer,
flight-path-vector, bank-angle scale, a linear heading/track strip, LOC/G-S
raw-deviation scales, and an FMA-equivalent annunciation row) driven by real
`toliss_airbus/pfdoutputs/*` and captain-side `AirbusFBW/*` datarefs
(xplane_command_catalog.json, aircraft=="toliss"), including native
`AirbusFBW/HDGCapt` and its validity flag. Every value key this
module reads via `values.get(...)` is a flat, already-resolved name built
upstream by `_toliss_pfd_values()` in bridge/final.py from the raw feed in
mcdu_bb36_toliss_paths.py's `TOLISS_MCDU_SECONDARY_DATAREFS["pfd"]` - this
module never talks to a dataref name directly.

Shares the PFD/ND/systems final-image differential contract (imported, not
reimplemented) with pfp_renderer.py: a complete frame is recorded in memory,
only the pixel regions that actually changed are emitted, and a recovery
frame repairs page entry/reconnect. Only the generic diff engine and
rasterisation primitives (`_merge_rows`/`_emit_rows`/`_straight_line_rects`/
`_solid_angled_line_rects`/`_filled_triangle_rows`/`_OpRecorder`/
`_dirty_boxes`/`_emit_frame`/`Rect`/`TextSlot`) are imported from
pfp_renderer.py, exactly as systems_renderer_toliss.py already does for the
ECAM pages - no Boeing widget geometry, colour choice, or label is reused.
The PFD uses the proven slot-3 packed micro typography shared by the coded
Zibo PFD/ND.  Only the generic glyph packing is shared: every Airbus label,
colour, position and instrument shape remains authored in this module.  The
fixed 17px firmware cells therefore retain safe opaque backgrounds while the
visible glyphs advance at their measured ink widths.

Every judgment call (roll-sign convention, V-speed band boundaries, FMA
thrust-mode enum labels, the baro-value proxy source, ILS raw-needle scale,
selected-heading source) is flagged in-code for live-session confirmation -
same "prove, don't guess" discipline as every other first-pass ToLiss
renderer in this project.
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
    FULL_REPAINT_SECONDS,
    GREEN,
    HEIGHT,
    MAGENTA,
    PFD_NUMBER_FONT_ID,
    RED,
    WHITE,
    WIDTH,
    Rect,
    TextSlot,
    _clamp,
    _dirty_boxes,
    _emit_frame,
    _emit_rows,
    _filled_triangle_rows,
    _finite,
    _OpRecorder,
    _packed_number_cells,
    _slot,
    _solid_angled_line_rects,
    _straight_line_rects,
)

# Slot 4 is the established 10 x 15 ink face carried by the same immutable
# BB35/BB36 font resource.  Airbus uses visibly smaller rolling tens/units in
# the altitude drum; using that existing native face keeps the distinction
# crisp without adding a bitmap or another font upload.
PFD_TINY_FONT_ID = 4
PFD_ALTITUDE_LARGE_FONT_ID = 6

try:  # Reserved code-native slot-3 glyph; rectangle fallback stays valid.
    from muslimsim.devices import pfp_right_strip_tiles as _PFD_SHAPE_GLYPHS
except Exception:  # pragma: no cover - an older font resource can still render
    _PFD_SHAPE_GLYPHS = None

# ---------------------------------------------------------------------------
# Palette - a fresh set of tones for this renderer (not imported from Boeing's
# SKY/EARTH constants), kept close to real EFIS colours.
# ---------------------------------------------------------------------------
TOLISS_SKY = (18, 188, 210)
TOLISS_EARTH = (156, 88, 18)
TAPE_GREY = (82, 94, 118)
DIM_GREY = (100, 106, 118)
PANEL_LINE = (58, 63, 74)
FMA_BG = (20, 21, 26)
ECAM_BLUE = CYAN                # see mcdu_bb36_toliss_paths.py's own "b" ->
                                 # COLOR_CYAN precedent for Airbus-blue-as-cyan

# Same physical bezel-masked strip as systems_renderer_toliss.py's
# TOLISS_SAFE_LEFT/RIGHT - same hardware (this is the BB36 F0 mirror canvas,
# not the dedicated PFP unit), duplicated here rather than imported so this
# file stays decoupled from its ECAM sibling.
X_SAFE_LEFT = 34
X_SAFE_RIGHT = 606

TOLISS_PFD_FULL_REPAINT_FRAMES = 600

# ---------------------------------------------------------------------------
# Layout traced from the ToLiss manual/tutorial PFD and the owner's supplied
# valid/invalid crops, then fitted into the BB35/BB36 640x480 bezel-safe strip.
# The real display has a three-row FMA, narrow side tapes, a rounded attitude
# field, a separate G/S strip, a slim tapered V/S scale and the heading strip
# low in the centre.  These proportions are a contract, not a generic glass-
# cockpit approximation.
# ---------------------------------------------------------------------------
FMA_Y = 0
FMA_HEIGHT = 87
FMA_TEXT_X = 48
FMA_TEXT_COLUMNS = 32
FMA_ROW_Y = (0, 29, 58)
TARGET_ROW_Y = 87
MAIN_TOP = 116
MAIN_BOTTOM = 374
LOC_STRIP_TOP = MAIN_BOTTOM
HEADING_TOP = 416
HEADING_BOTTOM = 455
BOTTOM_ROW1_Y = 382
BOTTOM_ROW2_Y = 411
BOTTOM_ROW3_Y = 450

SPEED_TAPE = Rect(62, MAIN_TOP, 56, MAIN_BOTTOM - MAIN_TOP)
ATTITUDE = Rect(145, MAIN_TOP, 282, MAIN_BOTTOM - MAIN_TOP)
LOC_STRIP = Rect(ATTITUDE.x, LOC_STRIP_TOP, ATTITUDE.width, HEADING_TOP - 6 - LOC_STRIP_TOP)
GS_STRIP = Rect(430, MAIN_TOP, 12, MAIN_BOTTOM - MAIN_TOP)
ALTITUDE_TAPE = Rect(446, MAIN_TOP, 56, MAIN_BOTTOM - MAIN_TOP)
VS_WEDGE = Rect(552, MAIN_TOP, 28, MAIN_BOTTOM - MAIN_TOP)
HEADING_TAPE = Rect(ATTITUDE.x, HEADING_TOP, ATTITUDE.width, HEADING_BOTTOM - HEADING_TOP)

ATT_CENTER_X = ATTITUDE.x + ATTITUDE.width // 2
ATT_CENTER_Y = ATTITUDE.y + ATTITUDE.height // 2
TAPE_CENTER_Y = ATT_CENTER_Y

SPEED_WINDOW = Rect(SPEED_TAPE.x, TAPE_CENTER_Y - 18, SPEED_TAPE.width, 36)
ALTITUDE_WINDOW = Rect(ALTITUDE_TAPE.x + 1, TAPE_CENTER_Y - 12, 53, 26)

SPEED_PX_PER_KT = 4.0
SPEED_TICK_STEP = 10.0
SPEED_LABEL_STEP = 20.0
SPEED_BAND_X = SPEED_TAPE.right - 9
SPEED_BAND_WIDTH = 7
SPEED_BUG_X = SPEED_TAPE.right - 10

ALT_PX_PER_FT = 0.23
ALT_TICK_STEP = 100.0
ALT_LABEL_STEP = 500.0
ALT_SCALE_X = ALTITUDE_TAPE.right - 2
ALT_DRUM_STEP_FT = 20.0
ALT_DRUM_PITCH = 23
ALT_DRUM_BOX = Rect(ALT_SCALE_X, TAPE_CENTER_Y - 21, 30, 44)
ALT_FIXED_X = ALTITUDE_TAPE.x + 2
ALT_DRUM_X = ALT_DRUM_BOX.x + 2
ALT_DRUM_WIDTH = 27

PITCH_PX_PER_DEG = 4.0
BANK_SCALE_RADIUS = 113.0

HEADING_PX_PER_DEG = 4.4
HEADING_TICK_STEP = 10.0

# ---------------------------------------------------------------------------
# Fixed text zones (module constants so the self-test can assert none of them
# ever overlap - see assert_layout_contract).
# ---------------------------------------------------------------------------
# Unequal column widths, not five equal fifths: THR and A/THR carry the
# longest real labels ("MAN TOGA", "THR IDLE", "A.FLOOR" - up to 8
# characters = 136px), while LAT/VERT only ever show the fixed "-----"
# placeholder and AP only ever shows "AP"/"AP1" - budget accordingly so no
# label silently fails TextSlot.position_for's capacity check and gets
# dropped (that failure mode is a *silent* skip, not an exception - see
# _draw_text_with_font in pfp_renderer.py - which is exactly what happened
# here on the first pass: caught by rendering a debug canvas, not by
# assert_layout_contract's bounds/overlap checks alone).
FMA_THR = _slot("fma thrust mode", X_SAFE_LEFT, FMA_Y, 150, "center")
FMA_LAT = _slot("fma lateral", FMA_THR.rect.right, FMA_Y, 90, "center")
FMA_VERT = _slot("fma vertical", FMA_LAT.rect.right, FMA_Y, 90, "center")
FMA_AP = _slot("fma ap fd", FMA_VERT.rect.right, FMA_Y, 90, "center")
FMA_ATHR = _slot("fma athr", FMA_AP.rect.right, FMA_Y, X_SAFE_RIGHT - FMA_AP.rect.right, "center")

SELECTED_SPEED = _slot("selected speed", SPEED_TAPE.x, TARGET_ROW_Y, SPEED_TAPE.width, "center")
SELECTED_ALTITUDE = _slot("selected altitude", ALTITUDE_TAPE.x, TARGET_ROW_Y, ALTITUDE_TAPE.width, "center")

IAS_TEXT = _slot("live ias", SPEED_WINDOW.x, TAPE_CENTER_Y - 14, SPEED_WINDOW.width, "center")
ALT_TEXT = _slot("live altitude", ALTITUDE_WINDOW.x, TAPE_CENTER_Y - 14, ALTITUDE_WINDOW.width, "center")

# Widths chosen from the actual longest formatted string each slot can carry
# (verified by assert_layout_contract's exhaustive-format check below), not
# guessed round numbers - "1013.00HPA" (10 chars) for BARO_TEXT, "M.620
# P.780" (11 chars) for the combined MACH_TEXT, "ILS 109.50  DME12.4" (19
# chars) for ILS_TEXT. The first pass of this file budgeted these too
# narrowly and TextSlot.position_for silently dropped the overflowing text
# (see _CaptureCanvas's docstring) - now sized with margin instead.
LEFT_INFO_WIDTH = ATTITUDE.x - X_SAFE_LEFT - 6
RIGHT_INFO_X = ALT_DRUM_BOX.right - 10 * FONT_CELL_WIDTH
RIGHT_INFO_WIDTH = ALT_DRUM_BOX.right - RIGHT_INFO_X
MACH_TEXT = _slot("mach", SPEED_TAPE.right - 5 * FONT_CELL_WIDTH, BOTTOM_ROW1_Y,
                  5 * FONT_CELL_WIDTH, "right")
PRESEL_MACH_TEXT = _slot("cruise mach preselect",
                         SPEED_TAPE.right - 5 * FONT_CELL_WIDTH, BOTTOM_ROW2_Y,
                         5 * FONT_CELL_WIDTH, "right")
ILS_TEXT = _slot("ils frequency", X_SAFE_LEFT, BOTTOM_ROW3_Y, LEFT_INFO_WIDTH, "left")
BARO_TEXT = _slot("baro value unit", RIGHT_INFO_X, BOTTOM_ROW1_Y, RIGHT_INFO_WIDTH, "right")
LANDING_ELEV_TEXT = _slot("landing elevation", RIGHT_INFO_X, BOTTOM_ROW2_Y, RIGHT_INFO_WIDTH, "right")
DME_TEXT = _slot("ils dme", RIGHT_INFO_X, BOTTOM_ROW3_Y, RIGHT_INFO_WIDTH, "right")

# Every declared fixed slot, for the self-test's pairwise overlap sweep. Two
# slots that legitimately sit on the same row at different columns (e.g. the
# five FMA columns) are still checked - they must not overlap each other
# either, which is exactly what the FMA_COL_WIDTH arithmetic above exists to
# guarantee.
_ALL_TEXT_SLOTS: Tuple[TextSlot, ...] = (
    FMA_THR, FMA_LAT, FMA_VERT, FMA_AP, FMA_ATHR,
    SELECTED_SPEED, SELECTED_ALTITUDE, IAS_TEXT, ALT_TEXT,
    BARO_TEXT, LANDING_ELEV_TEXT, DME_TEXT,
    MACH_TEXT, PRESEL_MACH_TEXT, ILS_TEXT,
)


class TolissPfdLayoutError(RuntimeError):
    """A ToLiss PFD primitive left the physical LCD or collided with another."""


def _text(
    canvas: Any,
    slot: TextSlot,
    value: str,
    colour: Tuple[int, int, int] = WHITE,
    background: Tuple[int, int, int] = BLACK,
) -> None:
    text = str(value)
    if not text:
        return
    cells = _packed_number_cells(slot, text)
    if cells is None:
        return
    logical = getattr(canvas, "_record_logical_text", None)
    if callable(logical):
        logical(text)
    for x, character in cells:
        canvas.text(
            x, slot.rect.y, character, colour, background,
            PFD_NUMBER_FONT_ID,
        )


def _fmt(value: Any, decimals: int = 0, fallback: str = "---") -> str:
    if not _finite(value):
        return fallback
    if decimals <= 0:
        return str(int(round(float(value))))
    return f"{float(value):.{decimals}f}"


def _bool(value: Any) -> bool:
    return _finite(value) and float(value) >= 0.5


def _source_valid(
    values: Mapping[str, Any], validity_key: str, *fallback_keys: str,
) -> bool:
    """Prefer ToLiss's explicit source-valid flag, with an old-feed fallback.

    Older cached/offline snapshots predate the validity datarefs.  They remain
    useful when all required source values are finite; a live explicit zero is
    always authoritative and produces the Airbus red failure presentation.
    """
    flag = values.get(validity_key)
    if _finite(flag):
        return _bool(flag)
    return bool(fallback_keys) and all(_finite(values.get(key)) for key in fallback_keys)


def _line(canvas: Any, x0: float, y0: float, x1: float, y1: float,
          colour: Tuple[int, int, int], thickness: int = 2) -> None:
    canvas.colour(*colour)
    for x, y, w, h in _solid_angled_line_rects(x0, y0, x1, y1, thickness):
        canvas.fill(x, y, w, h)


def _outline(canvas: Any, rect: Rect, colour: Tuple[int, int, int], thickness: int = 2) -> None:
    canvas.colour(*colour)
    canvas.fill(rect.x, rect.y, rect.width, thickness)
    canvas.fill(rect.x, rect.bottom - thickness, rect.width, thickness)
    canvas.fill(rect.x, rect.y, thickness, rect.height)
    canvas.fill(rect.right - thickness, rect.y, thickness, rect.height)


def _feature(canvas: Any, value: str) -> None:
    record = getattr(canvas, "_record_feature", None)
    if callable(record):
        record(value)


def _attitude_row_span(y: int) -> Tuple[int, int]:
    """Stepped rounded Airbus attitude aperture for one LCD row."""
    edge = min(y - ATTITUDE.y, ATTITUDE.bottom - 1 - y)
    if edge < 4:
        inset = 32
    elif edge < 9:
        inset = 24
    elif edge < 15:
        inset = 16
    elif edge < 23:
        inset = 8
    elif edge < 31:
        inset = 3
    else:
        inset = 0
    return ATTITUDE.x + inset, ATTITUDE.right - inset


def _fill_attitude_shape(canvas: Any, colour: Tuple[int, int, int]) -> None:
    rows = []
    for y in range(ATTITUDE.y, ATTITUDE.bottom):
        left, right = _attitude_row_span(y)
        rows.append((left, y, right - left))
    _emit_rows(canvas, colour, rows)


def _vs_row_span(y: int) -> Tuple[int, int]:
    edge = min(y - VS_WEDGE.y, VS_WEDGE.bottom - 1 - y)
    if edge < 8:
        inset = 8
    elif edge < 16:
        inset = 5
    elif edge < 26:
        inset = 2
    else:
        inset = 0
    return VS_WEDGE.x + inset, VS_WEDGE.right - max(0, inset // 2)


def _fill_vs_shape(canvas: Any, colour: Tuple[int, int, int]) -> None:
    rows = []
    for y in range(VS_WEDGE.y, VS_WEDGE.bottom):
        left, right = _vs_row_span(y)
        rows.append((left, y, right - left))
    _emit_rows(canvas, colour, rows)


def _draw_invalid_speed(canvas: Any) -> None:
    canvas.colour(*TAPE_GREY)
    canvas.fill(SPEED_TAPE.x, SPEED_TAPE.y, SPEED_TAPE.width, SPEED_TAPE.height)
    canvas.colour(*RED)
    canvas.fill(SPEED_TAPE.right - 3, SPEED_TAPE.y, 3, SPEED_TAPE.height)
    canvas.fill(SPEED_TAPE.x - 5, SPEED_TAPE.y, SPEED_TAPE.width + 10, 3)
    canvas.fill(SPEED_TAPE.x - 5, SPEED_TAPE.bottom - 3, SPEED_TAPE.width + 10, 3)
    _text(canvas, _slot("invalid SPD", SPEED_TAPE.x + 4, TAPE_CENTER_Y - 14,
                        SPEED_TAPE.width - 8, "center"), "SPD", RED, TAPE_GREY)
    _feature(canvas, "INVALID_SPEED_SHAPE")


def _draw_invalid_attitude(canvas: Any) -> None:
    _fill_attitude_shape(canvas, (2, 8, 15))
    _text(canvas, _slot("invalid ATT", ATT_CENTER_X - 42, TAPE_CENTER_Y - 14,
                        84, "center"), "ATT", RED, (2, 8, 15))
    _feature(canvas, "INVALID_ATTITUDE_SHAPE")


def _draw_invalid_altitude(canvas: Any) -> None:
    gap_top = TAPE_CENTER_Y - 18
    gap_bottom = TAPE_CENTER_Y + 18
    canvas.colour(*TAPE_GREY)
    canvas.fill(ALTITUDE_TAPE.x, ALTITUDE_TAPE.y, ALTITUDE_TAPE.width,
                gap_top - ALTITUDE_TAPE.y)
    canvas.fill(ALTITUDE_TAPE.x, gap_bottom, ALTITUDE_TAPE.width,
                ALTITUDE_TAPE.bottom - gap_bottom)
    canvas.colour(*RED)
    canvas.fill(ALTITUDE_TAPE.x, ALTITUDE_TAPE.y, ALTITUDE_TAPE.width + 3, 3)
    canvas.fill(ALTITUDE_TAPE.x, ALTITUDE_TAPE.bottom - 3, ALTITUDE_TAPE.width + 3, 3)
    canvas.fill(ALTITUDE_TAPE.right - 3, ALTITUDE_TAPE.y, 3, gap_top - ALTITUDE_TAPE.y)
    canvas.fill(ALTITUDE_TAPE.right - 3, gap_bottom, 3, ALTITUDE_TAPE.bottom - gap_bottom)
    _text(canvas, _slot("invalid ALT", ALTITUDE_TAPE.x - 2, TAPE_CENTER_Y - 14,
                        ALTITUDE_TAPE.width + 4, "center"), "ALT", RED, BLACK)
    _feature(canvas, "INVALID_ALTITUDE_SPLIT_SHAPE")


def _draw_invalid_vs(canvas: Any) -> None:
    _fill_vs_shape(canvas, TAPE_GREY)
    logical = getattr(canvas, "_record_logical_text", None)
    if callable(logical):
        logical("V/S")
    x = VS_WEDGE.x + (VS_WEDGE.width - FONT_CELL_WIDTH) // 2
    for y, character in zip((TAPE_CENTER_Y - 43, TAPE_CENTER_Y - 14, TAPE_CENTER_Y + 15), "V/S"):
        _text(canvas, _slot(f"invalid VS {character}", x, y, FONT_CELL_WIDTH, "center"),
              character, RED, TAPE_GREY)
    _feature(canvas, "INVALID_VS_TAPERED_SHAPE")


def _draw_invalid_heading(canvas: Any) -> None:
    canvas.colour(*TAPE_GREY)
    canvas.fill(HEADING_TAPE.x, HEADING_TAPE.y, HEADING_TAPE.width, HEADING_TAPE.height)
    canvas.colour(*RED)
    canvas.fill(HEADING_TAPE.x, HEADING_TAPE.y, HEADING_TAPE.width, 3)
    canvas.fill(HEADING_TAPE.x, HEADING_TAPE.y, 3, HEADING_TAPE.height)
    canvas.fill(HEADING_TAPE.right - 3, HEADING_TAPE.y, 3, HEADING_TAPE.height)
    _text(canvas, _slot("invalid HDG", ATT_CENTER_X - 42, HEADING_TAPE.y + 4,
                        84, "center"), "HDG", RED, TAPE_GREY)
    _feature(canvas, "INVALID_HEADING_SHAPE")


# ---------------------------------------------------------------------------
# FMA row - engagement/thrust-mode annunciation from the real ToLiss engage-
# boxed flags plus a guessed thrust-mode enum table (flagged, same precedent
# as pfp_renderer.py's own FMA_SPEED_LABELS/FMA_LATERAL_LABELS guess tables).
# LAT/VERT columns are intentionally left as real "no data" placeholders: no
# lateral or vertical guidance-mode dataref is catalogued for ToLiss (only
# the thrust-mode enum and AP/FD/A-THR engage-boxed booleans are), so they
# show a dash rather than fabricated mode text - same discipline as the
# STATUS ECAM page in systems_renderer_toliss.py.
# ---------------------------------------------------------------------------
_ATHR_MODE_LABELS = {
    0: "",
    1: "MAN TOGA",
    2: "MAN FLX",
    3: "MAN MCT",
    4: "MAN CLB",
    5: "THR CLB",
    6: "THR IDLE",
    7: "THR LVR",
    8: "SPEED",
    9: "MACH",
    10: "A.FLOOR",
    11: "TOGA LK",
}


def _athr_mode_text(value: Any) -> str:
    if not _finite(value):
        return "---"
    mode = int(round(float(value)))
    return _ATHR_MODE_LABELS.get(mode, f"MODE {mode}")


def _draw_fma(canvas: Any, values: Mapping[str, Any], *, annunciations_valid: bool = True) -> None:
    canvas.colour(*FMA_BG)
    canvas.fill(0, 0, WIDTH, FMA_HEIGHT)
    rows = (
        (("fma1_green", GREEN), ("fma1_blue", CYAN), ("fma1_white", WHITE)),
        (("fma2_blue", CYAN), ("fma2_magenta", MAGENTA), ("fma2_white", WHITE)),
        (("fma3_amber", AMBER), ("fma3_blue", CYAN), ("fma3_white", WHITE)),
    )
    native = annunciations_valid and any(
        values.get(key) is not None for row in rows for key, _colour in row
    )

    if native:
        for y, row in zip(FMA_ROW_Y, rows):
            layers = [
                (str(values.get(key) or "")[:FMA_TEXT_COLUMNS].ljust(FMA_TEXT_COLUMNS), colour)
                for key, colour in row
            ]
            cells = []
            for index in range(FMA_TEXT_COLUMNS):
                chosen = (" ", WHITE)
                for text, colour in layers:
                    if text[index] != " ":
                        chosen = (text[index], colour)
                        break
                cells.append(chosen)
            index = 0
            while index < FMA_TEXT_COLUMNS:
                character, colour = cells[index]
                if character == " ":
                    index += 1
                    continue
                end = index + 1
                while end < FMA_TEXT_COLUMNS and cells[end][0] != " " and cells[end][1] == colour:
                    end += 1
                text = "".join(cells[position][0] for position in range(index, end))
                logical = getattr(canvas, "_record_logical_text", None)
                if callable(logical):
                    logical(text)
                canvas.text(
                    FMA_TEXT_X + index * FONT_CELL_WIDTH,
                    y,
                    text,
                    colour,
                    FMA_BG,
                    PFD_NUMBER_FONT_ID,
                )
                index = end
        _feature(canvas, "NATIVE_TOLISS_FMA")
    elif annunciations_valid:
        # Old capture fallback: retain only the values actually available in
        # pre-FMA-layer feeds, arranged in the real three-row FMA height.
        thrust_mode = values.get("athr_thrust_mode")
        thrust_colour = GREEN if _finite(thrust_mode) and float(thrust_mode) > 0.5 else DIM_GREY
        _text(canvas, FMA_THR, _athr_mode_text(thrust_mode), thrust_colour, FMA_BG)
        ap_on = _bool(values.get("ap_on"))
        _text(canvas, _slot("fallback AP", 490, FMA_ROW_Y[0], 96, "center"),
              "AP1" if ap_on else "AP", GREEN if ap_on else DIM_GREY, FMA_BG)
        _text(canvas, _slot("fallback FD", 490, FMA_ROW_Y[1], 96, "center"),
              "1 FD 2" if _bool(values.get("fd_on")) else "", WHITE, FMA_BG)
        if _bool(values.get("alpha_floor")):
            athr_text, athr_colour = "A.FLOOR", AMBER
        else:
            athr_on = _bool(values.get("athr_on"))
            athr_text, athr_colour = "A/THR", GREEN if athr_on else DIM_GREY
        _text(canvas, _slot("fallback A/THR", 490, FMA_ROW_Y[2], 96, "center"),
              athr_text, athr_colour, FMA_BG)

    # The ToLiss full-width strings already reserve these column boundaries.
    canvas.colour(*WHITE)
    for column in (8, 15, 22, 27):
        x = FMA_TEXT_X + column * FONT_CELL_WIDTH
        canvas.fill(x, 0, 2, FMA_HEIGHT - 10)


def _draw_target_windows(
    canvas: Any,
    values: Mapping[str, Any],
    *,
    speed_valid: bool,
    altitude_valid: bool,
) -> None:
    # A failed source removes the corresponding target from the PFD, as in
    # the owner's red SPD/ALT reference; leaving a healthy FCU target above a
    # red failed tape creates a presentation the real ToLiss screen does not.
    if speed_valid:
        target_speed = values.get("target_speed")
        ias = values.get("ias")
        if _finite(target_speed) and _finite(ias):
            target_y = _speed_y(float(target_speed), float(ias))
            if target_y < SPEED_TAPE.y + 8:
                _text(canvas, SELECTED_SPEED, _fmt(target_speed, 0), MAGENTA)
            elif target_y > SPEED_TAPE.bottom - 8:
                _text(
                    canvas,
                    _slot("selected speed below scale", SPEED_TAPE.x,
                          SPEED_TAPE.bottom + 2, SPEED_TAPE.width, "center"),
                    _fmt(target_speed, 0), MAGENTA,
                )

    if altitude_valid:
        target_alt = values.get("target_altitude")
        # JUDGMENT CALL: ap_alt_target_type's boolean meaning (managed vs
        # selected) is not documented in the catalog - >=0.5 guessed as
        # "managed" (cyan, real Airbus convention), else "selected" (magenta).
        # Confirm live and swap the branches if this reads backwards.
        alt_type = values.get("target_altitude_type")
        colour = CYAN if _finite(alt_type) and float(alt_type) >= 0.5 else MAGENTA
        altitude = values.get("altitude")
        if _finite(target_alt) and _finite(altitude):
            target_y = _alt_y(float(target_alt), float(altitude))
            if not (ALTITUDE_TAPE.y + 29 <= target_y <= ALTITUDE_TAPE.bottom - 29):
                if _bool(values.get("baro_std")):
                    text = f"FL{max(0, int(round(float(target_alt) / 100.0))):03d}"
                else:
                    text = f"{max(0, int(round(float(target_alt)))):05d}"
                y = TARGET_ROW_Y if target_y < ALTITUDE_TAPE.y else ALTITUDE_TAPE.bottom + 2
                _text(
                    canvas,
                    _slot("selected altitude outside scale", ALTITUDE_TAPE.x - 8,
                          y, ALTITUDE_TAPE.width + 16, "center"),
                    text, colour,
                )


# ---------------------------------------------------------------------------
# Attitude sphere: the rounded/chamfered aperture visible in the ToLiss
# manual and the owner's real-screen reference, pitch ladder, bank scale +
# moving pointer, FD single-cue cross-pointer, a fixed
# (screen-level, non-rotating) aircraft reference, and a flight-path-vector
# built from real drift_angle/flight_path_angle data.
# ---------------------------------------------------------------------------
def _draw_horizon(canvas: Any, values: Mapping[str, Any]) -> Tuple[float, float]:
    pitch = _clamp(float(values["pitch"]) if _finite(values.get("pitch")) else 0.0, -30.0, 30.0)
    # JUDGMENT CALL: roll-sign convention copied from Zibo's confirmed
    # X-Plane AHARS behaviour (pfp_renderer.py's own comment: "X-Plane's
    # captain AHARS roll is negative for a right bank") as a starting
    # assumption. toliss_airbus/pfdoutputs/captain/roll_angle's own sign is
    # NOT confirmed against a live ToLiss session - if a real right bank
    # rolls the horizon/pointer the wrong way on hardware, negate `roll`
    # here (and in every other function below that reads it).
    roll = _clamp(float(values["roll"]) if _finite(values.get("roll")) else 0.0, -60.0, 60.0)
    horizon_y = ATT_CENTER_Y + pitch * PITCH_PX_PER_DEG
    slope = math.tan(math.radians(roll))

    sky_rows: list = []
    earth_rows: list = []
    edge_rows: list = []
    for y in range(ATTITUDE.y, ATTITUDE.bottom):
        left, right = _attitude_row_span(y)
        sky_rows.append((left, y, right - left))
        if abs(slope) < 1e-4:
            if y + 0.5 >= horizon_y:
                earth_rows.append((left, y, right - left))
            if y <= horizon_y < y + 1:
                edge_rows.append((left, y, right - left))
            continue
        x_top = ATT_CENTER_X + (y - horizon_y) / slope
        x_bottom = ATT_CENTER_X + (y + 1 - horizon_y) / slope
        lo = max(left, min(right, int(round(min(x_top, x_bottom)))))
        hi = max(left, min(right, int(round(max(x_top, x_bottom)))))
        if slope > 0.0:
            if lo > left:
                earth_rows.append((left, y, lo - left))
        else:
            if right > hi:
                earth_rows.append((hi, y, right - hi))
        if hi > lo:
            edge_rows.append((lo, y, hi - lo))

    _emit_rows(canvas, TOLISS_SKY, sky_rows)
    _emit_rows(canvas, TOLISS_EARTH, earth_rows)
    _emit_rows(canvas, WHITE, edge_rows)
    _feature(canvas, "AIRBUS_ATTITUDE_APERTURE")
    return horizon_y, slope


def _ladder_y(x: float, horizon_y: float, slope: float, pitch_mark: float) -> float:
    """Same-style approximation pfp_renderer.py's own `_world_y` uses: shift
    the horizon's local intercept and keep its slope, rather than true
    per-row perpendicular-offset geometry - visually adequate at this scale.
    """
    return horizon_y - pitch_mark * PITCH_PX_PER_DEG + slope * (x - ATT_CENTER_X)


def _draw_pitch_ladder(canvas: Any, values: Mapping[str, Any], horizon_y: float, slope: float) -> None:
    pitch = float(values["pitch"]) if _finite(values.get("pitch")) else 0.0
    for mark in (-30.0, -25.0, -20.0, -15.0, -10.0, -5.0,
                 5.0, 10.0, 15.0, 20.0, 25.0, 30.0):
        centre_y = _ladder_y(ATT_CENTER_X, horizon_y, slope, mark)
        if centre_y < ATTITUDE.y + 12 or centre_y > ATTITUDE.bottom - 12:
            continue
        major = int(abs(mark)) % 10 == 0
        half_width = 48.0 if major else 25.0
        gap = 40.0 if major else 14.0
        colour = WHITE
        segments = (
            (-half_width, -gap / 2.0),
            (gap / 2.0, half_width),
        )
        for start_dx, end_dx in segments:
            x0, x1 = ATT_CENTER_X + start_dx, ATT_CENTER_X + end_dx
            y0 = _ladder_y(x0, horizon_y, slope, mark)
            y1 = _ladder_y(x1, horizon_y, slope, mark)
            _line(canvas, x0, y0, x1, y1, colour, 2 if not major else 3)
        label_y = int(round(centre_y - FONT_CELL_HEIGHT / 2.0))
        if major and ATTITUDE.y <= label_y <= ATTITUDE.bottom - FONT_CELL_HEIGHT:
            background = TOLISS_SKY if mark > 0 else TOLISS_EARTH
            left_edge = ATT_CENTER_X - int(round(gap / 2.0)) - 3
            right_edge = ATT_CENTER_X + int(round(gap / 2.0)) + 3
            label = _fmt(abs(mark), 0)
            _text(canvas, _slot("pitch ladder left label", left_edge - 34, label_y,
                                 34, "right"), label, colour, background)
            _text(canvas, _slot("pitch ladder right label", right_edge, label_y,
                                 34, "left"), label, colour, background)
    _feature(canvas, "AIRBUS_FULL_5DEG_PITCH_LADDER")


def _bank_point(angle_deg: float, radius: float) -> Tuple[float, float]:
    rad = math.radians(angle_deg)
    return ATT_CENTER_X + radius * math.sin(rad), ATT_CENTER_Y - radius * math.cos(rad)


def _draw_bank_scale(canvas: Any, roll: float) -> None:
    for angle in (-67.0, -45.0, -30.0, -20.0, -10.0, 0.0,
                  10.0, 20.0, 30.0, 45.0, 67.0):
        length = 12.0 if abs(angle) in (0.0, 30.0, 45.0) else 9.0
        outer = _bank_point(angle, BANK_SCALE_RADIUS)
        inner = _bank_point(angle, BANK_SCALE_RADIUS - length)
        if outer[1] < ATTITUDE.y - 4:
            continue
        _line(canvas, inner[0], inner[1], outer[0], outer[1], WHITE, 3)

    # Fixed index triangle (does not move) pointing at the 0 mark.
    tip = _bank_point(0.0, BANK_SCALE_RADIUS - 22.0)
    left = _bank_point(-4.0, BANK_SCALE_RADIUS - 10.0)
    right = _bank_point(4.0, BANK_SCALE_RADIUS - 10.0)
    _emit_rows(canvas, WHITE, _filled_triangle_rows((tip, left, right)))

    # Moving pointer, aimed at the live bank angle on the fixed scale above.
    pointer_angle = _clamp(-roll, -60.0, 60.0)
    tip = _bank_point(pointer_angle, BANK_SCALE_RADIUS - 6.0)
    left = _bank_point(pointer_angle - 4.0, BANK_SCALE_RADIUS - 22.0)
    right = _bank_point(pointer_angle + 4.0, BANK_SCALE_RADIUS - 22.0)
    _emit_rows(canvas, AMBER, _filled_triangle_rows((tip, left, right)))


def _draw_slip_skid(canvas: Any, values: Mapping[str, Any], roll: float) -> None:
    accel = values.get("lateral_accel")
    track_y = int(round(_bank_point(0.0, BANK_SCALE_RADIUS - 34.0)[1]))
    track = Rect(ATT_CENTER_X - 22, track_y, 44, 6)
    _outline(canvas, track, DIM_GREY, 1)
    offset = 0.0
    if _finite(accel):
        offset = _clamp(float(accel), -1.0, 1.0) * 16.0
    canvas.colour(*AMBER if _finite(accel) else DIM_GREY)
    canvas.fill(int(round(ATT_CENTER_X + offset - 4)), track.y + 1, 8, track.height - 2)


def _draw_fd_bars(canvas: Any, values: Mapping[str, Any]) -> None:
    if not _bool(values.get("fd_on")):
        return
    pitch_cmd = values.get("fd_pitch_cmd")
    if _finite(pitch_cmd):
        y = int(round(ATT_CENTER_Y - _clamp(float(pitch_cmd), -15.0, 15.0) * PITCH_PX_PER_DEG))
        y = max(ATTITUDE.y + 6, min(ATTITUDE.bottom - 6, y))
        canvas.colour(*MAGENTA)
        canvas.fill(ATT_CENTER_X - 60, y - 2, 120, 4)
    roll_cmd = values.get("fd_roll_cmd")
    if _finite(roll_cmd):
        x = int(round(ATT_CENTER_X + _clamp(float(roll_cmd), -25.0, 25.0) * 3.6))
        x = max(ATTITUDE.x + 6, min(ATTITUDE.right - 6, x))
        canvas.colour(*MAGENTA)
        canvas.fill(x - 2, ATT_CENTER_Y - 60, 4, 120)


def _draw_aircraft_reference(canvas: Any) -> None:
    """Fixed (screen-level, non-rotating) reference - the real A320 wings/dot
    symbol always stays level; only the sphere behind it moves. Simpler and
    more accurate to the real aircraft than replicating Boeing's own
    rotating-reference technique.
    """
    canvas.colour(*AMBER)
    # Two stepped wings and the small centre box from the supplied A321 PFD,
    # rather than the former generic pair of straight bars.
    canvas.fill(ATT_CENTER_X - 76, ATT_CENTER_Y - 3, 48, 4)
    canvas.fill(ATT_CENTER_X - 31, ATT_CENTER_Y - 3, 4, 13)
    canvas.fill(ATT_CENTER_X - 31, ATT_CENTER_Y + 7, 14, 4)
    canvas.fill(ATT_CENTER_X + 28, ATT_CENTER_Y - 3, 48, 4)
    canvas.fill(ATT_CENTER_X + 27, ATT_CENTER_Y - 3, 4, 13)
    canvas.fill(ATT_CENTER_X + 17, ATT_CENTER_Y + 7, 14, 4)
    _outline(canvas, Rect(ATT_CENTER_X - 5, ATT_CENTER_Y - 5, 10, 10), AMBER, 2)
    _feature(canvas, "AIRBUS_STEPPED_AIRCRAFT_REFERENCE")


def _draw_fpv(canvas: Any, values: Mapping[str, Any], horizon_y: float, slope: float) -> None:
    drift = values.get("drift_angle")
    fpa = values.get("flight_path_angle")
    if not (_finite(drift) and _finite(fpa)):
        return
    x = ATT_CENTER_X + _clamp(float(drift), -12.0, 12.0) * 6.0
    y = _ladder_y(x, horizon_y, slope, _clamp(float(fpa), -15.0, 15.0))
    x = _clamp(x, ATTITUDE.x + 12.0, ATTITUDE.right - 12.0)
    y = _clamp(y, ATTITUDE.y + 12.0, ATTITUDE.bottom - 12.0)
    xi, yi = int(round(x)), int(round(y))
    canvas.colour(*GREEN)
    canvas.fill(xi - 6, yi - 1, 5, 2)
    canvas.fill(xi + 1, yi - 1, 5, 2)
    canvas.fill(xi - 1, yi - 6, 2, 5)
    canvas.fill(xi - 1, yi - 1, 2, 2)
    canvas.fill(xi - 3, yi - 4, 2, 2)
    canvas.fill(xi + 1, yi - 4, 2, 2)


def _draw_deviation_diamond(canvas: Any, cx: int, cy: int) -> None:
    """Draw one compact filled Airbus deviation diamond without a PNG.

    The former 12x12 square was only a first-pass placeholder.  A reserved
    native slot-3 glyph now produces the clean symmetric diamond on both BB35
    and BB36; the three-band primitive below remains the defensive fallback.
    """
    record = getattr(canvas, "_record_feature", None)
    if callable(record):
        record("ILS_DEVIATION_DIAMOND")
    glyph = (
        getattr(_PFD_SHAPE_GLYPHS, "DEVIATION_DIAMOND_CHARACTER", "")
        if _PFD_SHAPE_GLYPHS is not None else ""
    )
    font_id = (
        getattr(_PFD_SHAPE_GLYPHS, "DEVIATION_DIAMOND_FONT_ID", PFD_NUMBER_FONT_ID)
        if _PFD_SHAPE_GLYPHS is not None else PFD_NUMBER_FONT_ID
    )
    if glyph:
        # Both deviation strips are solid black, so the native cell's opaque
        # background is safe here.  One glyph replaces three rectangle fills
        # and keeps a full ILS recovery frame below BB36's report ceiling.
        canvas.text(cx - 8, cy - 14, glyph, MAGENTA, BLACK, font_id)
        return

    canvas.colour(*MAGENTA)
    for x, y, width, height in (
        (cx - 2, cy - 5, 5, 3),
        (cx - 5, cy - 2, 11, 4),
        (cx - 2, cy + 2, 5, 3),
    ):
        canvas.fill(x, y, width, height)


def _draw_ils_scales(canvas: Any, values: Mapping[str, Any]) -> None:
    """Draw LOC and G/S scales in one colour-grouped native transaction."""
    if not _bool(values.get("ils_on")):
        return

    # Paint every white scale primitive before either magenta deviation
    # symbol.  The two areas are disjoint black strips, so this preserves the
    # exact pixels while avoiding two expensive WHITE/MAGENTA/WHITE/MAGENTA
    # colour round trips on the BB35/BB36 protocol.
    cx = GS_STRIP.x + GS_STRIP.width // 2
    cy = ATT_CENTER_Y
    canvas.colour(*WHITE)
    for offset in (-2, -1, 1, 2):
        y = cy + offset * 44
        canvas.fill(cx - 2, y - 2, 4, 4)
    canvas.fill(GS_STRIP.x + 2, cy - 1, GS_STRIP.width - 4, 2)
    loc_cx = ATT_CENTER_X
    loc_cy = LOC_STRIP.y + LOC_STRIP.height // 2

    # A single native text run supplies all four evenly spaced LOC dots on
    # this black strip.  Its opaque black spaces intentionally leave only
    # those dots visible; repaint the white centre index immediately after
    # the run so the text cell can never cut it.
    dot_run = ".  .  .  ."
    canvas.text(
        loc_cx - (len(dot_run) * FONT_CELL_WIDTH) // 2,
        loc_cy - 14,
        dot_run,
        WHITE,
        BLACK,
        PFD_NUMBER_FONT_ID,
    )
    # The active foreground is already WHITE after the text run, so this
    # fill needs no additional colour command on the native controller.
    canvas.fill(loc_cx - 1, LOC_STRIP.y + 2, 2, LOC_STRIP.height - 4)

    gs_dev = values.get("gs_dev")
    if _finite(gs_dev):
        y = int(round(cy - _clamp(float(gs_dev), -1.0, 1.0) * 88.0))
        y = max(GS_STRIP.y + 6, min(GS_STRIP.bottom - 6, y))
        _draw_deviation_diamond(canvas, cx, y)

    loc_dev = values.get("loc_dev")
    if _finite(loc_dev):
        x = int(round(loc_cx + _clamp(float(loc_dev), -1.0, 1.0) * 88.0))
        x = max(LOC_STRIP.x + 6, min(LOC_STRIP.right - 6, x))
        _draw_deviation_diamond(canvas, x, loc_cy)


# ---------------------------------------------------------------------------
# Speed tape: 10kt ticks / 20kt labels, ToLiss-computed low/high-speed bands,
# take-off V-speeds and flap-retraction cues.  The upper limit is the real
# red/black Airbus strip.  ToLiss's VMax_value already selects the lowest of
# VMO/MMO/VFE/VLE/VLO, so it moves immediately with flap-lever/gear state
# without Studio inventing a second set of aircraft limits.
# ---------------------------------------------------------------------------
def _speed_y(value: float, ias: float) -> float:
    return TAPE_CENTER_Y - (value - ias) * SPEED_PX_PER_KT


def _tape_span(top: float, bottom: float, tape: Rect) -> Tuple[int, int] | None:
    first = int(round(max(top, tape.y)))
    last = int(round(min(bottom, tape.bottom)))
    if last - first < 2:
        return None
    return first, last


def _draw_speed_bands(canvas: Any, values: Mapping[str, Any], ias: float) -> None:
    v_ls = values.get("v_ls")
    v_max = values.get("v_max")
    v_alpha_max = values.get("v_alpha_max")
    v_sw = values.get("v_sw")
    lower_bound = v_alpha_max if _finite(v_alpha_max) else v_sw

    canvas.colour(*RED)
    if _finite(lower_bound):
        span = _tape_span(_speed_y(float(lower_bound), ias), SPEED_TAPE.bottom, SPEED_TAPE)
        if span:
            canvas.fill(SPEED_BAND_X, span[0], SPEED_BAND_WIDTH, span[1] - span[0])
    if _finite(v_max) and float(v_max) > 0.0:
        span = _tape_span(SPEED_TAPE.y, _speed_y(float(v_max), ias), SPEED_TAPE)
        if span:
            # Ten equal-height sections (five red, five black) give a real
            # red/black maximum-speed strip at a fixed six native fills,
            # independent of how much of the band is currently visible.
            top, bottom = span
            height = bottom - top
            canvas.colour(*BLACK)
            canvas.fill(SPEED_BAND_X, top, SPEED_BAND_WIDTH, height)
            for section in range(0, 10, 2):
                y0 = top + (height * section) // 10
                y1 = top + (height * (section + 1)) // 10
                if y1 > y0:
                    canvas.colour(*RED)
                    canvas.fill(SPEED_BAND_X, y0, SPEED_BAND_WIDTH, y1 - y0)

    canvas.colour(*AMBER)
    if _finite(lower_bound) and _finite(v_ls):
        span = _tape_span(_speed_y(float(v_ls), ias), _speed_y(float(lower_bound), ias), SPEED_TAPE)
        if span:
            canvas.fill(SPEED_BAND_X, span[0], SPEED_BAND_WIDTH, span[1] - span[0])

    # VLS is the top of the amber line on the Airbus speed tape.  Draw the
    # line all the way down through the protected low-speed region, with its
    # short horizontal cap at the computed VLS value.
    if _finite(v_ls) and float(v_ls) > 0.0:
        vls_y = int(round(_speed_y(float(v_ls), ias)))
        top = max(SPEED_TAPE.y, vls_y)
        if top < SPEED_TAPE.bottom:
            canvas.colour(*AMBER)
            canvas.fill(SPEED_BAND_X - 3, top, 2, SPEED_TAPE.bottom - top)
            if SPEED_TAPE.y <= vls_y < SPEED_TAPE.bottom:
                canvas.fill(SPEED_BAND_X - 3, vls_y, SPEED_BAND_WIDTH + 3, 2)

    v_aprot = values.get("v_aprot")
    if _finite(v_aprot):
        y = int(round(_speed_y(float(v_aprot), ias)))
        if SPEED_TAPE.y <= y < SPEED_TAPE.bottom:
            canvas.colour(*AMBER)
            canvas.fill(SPEED_BAND_X - 3, y, SPEED_BAND_WIDTH + 3, 2)


def _draw_speed_bug(canvas: Any, y: float, colour: Tuple[int, int, int], shape: str) -> bool:
    if y < SPEED_TAPE.y + 4 or y > SPEED_TAPE.bottom - 4:
        return False
    yi = int(round(y))
    x = SPEED_BUG_X
    if shape == "dot":
        canvas.colour(*colour)
        canvas.fill(x - 3, yi - 3, 6, 6)
    elif shape == "ring":
        glyph = (
            getattr(_PFD_SHAPE_GLYPHS, "SPEED_RING_CHARACTER", "")
            if _PFD_SHAPE_GLYPHS is not None else ""
        )
        if glyph:
            canvas.text(x - 8, yi - 14, glyph, colour, TAPE_GREY, PFD_NUMBER_FONT_ID)
        else:
            _outline(canvas, Rect(x - 5, yi - 5, 10, 10), colour, 2)
    elif shape == "equal":
        # The ordinary slot-3 equals glyph is the exact two-bar VFE-next
        # symbol and its opaque cell is safe over the uniform grey tape.
        canvas.text(x - 8, yi - 14, "=", colour, TAPE_GREY, PFD_NUMBER_FONT_ID)
    else:  # small left-pointing target triangle
        glyph = (
            getattr(_PFD_SHAPE_GLYPHS, "SPEED_TRIANGLE_CHARACTER", "")
            if _PFD_SHAPE_GLYPHS is not None else ""
        )
        if glyph:
            canvas.text(x - 8, yi - 14, glyph, colour, TAPE_GREY, PFD_NUMBER_FONT_ID)
        else:
            # Airbus target-speed symbols sit at the inboard edge and point
            # into the scale, i.e. left on this captain-side tape.
            tip = (x - 6, yi)
            top = (x + 4, yi - 5)
            bottom = (x + 4, yi + 5)
            _emit_rows(canvas, colour, _filled_triangle_rows((tip, top, bottom)))
    return True


def _draw_speed_letter(canvas: Any, y: float, label: str, colour: Tuple[int, int, int]) -> bool:
    """Draw a one-cell Airbus speed letter safely clear of the limit band."""
    if y < SPEED_TAPE.y + 12 or y > SPEED_TAPE.bottom - 12:
        return False
    yi = int(round(y))
    _text(
        canvas,
        _slot(f"speed marker {label}", SPEED_BUG_X - 20, yi - 14, FONT_CELL_WIDTH, "left"),
        label,
        colour,
        TAPE_GREY,
    )
    # F and S use a short leader to the tape in the real ToLiss atlas.
    if label in {"F", "S"}:
        canvas.colour(*colour)
        canvas.fill(SPEED_BUG_X - 5, yi - 1, 5, 2)
    return True


def _draw_speed_tape(canvas: Any, values: Mapping[str, Any]) -> None:
    canvas.colour(*TAPE_GREY)
    canvas.fill(SPEED_TAPE.x, SPEED_TAPE.y, SPEED_TAPE.width, SPEED_TAPE.height)

    ias = values.get("ias")
    if _finite(ias):
        ias_f = float(ias)
        base = int(round(ias_f / SPEED_TICK_STEP)) * int(SPEED_TICK_STEP)
        canvas.colour(*WHITE)
        for tick in range(base - 60, base + 61, int(SPEED_TICK_STEP)):
            if tick < 0:
                continue
            y = _speed_y(float(tick), ias_f)
            if SPEED_TAPE.y + 10 <= y <= SPEED_TAPE.bottom - 10:
                yi = int(round(y))
                canvas.fill(SPEED_TAPE.right - 6, yi, 6, 2)
                if tick % int(SPEED_LABEL_STEP) == 0 and not (SPEED_WINDOW.y - 4 <= yi <= SPEED_WINDOW.bottom + 4):
                    label_y = int(y - FONT_CELL_HEIGHT / 2.0)
                    if SPEED_TAPE.y <= label_y <= SPEED_TAPE.bottom - FONT_CELL_HEIGHT:
                        # 54px (3-char capacity) - a 44px/2-char slot here
                        # silently dropped every 3-digit tick (i.e. almost
                        # every real speed above 99kt) on the first pass.
                        _text(canvas, _slot("speed tick", SPEED_TAPE.x + 4, label_y, 54, "left"),
                              str(tick), WHITE, TAPE_GREY)

        _draw_speed_bands(canvas, values, ias_f)

        # ToLiss decides when take-off speeds belong on the tape.  Preserve
        # an old-capture fallback only when the flag is absent; an explicit
        # zero is authoritative and hides V1/VR/V2.
        show_to_flag = values.get("show_to_speeds")
        show_to = _bool(show_to_flag) if _finite(show_to_flag) else any(
            _finite(values.get(key)) and float(values[key]) > 0.0
            for key in ("v1", "v_r", "v2")
        )
        if show_to:
            v1 = values.get("v1")
            if _finite(v1) and float(v1) > 0.0:
                if _draw_speed_letter(canvas, _speed_y(float(v1), ias_f), "1", CYAN):
                    record = getattr(canvas, "_record_feature", None)
                    if callable(record):
                        record("V1")
            vr = values.get("v_r")
            if _finite(vr) and float(vr) > 0.0:
                if _draw_speed_bug(canvas, _speed_y(float(vr), ias_f), CYAN, "ring"):
                    record = getattr(canvas, "_record_feature", None)
                    if callable(record):
                        record("VR")
            v2 = values.get("v2")
            if _finite(v2) and float(v2) > 0.0:
                if _draw_speed_bug(canvas, _speed_y(float(v2), ias_f), MAGENTA, "tri"):
                    record = getattr(canvas, "_record_feature", None)
                    if callable(record):
                        record("V2")

        # F/S/green-dot/VFE-next are mutually selected by ToLiss's own
        # computed output values and therefore follow the active slat/flap
        # configuration through take-off, climb, approach and landing.
        for key, label in (("v_f", "F"), ("v_s", "S")):
            value = values.get(key)
            if _finite(value) and float(value) > 0.0:
                if _draw_speed_letter(canvas, _speed_y(float(value), ias_f), label, GREEN):
                    record = getattr(canvas, "_record_feature", None)
                    if callable(record):
                        record(f"{label}_SPEED")

        for key, colour, shape in (
            ("v_green_dot", GREEN, "dot"),
            ("v_vfe_next", AMBER, "equal"),
            ("climb_cas_presel", MAGENTA, "ring"),
            ("cruise_cas_presel", MAGENTA, "ring"),
        ):
            value = values.get(key)
            if _finite(value) and float(value) > 0.0:
                _draw_speed_bug(canvas, _speed_y(float(value), ias_f), colour, shape)

        target_speed = values.get("target_speed")
        if _finite(target_speed):
            target_y = _speed_y(float(target_speed), ias_f)
            if SPEED_TAPE.y + 8 <= target_y <= SPEED_TAPE.bottom - 8:
                _draw_speed_bug(canvas, target_y, MAGENTA, "tri")
                _feature(canvas, "AIRSPEED_SELECTED_TRIANGLE")

    # The inboard white scale edge is a defining Airbus tape shape.  It is
    # deliberately painted after the protection bands so their stripes end
    # cleanly against it rather than replacing the edge.
    canvas.colour(*WHITE)
    canvas.fill(SPEED_TAPE.right - 2, SPEED_TAPE.y, 2, SPEED_TAPE.height)

    # The supplied ToLiss tape has no oversized generic rectangular readout:
    # the live value sits on the grey tape at the fixed amber datum.
    canvas.colour(*AMBER)
    canvas.fill(SPEED_TAPE.x - 8, TAPE_CENTER_Y - 1, 11, 3)
    _text(canvas, IAS_TEXT, _fmt(ias, 0), WHITE, TAPE_GREY)
    _feature(canvas, "AIRBUS_NARROW_SPEED_DATUM")


# ---------------------------------------------------------------------------
# Altitude tape traced from the owner's live A321 reference: a single inboard
# scale wall on the RIGHT, 100 ft ticks / 500 ft labels, a cyan selected-
# altitude bracket and a centred amber hammer containing fixed hundreds plus
# a smaller continuously moving 20 ft drum.
# ---------------------------------------------------------------------------
def _alt_y(value: float, altitude: float) -> float:
    return TAPE_CENTER_Y - (value - altitude) * ALT_PX_PER_FT


def _draw_altitude_bug(canvas: Any, y: int) -> None:
    """Draw the cyan target box with its inboard-pointing triangular nipple."""
    left = ALTITUDE_WINDOW.x - 18
    right = ALTITUDE_WINDOW.x + 22
    half_height = 29
    top = max(ALTITUDE_TAPE.y + 2, y - half_height)
    bottom = min(ALTITUDE_TAPE.bottom - 2, y + half_height)
    nipple_half = 7
    canvas.colour(*CYAN)
    canvas.fill(left, top, 3, bottom - top)
    canvas.fill(left, top, right - left, 3)
    canvas.fill(left, bottom - 3, right - left, 3)
    if top + nipple_half < y < bottom - nipple_half:
        canvas.fill(right - 3, top, 3, y - nipple_half - top)
        canvas.fill(right - 3, y + nipple_half, 3, bottom - y - nipple_half)
        _line(canvas, right - 2, y - nipple_half, right + 7, y, CYAN, 2)
        _line(canvas, right + 7, y, right - 2, y + nipple_half, CYAN, 2)
    else:
        canvas.fill(right - 3, top, 3, bottom - top)
    _feature(canvas, "ALTITUDE_CYAN_TARGET_BOX")


def _draw_altitude_hammer_outline(canvas: Any, *, fill_body: bool = True) -> None:
    """Draw the reference's open main cradle and separate vertical drum.

    The large three-digit field stays wholly inside the grey tape.  It has
    only horizontal amber rails (open at both ends).  The joined two-digit
    drum begins at the right scale wall and is the only part allowed to
    project outboard into the black area.
    """
    if fill_body:
        canvas.colour(*BLACK)
        canvas.fill(
            ALTITUDE_WINDOW.x, ALTITUDE_WINDOW.y,
            ALTITUDE_WINDOW.width, ALTITUDE_WINDOW.height,
        )
        canvas.fill(
            ALT_DRUM_BOX.x, ALT_DRUM_BOX.y,
            ALT_DRUM_BOX.width, ALT_DRUM_BOX.height,
        )
    canvas.colour(*AMBER)
    canvas.fill(
        ALTITUDE_WINDOW.x, ALTITUDE_WINDOW.y,
        ALTITUDE_WINDOW.width, 2,
    )
    canvas.fill(
        ALTITUDE_WINDOW.x, ALTITUDE_WINDOW.bottom - 2,
        ALTITUDE_WINDOW.width, 2,
    )
    # The small left-pointing datum belongs to the open cradle; it is not a
    # vertical closure and does not alter the cradle's tape-bounded rails.
    _line(
        canvas,
        ALTITUDE_WINDOW.x, TAPE_CENTER_Y - 6,
        ALTITUDE_WINDOW.x - 10, TAPE_CENTER_Y,
        AMBER, 2,
    )
    _line(
        canvas,
        ALTITUDE_WINDOW.x - 10, TAPE_CENTER_Y,
        ALTITUDE_WINDOW.x, TAPE_CENTER_Y + 6,
        AMBER, 2,
    )
    _outline(canvas, ALT_DRUM_BOX, AMBER, 2)
    _feature(canvas, "ALTITUDE_AMBER_HAMMER")
    _feature(canvas, "ALTITUDE_OPEN_MAIN_CRADLE")
    _feature(canvas, "ALTITUDE_OUTBOARD_DRUM_BOX")


def _draw_tiny_altitude_pair(canvas: Any, y: int, pair: int) -> None:
    text = f"{pair % 100:02d}"
    logical = getattr(canvas, "_record_logical_text", None)
    if callable(logical):
        logical(text)
    for index, character in enumerate(text):
        canvas.text(
            ALT_DRUM_X + index * 10, y, character,
            GREEN, BLACK, PFD_TINY_FONT_ID,
        )


def _draw_altitude_drum(canvas: Any, altitude: float) -> None:
    """Fixed hundreds plus the live, continuously rolling 00/20/.../80 pair."""
    magnitude = abs(float(altitude))
    fixed = int(magnitude // 100.0)
    fixed_text = f"{fixed:03d}"
    if altitude < 0.0:
        fixed_text = "-" + fixed_text[-2:]
    logical = getattr(canvas, "_record_logical_text", None)
    if callable(logical):
        logical(fixed_text)
    canvas.text(
        ALT_FIXED_X, TAPE_CENTER_Y - 14, fixed_text,
        GREEN, BLACK, PFD_ALTITUDE_LARGE_FONT_ID,
    )

    stepped = math.floor(magnitude / ALT_DRUM_STEP_FT) * ALT_DRUM_STEP_FT
    fraction = (magnitude - stepped) / ALT_DRUM_STEP_FT
    base_y = TAPE_CENTER_Y - 14 - int(round(fraction * ALT_DRUM_PITCH))
    for neighbour in (-1, 1, 0):
        pair = int(stepped + neighbour * ALT_DRUM_STEP_FT) % 100
        _draw_tiny_altitude_pair(canvas, base_y + neighbour * ALT_DRUM_PITCH, pair)

    spill_top = TAPE_CENTER_Y - 14 - 2 * ALT_DRUM_PITCH
    spill_bottom = TAPE_CENTER_Y - 14 + ALT_DRUM_PITCH + FONT_CELL_HEIGHT + 1
    canvas.colour(*BLACK)
    canvas.fill(
        ALT_DRUM_X, spill_top, ALT_DRUM_WIDTH,
        ALT_DRUM_BOX.y - spill_top,
    )
    canvas.fill(
        ALT_DRUM_X, ALT_DRUM_BOX.bottom, ALT_DRUM_WIDTH,
        spill_bottom - ALT_DRUM_BOX.bottom,
    )
    _draw_altitude_hammer_outline(canvas, fill_body=False)
    _feature(canvas, "ALTITUDE_20FT_ROLLING_DRUM")


def _draw_altitude_tape(canvas: Any, values: Mapping[str, Any]) -> None:
    canvas.colour(*TAPE_GREY)
    canvas.fill(ALTITUDE_TAPE.x, ALTITUDE_TAPE.y, ALTITUDE_TAPE.width, ALTITUDE_TAPE.height)

    altitude = values.get("altitude")
    if _finite(altitude):
        alt_f = float(altitude)
        base = int(round(alt_f / ALT_TICK_STEP)) * int(ALT_TICK_STEP)
        canvas.colour(*WHITE)
        for tick in range(base - 500, base + 501, int(ALT_TICK_STEP)):
            y = _alt_y(float(tick), alt_f)
            if ALTITUDE_TAPE.y + 10 <= y <= ALTITUDE_TAPE.bottom - 10:
                yi = int(round(y))
                tick_width = 12 if tick % int(ALT_LABEL_STEP) == 0 else 8
                canvas.fill(ALT_SCALE_X - tick_width, yi, tick_width, 2)
                if (
                    tick % int(ALT_LABEL_STEP) == 0
                    and not (ALTITUDE_WINDOW.y - 4 <= yi <= ALTITUDE_WINDOW.bottom + 4)
                ):
                    label_y = int(_clamp(
                        y - FONT_CELL_HEIGHT / 2.0,
                        ALTITUDE_TAPE.y,
                        ALTITUDE_TAPE.bottom - FONT_CELL_HEIGHT,
                    ))
                    _text(canvas, _slot("altitude tick", ALTITUDE_TAPE.x + 1, label_y,
                                         ALTITUDE_TAPE.width - 5, "left"),
                          f">{max(0, int(round(tick / 100.0))):03d}", WHITE, TAPE_GREY)

        target = values.get("target_altitude")
        if _finite(target):
            y = _alt_y(float(target), alt_f)
            if ALTITUDE_TAPE.y + 29 <= y <= ALTITUDE_TAPE.bottom - 29:
                _draw_altitude_bug(canvas, int(round(y)))

    canvas.colour(*WHITE)
    canvas.fill(ALT_SCALE_X, ALTITUDE_TAPE.y, 2, ALTITUDE_TAPE.height)
    _draw_altitude_hammer_outline(canvas)
    if _finite(altitude):
        _draw_altitude_drum(canvas, float(altitude))
    else:
        _text(canvas, ALT_TEXT, "-----", DIM_GREY, BLACK)
    _feature(canvas, "ALTITUDE_ROLLING_WINDOW")


def _vs_offset(value: float) -> float:
    magnitude = min(6000.0, abs(float(value)))
    if magnitude <= 1000.0:
        pixels = magnitude * 54.0 / 1000.0
    elif magnitude <= 2000.0:
        pixels = 54.0 + (magnitude - 1000.0) * 34.0 / 1000.0
    else:
        pixels = 88.0 + (magnitude - 2000.0) * 34.0 / 4000.0
    return math.copysign(pixels, float(value))


def _draw_vs_wedge(canvas: Any, values: Mapping[str, Any]) -> None:
    _fill_vs_shape(canvas, TAPE_GREY)
    pivot_x, pivot_y = VS_WEDGE.right - 3, TAPE_CENTER_Y
    canvas.colour(*WHITE)
    for thousands in (-6, -2, -1, 1, 2, 6):
        y = int(round(pivot_y - _vs_offset(thousands * 1000.0)))
        if VS_WEDGE.y + 8 <= y <= VS_WEDGE.bottom - 8:
            canvas.fill(VS_WEDGE.right - 7, y - 1, 7, 2)
            _text(canvas, _slot("vs tick", VS_WEDGE.x + 1, y - 14, FONT_CELL_WIDTH, "left"),
                  str(abs(thousands)), WHITE, TAPE_GREY)
    for hundreds in (-15, -5, 5, 15):
        y = int(round(pivot_y - _vs_offset(hundreds * 100.0)))
        if VS_WEDGE.y + 4 <= y <= VS_WEDGE.bottom - 4:
            canvas.fill(VS_WEDGE.right - 5, y, 5, 1)

    vs = values.get("vertical_speed")
    if _finite(vs):
        v = _clamp(float(vs), -6000.0, 6000.0)
        tip_y = _clamp(pivot_y - _vs_offset(v), VS_WEDGE.y + 6.0, VS_WEDGE.bottom - 6.0)
        tip_x = VS_WEDGE.x + 3
        canvas.colour(*GREEN)
        for x, y, width, height in _straight_line_rects(
            float(pivot_x), float(pivot_y), float(tip_x + 7), float(tip_y), 2,
        ):
            canvas.fill(x, y, width, height)
        _emit_rows(
            canvas,
            GREEN,
            _filled_triangle_rows((
                (tip_x, tip_y),
                (tip_x + 7, tip_y - 4),
                (tip_x + 7, tip_y + 4),
            )),
        )
    _feature(canvas, "TAPERED_VS_SCALE")


# ---------------------------------------------------------------------------
# Heading/track strip - linear scale (real Airbus PFD convention; the
# compass ROSE lives on the ND, step 3 of this plan pass).
# `values["heading"]` comes from the native captain-side AirbusFBW/HDGCapt
# source and the selected target from AirbusFBW/APHDG_Capt.
# ---------------------------------------------------------------------------
def _draw_heading_tape(canvas: Any, values: Mapping[str, Any]) -> None:
    canvas.colour(*TAPE_GREY)
    canvas.fill(HEADING_TAPE.x, HEADING_TAPE.y, HEADING_TAPE.width, HEADING_TAPE.height)
    cx = HEADING_TAPE.x + HEADING_TAPE.width // 2

    heading = values.get("heading")
    if _finite(heading):
        hdg = float(heading) % 360.0
        base = int(round(hdg / HEADING_TICK_STEP)) * int(HEADING_TICK_STEP)
        canvas.colour(*WHITE)
        half_span = int(HEADING_TAPE.width / 2 / HEADING_PX_PER_DEG) + int(HEADING_TICK_STEP)
        for tick in range(base - half_span, base + half_span + 1, int(HEADING_TICK_STEP)):
            delta = (tick - hdg + 540.0) % 360.0 - 180.0
            x = cx + delta * HEADING_PX_PER_DEG
            if HEADING_TAPE.x + 6 <= x <= HEADING_TAPE.right - 6:
                xi = int(round(x))
                canvas.fill(xi, HEADING_TAPE.y + 2, 2, 8)
                label = f"{(tick % 360) // 10:02d}"
                _text(canvas, _slot("heading tick", xi - 17, HEADING_TAPE.y + 12, 34, "center"),
                      label, WHITE, TAPE_GREY)

        target = values.get("target_heading")
        if _finite(target):
            # Native captain-side ToLiss selected-heading source.
            delta = (float(target) - hdg + 540.0) % 360.0 - 180.0
            x = _clamp(cx + delta * HEADING_PX_PER_DEG, HEADING_TAPE.x + 6.0, HEADING_TAPE.right - 6.0)
            xi = int(round(x))
            tip = (xi, HEADING_TAPE.y - 2)
            left = (xi - 6, HEADING_TAPE.y + 6)
            right = (xi + 6, HEADING_TAPE.y + 6)
            _emit_rows(canvas, MAGENTA, _filled_triangle_rows((tip, left, right)))

    # Current-track index: green stem with the yellow Airbus reference head.
    canvas.colour(*GREEN)
    canvas.fill(cx - 1, HEADING_TAPE.y, 2, HEADING_TAPE.height)
    _emit_rows(
        canvas,
        AMBER,
        _filled_triangle_rows((
            (cx, HEADING_TAPE.y + 10),
            (cx - 6, HEADING_TAPE.y),
            (cx + 6, HEADING_TAPE.y),
        )),
    )
    canvas.colour(*WHITE)
    canvas.fill(HEADING_TAPE.x, HEADING_TAPE.y, HEADING_TAPE.width, 2)


# ---------------------------------------------------------------------------
# Bottom text rows - baro setting, landing elevation, Mach, cruise Mach
# preselect (text-only: converting a Mach target to a tape position needs
# the live Mach/CAS relationship, which is not reliably available, so it is
# shown as a number rather than fabricating a tape bug), ILS frequency/DME.
# ---------------------------------------------------------------------------
def _draw_bottom_text(canvas: Any, values: Mapping[str, Any]) -> None:
    std = values.get("baro_std")
    if _bool(std):
        std_box = Rect(BARO_TEXT.rect.right - 58, BARO_TEXT.rect.y - 2, 58, 33)
        _outline(canvas, std_box, AMBER, 2)
        _text(canvas, BARO_TEXT, "STD", CYAN, BLACK)
        _feature(canvas, "STD_BOX")
    else:
        baro_value = values.get("baro_value")
        unit_flag = values.get("baro_unit")
        if _finite(baro_value):
            # JUDGMENT CALL: AirbusFBW/ISIBaroSetting is used as a proxy for
            # the captain's own baro value - no AirbusFBW captain baro VALUE
            # dataref is catalogued (only BaroStdCapt/BaroUnitCapt flags and
            # a knob-rotation ratio). Confirm live that the ISI and captain
            # settings track together. Its native unit/range is also
            # undocumented in the catalog, so no hPa/inHg conversion is
            # applied - shown as-read with two decimals plus the unit flag's
            # own label instead of guessing a conversion.
            if _bool(unit_flag):
                value_text = f"QNH{int(round(float(baro_value))):04d}"
            else:
                value_text = f"QNH{float(baro_value):.2f}"
            _text(canvas, BARO_TEXT, value_text, CYAN, BLACK)
        else:
            _text(canvas, BARO_TEXT, "----", DIM_GREY, BLACK)

    landing_elev = values.get("landing_elev")
    _text(canvas, LANDING_ELEV_TEXT, "ELEV" + _fmt(landing_elev, 0), CYAN, BLACK)

    mach = values.get("mach")
    if _finite(mach) and 0.0 <= float(mach) < 10.0:
        _text(canvas, MACH_TEXT, f"{float(mach):.3f}"[1:], GREEN, BLACK)
    else:
        _text(canvas, MACH_TEXT, ".---", DIM_GREY, BLACK)

    presel_mach = values.get("cruise_mach_presel")
    if _finite(presel_mach) and float(presel_mach) > 0.0:
        _text(canvas, PRESEL_MACH_TEXT, "P" + f"{float(presel_mach):.3f}"[1:], MAGENTA, BLACK)

    if _bool(values.get("ils_on")):
        freq = values.get("ils_freq")
        dme = values.get("dme_distance")
        # Kept deliberately short (no "ILS"/"DME" literal prefix - the
        # frequency format and position already identify it, same minimal-
        # text convention the tape bugs below use) so the combined string
        # stays inside ILS_TEXT's budget: "109.50  12.4NM" is 15 characters.
        if _finite(freq):
            _text(canvas, ILS_TEXT, f"{float(freq):.2f}", MAGENTA, BLACK)
        if _finite(dme):
            _text(canvas, DME_TEXT, f"{float(dme):.1f}NM", GREEN, BLACK)


# ---------------------------------------------------------------------------
# Frame assembly + live diff-engine wrapper (same contract as
# systems_renderer_toliss.draw_live_toliss_system_page / pfp_renderer's own
# draw_live_pfd): record the whole frame, diff against the previous one, and
# emit only the pixels that changed.
# ---------------------------------------------------------------------------
_PFD_QUANTISED_STEPS = {
    "pitch": 0.2,
    "roll": 0.2,
    "heading": 0.25,
}


def _steady(values: Mapping[str, Any]) -> Mapping[str, Any]:
    steady = dict(values)
    for name, step in _PFD_QUANTISED_STEPS.items():
        value = steady.get(name)
        if _finite(value):
            steady[name] = round(float(value) / step) * step
    return steady


def draw_toliss_pfd_frame(canvas: Any, values: Mapping[str, Any]) -> None:
    canvas.colour(*BLACK)
    canvas.fill(0, 0, WIDTH, HEIGHT)

    attitude_valid = _source_valid(values, "att_valid", "pitch", "roll")
    ias_valid = _source_valid(values, "ias_valid", "ias")
    altitude_valid = _source_valid(values, "alt_valid", "altitude")
    heading_valid = _source_valid(values, "hdg_valid", "heading")
    any_primary_source = attitude_valid or ias_valid or altitude_valid or heading_valid
    _draw_fma(canvas, values, annunciations_valid=any_primary_source)
    _draw_target_windows(
        canvas, values, speed_valid=ias_valid, altitude_valid=altitude_valid,
    )

    if attitude_valid:
        horizon_y, slope = _draw_horizon(canvas, values)
        _draw_pitch_ladder(canvas, values, horizon_y, slope)
        roll = _clamp(
            float(values["roll"]) if _finite(values.get("roll")) else 0.0,
            -60.0,
            60.0,
        )
        _draw_bank_scale(canvas, roll)
        _draw_slip_skid(canvas, values, roll)
        _draw_fd_bars(canvas, values)
        _draw_fpv(canvas, values, horizon_y, slope)
        _draw_aircraft_reference(canvas)
        _draw_ils_scales(canvas, values)
    else:
        _draw_invalid_attitude(canvas)
        canvas.colour(*BLACK)
        canvas.fill(LOC_STRIP.x, LOC_STRIP.y, LOC_STRIP.width, LOC_STRIP.height)
        canvas.fill(GS_STRIP.x, GS_STRIP.y, GS_STRIP.width, GS_STRIP.height)

    if ias_valid:
        _draw_speed_tape(canvas, values)
    else:
        _draw_invalid_speed(canvas)

    if altitude_valid:
        _draw_altitude_tape(canvas, values)
    else:
        _draw_invalid_altitude(canvas)

    if altitude_valid and _finite(values.get("vertical_speed")):
        _draw_vs_wedge(canvas, values)
    else:
        _draw_invalid_vs(canvas)

    if heading_valid:
        _draw_heading_tape(canvas, values)
    else:
        _draw_invalid_heading(canvas)
    if any_primary_source:
        _draw_bottom_text(canvas, values)


def draw_live_toliss_pfd(canvas: Any, values: Mapping[str, Any]) -> bool:
    """Emit changed regions for one PFD frame; return True if it drew."""
    steady = _steady(values)
    recorder = _OpRecorder()
    draw_toliss_pfd_frame(recorder, steady)
    operations = recorder.ops

    state = getattr(canvas, "_muslimsim_toliss_pfd_state", None)
    now = time.monotonic()
    stale = (
        state is None
        or now - state[1] > FULL_REPAINT_SECONDS
        or state[2] >= TOLISS_PFD_FULL_REPAINT_FRAMES
    )
    if stale:
        boxes = [(0, 0, WIDTH, HEIGHT)]
        sequence = 0
    else:
        boxes = _dirty_boxes(operations, state[0])
        sequence = state[2] + 1
    _emit_frame(canvas, operations, boxes)
    try:
        canvas._muslimsim_toliss_pfd_state = (operations, now, sequence)
    except AttributeError:
        pass
    return bool(boxes)


def invalidate(canvas: Any) -> None:
    try:
        del canvas._muslimsim_toliss_pfd_state
    except (AttributeError, TypeError):
        pass


# ---------------------------------------------------------------------------
# Value-key contract - documented for bridge/final.py's _toliss_pfd_values()
# translator, matching systems_renderer_toliss.TOLISS_SYSTEM_PAGE_VALUE_KEYS'
# own documentation role.
# ---------------------------------------------------------------------------
TOLISS_PFD_VALUE_KEYS: Tuple[str, ...] = (
    "ias_valid", "alt_valid", "att_valid", "hdg_valid",
    "ias", "mach", "altitude",
    "pitch", "roll", "vertical_speed", "drift_angle", "flight_path_angle",
    "fd_pitch_cmd", "fd_roll_cmd", "fd_on",
    "ap_on", "athr_on", "athr_thrust_mode", "alpha_floor",
    "fma1_green", "fma1_blue", "fma1_white",
    "fma2_blue", "fma2_magenta", "fma2_white",
    "fma3_amber", "fma3_blue", "fma3_white",
    "target_speed", "target_altitude", "target_altitude_type", "target_heading",
    "heading",
    "v_ls", "v_max", "v_sw", "v_green_dot", "v1", "v_r", "v2",
    "v_f", "v_s", "v_vfe_next", "v_alpha_max", "v_aprot",
    "show_to_speeds",
    "climb_cas_presel", "cruise_cas_presel", "cruise_mach_presel",
    "baro_std", "baro_unit", "baro_value",
    "ils_on", "ils_freq", "ils_type", "ils_slope", "loc_dev", "gs_dev",
    "dme_distance", "landing_elev", "lateral_accel",
)


class _BoundsCanvas:
    def colour(self, _red: int, _green: int, _blue: int) -> None:
        return None

    def fill(self, x: int, y: int, width: int, height: int) -> None:
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > WIDTH or y + height > HEIGHT:
            raise TolissPfdLayoutError(f"fill outside display: {(x, y, width, height)}")

    def text(self, x: int, y: int, value: str, _foreground, _background, _font_id) -> None:
        if x < 0 or y < 0 or x + len(value) * FONT_CELL_WIDTH > WIDTH or y + FONT_CELL_HEIGHT > HEIGHT:
            raise TolissPfdLayoutError(f"text outside display: {(x, y, value)!r}")


class _CaptureCanvas(_BoundsCanvas):
    """Bounds-checking canvas that also records every text run drawn.

    TextSlot.position_for silently drops (does not raise, does not call
    canvas.text at all) any value too wide for its slot's capacity - see
    _draw_text_with_font in pfp_renderer.py. A bounds-only self-test cannot
    see that: the drop just means the call never happens, well inside every
    bound. This is exactly the bug the first pass of this renderer shipped
    with (an 8-character thrust-mode label silently vanishing inside a
    6-character-capacity FMA column) and only a rendered-text assertion like
    the one below actually catches it.
    """

    def __init__(self) -> None:
        super().__init__()
        self.texts: list = []
        self.features: list = []

    def _record_logical_text(self, value: str) -> None:
        self.texts.append(value)

    def _record_feature(self, value: str) -> None:
        self.features.append(value)

    def text(self, x: int, y: int, value: str, foreground, background, font_id) -> None:
        super().text(x, y, value, foreground, background, font_id)


def assert_layout_contract() -> None:
    # ToLiss/manual-derived proportions.  These explicit checks prevent a
    # future "make it fit" edit from silently turning the Airbus PFD back
    # into the former generic rectangular layout.
    if FMA_HEIGHT < 3 * FONT_CELL_HEIGHT:
        raise TolissPfdLayoutError("PFD FMA no longer has three full rows")
    if ATTITUDE.width < 270 or ATTITUDE.height < 250:
        raise TolissPfdLayoutError("Airbus attitude aperture was undersized")
    if SPEED_TAPE.width > 82 or ALTITUDE_TAPE.width > 82:
        raise TolissPfdLayoutError("Airbus side tape proportions regressed")
    if VS_WEDGE.width > 30 or not 35 <= HEADING_TAPE.height <= 45:
        raise TolissPfdLayoutError("Airbus V/S or heading-strip silhouette regressed")
    top_left, top_right = _attitude_row_span(ATTITUDE.y)
    mid_left, mid_right = _attitude_row_span(TAPE_CENTER_Y)
    if not (top_left > mid_left and top_right < mid_right):
        raise TolissPfdLayoutError("Attitude aperture lost its rounded shoulders")

    # 1. Every fixed slot lies inside the physical display and has a
    #    positive capacity.
    for slot in _ALL_TEXT_SLOTS:
        if (
            slot.rect.x < 0 or slot.rect.y < 0
            or slot.rect.right > WIDTH or slot.rect.bottom > HEIGHT
            or slot.capacity < 1
        ):
            raise TolissPfdLayoutError(f"Unsafe PFD slot: {slot.name}")

    # 2. Automated pairwise overlap sweep across every declared fixed slot -
    #    step 1's own approach (systems_renderer_toliss.py's assert used
    #    manual per-page checks; this renderer has enough simultaneous fixed
    #    zones that a generic sweep is the more reliable guard, matching the
    #    plan's own suggestion to automate this at this scale).
    for i, a in enumerate(_ALL_TEXT_SLOTS):
        for b in _ALL_TEXT_SLOTS[i + 1:]:
            if a.rect.intersects(b.rect):
                raise TolissPfdLayoutError(f"PFD slots overlap: {a.name!r} / {b.name!r}")

    # 3. The major zone rectangles (tapes, attitude sphere, LOC/G-S strips,
    #    heading strip) must not overlap each other either.
    zones = {
        "speed tape": SPEED_TAPE, "attitude": ATTITUDE, "loc strip": LOC_STRIP,
        "gs strip": GS_STRIP, "altitude tape": ALTITUDE_TAPE, "vs wedge": VS_WEDGE,
        "heading tape": HEADING_TAPE,
    }
    names = list(zones)
    for i, name_a in enumerate(names):
        for name_b in names[i + 1:]:
            if zones[name_a].intersects(zones[name_b]):
                raise TolissPfdLayoutError(f"PFD zones overlap: {name_a!r} / {name_b!r}")
    for rect in zones.values():
        if rect.x < 0 or rect.y < 0 or rect.right > WIDTH or rect.bottom > HEIGHT:
            raise TolissPfdLayoutError(f"PFD zone left the display: {rect}")
        if rect.x < X_SAFE_LEFT or rect.right > X_SAFE_RIGHT:
            raise TolissPfdLayoutError(f"PFD zone left the bezel-safe strip: {rect}")

    # 4. Every possible FMA thrust-mode label (the guessed enum table plus
    #    its numeric fallback) must actually fit FMA_THR's capacity - an
    #    exhaustive, cheap check that catches a too-narrow column directly,
    #    rather than relying on happening to sample the longest label.
    longest_fallback = "MODE 99"
    for label in list(_ATHR_MODE_LABELS.values()) + [longest_fallback]:
        if label and len(label) > FMA_THR.capacity:
            raise TolissPfdLayoutError(
                f"FMA thrust-mode label {label!r} does not fit FMA_THR "
                f"(capacity {FMA_THR.capacity})"
            )

    # The same exhaustive-format check for every other slot whose text is
    # built from a realistic-range formatted number rather than a fixed
    # table - each sample below is the longest string that plausible flight
    # data actually produces for that slot (not an arbitrary extreme value).
    for slot, sample in (
        (BARO_TEXT, "QNH29.92"),
        (PRESEL_MACH_TEXT, "P.780"),
        (ILS_TEXT, "109.50"),
        (LANDING_ELEV_TEXT, "ELEV-1000"),
        (DME_TEXT, "123.4NM"),
        (MACH_TEXT, ".620"),
    ):
        if len(sample) > slot.capacity:
            raise TolissPfdLayoutError(
                f"{slot.name!r} cannot hold {sample!r}: {len(sample)} cells "
                f"> capacity {slot.capacity}"
            )

    # 5. Render a normal frame, an all-missing frame, and extreme-value
    #    frames through the bounds-checking canvas - catches any drawing
    #    primitive that could run off the physical LCD.
    normal = {
        "ias_valid": 1.0, "alt_valid": 1.0,
        "att_valid": 1.0, "hdg_valid": 1.0,
        "ias": 250.0, "mach": 0.62, "altitude": 24500.0,
        "pitch": 3.5, "roll": -8.0, "vertical_speed": 800.0,
        "drift_angle": 2.0, "flight_path_angle": 2.5,
        "fd_pitch_cmd": 2.0, "fd_roll_cmd": -5.0, "fd_on": 1.0,
        "ap_on": 1.0, "athr_on": 1.0, "athr_thrust_mode": 4.0, "alpha_floor": 0.0,
        "target_speed": 260.0, "target_altitude": 30000.0, "target_altitude_type": 1.0,
        "target_heading": 275.0, "heading": 268.0,
        "v_ls": 172.0, "v_max": 340.0, "v_sw": 158.0, "v_green_dot": 210.0,
        "v1": 138.0, "v_r": 145.0, "v2": 150.0, "show_to_speeds": 1.0,
        "v_f": 195.0, "v_s": 205.0, "v_vfe_next": 215.0, "v_alpha_max": 150.0,
        "v_aprot": 165.0,
        "climb_cas_presel": 280.0, "cruise_cas_presel": 290.0, "cruise_mach_presel": 0.78,
        "baro_std": 0.0, "baro_unit": 1.0, "baro_value": 1013.0,
        "ils_on": 1.0, "ils_freq": 109.50, "ils_type": 1.0, "ils_slope": 3.0,
        "loc_dev": 0.2, "gs_dev": -0.3,
        "dme_distance": 12.4, "landing_elev": 610.0, "lateral_accel": 0.1,
    }
    variants = (
        normal,
        {},
        {key: 999999.0 for key in TOLISS_PFD_VALUE_KEYS},
        {key: -999999.0 for key in TOLISS_PFD_VALUE_KEYS},
        {**normal, "roll": 55.0, "pitch": -28.0, "baro_std": 1.0, "ils_on": 0.0, "fd_on": 0.0, "alpha_floor": 1.0},
        {**normal, "roll": -55.0, "pitch": 28.0, "altitude": 900.0, "ias": 95.0},
    )
    for values in variants:
        canvas = _BoundsCanvas()
        draw_toliss_pfd_frame(canvas, values)
        # A second draw through the live diff-engine wrapper on a canvas
        # that persists state, matching how the physical BB36 canvas
        # behaves - the second call exercises the dirty-box diff path (the
        # first call to draw_live_toliss_pfd always forces a full repaint).
        draw_live_toliss_pfd(canvas, values)
        draw_live_toliss_pfd(canvas, values)

    # 6. Confirm real labels actually reach the canvas (not just "did not
    #    raise") for a representative set of engagement/mode states - the
    #    positive-evidence counterpart to the bounds checks above.
    capture = _CaptureCanvas()
    draw_toliss_pfd_frame(capture, normal)
    seen = set(capture.texts)
    required = {
        "MAN CLB", "AP1", "A/THR", "250", "245", "00",
        "QNH1013", ".620", "P.780", "109.50", "12.4NM", "ELEV610",
        "260", "240",  # labelled speed and Airbus hundreds altitude ticks
    }
    missing = required - seen
    if missing:
        raise TolissPfdLayoutError(f"PFD required labels did not render: {sorted(missing)}")

    std_capture = _CaptureCanvas()
    draw_toliss_pfd_frame(std_capture, {**normal, "baro_std": 1.0})
    if "STD" not in set(std_capture.texts):
        raise TolissPfdLayoutError("PFD STD baro label did not render")

    floor_capture = _CaptureCanvas()
    draw_toliss_pfd_frame(floor_capture, {**normal, "alpha_floor": 1.0})
    if "A.FLOOR" not in set(floor_capture.texts):
        raise TolissPfdLayoutError("PFD A.FLOOR annunciation did not render")

    invalid_capture = _CaptureCanvas()
    draw_toliss_pfd_frame(invalid_capture, {
        **normal,
        "ias_valid": 0.0,
        "alt_valid": 0.0,
        "att_valid": 0.0,
        "hdg_valid": 0.0,
    })
    invalid_seen = set(invalid_capture.texts)
    required_invalid = {"SPD", "ALT", "ATT", "V/S", "HDG"}
    if not required_invalid.issubset(invalid_seen):
        raise TolissPfdLayoutError(
            "PFD invalid-source flags did not render: "
            f"{sorted(required_invalid - invalid_seen)}"
        )
    required_invalid_shapes = {
        "INVALID_SPEED_SHAPE", "INVALID_ATTITUDE_SHAPE",
        "INVALID_ALTITUDE_SPLIT_SHAPE", "INVALID_VS_TAPERED_SHAPE",
        "INVALID_HEADING_SHAPE",
    }
    if not required_invalid_shapes.issubset(set(invalid_capture.features)):
        raise TolissPfdLayoutError(
            "PFD invalid silhouettes regressed: "
            f"{sorted(required_invalid_shapes - set(invalid_capture.features))}"
        )

    native_fma = _CaptureCanvas()
    draw_toliss_pfd_frame(native_fma, {
        **normal,
        "fma1_green": "SPEED   G/S     LOC             AP1 ",
        "fma2_blue": "        ALT                     ",
        "fma2_white": "                           1FD2 ",
        "fma3_white": "                           A/THR",
    })
    if "NATIVE_TOLISS_FMA" not in native_fma.features:
        raise TolissPfdLayoutError("PFD did not use ToLiss's native FMA layers")

    # 7. The first-pass renderer subscribed to VR but never painted it, and
    # had no V1/V2 subscription at all.  Exercise an actual take-off-scale
    # frame so all three symbols must reach the canvas, then prove ToLiss's
    # explicit phase flag removes them again.  This guard prevents a future
    # refactor from leaving a subscribed-but-invisible value behind.
    takeoff = {
        **normal,
        "ias": 135.0,
        "v1": 138.0,
        "v_r": 145.0,
        "v2": 150.0,
        "show_to_speeds": 1.0,
        "v_f": 0.0,
        "v_s": 0.0,
        "v_green_dot": 0.0,
        "v_vfe_next": 0.0,
    }
    takeoff_capture = _CaptureCanvas()
    draw_toliss_pfd_frame(takeoff_capture, takeoff)
    required_takeoff = {"V1", "VR", "V2"}
    if not required_takeoff.issubset(set(takeoff_capture.features)):
        raise TolissPfdLayoutError(
            "PFD take-off speed symbols did not render: "
            f"{sorted(required_takeoff - set(takeoff_capture.features))}"
        )
    hidden_capture = _CaptureCanvas()
    draw_toliss_pfd_frame(hidden_capture, {**takeoff, "show_to_speeds": 0.0})
    if required_takeoff.intersection(hidden_capture.features):
        raise TolissPfdLayoutError("PFD take-off symbols ignored show_to_speeds=0")

    flap_capture = _CaptureCanvas()
    draw_toliss_pfd_frame(
        flap_capture,
        {
            **normal,
            "ias": 190.0,
            "v_f": 195.0,
            "v_s": 205.0,
            "show_to_speeds": 0.0,
        },
    )
    if not {"F_SPEED", "S_SPEED"}.issubset(set(flap_capture.features)):
        raise TolissPfdLayoutError("PFD flap-retraction F/S cues did not render")

    ils_capture = _CaptureCanvas()
    draw_toliss_pfd_frame(ils_capture, normal)
    if ils_capture.features.count("ILS_DEVIATION_DIAMOND") != 2:
        raise TolissPfdLayoutError("PFD LOC/G-S deviations are not both diamonds")


__all__ = (
    "TOLISS_PFD_VALUE_KEYS",
    "TolissPfdLayoutError",
    "assert_layout_contract",
    "draw_live_toliss_pfd",
    "draw_toliss_pfd_frame",
    "invalidate",
)
