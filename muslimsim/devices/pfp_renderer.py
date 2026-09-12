"""Native 640x480 Boeing-style PFD renderer for the WinCtrl PFP.

The PFP's native compact bitmap font has fixed 17x29 opaque cells.  This module
therefore uses an explicit zone contract for every text run.  Value glyphs are
left-aligned inside those cells and may overlap only after the preceding
glyph's visible ink has ended; this gives compact aircraft-like spacing
without the chopped letters produced by the earlier blind-overlap experiment.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import time
from typing import Any, Mapping, Sequence, Tuple

from muslimsim.devices.pfp_bank_line_font import (
    BANK_LINE_CELL_HEIGHT,
    BANK_LINE_CELL_WIDTH,
    BANK_LINE_FONT_IDS,
    bank_line_glyph_rectangles,
    bank_rung_runs,
    pfd_number_glyph_rectangles,
)


WIDTH = 640
HEIGHT = 480
FONT_CELL_WIDTH = 17
FONT_CELL_HEIGHT = 29
FONT_ID = 6
PFD_TEXT_FONT_ID = 5
PFD_NUMBER_FONT_ID = 3

BLACK = (6, 7, 13)
WHITE = (245, 246, 249)
CYAN = (0, 225, 255)
GREEN = (0, 255, 82)
MAGENTA = (255, 99, 255)
AMBER = (255, 183, 0)
RED = (255, 64, 52)          # limit-speed barber poles
TAPE_GREY = (64, 66, 71)
FMA_GREY = (39, 40, 46)
VS_GREY = (52, 53, 58)
SKY = (20, 101, 211)
EARTH = (121, 65, 20)


try:  # Optional: static shapes baked into spare glyph codes of native font 6.
    from muslimsim.devices import pfp_shape_tiles as _SHAPE_TILES
except Exception:  # pragma: no cover - the renderer must work without them
    _SHAPE_TILES = None

try:  # The notched V/S silhouette is appended only to native font slot 3.
    from muslimsim.devices import pfp_right_strip_tiles as _RIGHT_STRIP_TILES
except Exception:  # pragma: no cover - the exact-row fallback remains valid
    _RIGHT_STRIP_TILES = None


class PfdLayoutError(RuntimeError):
    """A renderer change would place content outside its protected PFD zone."""


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def intersects(self, other: "Rect") -> bool:
        return not (
            self.right <= other.x
            or other.right <= self.x
            or self.bottom <= other.y
            or other.bottom <= self.y
        )


@dataclass(frozen=True)
class TextSlot:
    """A native-font text zone with enough space for its full opaque cells."""

    name: str
    rect: Rect
    align: str = "left"

    @property
    def capacity(self) -> int:
        return self.rect.width // FONT_CELL_WIDTH

    def position_for(self, text: str) -> Tuple[int, int]:
        if len(text) > self.capacity:
            raise PfdLayoutError(
                f"{self.name} cannot hold {text!r}: {len(text)} cells > "
                f"{self.capacity}"
            )
        run_width = len(text) * FONT_CELL_WIDTH
        if self.align == "center":
            x = self.rect.x + (self.rect.width - run_width) // 2
        elif self.align == "right":
            x = self.rect.right - run_width
        else:
            x = self.rect.x
        if x < self.rect.x or x + run_width > self.rect.right:
            raise PfdLayoutError(f"{self.name} computed an unsafe text position")
        return x, self.rect.y


# This coordinate contract is deliberately small and readable.  It prevents a
# future cosmetic change from quietly letting a native opaque glyph run over a
# tape, the attitude display, or the vertical-speed scale.
# The PFP bezel masks a small strip at the physical left edge.  Start the MCP
# speed well inside that guard area so the leading digit of values such as 200
# is always visible on the actual LCD.
SELECTED_SPEED = TextSlot("selected speed", Rect(50, 5, 51, FONT_CELL_HEIGHT), "left")
SELECTED_ALTITUDE = TextSlot("selected altitude", Rect(504, 5, 102, FONT_CELL_HEIGHT), "right")
FMA_SPEED = TextSlot("FMA speed", Rect(76, 38, 170, FONT_CELL_HEIGHT), "center")
FMA_LATERAL = TextSlot("FMA lateral", Rect(250, 38, 170, FONT_CELL_HEIGHT), "center")
FMA_VERTICAL = TextSlot("FMA vertical", Rect(421, 38, 185, FONT_CELL_HEIGHT), "center")
COMMAND = TextSlot("command status", Rect(251, 70, 138, FONT_CELL_HEIGHT), "center")

SPEED_TAPE = Rect(90, 72, 70, 328)
ALTITUDE_TAPE = Rect(480, 72, 72, 328)
SPEED_TAPE_LABEL_WIDTH = FONT_CELL_WIDTH * 3
# The speed tape's inner strip, reading outward: three cells of numbers, the
# tick marks, then the awareness bands against the tape's inboard edge, which
# is where the aircraft draws them.
SPEED_LABEL_X = 92
SPEED_TICK_X = 144
SPEED_TICK_WIDTH = 8
SPEED_BAND_X = 153
SPEED_BAND_WIDTH = 7
SPEED_BUG_LINE_X = 145          # V-speed and flap bugs reach into the gutter
SPEED_BUG_LINE_WIDTH = 13
# The gutter inboard of the tape belongs to the trend vector, so the bug
# labels sit outboard of the tape instead.  The aircraft puts them inboard,
# but at this cell size both cannot have the same 34 pixels, and a label that
# has to be cut to one character stops being a label.
SPEED_BUG_LABEL_X = 56
SPEED_BUG_LABEL_WIDTH = FONT_CELL_WIDTH * 2
# The trend vector: where the speed will be in ten seconds at the present
# acceleration, which is the Boeing projection.
SPEED_TREND_X = 164
SPEED_TREND_SECONDS = 10.0
SPEED_TREND_MIN_KNOTS = 4.0     # below this the aircraft shows nothing
SPEED_TREND_STEP = 0.5          # round the tip, so noise cannot flicker it
# The flap lever's detent, which is what the aircraft labels its flap
# manoeuvre bug with.  Zibo reports the lever as a ratio of full travel.
FLAP_DETENTS = (
    (0.0, "UP"), (0.125, "1"), (0.25, "2"), (0.375, "5"), (0.5, "10"),
    (0.625, "15"), (0.75, "25"), (0.875, "30"), (1.0, "40"),
)
BARBER_PITCH = 8                # red dash, then an equal gap
BARBER_DASH = 4
ALTITUDE_TAPE_LABEL_WIDTH = FONT_CELL_WIDTH * 4
TAPE_TEXT_TOP_OFFSET = 12
TAPE_TEXT_BOTTOM_OFFSET = FONT_CELL_HEIGHT - TAPE_TEXT_TOP_OFFSET
# The live boxes deliberately overlap their own tapes, exactly like the real
# 737 PFD.  Their shaped tape-facing edges are drawn below; the text cells stay
# completely inside the black interior so the compact font can never run into
# the sky/earth display or the V/S scale.
SPEED_WINDOW = Rect(44, 200, 100, 52)
SPEED_WINDOW_POINT = 16          # chevron reaching the live-speed line
# Keep the established nipple and left edge fixed.  Only the outboard wall is
# pulled another twelve pixels inward (about two physical millimetres on the
# PFP LCD).  The compact rolling cells still end at x=551.
ALTITUDE_WINDOW = Rect(480, 200, 86, 52)
ALTITUDE_WINDOW_POINT = 14
ALTITUDE_WINDOW_BODY_X = ALTITUDE_WINDOW.x + ALTITUDE_WINDOW_POINT
# Two static cells and one rolling cell, exactly like the 737 readout.  The
# drum pitch is deliberately shorter than a full font cell: the compact
# cockpit glyph sits in the middle of its cell, so a full-cell step would roll
# only blank cell edges through the window instead of the next digit.
SPEED_VALUE = TextSlot("live speed", Rect(71, 211, 34, FONT_CELL_HEIGHT), "right")
SPEED_DRUM = Rect(105, 204, FONT_CELL_WIDTH, 44)
SPEED_DRUM_PITCH = 26          # one ink height plus a gap, so digits never touch
# The 737 altitude readout: a ten-thousands position that carries a green and
# black hatch below 10,000 ft, two fixed digits, and a rolling pair that steps
# in twenty-foot increments.  The rolling pair sits wholly over the tape so its
# overspill can be trimmed back in one colour.
ALTITUDE_DIGIT_PITCH = 10
ALTITUDE_VALUE = TextSlot("live altitude", Rect(504, 211, 51, FONT_CELL_HEIGHT))
ALTITUDE_TEN_THOUSANDS = Rect(494, 211, 10, FONT_CELL_HEIGHT)
ALTITUDE_FIXED_X = 504
ALTITUDE_DRUM = Rect(524, 204, ALTITUDE_DIGIT_PITCH + FONT_CELL_WIDTH, 44)
ALTITUDE_DRUM_PITCH = 26
ALTITUDE_DRUM_STEP = 20.0
# The 737 vertical-speed scale: a grey wedge with chamfered outer corners,
# numbers down its inner edge and tick dashes outboard of them.  There is no
# ruler line on the real display.
VERTICAL_SPEED_WEDGE = Rect(566, 116, 68, 220)
VERTICAL_SPEED_CHAMFER = 34
VERTICAL_SPEED_LABELS = Rect(570, 116, FONT_CELL_WIDTH, 220)
VERTICAL_SPEED_TICK_X = 590
# The V/S silhouette remains at its established position while the altitude
# wall moves inward.  Twenty black pixels now separate the two shapes.
ALTITUDE_VS_GAP = 20
VERTICAL_SPEED_NOTCH_X = ALTITUDE_WINDOW.right + ALTITUDE_VS_GAP
VERTICAL_SPEED_NOTCH_SLOPE = VERTICAL_SPEED_NOTCH_X - VERTICAL_SPEED_WEDGE.x
# Keep the V/S needle's inboard end at its established position.  Shortening
# the altitude readout must not stretch or shift the independent V/S needle.
VERTICAL_SPEED_NEEDLE_X = 578
VERTICAL_SPEED_PIVOT_X = 626
VERTICAL_SPEED_PIVOT_Y = 226

# The simulator's attitude sphere runs behind the inboard edge of the altitude
# readout rather than ending at the box.  Expanding into the two proven black
# gutters restores that proportion while staying clear of both tape bodies.
# The altitude window is intentionally painted later and owns its overlap.
ATTITUDE = Rect(184, 100, 272, 252)
COMPASS_CENTER_X = 320
# Keep the same visible width at the bottom, but lower the arc's apex.  This
# produces the shallow lower-heading arc in the reference PFD instead of a
# tall semicircle climbing toward the attitude display.
COMPASS_CENTER_Y = 583
COMPASS_RADIUS = 193
COMPASS_TOP = COMPASS_CENTER_Y - COMPASS_RADIUS
COMPASS_TEXT = TextSlot("heading", Rect(286, COMPASS_TOP - 1, 69, FONT_CELL_HEIGHT), "center")
MAG_LABEL = TextSlot("magnetic label", Rect(363, COMPASS_TOP + 61, 51, FONT_CELL_HEIGHT), "left")
SELECTED_HEADING = TextSlot(
    "selected heading", Rect(210, COMPASS_TOP + 61, 68, FONT_CELL_HEIGHT), "right"
)
# Keep the number and its unit in one native text run.  Separate opaque native
# cells made the boundary between 1013 and HPA look almost two digits wide.
BARO_VALUE_UNIT = TextSlot(
    "barometer value and unit",
    Rect(ALTITUDE_TAPE.x, 404, ALTITUDE_TAPE.width, FONT_CELL_HEIGHT),
    "right",
)
BARO_STD = TextSlot("baro std", Rect(494, 404, 51, FONT_CELL_HEIGHT), "left")
# The barometric setting owns the first line directly beneath the altitude
# tape.  Approach minimums use the next line below it, so RADIO never takes
# the BARO/HPA position.
# Ten cells: RADIO 200 needs nine, and a five-figure barometric setting needs
# ten.  At nine the longest value would have been silently dropped, which is
# the same fault the barometric unit had.
MINIMUMS_LABEL = TextSlot(
    "minimums",
    Rect(ALTITUDE_TAPE.right - 170, 435, 170, FONT_CELL_HEIGHT),
    "right",
)
# Align the Mach line and LS/frequency line with the left edge of the speed
# tape.  This also keeps the leading M visible instead of losing it behind the
# physical left bezel and leaving only .00 on the panel.
MACH_LABEL = TextSlot(
    "mach", Rect(SPEED_TAPE.x, 404, 119, FONT_CELL_HEIGHT), "left"
)
ILS_LABEL = TextSlot(
    "ILS identifier", Rect(SPEED_TAPE.x, 435, 153, FONT_CELL_HEIGHT), "left"
)
RADIO_ALT_LABEL = TextSlot("radio altitude", Rect(286, 314, 68, FONT_CELL_HEIGHT), "center")
MARKER_LABEL = TextSlot("marker beacon", Rect(380, 70, 51, FONT_CELL_HEIGHT), "center")
FMA_ARMED_LEFT = TextSlot("FMA armed lateral", Rect(76, 70, 136, FONT_CELL_HEIGHT), "center")
FMA_ARMED_RIGHT = TextSlot("FMA armed vertical", Rect(424, 70, 153, FONT_CELL_HEIGHT), "center")

LOCALIZER_Y = 336
GLIDESLOPE_X = 434
ILS_DOT_SPACING = 29


FMA_SPEED_LABELS = {
    1: "ARM",
    2: "N1",
    3: "MCP SPD",
    4: "FMC SPD",
    5: "GA",
    6: "THR HLD",
    7: "RETARD",
}
FMA_LATERAL_LABELS = {
    1: "HDG SEL",
    2: "VOR LOC",
    3: "LNAV",
    4: "ROLLOUT",
    5: "FAC",
    6: "BCRS",
}
FMA_VERTICAL_LABELS = {
    1: "V/S",
    2: "MCP SPD",
    3: "ALT ACQ",
    4: "ALT HOLD",
    5: "G/S",
    6: "FLARE",
    7: "G/P",
    8: "VNAV SPD",
    9: "VNAV PTH",
    10: "VNAV ALT",
    11: "TO/GA",
}


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _number(value: Any, width: int, unavailable: str) -> str:
    if not _finite(value):
        return unavailable
    numeric = int(round(float(value)))
    if numeric < 0:
        return unavailable
    if numeric > (10 ** width) - 1:
        return "HIGH"[:width]
    return str(numeric).rjust(width)


def _speed(value: Any) -> str:
    return _number(value, 3, "---")


def _speed_tape(value: Any) -> str:
    if not _finite(value) or float(value) < 0.0 or float(value) > 999.0:
        return ""
    return _speed(value)


def _altitude(value: Any) -> str:
    """Use four safe cells without silently changing the indicated altitude."""
    if not _finite(value):
        return "----"
    numeric = int(round(float(value)))
    if numeric < 0:
        # Aerodromes below sea level, and a low QNH, both put the tape and the
        # readout below zero.  Blanking them there would hide a real altitude.
        return f"{numeric}".rjust(4) if numeric >= -999 else "----"
    if numeric <= 9999:
        return str(numeric).rjust(4)
    # On a Boeing tape a three-digit flight-level-style readout is conventional
    # above 10,000 ft.  The leading blank keeps it centred in the four-cell box.
    if numeric <= 99900:
        return str(int(round(numeric / 100.0))).rjust(4)
    return "HIGH"


def _mach(value: Any) -> str:
    if not _finite(value) or float(value) < 0.0 or float(value) >= 10.0:
        return "---"
    return f"{float(value):.2f}".lstrip("0")[:3]


def _baro(value: Any, use_hpa: bool, std: bool) -> Tuple[str, str]:
    if std:
        return "STD", ""
    if not _finite(value):
        return "", ""
    if use_hpa:
        hpa = int(round(float(value) * 33.8639))
        return (str(hpa).rjust(4) if 800 <= hpa <= 1100 else "----"), "HPA"
    in_hg = f"{float(value):.2f}"
    return (in_hg if len(in_hg) <= 5 else "-----"), "IN"


def _fma(value: Any, labels: Mapping[int, str]) -> str:
    if not _finite(value):
        return ""
    return labels.get(int(round(float(value))), "")


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _heading_delta(target: float, live: float) -> float:
    return (target - live + 540.0) % 360.0 - 180.0


def _heading_label(heading: float) -> str:
    tens = int(round(heading / 10.0)) % 36
    return {0: "N", 9: "E", 18: "S", 27: "W"}.get(tens, f"{tens:02d}")


def _bug_y(
    live: Any,
    target: Any,
    pixels_per_unit: float,
    datum_y: int,
    edge_margin: int = 10,
) -> int | None:
    if not _finite(live) or not _finite(target):
        return None
    y = datum_y - (float(target) - float(live)) * pixels_per_unit
    # Each tape marker has its own height.  Keep its complete outline inside
    # the visible scale even when an MCP target is far off-scale.
    return int(round(_clamp(y, SPEED_TAPE.y + edge_margin, SPEED_TAPE.bottom - edge_margin)))


def _stamp_shape_tiles(canvas: Any, shape: Any, colour: Tuple[int, int, int]) -> None:
    """Stamp one generated shape with the font slot recorded beside it."""
    font_id = int(getattr(shape, "font_id", FONT_ID))
    for x, y, run in shape.runs:
        canvas.text(x, y, run, colour, BLACK, font_id)
    if shape.remainder:
        canvas.colour(*colour)
        for x, y, width, height in shape.remainder:
            canvas.fill(x, y, width, height)


def _draw_tiles(canvas: Any, name: str, colour: Tuple[int, int, int]) -> bool:
    """Paint a slot-6 static shape; False if no tiles are available.

    A native text run costs about one byte per 17x29 cell against twenty-five
    bytes for one rectangle, so a shape that never changes is far cheaper to
    stamp out of spare glyph codes than to rasterise every frame.
    """
    if _SHAPE_TILES is None:
        return False
    shape = getattr(_SHAPE_TILES, name, None)
    if not shape:
        return False
    _stamp_shape_tiles(canvas, shape, colour)
    return True


def _draw_outline(canvas: Any, rect: Rect, thickness: int = 2) -> None:
    canvas.fill(rect.x, rect.y, rect.width, thickness)
    canvas.fill(rect.x, rect.bottom - thickness, rect.width, thickness)
    canvas.fill(rect.x, rect.y, thickness, rect.height)
    canvas.fill(rect.right - thickness, rect.y, thickness, rect.height)


def _draw_text_with_font(
    canvas: Any,
    slot: TextSlot,
    value: str,
    foreground: Tuple[int, int, int],
    background: Tuple[int, int, int],
    font_id: int,
) -> None:
    if not value:
        return
    try:
        x, y = slot.position_for(value)
    except PfdLayoutError:
        # Every supplied value has a semantic formatter.  An unknown future
        # label must disappear instead of being chopped over another zone.
        return
    canvas.text(x, y, value, foreground, background, int(font_id))


def _draw_text(
    canvas: Any,
    slot: TextSlot,
    value: str,
    foreground: Tuple[int, int, int],
    background: Tuple[int, int, int],
) -> None:
    """Draw the PFD-only smaller artwork from native font slot 5."""
    _draw_text_with_font(
        canvas, slot, value, foreground, background, PFD_TEXT_FONT_ID
    )


def _draw_number_text(
    canvas: Any,
    slot: TextSlot,
    value: str,
    foreground: Tuple[int, int, int],
    background: Tuple[int, int, int],
) -> None:
    """Draw tightly packed PFD values with the proven opaque slot-3 cells.

    The recovery frame keeps one low-cost native run.  Precision frames use
    the left-aligned glyph resource and advance each cell only after its ink,
    so digits, decimal points and letters read as one compact value without
    either clipping ink or changing the controller's fixed 17-pixel header.
    """
    if not value:
        return
    if not _pack_value_slot(slot):
        _draw_text_with_font(
            canvas, slot, value, foreground, background, PFD_NUMBER_FONT_ID
        )
        return

    cells = _packed_number_cells(slot, value)
    if cells is None:
        return
    for x, character in cells:
        canvas.text(
            x,
            slot.rect.y,
            character,
            foreground,
            background,
            PFD_NUMBER_FONT_ID,
        )


def _packed_number_cells(
    slot: TextSlot,
    value: str,
) -> list[Tuple[int, str]] | None:
    """Return the exact compact slot-3 cell origins used on the real panel."""
    visible = _tight_visible(value)
    advances = [_packed_value_advance(character) for character in visible]
    run_width = sum(advances[:-1]) + FONT_CELL_WIDTH if advances else 0
    if run_width > slot.rect.width:
        return None
    if slot.align == "center":
        x = slot.rect.x + (slot.rect.width - run_width) // 2
    elif slot.align == "right":
        x = slot.rect.right - run_width
    else:
        x = slot.rect.x
    cells: list[Tuple[int, str]] = []
    for index, character in enumerate(value):
        cells.append((x, character))
        if index + 1 < len(value):
            x += advances[index]
    return cells


# The proven native cell remains 17 pixels wide.  Slot 3 retains the earlier
# lower-case aliases so saved layouts and unit joins remain compatible; the
# rebuilt resource now left-aligns all value ink, and staged precision drawing
# applies safe per-character advances to the complete visible value.
_TIGHT_DIGIT_ALIASES = "abcdefghij"
_TIGHT_LETTER_ALIASES = {"H": "k", "I": "l"}
_TIGHT_ALTITUDE_MINUS_ALIAS = "x"
_TIGHT_ALIAS_VISIBLE = {
    **{alias: str(digit) for digit, alias in enumerate(_TIGHT_DIGIT_ALIASES)},
    **{alias: visible for visible, alias in _TIGHT_LETTER_ALIASES.items()},
    _TIGHT_ALTITUDE_MINUS_ALIAS: "-",
}

# Visible widths of the 14-point Bahnschrift micro glyphs after the builder
# left-aligns them.  One clear pixel follows each glyph before the next opaque
# cell begins.  The last cell keeps its full 17-pixel background, so every
# packed run remains safe inside its declared TextSlot.
_PACKED_VALUE_WIDTHS = {
    **dict(zip("0123456789", (6, 4, 7, 7, 8, 6, 7, 7, 7, 7))),
    **dict(zip(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        (9, 8, 7, 8, 7, 7, 8, 8, 2, 6, 8, 7, 9,
         8, 8, 8, 8, 8, 8, 8, 8, 8, 12, 8, 9, 7),
    )),
    ".": 3,
    "-": 5,
    "/": 7,
    "+": 7,
    "%": 9,
    " ": 4,
}


def _packed_value_advance(character: str) -> int:
    """Safe visual advance for one left-aligned micro glyph."""
    return _PACKED_VALUE_WIDTHS.get(character.upper(), 9) + 1


def _pack_value_slot(slot: TextSlot) -> bool:
    """Stage compact value groups so no refinement overruns BB36's queue."""
    if slot is BARO_VALUE_UNIT:
        return True
    name = slot.name
    if name in {
        "ILS identifier",
        "mach",
        "minimums",
        "magnetic label",
        "selected heading",
    }:
        return _packed_value_phase >= 2
    if name in {
        "selected speed",
        "selected altitude",
        "heading",
        "radio altitude",
    } or name.startswith("speed bug"):
        return _packed_value_phase >= 2
    return _packed_value_phase >= 3


def _tight_join(left: str, right: str) -> str:
    if not left:
        return right
    if not right:
        return left
    first = right[0]
    if first.isdigit():
        first = _TIGHT_DIGIT_ALIASES[int(first)]
    else:
        first = _TIGHT_LETTER_ALIASES.get(first, first)
    return left + first + right[1:]


def _tight_visible(value: str) -> str:
    """Return the characters a slot-3 alias run visibly paints."""
    return "".join(_TIGHT_ALIAS_VISIBLE.get(character, character) for character in value)


def _draw_large_text(
    canvas: Any,
    slot: TextSlot,
    value: str,
    foreground: Tuple[int, int, int],
    background: Tuple[int, int, int],
) -> None:
    """Retain the proven larger font for ND and coded systems pages."""
    _draw_text_with_font(canvas, slot, value, foreground, background, FONT_ID)


def _slot(name: str, x: int, y: int, width: int, align: str = "left") -> TextSlot:
    return TextSlot(name, Rect(x, y, width, FONT_CELL_HEIGHT), align)


ATTITUDE_CORNER_RADIUS = 30.0
BANK_SCALE_RADIUS = 116.0
# Differential drawing: the grid the changed area is measured in. Complete
# frames are lifecycle recovery only (page entry/reconnect/standby return).
DIRTY_CELL = 24           # measured: 8/12/16/24 px cells cost 90/83/75/77
                          # reports in cruise and 256/231/229/215 in a turn
# Shared defaults retained for the ND and systems-page renderers.  The PFD no
# longer uses either value for timed healing; its complete repaints are
# lifecycle-only.
FULL_REPAINT_FRAMES = 120
FULL_REPAINT_SECONDS = 1.5
# Live attitude and heading never hold still: they jitter by hundredths of a
# degree even in level flight.  Drawn straight, that repaints the whole
# attitude field every frame for movement far below one pixel.  Rounding them
# to a step worth less than a pixel means the display redraws when the
# aeroplane actually moves, and holds still when it does not.
ATTITUDE_STEP = 0.2       # degrees; 1 pixel of pitch, and less of bank
HEADING_STEP = 0.25       # degrees; under a pixel on the heading arc
QUANTISED_VALUES = {
    "pitch": ATTITUDE_STEP,
    "roll": ATTITUDE_STEP,
    "fd_pitch": ATTITUDE_STEP,
    "fd_roll": ATTITUDE_STEP,
    "heading": HEADING_STEP,
    "target_heading": HEADING_STEP,
    "fpv_horizontal": ATTITUDE_STEP,
    "fpv_vertical": 1.0,
    "stall_pitch": ATTITUDE_STEP,
    "runway_x": 1.0,
    "runway_y": 1.0,
}
# Edge-quality controls.  The panel bills roughly one millisecond per native
# HID report, so smoother edges cost frame rate.  These two constants are the
# only place to trade one against the other.
BLEND_HORIZON_EDGE = True   # one blended run over the pixels the horizon crosses
# While the aeroplane is actually rolling or pitching, the whole attitude field
# has to be resent, and at a millisecond per report that is what makes a
# manoeuvre stutter.  Above this rate of change the large sky/earth field moves
# in two-pixel bands and omits its blended boundary.  Pitch lines stay exact
# during normal motion; only a periodic complete healing frame is economical,
# and its next differential frame restores the exact line geometry.
MOTION_DEGREES_PER_FRAME = 0.5
MOTION_LADDER_MIN_STEP = 9
MOTION_HORIZON_ROW_STEP = 2
_moving = False             # set once per frame by draw_live_pfd
_recovery_frame = False     # one economical complete frame, then exact lines
_packed_value_phase = 3     # staged after recovery; direct offline drawing is exact
# One intermediate colour along the sky/earth boundary.  The panel can only
# fill rectangles, so a single blended run over the pixels the horizon truly
# crosses is what takes the hard staircase off the edge.
# The supplied clean PFD reference uses a distinct white horizon separator.
# It is not a texture or image: the renderer still draws it from native fills.
HORIZON_EDGE = WHITE


def _attitude_row_span(y: int) -> Tuple[float, float]:
    """Exact left and right edge of the rounded attitude field on one row."""
    radius = ATTITUDE_CORNER_RADIUS
    centre = y + 0.5
    if centre < ATTITUDE.y + radius:
        offset = (ATTITUDE.y + radius) - centre
    elif centre > ATTITUDE.bottom - radius:
        offset = centre - (ATTITUDE.bottom - radius)
    else:
        offset = 0.0
    inset = radius - math.sqrt(max(0.0, radius * radius - offset * offset))
    return ATTITUDE.x + inset, ATTITUDE.right - inset


def _rounded_bounds(mid_x: float) -> Tuple[int, int]:
    """Top and bottom of the rounded attitude field at one column."""
    radius = ATTITUDE_CORNER_RADIUS
    distance = min(mid_x - ATTITUDE.x, ATTITUDE.right - mid_x)
    if distance >= radius:
        inset = 0
    else:
        delta = distance - radius
        inset = int(round(radius - math.sqrt(max(0.0, radius * radius - delta * delta))))
    return ATTITUDE.y + inset, ATTITUDE.bottom - inset


def _merge_rows(rows: list[Tuple[int, int, int]]) -> list[Tuple[int, int, int, int]]:
    """Collapse single-pixel rows with the same span into taller rectangles.

    The straight middle of a shape becomes one native command again, so exact
    one-pixel edges cost display traffic only where a shape is actually
    curved or sloped.
    """
    merged: list[Tuple[int, int, int, int]] = []
    for x, y, width in rows:
        if merged:
            last_x, last_y, last_width, last_height = merged[-1]
            if last_x == x and last_width == width and last_y + last_height == y:
                merged[-1] = (last_x, last_y, last_width, last_height + 1)
                continue
        merged.append((x, y, width, 1))
    return merged


def _emit_rows(canvas: Any, colour: Tuple[int, int, int], rows: list[Tuple[int, int, int]]) -> None:
    """Draw one colour's rows as merged rectangles in a single native pass."""
    if not rows:
        return
    canvas.colour(*colour)
    for x, y, width, height in _merge_rows(rows):
        canvas.fill(x, y, width, height)


def _sloped_runs(start_x: int, end_x: int, y_at) -> list[Tuple[int, int, int]]:
    """Rasterise a sloped line as the longest possible constant-y runs.

    A level line costs one native fill; a steeply banked one costs a fill per
    pixel row.  The staircase is therefore always one pixel high, and the
    traffic is proportional to how far the line actually climbs.
    """
    runs: list[Tuple[int, int, int]] = []
    if end_x <= start_x:
        return runs
    run_start = start_x
    y = int(round(y_at(start_x + 0.5)))
    for x in range(start_x + 1, end_x):
        next_y = int(round(y_at(x + 0.5)))
        if next_y != y:
            runs.append((run_start, x - run_start, y))
            run_start, y = x, next_y
    runs.append((run_start, end_x - run_start, y))
    return runs


def _straight_line_rects(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    thickness: int = 1,
) -> list[Tuple[int, int, int, int]]:
    """Rasterise one unbroken angled segment along its major axis.

    This is used for the short attitude marks whose former chain of square
    blocks looked dotted at bank.  Consecutive pixels with the same minor
    coordinate are merged into one native rectangle, preserving a mathematically
    straight endpoint-to-endpoint line without paying one command per pixel.
    """
    thickness = max(1, int(thickness))
    rectangles: list[Tuple[int, int, int, int]] = []
    if abs(x1 - x0) >= abs(y1 - y0):
        if x1 < x0:
            x0, y0, x1, y1 = x1, y1, x0, y0
        start, end = int(round(x0)), int(round(x1))
        if end <= start:
            return [(start, int(round(y0)) - thickness // 2, 1, thickness)]
        run_start = start
        current = int(round(y0))
        for x in range(start + 1, end + 1):
            fraction = (x - x0) / (x1 - x0)
            value = int(round(y0 + (y1 - y0) * fraction))
            if value != current:
                rectangles.append(
                    (run_start, current - thickness // 2, x - run_start, thickness)
                )
                run_start, current = x, value
        rectangles.append(
            (run_start, current - thickness // 2, end - run_start + 1, thickness)
        )
        return rectangles

    if y1 < y0:
        x0, y0, x1, y1 = x1, y1, x0, y0
    start, end = int(round(y0)), int(round(y1))
    if end <= start:
        return [(int(round(x0)) - thickness // 2, start, thickness, 1)]
    run_start = start
    current = int(round(x0))
    for y in range(start + 1, end + 1):
        fraction = (y - y0) / (y1 - y0)
        value = int(round(x0 + (x1 - x0) * fraction))
        if value != current:
            rectangles.append(
                (current - thickness // 2, run_start, thickness, y - run_start)
            )
            run_start, current = y, value
    rectangles.append(
        (current - thickness // 2, run_start, thickness, end - run_start + 1)
    )
    return rectangles


def _solid_angled_line_rects(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    thickness: int = 1,
) -> list[Tuple[int, int, int, int]]:
    """Rasterise one continuous rotated bar instead of a chain of blocks.

    The segment is treated as a true rectangle with its thickness measured
    perpendicular to the requested angle.  Scanline filling then gives every
    LCD row one unbroken span, including at 45 degrees and on steep slopes.
    Integer drawing coordinates are shifted to pixel centres before the
    polygon is sampled, avoiding the corner-only contacts that made the old
    pitch marks look like diamonds.
    """
    dx, dy = float(x1) - float(x0), float(y1) - float(y0)
    length = math.hypot(dx, dy)
    if length < 0.001:
        size = max(1, int(thickness))
        return [(int(round(x0)), int(round(y0)), size, size)]

    tangent_x, tangent_y = dx / length, dy / length
    normal_x, normal_y = -tangent_y, tangent_x
    # Slightly more than half a diagonal pixel makes 1-pixel strokes
    # edge-connected at exactly 45 degrees instead of touching only at their
    # corners and looking like a string of diamonds.
    half = max(0.72, max(1, int(thickness)) / 2.0)
    cap = 0.5
    start_x = float(x0) + 0.5 - cap * tangent_x
    start_y = float(y0) + 0.5 - cap * tangent_y
    end_x = float(x1) + 0.5 + cap * tangent_x
    end_y = float(y1) + 0.5 + cap * tangent_y
    vertices = (
        (start_x + half * normal_x, start_y + half * normal_y),
        (end_x + half * normal_x, end_y + half * normal_y),
        (end_x - half * normal_x, end_y - half * normal_y),
        (start_x - half * normal_x, start_y - half * normal_y),
    )

    rows: list[Tuple[int, int, int]] = []
    first_y = int(math.floor(min(point[1] for point in vertices)))
    last_y = int(math.ceil(max(point[1] for point in vertices)))
    for y in range(first_y, last_y):
        scan_y = y + 0.5
        intersections: list[float] = []
        for index, (edge_x0, edge_y0) in enumerate(vertices):
            edge_x1, edge_y1 = vertices[(index + 1) % len(vertices)]
            if edge_y0 == edge_y1:
                continue
            low_y, high_y = sorted((edge_y0, edge_y1))
            if not (low_y <= scan_y < high_y):
                continue
            fraction = (scan_y - edge_y0) / (edge_y1 - edge_y0)
            intersections.append(edge_x0 + fraction * (edge_x1 - edge_x0))
        if len(intersections) < 2:
            continue
        left, right = min(intersections), max(intersections)
        first_x = int(math.ceil(left - 0.5 - 1e-9))
        last_x = int(math.floor(right - 0.5 + 1e-9))
        if last_x < first_x:
            midpoint = int(round((left + right) / 2.0 - 0.5))
            first_x = last_x = midpoint
        rows.append((first_x, y, last_x - first_x + 1))
    return _merge_rows(rows)


def _coalesce_line_rects(
    rectangles: Sequence[Tuple[int, int, int, int]],
    maximum: int,
) -> list[Tuple[int, int, int, int]]:
    """Join consecutive pieces of a tiny line without creating a gap.

    Bank-scale ticks are only 9-14 pixels long.  Four overlapping bounding
    pieces retain their solid angled silhouette while keeping the same native
    command budget as the old dotted 3x3 construction.
    """
    items = list(rectangles)
    maximum = max(1, int(maximum))
    if len(items) <= maximum:
        return items
    merged: list[Tuple[int, int, int, int]] = []
    for group in range(maximum):
        start = len(items) * group // maximum
        end = len(items) * (group + 1) // maximum
        if end <= start:
            continue
        chunk = items[start:end]
        left = min(rect[0] for rect in chunk)
        top = min(rect[1] for rect in chunk)
        right = max(rect[0] + rect[2] for rect in chunk)
        bottom = max(rect[1] + rect[3] for rect in chunk)
        merged.append((left, top, right - left, bottom - top))
    return merged


def _draw_horizon(canvas: Any, values: Mapping[str, Any]) -> Tuple[float, float]:
    """Scanline the whole attitude field: rounded shell, sky, earth, and edge.

    Every row carries its exact span, so the rounded corners and the banked
    horizon step by one pixel instead of the old four-pixel bands, and the
    pixels the horizon actually crosses are drawn as the reference's clean
    white separator.
    """
    pitch = float(values["pitch"]) if _finite(values.get("pitch")) else 0.0
    roll = float(values["roll"]) if _finite(values.get("roll")) else 0.0
    horizon_y = 226.0 + _clamp(pitch, -25.0, 25.0) * 5.0
    # X-Plane's captain AHARS roll is negative for a right bank.  The horizon
    # and pitch ladder represent the natural horizon, so they use that reported
    # sign directly and rotate opposite the aircraft: in a right bank their
    # left side descends and their right side rises.
    slope = math.tan(math.radians(_clamp(roll, -45.0, 45.0)))

    sky_rows: list[Tuple[int, int, int]] = []
    earth_rows: list[Tuple[int, int, int]] = []
    edge_rows: list[Tuple[int, int, int]] = []

    def crossing(row: float) -> float:
        return 320.0 + (row - horizon_y) / slope

    # Once the commanded bank is held, the horizon uses exact one-pixel rows.
    # While roll/pitch is actively changing (or during a periodic complete
    # recovery) two-pixel bulk bands prevent the screen queue from falling
    # behind; the exact line replaces them as soon as the attitude settles.
    # Pitch-ladder rungs below remain exact on every non-recovery live frame.
    row_step = MOTION_HORIZON_ROW_STEP if _moving else 1
    for y in range(ATTITUDE.y, ATTITUDE.bottom, row_step):
        band_height = min(row_step, ATTITUDE.bottom - y)
        sample_y = y + (band_height - 1) / 2.0
        left, right = _attitude_row_span(int(round(sample_y)))
        span_left, span_right = int(round(left)), int(round(right))
        if span_right <= span_left:
            continue
        # The whole field is laid down in sky first.  Earth and the blended
        # edge are then overlaid, which saves one native fill on every row the
        # horizon crosses without changing what the pilot sees.
        for band_y in range(y, y + band_height):
            sky_rows.append((span_left, band_y, span_right - span_left))
        if abs(slope) < 1e-4:
            if sample_y + 0.5 >= horizon_y:
                for band_y in range(y, y + band_height):
                    earth_rows.append((span_left, band_y, span_right - span_left))
            if BLEND_HORIZON_EDGE and y <= horizon_y < y + band_height:
                edge_y = max(y, min(y + band_height - 1, int(round(horizon_y))))
                edge_rows.append((span_left, edge_y, span_right - span_left))
            continue
        first, second = crossing(float(y)), crossing(float(y + band_height))
        low = max(span_left, min(span_right, int(round(min(first, second)))))
        high = max(span_left, min(span_right, int(round(max(first, second)))))
        if slope > 0.0:
            if low > span_left:
                for band_y in range(y, y + band_height):
                    earth_rows.append((span_left, band_y, low - span_left))
        elif span_right > high:
            for band_y in range(y, y + band_height):
                earth_rows.append((high, band_y, span_right - high))
        if high > low and BLEND_HORIZON_EDGE:
            for band_y in range(y, y + band_height):
                edge_rows.append((low, band_y, high - low))

    _emit_rows(canvas, SKY, sky_rows)
    _emit_rows(canvas, EARTH, earth_rows)
    _emit_rows(canvas, HORIZON_EDGE, edge_rows)
    return horizon_y, slope


def _world_y(horizon_y: float, slope: float, x: float, pitch_mark: float = 0.0) -> int:
    return int(round(horizon_y - pitch_mark * 5.0 + slope * (x - 320.0)))


def _pitch_ladder_center(
    horizon_y: float,
    pointer_slope: float,
    pitch_mark: float,
) -> Tuple[float, float]:
    """Centre one rung on the moving upward roll-pointer radial axis."""
    radial, _tangent = _bank_axes(pointer_slope)
    distance = pitch_mark * 5.0 - (horizon_y - 226.0)
    return (
        320.0 + distance * radial[0],
        226.0 + distance * radial[1],
    )


def _uniform_attitude_background(
    x: int,
    y: int,
    width: int,
    height: int,
    horizon_y: float,
    horizon_slope: float,
) -> Tuple[int, int, int] | None:
    """Return a safe opaque-cell colour, or None when alpha is required."""
    right, bottom = x + width, y + height
    if x < ATTITUDE.x or right > ATTITUDE.right:
        return None
    for corner_x in (x, right - 1):
        top_bound, bottom_bound = _rounded_bounds(float(corner_x))
        if y < top_bound or bottom > bottom_bound:
            return None
    signed_distances = tuple(
        corner_y - (horizon_y + horizon_slope * (corner_x - 320.0))
        for corner_x in (x, right - 1)
        for corner_y in (y, bottom - 1)
    )
    if min(signed_distances) >= 1.0:
        return EARTH
    if max(signed_distances) <= -1.0:
        return SKY
    return None


def _clip_foreground_rectangles(
    origin_x: int,
    origin_y: int,
    rectangles: Sequence[Tuple[int, int, int, int]],
) -> list[Tuple[int, int, int, int]]:
    """Clip foreground-only glyph ink to the rounded attitude shell.

    No background pixel is emitted here.  This is genuine software alpha over
    the live sky/earth field even though the controller's text command ignores
    its alpha byte.
    """
    active: dict[tuple[int, int], list[int]] = {}
    finished: list[Tuple[int, int, int, int]] = []
    rows: dict[int, list[Tuple[int, int]]] = {}
    for local_x, local_y, width, height in rectangles:
        for y in range(origin_y + local_y, origin_y + local_y + height):
            if y < ATTITUDE.y or y >= ATTITUDE.bottom:
                continue
            shell_left, shell_right = _attitude_row_span(y)
            left = max(origin_x + local_x, int(math.ceil(shell_left)))
            right = min(origin_x + local_x + width, int(math.floor(shell_right)))
            if right > left:
                rows.setdefault(y, []).append((left, right - left))
    for y in sorted(rows):
        current = set(rows[y])
        for key in tuple(active):
            if key not in current:
                finished.append(tuple(active.pop(key)))
        for x, width in current:
            key = (x, width)
            if key in active:
                active[key][3] += 1
            else:
                active[key] = [x, y, width, 1]
    finished.extend(tuple(rectangle) for rectangle in active.values())
    return sorted(finished, key=lambda rect: (rect[1], rect[0]))


def _bank_rung_parts(
    center_x: float,
    center_y: float,
    line_angle: float,
    horizon_y: float,
    horizon_slope: float,
) -> tuple[
    list[Tuple[int, int, int, str, Tuple[int, int, int]]],
    list[Tuple[int, int, int, int]],
] | None:
    """Return native cells plus exact foreground-only cells for one rung.

    Safe cells retain the proven low-cost background-matched native glyph.
    Any cell that crosses the horizon or rounded edge is replaced by the exact
    foreground mask from that same glyph, so the live background survives and
    the clean diagonal does not fall back to the old block construction.
    """
    glyphs: list[Tuple[int, int, int, str, Tuple[int, int, int]]] = []
    foreground: list[Tuple[int, int, int, int]] = []
    for font_id, offset_x, offset_y, text in bank_rung_runs(line_angle):
        run_x = int(round(center_x + offset_x))
        run_y = int(round(center_y + offset_y))
        for index, character in enumerate(text):
            x = run_x + index * BANK_LINE_CELL_WIDTH
            y = run_y
            background = _uniform_attitude_background(
                x,
                y,
                BANK_LINE_CELL_WIDTH,
                BANK_LINE_CELL_HEIGHT,
                horizon_y,
                horizon_slope,
            )
            if background is not None:
                if (
                    glyphs
                    and glyphs[-1][0] == font_id
                    and glyphs[-1][2] == y
                    and glyphs[-1][4] == background
                    and glyphs[-1][1]
                    + len(glyphs[-1][3]) * BANK_LINE_CELL_WIDTH == x
                ):
                    previous = glyphs[-1]
                    glyphs[-1] = (
                        previous[0], previous[1], previous[2],
                        previous[3] + character, previous[4],
                    )
                else:
                    glyphs.append((font_id, x, y, character, background))
            else:
                mask = bank_line_glyph_rectangles(font_id, character)
                if not mask:
                    return None
                foreground.extend(_clip_foreground_rectangles(x, y, mask))
    return (glyphs, foreground) if glyphs or foreground else None


def _draw_attitude_number_text(
    canvas: Any,
    slot: TextSlot,
    value: str,
    foreground: Tuple[int, int, int],
    horizon_y: float,
    horizon_slope: float,
) -> None:
    """Draw slot-3 text with foreground-only ink wherever opacity would show."""
    packed = _pack_value_slot(slot)
    if packed:
        cells = _packed_number_cells(slot, value)
        if cells is None:
            return
    else:
        try:
            run_x, _run_y = slot.position_for(value)
        except PfdLayoutError:
            return
        run_background = _uniform_attitude_background(
            run_x,
            slot.rect.y,
            len(value) * FONT_CELL_WIDTH,
            FONT_CELL_HEIGHT,
            horizon_y,
            horizon_slope,
        )
        if run_background is not None:
            canvas.text(
                run_x,
                slot.rect.y,
                value,
                foreground,
                run_background,
                PFD_NUMBER_FONT_ID,
            )
            return
        cells = [
            (run_x + index * FONT_CELL_WIDTH, character)
            for index, character in enumerate(value)
        ]

    ink: list[Tuple[int, int, int, int]] = []
    for x, character in cells:
        background = _uniform_attitude_background(
            x,
            slot.rect.y,
            FONT_CELL_WIDTH,
            FONT_CELL_HEIGHT,
            horizon_y,
            horizon_slope,
        )
        if background is not None:
            canvas.text(
                x,
                slot.rect.y,
                character,
                foreground,
                background,
                PFD_NUMBER_FONT_ID,
            )
            continue
        rectangles = pfd_number_glyph_rectangles(character)
        if not rectangles:
            # Every printable slot-3 glyph is generated into the plan.  Keep a
            # guarded fallback for an unknown future character.
            sample_x = x + FONT_CELL_WIDTH / 2.0
            sample_y = slot.rect.y + FONT_CELL_HEIGHT / 2.0
            sample_horizon = horizon_y + horizon_slope * (sample_x - 320.0)
            background = SKY if sample_y < sample_horizon else EARTH
            canvas.text(
                x,
                slot.rect.y,
                character,
                foreground,
                background,
                PFD_NUMBER_FONT_ID,
            )
            continue
        ink.extend(
            _clip_foreground_rectangles(x, slot.rect.y, rectangles)
        )
    if ink:
        canvas.colour(*foreground)
        for x, y, width, height in ink:
            canvas.fill(x, y, width, height)


def _draw_bank_and_pitch(canvas: Any, horizon_y: float, slope: float) -> None:
    canvas.colour(*WHITE)
    # The bank scale marks 10, 20, 30, 45 and 60 degrees.  Each mark is one
    # continuous radial line; the former chain of 3x3 squares looked dotted
    # and crooked at the angled positions.
    for angle in (-60, -45, -30, -20, -10, 10, 20, 30, 45, 60):
        radians = math.radians(angle)
        length = 14 if abs(angle) in (30, 60) else (11 if abs(angle) == 45 else 9)
        inner = BANK_SCALE_RADIUS
        outer = BANK_SCALE_RADIUS + length
        tick = _solid_angled_line_rects(
            320 + inner * math.sin(radians), 226 - inner * math.cos(radians),
            320 + outer * math.sin(radians), 226 - outer * math.cos(radians), 2,
        )
        for x, y, width, height in _coalesce_line_rects(tick, 4):
            canvas.fill(x, y, width, height)
    # Fixed bank index: a compact three-step triangle, still only three fills.
    canvas.fill(311, 100, 18, 2)
    canvas.fill(315, 102, 10, 3)
    canvas.fill(318, 105, 4, 3)

    # The roll pointer represents the aeroplane rather than the outside world.
    # It therefore uses the opposite sign: right of zero for a right bank.
    _draw_bank_pointer(canvas, -slope)

    # The owner's required indication deliberately separates the aeroplane
    # pitch ladder from the outside-world horizon.  The numbered 10/20 rungs
    # form one rigid rotated ladder centred on the radial axis of the moving
    # upward-pointing triangle.  The fixed downward triangle at the top centre
    # is only the zero-bank index and does not control the ladder.
    ladder_slope = -slope
    _radial, ladder_tangent = _bank_axes(ladder_slope)

    # The supplied clean PFD reference uses paired 2.5-degree ladder segments:
    # long labelled rungs every ten degrees, medium rungs every five, short
    # rungs between them, and a clear centre gap.  All four endpoints use the
    # same bank slope as the moving pointer; there are no blocky lower hooks.
    marks: list[Tuple[float, int, int, bool, float, float]] = []
    for tenths in range(-250, 251, 25):
        if tenths == 0:
            continue
        pitch_mark = tenths / 10.0
        if tenths % 100 == 0:
            half_width, inner_gap, labelled = 42, 10, True
        elif tenths % 50 == 0:
            half_width, inner_gap, labelled = 16, 0, False
        else:
            half_width, inner_gap, labelled = 8, 0, False
        if _recovery_frame and not labelled and tenths % 50 != 0:
            # Rebuild the principal 5/10-degree ladder first.  The exact
            # 2.5-degree strokes arrive in the immediate refinement frame,
            # avoiding both a chunky temporary approximation and a USB burst.
            continue
        center_x, center_y = _pitch_ladder_center(
            horizon_y, ladder_slope, pitch_mark
        )
        marks.append(
            (pitch_mark, half_width, inner_gap, labelled, center_x, center_y)
        )

    label_runs: list[Tuple[str, float, float, str, float, float, float]] = []
    line_angle = math.degrees(math.atan(ladder_slope))
    use_bank_line_font = bool(
        getattr(canvas, "_muslimsim_bank_line_font", False)
    )

    # Opaque glyph cells are painted first.  Their locally matched background
    # disappears into the sky/earth field, then exact 2.5/5-degree strokes go
    # over them.  Text labels remain last, as on the original coded path.
    for labelled_pass in (True, False):
        for (
            pitch_mark,
            half_width,
            inner_gap,
            labelled,
            center_x,
            center_y,
        ) in marks:
            if labelled != labelled_pass:
                continue
        # The labelled 10/20 rungs retain their centre gap for the aircraft
        # reference.  Splitting a four-pixel minor rung produced two square
        # clusters, so every unlabelled mark is one centred continuous stroke.
            segments = (
                ((-half_width, -inner_gap), (inner_gap, half_width))
                if labelled
                else ((-half_width, half_width),)
            )
            line_rects: list[Tuple[int, int, int, int]] = []
            glyph_parts: tuple[
                list[Tuple[int, int, int, str, Tuple[int, int, int]]],
                list[Tuple[int, int, int, int]],
            ] | None = None
            if labelled and use_bank_line_font:
                glyph_parts = _bank_rung_parts(
                    center_x,
                    center_y,
                    line_angle,
                    horizon_y,
                    slope,
                )
            glyph_runs, masked_rects = glyph_parts or ([], [])
            line_rects.extend(masked_rects)
            for along_start, along_end in (() if glyph_parts else segments):
                segment_start = (
                    center_x + along_start * ladder_tangent[0],
                    center_y + along_start * ladder_tangent[1],
                )
                segment_end = (
                    center_x + along_end * ladder_tangent[0],
                    center_y + along_end * ladder_tangent[1],
                )
                # Two pixels measured perpendicular to the stroke keep every
                # diagonal edge-connected.  Command count is unchanged because
                # each scanline is still one continuous span.
                thickness = 2
                precise = _solid_angled_line_rects(
                    *segment_start, *segment_end, thickness
                )
                if _recovery_frame:
                    # Keep a complete healing repaint below the controller's
                    # protected USB budget.  The next differential frame replaces
                    # these runs with the exact paired geometry below.
                    span = along_end - along_start
                    step = span if abs(ladder_slope) < 0.02 else max(
                        MOTION_LADDER_MIN_STEP,
                        min(span, int(round(1.0 / abs(ladder_slope)))),
                    )
                    maximum = max(1, int(math.ceil(span / max(1, step))))
                    if not labelled:
                        # A healing frame only has to rebuild a safe continuous
                        # silhouette; the next differential frame installs the
                        # exact scanline bar.  Cap these longer centred strokes so
                        # the complete frame stays inside BB36's USB budget.
                        maximum = min(maximum, 4 if half_width >= 16 else 2)
                    line_rects.extend(
                        _coalesce_line_rects(
                            precise,
                            maximum,
                        )
                    )
                else:
                    line_rects.extend(precise)
            for font_id, x, y, text, background in glyph_runs or ():
                canvas.text(
                    x, y, text, WHITE, background, font_id
                )
            canvas.colour(*WHITE)
            for x, y, draw_width, draw_height in line_rects:
                top, bottom = _rounded_bounds(x + draw_width / 2.0)
                if top <= y and y + draw_height <= bottom:
                    canvas.fill(x, y, draw_width, draw_height)
            if not labelled:
                continue
            label_runs.extend((
                (
                    "left pitch",
                    center_x - half_width * ladder_tangent[0] - 40.0,
                    center_y - half_width * ladder_tangent[1] - 12.0,
                    "right",
                    center_x,
                    center_y,
                    pitch_mark,
                ),
                (
                    "right pitch",
                    center_x + half_width * ladder_tangent[0] + 6.0,
                    center_y + half_width * ladder_tangent[1] - 12.0,
                    "left",
                    center_x,
                    center_y,
                    pitch_mark,
                ),
            ))

    for (
        name,
        raw_x,
        raw_y,
        alignment,
        center_x,
        center_y,
        pitch_mark,
    ) in label_runs:
        label_x, label_y = int(round(raw_x)), int(round(raw_y))
        label_rect = Rect(label_x, label_y, 34, FONT_CELL_HEIGHT)
        top, bottom = _rounded_bounds(label_x + 17.0)
        if (
            label_rect.x < ATTITUDE.x
            or label_rect.right > ATTITUDE.right
            or label_rect.y < top
            or label_rect.bottom > bottom
        ):
            continue
        _draw_attitude_number_text(
            canvas,
            _slot(name, label_x, label_y, 34, alignment),
            str(int(abs(pitch_mark))),
            WHITE,
            horizon_y,
            slope,
        )


def _bank_pointer_tip(slope: float) -> Tuple[int, int]:
    """Return the moving bank pointer tip for the aircraft-bank slope."""
    norm = math.sqrt(1.0 + slope * slope)
    return (
        int(round(320 + 108.0 * slope / norm)),
        int(round(226 - 108.0 / norm)),
    )


def _bank_axes(slope: float) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Return outward radial and clockwise tangent unit vectors for roll."""
    norm = math.sqrt(1.0 + slope * slope)
    return (slope / norm, -1.0 / norm), (1.0 / norm, slope / norm)


def _filled_triangle_rows(
    vertices: Sequence[Tuple[float, float]],
) -> list[Tuple[int, int, int]]:
    """Rasterise a small filled triangle as exact horizontal native runs."""
    rows: list[Tuple[int, int, int]] = []
    top = int(math.floor(min(vertex[1] for vertex in vertices)))
    bottom = int(math.ceil(max(vertex[1] for vertex in vertices)))
    edges = tuple(zip(vertices, (*vertices[1:], vertices[0])))
    for y in range(top, bottom + 1):
        sample_y = y + 0.5
        crossings: list[float] = []
        for (x0, y0), (x1, y1) in edges:
            if abs(y1 - y0) < 1e-6:
                continue
            if min(y0, y1) <= sample_y < max(y0, y1):
                fraction = (sample_y - y0) / (y1 - y0)
                crossings.append(x0 + (x1 - x0) * fraction)
        if len(crossings) < 2:
            continue
        left = int(math.floor(min(crossings)))
        right = int(math.ceil(max(crossings)))
        if right > left:
            rows.append((left, y, right - left))
    return rows


def _draw_bank_pointer(canvas: Any, slope: float) -> None:
    """Draw the aircraft roll pointer, aimed radially at the fixed scale."""
    radial, tangent = _bank_axes(slope)
    tip = (320.0 + 108.0 * radial[0], 226.0 + 108.0 * radial[1])
    base = (320.0 + 98.0 * radial[0], 226.0 + 98.0 * radial[1])
    half_width = 7.0
    vertices = (
        tip,
        (base[0] - half_width * tangent[0], base[1] - half_width * tangent[1]),
        (base[0] + half_width * tangent[0], base[1] + half_width * tangent[1]),
    )
    _emit_rows(canvas, WHITE, _filled_triangle_rows(vertices))


def _aircraft_reference_slope(values: Mapping[str, Any]) -> float:
    """Return the screen slope of the black aircraft-reference wings.

    X-Plane reports a left bank as positive roll.  On the LCD a left bank
    must lower the reference's left wing and raise its right wing, which is a
    negative screen slope because pixel Y increases downwards.
    """
    roll = float(values["roll"]) if _finite(values.get("roll")) else 0.0
    return -math.tan(math.radians(_clamp(roll, -45.0, 45.0)))


def _aircraft_reference_point(
    slope: float,
    x: float,
    y: float,
) -> Tuple[float, float]:
    """Rotate one level-reference point rigidly around the centre square."""
    radial, tangent = _bank_axes(slope)
    down = (-radial[0], -radial[1])
    local_x, local_y = x - 320.0, y - 226.0
    return (
        320.0 + local_x * tangent[0] + local_y * down[0],
        226.0 + local_x * tangent[1] + local_y * down[1],
    )


def _draw_aircraft_reference(canvas: Any, values: Mapping[str, Any]) -> None:
    """Draw the black aircraft reference inside a thick white contour."""
    slope = _aircraft_reference_slope(values)
    # Every segment uses one rigid transform, keeping the two wings, inner
    # hooks and centre square connected through the live bank angle.
    segments = (
        ((208.0, 224.5), (282.0, 224.5), 3),
        ((280.5, 224.5), (280.5, 237.5), 3),
        ((280.5, 237.5), (295.5, 237.5), 3),
        ((358.0, 224.5), (432.0, 224.5), 3),
        ((359.5, 224.5), (359.5, 237.5), 3),
        ((344.5, 237.5), (359.5, 237.5), 3),
        ((317.0, 222.0), (323.0, 222.0), 2),
        ((317.0, 230.0), (323.0, 230.0), 2),
        ((317.0, 222.0), (317.0, 230.0), 2),
        ((323.0, 222.0), (323.0, 230.0), 2),
    )

    # A recovery repaint has the strictest BB36 report budget.  It installs
    # the proven black silhouette first; the immediate precision frame adds
    # this exact four-pixel white contour without delaying page entry.
    if not _recovery_frame:
        canvas.colour(*WHITE)
        for start, end, thickness in segments:
            x0, y0 = _aircraft_reference_point(slope, *start)
            x1, y1 = _aircraft_reference_point(slope, *end)
            for x, y, width, height in _solid_angled_line_rects(
                x0, y0, x1, y1, thickness + 4
            ):
                canvas.fill(x, y, width, height)

    canvas.colour(*BLACK)

    if abs(slope) < 1e-4:
        # Preserve the exact proven level geometry rather than introducing a
        # rasterisation rounding difference at zero bank.
        canvas.fill(208, 223, 75, 3)
        canvas.fill(279, 223, 3, 16)
        canvas.fill(279, 236, 17, 3)
        canvas.fill(357, 223, 75, 3)
        canvas.fill(358, 223, 3, 16)
        canvas.fill(344, 236, 17, 3)
        canvas.fill(316, 221, 8, 2)
        canvas.fill(316, 229, 8, 2)
        canvas.fill(316, 221, 2, 10)
        canvas.fill(322, 221, 2, 10)
        return

    for index, (start, end, thickness) in enumerate(segments):
        x0, y0 = _aircraft_reference_point(slope, *start)
        x1, y1 = _aircraft_reference_point(slope, *end)
        rectangles = _solid_angled_line_rects(
            x0, y0, x1, y1, thickness
        )
        if _recovery_frame:
            # A complete healing frame has the strictest USB budget.  Install
            # a connected low-command silhouette first; the immediate
            # refinement frame replaces it with the exact scanline geometry.
            rectangles = _coalesce_line_rects(
                rectangles,
                3 if index in (0, 3) else 1,
            )
        for x, y, width, height in rectangles:
            canvas.fill(x, y, width, height)


def _draw_fd_and_aircraft(canvas: Any, values: Mapping[str, Any]) -> None:
    canvas.colour(*MAGENTA)
    if _finite(values.get("fd_pitch_visible")) and float(values["fd_pitch_visible"]) >= 0.5 and _finite(values.get("fd_pitch")):
        fd_y = int(round(226 - _clamp(float(values["fd_pitch"]), -15.0, 15.0) * 5.0))
        canvas.fill(284, max(ATTITUDE.y + 2, min(ATTITUDE.bottom - 4, fd_y)), 72, 3)
    if _finite(values.get("fd_roll_visible")) and float(values["fd_roll_visible"]) >= 0.5 and _finite(values.get("fd_roll")):
        fd_x = int(round(320 + _clamp(float(values["fd_roll"]), -45.0, 45.0) * 2.25))
        canvas.fill(max(ATTITUDE.x + 2, min(ATTITUDE.right - 4, fd_x)), 192, 3, 68)

    # The complete black aircraft reference banks with the aeroplane while
    # the white natural horizon moves oppositely behind it.
    _draw_aircraft_reference(canvas, values)


def _draw_flight_path_vector(canvas: Any, values: Mapping[str, Any]) -> None:
    """Draw Zibo's captain FPV at the aircraft-computed PFD position."""
    if not (_finite(values.get("fpv_on")) and float(values["fpv_on"]) >= 0.5):
        return
    horizontal = values.get("fpv_horizontal")
    vertical = values.get("fpv_vertical")
    if not (_finite(horizontal) and _finite(vertical)):
        return
    # The installed PFD maps +/-15 horizontal degrees to +/-78 pixels.  Its
    # vertical value is already the completed PFD offset, so no aerodynamic
    # calculation is duplicated here.
    x = int(round(320.0 - _clamp(float(horizontal), -15.0, 15.0) * 5.2))
    y = int(round(226.0 - _clamp(float(vertical), -104.0, 78.0)))
    x = max(ATTITUDE.x + 18, min(ATTITUDE.right - 18, x))
    y = max(ATTITUDE.y + 18, min(ATTITUDE.bottom - 18, y))
    canvas.colour(*WHITE)
    canvas.fill(x - 7, y - 9, 14, 2)
    canvas.fill(x - 9, y - 7, 2, 14)
    canvas.fill(x + 7, y - 7, 2, 14)
    canvas.fill(x - 7, y + 7, 14, 2)
    canvas.fill(x - 23, y - 1, 14, 3)
    canvas.fill(x + 9, y - 1, 14, 3)
    canvas.fill(x - 1, y + 9, 3, 12)


def _draw_pitch_limit(canvas: Any, values: Mapping[str, Any]) -> None:
    """Draw the installed Zibo stall/pitch-limit cue without a bitmap."""
    if not (
        _finite(values.get("stall_pitch_show"))
        and float(values["stall_pitch_show"]) >= 0.5
        and _finite(values.get("stall_pitch"))
    ):
        return
    y = int(round(226.0 - _clamp(float(values["stall_pitch"]), -15.0, 15.0) * 5.2))
    if not ATTITUDE.y + 8 <= y <= ATTITUDE.bottom - 8:
        return
    canvas.colour(*AMBER)
    canvas.fill(267, y, 36, 3)
    canvas.fill(337, y, 36, 3)
    canvas.fill(300, y, 3, 10)
    canvas.fill(337, y, 3, 10)


def _draw_rising_runway(canvas: Any, values: Mapping[str, Any]) -> None:
    """Render the Zibo-computed rising-runway position as native geometry."""
    if not (
        _finite(values.get("runway_show"))
        and float(values["runway_show"]) >= 0.5
        and _finite(values.get("runway_x"))
        and _finite(values.get("runway_y"))
    ):
        return
    x = int(round(320.0 + _clamp(float(values["runway_x"]), -87.5, 87.5) * 0.70))
    # Zibo's y is zero at touchdown and -70 at/above 200 ft.  Convert its
    # bottom-origin offset to this canvas's top-origin coordinate system.
    y = int(round(332.0 - _clamp(float(values["runway_y"]), -70.0, 0.0) * 0.70))
    if y > ATTITUDE.bottom + 10:
        return
    y = min(ATTITUDE.bottom - 3, y)
    canvas.colour(*WHITE)
    half_bottom, half_top, height = 28, 13, 22
    for row in range(0, height, 2):
        half = int(round(half_bottom - (half_bottom - half_top) * row / height))
        yy = y - row
        if ATTITUDE.y <= yy < ATTITUDE.bottom:
            canvas.fill(max(ATTITUDE.x, x - half), yy, 3, 2)
            canvas.fill(min(ATTITUDE.right - 3, x + half - 3), yy, 3, 2)
    if ATTITUDE.y <= y < ATTITUDE.bottom:
        canvas.fill(max(ATTITUDE.x, x - half_bottom), y, half_bottom * 2, 3)


def _draw_altitude_trend(canvas: Any, values: Mapping[str, Any]) -> None:
    """Six-second altitude prediction from the already sampled vertical speed."""
    vertical_speed = values.get("vertical_speed")
    if not _finite(vertical_speed):
        return
    delta_y = -float(vertical_speed) * 0.022  # (fpm / 10) * 0.22 px/ft
    if abs(delta_y) < 8.0:
        return
    tip_y = int(round(_clamp(226.0 + delta_y, ALTITUDE_TAPE.y + 5, ALTITUDE_TAPE.bottom - 5)))
    start_y, height = min(226, tip_y), abs(tip_y - 226) + 1
    canvas.colour(*GREEN)
    canvas.fill(556, start_y, 3, height)
    canvas.fill(550, tip_y - 1, 9, 3)


def _hidden_by_window(tick_y: int, window: Rect) -> bool:
    """True when a tape number's opaque cell would run into a live window.

    The native font cell is fully opaque, so a tape value drawn beside the
    IAS or altitude window would punch a grey block through that window's
    black interior.  The tick mark is still drawn; only the number is hidden.
    """
    top = tick_y - TAPE_TEXT_TOP_OFFSET
    return top < window.bottom and top + FONT_CELL_HEIGHT > window.y


def _speed_tape_y(speed: float, ias: float) -> float:
    """Where a speed sits on the tape, in the tape's own 2.15 px per knot."""
    return 226.0 - (speed - ias) * 2.15


def _band_value(values: Mapping[str, Any], name: str, flag: str | None) -> float | None:
    """A band speed, or None when the aircraft is not publishing it.

    Zibo hides each band with its own flag.  A band drawn from a value the
    aeroplane is not showing would be a speed limit that is not real, so a
    missing or cleared flag means nothing is drawn at all.
    """
    value = values.get(name)
    if not _finite(value) or float(value) <= 0.0:
        return None
    if flag is not None:
        shown = values.get(flag)
        # Only an explicit "do not show" hides a band.  A flag this build does
        # not publish must not hide a limit the aircraft is telling us about:
        # this Zibo has min_speed_show but no max_speed_show, and treating the
        # missing one as false would have silently dropped the VMO barber pole.
        if _finite(shown) and float(shown) < 0.5:
            return None
    return float(value)


def _band_span(top: float, bottom: float) -> Tuple[int, int] | None:
    """Clip a band to the tape, returning None when none of it is visible."""
    first = int(round(max(top, SPEED_TAPE.y)))
    last = int(round(min(bottom, SPEED_TAPE.bottom)))
    if last - first < 2:
        return None
    return first, last


def _draw_speed_bands(canvas: Any, values: Mapping[str, Any]) -> None:
    """Draw the amber manoeuvre bands and the red limit barber poles.

    Reading outward from the middle of the tape: amber from the manoeuvre
    speed to the limit speed, then red dashes beyond the limit, at both ends.
    """
    ias = values.get("ias")
    if not _finite(ias):
        return
    live = float(ias)

    minimum = _band_value(values, "min_speed", "min_speed_show")
    maximum = _band_value(values, "max_speed", "max_speed_show")
    min_manoeuvre = _band_value(values, "min_maneuver_speed", "min_maneuver_speed_show")
    max_manoeuvre = _band_value(values, "max_maneuver_speed", "max_maneuver_speed_show")

    canvas.colour(*AMBER)
    if min_manoeuvre is not None:
        floor = minimum if minimum is not None else live - 400.0
        span = _band_span(_speed_tape_y(min_manoeuvre, live), _speed_tape_y(floor, live))
        if span:
            canvas.fill(SPEED_BAND_X, span[0], SPEED_BAND_WIDTH, span[1] - span[0])
    if max_manoeuvre is not None:
        ceiling = maximum if maximum is not None else live + 400.0
        span = _band_span(_speed_tape_y(ceiling, live), _speed_tape_y(max_manoeuvre, live))
        if span:
            canvas.fill(SPEED_BAND_X, span[0], SPEED_BAND_WIDTH, span[1] - span[0])

    canvas.colour(*RED)
    for span in (
        _band_span(_speed_tape_y(minimum, live), SPEED_TAPE.bottom) if minimum is not None else None,
        _band_span(SPEED_TAPE.y, _speed_tape_y(maximum, live)) if maximum is not None else None,
    ):
        if not span:
            continue
        first, last = span
        for y in range(first, last, BARBER_PITCH):
            canvas.fill(SPEED_BAND_X, y, SPEED_BAND_WIDTH, min(BARBER_DASH, last - y))


SPEED_BUGS = (
    ("v1_speed", "1"),
    ("vr_speed", "R"),
    ("v2_speed", "2"),
    ("vref_speed", "RF"),
    ("flaps_speed", None),      # labelled with the flap lever's own detent
)


def _flap_label(values: Mapping[str, Any]) -> str:
    """The flap lever's detent name, or an empty label when it is unknown."""
    ratio = values.get("flap_lever")
    if not _finite(ratio):
        return ""
    position = _clamp(float(ratio), 0.0, 1.0)
    return min(FLAP_DETENTS, key=lambda detent: abs(detent[0] - position))[1]


def _draw_speed_trend(canvas: Any, values: Mapping[str, Any]) -> None:
    """Draw the green airspeed trend vector from the speed pointer.

    The tip is where the airspeed will be in ten seconds if the present
    acceleration holds, so a glance says whether the aeroplane will reach a
    limit before the pilot can act.  It is rounded to half a knot: the
    acceleration is live and would otherwise redraw the arrow every frame for
    movement below one pixel.
    """
    ias = values.get("ias")
    trend = values.get("speed_trend")
    if not _finite(ias) or not _finite(trend):
        return
    change = float(trend) * SPEED_TREND_SECONDS
    if abs(change) < SPEED_TREND_MIN_KNOTS:
        return
    change = round(change / SPEED_TREND_STEP) * SPEED_TREND_STEP
    live = float(ias)
    tip = int(round(_clamp(_speed_tape_y(live + change, live),
                           SPEED_TAPE.y + 6, SPEED_TAPE.bottom - 6)))
    if abs(tip - 226) < 6:
        return

    canvas.colour(*GREEN)
    top, bottom = min(226, tip), max(226, tip)
    canvas.fill(SPEED_TREND_X, top, 2, bottom - top)
    # An open arrowhead at the tip, pointing the way the speed is going.
    direction = 1 if tip > 226 else -1
    for step in range(5):
        canvas.fill(SPEED_TREND_X - step, tip - direction * step * 2, 2, 2)
        canvas.fill(SPEED_TREND_X + step, tip - direction * step * 2, 2, 2)


def _draw_speed_bugs(canvas: Any, values: Mapping[str, Any]) -> list:
    """Green reference bugs: V1, VR, V2, VREF, and the flap manoeuvre speed.

    The flap bug is the one that says when to move the flap lever.  Returns
    the labels for the text layer so their opaque cells stay off the tape.
    """
    ias = values.get("ias")
    if not _finite(ias):
        return []
    live = float(ias)
    labels: list = []
    canvas.colour(*GREEN)
    for name, mark in SPEED_BUGS:
        if mark is None:
            mark = _flap_label(values)
        speed = values.get(name)
        # A flag dataref would read 0 or 1; a speed never sensibly does, so a
        # small value is treated as "not set" rather than drawn at the bottom
        # of the tape.
        if not _finite(speed) or float(speed) < 40.0:
            continue
        y = int(round(_speed_tape_y(float(speed), live)))
        if not SPEED_TAPE.y + 14 <= y <= SPEED_TAPE.bottom - 14:
            continue
        canvas.fill(SPEED_BUG_LINE_X, y - 1, SPEED_BUG_LINE_WIDTH, 2)
        # V-speeds sit only a few knots apart, which is closer than one opaque
        # font cell.  The mark always shows; the label gives way to the one
        # already placed rather than printing over it.
        if mark and all(abs(y - placed) >= FONT_CELL_HEIGHT for _text, placed in labels):
            labels.append((mark, y))
    return labels


def _draw_tapes(canvas: Any, values: Mapping[str, Any]) -> Tuple[list[Tuple[int, int]], list[Tuple[int, int]]]:
    canvas.colour(*TAPE_GREY)
    canvas.fill(SPEED_TAPE.x, SPEED_TAPE.y, SPEED_TAPE.width, SPEED_TAPE.height)
    canvas.fill(ALTITUDE_TAPE.x, ALTITUDE_TAPE.y, ALTITUDE_TAPE.width, ALTITUDE_TAPE.height)

    speed_labels: list[Tuple[int, int]] = []
    altitude_labels: list[Tuple[int, int]] = []
    ias = values.get("ias")
    altitude = values.get("altitude")
    canvas.colour(*WHITE)
    if _finite(ias):
        base = int(round(float(ias) / 20.0)) * 20
        for value in range(base - 60, base + 61, 20):
            y = int(round(226 - (value - float(ias)) * 2.15))
            # The native text cell is 29 pixels high and begins 12 pixels
            # above this tick.  Keep its entire opaque background inside the
            # strip, not merely the tick itself.
            if SPEED_TAPE.y + TAPE_TEXT_TOP_OFFSET <= y <= SPEED_TAPE.bottom - TAPE_TEXT_BOTTOM_OFFSET:
                # Tick marks sit in the narrow black gutter beside each tape,
                # leaving the full grey strip available for clean number art.
                # The aircraft draws its tick marks inside the tape, beside
                # the numbers, not floating in the black gutter where the
                # speed bug and trend belong.
                canvas.fill(SPEED_TICK_X, y, SPEED_TICK_WIDTH, 2)
                if not _hidden_by_window(y, SPEED_WINDOW):
                    speed_labels.append((value, y))
    if _finite(altitude):
        base = int(round(float(altitude) / 200.0)) * 200
        for value in range(base - 600, base + 601, 200):
            y = int(round(226 - (value - float(altitude)) * 0.22))
            if ALTITUDE_TAPE.y + TAPE_TEXT_TOP_OFFSET <= y <= ALTITUDE_TAPE.bottom - TAPE_TEXT_BOTTOM_OFFSET:
                # Four native cells fill the altitude strip, so its ticks
                # keep to the gutter, shortened to read as marks.
                canvas.fill(ALTITUDE_TAPE.x - 12, y, 12, 2)
                if not _hidden_by_window(y, ALTITUDE_WINDOW):
                    altitude_labels.append((value, y))
    canvas.fill(SPEED_TAPE.right, 224, 24, 4)
    # The live-altitude datum belongs inside the grey tape.  The white box's
    # left-facing nipple terminates at this dash instead of floating in the
    # black attitude gutter.
    canvas.fill(
        ALTITUDE_TAPE.x,
        224,
        ALTITUDE_WINDOW_BODY_X - ALTITUDE_TAPE.x,
        4,
    )
    return speed_labels, altitude_labels


def _clear_speed_window(canvas: Any) -> None:
    """Clear the IAS body; caller already selected black."""
    rect = SPEED_WINDOW
    canvas.fill(rect.x + 2, rect.y + 2, rect.width - 4, rect.height - 4)


def _draw_speed_window_outline(canvas: Any) -> None:
    """Draw the IAS outline; caller supplies white or magenta.

    The 737 readout is a plain box whose inboard side carries a chevron that
    points at the live-speed line on the tape.  The chevron is rasterised by
    row so its two diagonals are one pixel apart, not stepped in blocks.
    """
    rect = SPEED_WINDOW
    canvas.fill(rect.x, rect.y, rect.width, 2)
    canvas.fill(rect.x, rect.bottom - 2, rect.width, 2)
    canvas.fill(rect.x, rect.y, 2, rect.height)
    canvas.fill(rect.right - 2, rect.y, 2, 12)
    canvas.fill(rect.right - 2, rect.bottom - 12, 2, 12)
    tip_x = rect.right + SPEED_WINDOW_POINT
    for step in range(0, SPEED_WINDOW_POINT, 2):
        x = rect.right + step
        drop = int(round(step * 12.0 / SPEED_WINDOW_POINT))
        canvas.fill(x, rect.y + 12 + drop, 2, 2)
        canvas.fill(x, rect.bottom - 14 - drop, 2, 2)
    canvas.fill(tip_x - 2, 225, 2, 2)


def _clear_altitude_window(canvas: Any) -> None:
    """Clear only the live-altitude box interior, including its nipple.

    The old rectangular clear extended black beyond the diagonal white edge.
    These rows follow the inside of the outline, so black can never escape the
    box even where the nipple cuts back through the grey altitude tape.
    """
    rect = ALTITUDE_WINDOW
    # One rectangle owns the body.  Seven nested two-pixel columns fill the
    # nipple; every column lies between the two white 45-degree edges, and the
    # final outline repaints their boundary pixels.  This is pixel-equivalent
    # to scanlining the triangle but saves twenty-one native fill commands.
    canvas.fill(
        ALTITUDE_WINDOW_BODY_X + 2,
        rect.y + 2,
        rect.right - ALTITUDE_WINDOW_BODY_X - 4,
        rect.height - 4,
    )
    shoulder_top = rect.y + 12
    shoulder_bottom = rect.bottom - 12
    for inset in range(2, ALTITUDE_WINDOW_POINT + 1, 2):
        x = ALTITUDE_WINDOW_BODY_X - inset + 2
        y = shoulder_top + inset
        bottom = shoulder_bottom - inset + 2
        if bottom > y:
            canvas.fill(x, y, 2, bottom - y)


def _draw_altitude_window_outline(canvas: Any) -> None:
    """Draw the altitude outline; caller supplies white or magenta.

    A plain box whose inboard side carries a chevron pointing at the live
    altitude on the tape, mirroring the airspeed readout.
    """
    rect = ALTITUDE_WINDOW
    left = ALTITUDE_WINDOW_BODY_X
    canvas.fill(left, rect.y, rect.right - left, 2)
    canvas.fill(left, rect.bottom - 2, rect.right - left, 2)
    canvas.fill(rect.right - 2, rect.y, 2, rect.height)
    # The first diagonal blocks share their x coordinate with the two straight
    # shoulders, so keep each pair as one rectangle.  Likewise the final upper
    # and lower blocks meet at the centre.  The pixels are unchanged, with
    # three fewer native commands each time this outline is painted.
    canvas.fill(left, rect.y, 2, 14)
    canvas.fill(left, rect.bottom - 14, 2, 14)
    for step in range(2, ALTITUDE_WINDOW_POINT - 2, 2):
        x = left - step
        canvas.fill(x, rect.y + 12 + step, 2, 2)
        canvas.fill(x, rect.bottom - 14 - step, 2, 2)
    canvas.fill(left - (ALTITUDE_WINDOW_POINT - 2), 224, 2, 4)
    canvas.fill(rect.x, 225, 2, 3)


SPEED_BUG_TIP = SPEED_TAPE.right - 8
SPEED_BUG_LEFT = SPEED_TAPE.right + 6
SPEED_BUG_RIGHT = SPEED_TAPE.right + 30


def _draw_speed_target_bug_outline(canvas: Any, center_y: int) -> None:
    """The hollow MCP speed bug: a pennant pointing into the tape.

    Caller already selected magenta.  The point sits on the tape beside the
    live speed and the body hangs outboard, which is how the 737 draws it.
    """
    top, bottom = center_y - 11, center_y + 11
    canvas.fill(SPEED_BUG_LEFT, top, SPEED_BUG_RIGHT - SPEED_BUG_LEFT, 2)
    canvas.fill(SPEED_BUG_LEFT, bottom - 1, SPEED_BUG_RIGHT - SPEED_BUG_LEFT, 2)
    canvas.fill(SPEED_BUG_RIGHT - 2, top, 2, bottom - top)
    span = SPEED_BUG_LEFT - SPEED_BUG_TIP
    for step in range(0, span, 2):
        x = SPEED_BUG_TIP + step
        drop = int(round(step * 11.0 / span))
        canvas.fill(x, center_y - drop - 1, 2, 2)
        canvas.fill(x, center_y + drop - 1, 2, 2)


def _draw_altitude_target_bug_outline(canvas: Any, center_y: int) -> None:
    """The MCP altitude bracket, as drawn on the aircraft.

    Caller already selected magenta.  A hollow rectangle straddles the tape's
    inboard edge.  Its left boundary folds *into* the bracket, matching the
    simulator: the notch is an inward cut, never an arrow outside the box.
    """
    left, right = ALTITUDE_TAPE.x - 12, ALTITUDE_TAPE.x + 22
    top, bottom = center_y - 24, center_y + 24
    canvas.fill(left, top, right - left, 2)
    canvas.fill(left, bottom - 2, right - left, 2)
    canvas.fill(right - 2, top, 2, bottom - top)
    canvas.fill(left, top, 2, 16)
    canvas.fill(left, bottom - 16, 2, 16)
    for step in range(0, 10, 2):
        x = left + step
        canvas.fill(x, center_y - 8 + step, 2, 2)
        canvas.fill(x, center_y + 6 - step, 2, 2)


def _draw_live_windows_and_bugs(canvas: Any, values: Mapping[str, Any]) -> None:
    """Lay down the two live black readout boxes below their rolling digits."""
    canvas.colour(*BLACK)
    _clear_speed_window(canvas)
    _clear_altitude_window(canvas)

    canvas.colour(*WHITE)
    _draw_speed_window_outline(canvas)
    _draw_altitude_window_outline(canvas)


def _draw_target_bugs_overlay(canvas: Any, values: Mapping[str, Any]) -> None:
    """Paint MCP bugs after tape text so their complete outlines remain clean."""
    target_mach = _finite(values.get("target_ias_is_mach")) and float(values["target_ias_is_mach"]) >= 0.5
    speed_visible = not _finite(values.get("target_ias_visible")) or float(values["target_ias_visible"]) >= 0.5
    speed_bug_y = None if target_mach or not speed_visible else _bug_y(
        values.get("ias"), values.get("target_ias"), 2.15, 226
    )
    altitude_bug_y = _bug_y(
        values.get("altitude"), values.get("target_altitude"), 0.22, 226, edge_margin=27
    )
    if speed_bug_y is None and altitude_bug_y is None:
        return
    canvas.colour(*MAGENTA)
    if speed_bug_y is not None:
        speed_bug_y = int(_clamp(speed_bug_y, SPEED_TAPE.y + 13, SPEED_TAPE.bottom - 13))
        if abs(speed_bug_y - 226) <= 2:
            _draw_speed_window_outline(canvas)
        else:
            _draw_speed_target_bug_outline(canvas, speed_bug_y)
    if altitude_bug_y is not None:
        altitude_bug_y = int(_clamp(altitude_bug_y, ALTITUDE_TAPE.y + 27, ALTITUDE_TAPE.bottom - 27))
        if abs(altitude_bug_y - 226) <= 2:
            _draw_altitude_window_outline(canvas)
        else:
            _draw_altitude_target_bug_outline(canvas, altitude_bug_y)


def vertical_speed_wedge_rows() -> list[Tuple[int, int, int]]:
    """The grey V/S wedge with chamfers and the live-altitude box void."""
    wedge = VERTICAL_SPEED_WEDGE
    rows: list[Tuple[int, int, int]] = []
    for y in range(wedge.y, wedge.bottom):
        cut = max(
            0,
            (wedge.y + VERTICAL_SPEED_CHAMFER) - y,
            y - (wedge.bottom - VERTICAL_SPEED_CHAMFER),
        )
        left = _vertical_speed_left_edge(y)
        width = wedge.right - cut - left
        if width > 0:
            rows.append((left, y, width))
    return rows


def _vertical_speed_left_edge(y: int) -> int:
    """Shape the V/S left edge around the live-altitude readout.

    The two transitions are true 45-degree lines.  Between them, the edge is
    vertical and two pixels clear of the white box, producing the aircraft's
    characteristic inset rather than letting the two grey/black regions fight.
    """
    notch_top = ALTITUDE_WINDOW.y
    notch_bottom = ALTITUDE_WINDOW.bottom
    slope_top = notch_top - VERTICAL_SPEED_NOTCH_SLOPE
    slope_bottom = notch_bottom + VERTICAL_SPEED_NOTCH_SLOPE
    if y < slope_top or y >= slope_bottom:
        return VERTICAL_SPEED_WEDGE.x
    if y < notch_top:
        return VERTICAL_SPEED_WEDGE.x + (y - slope_top)
    if y < notch_bottom:
        return VERTICAL_SPEED_NOTCH_X
    return VERTICAL_SPEED_NOTCH_X - (y - notch_bottom)


def _clear_vertical_speed_notch(canvas: Any) -> None:
    """Cut the new inset out of the established low-cost font-tile wedge."""
    rows: list[Tuple[int, int, int]] = []
    for y in range(VERTICAL_SPEED_WEDGE.y, VERTICAL_SPEED_WEDGE.bottom):
        left = _vertical_speed_left_edge(y)
        if left > VERTICAL_SPEED_WEDGE.x:
            rows.append((VERTICAL_SPEED_WEDGE.x, y, left - VERTICAL_SPEED_WEDGE.x))
    _emit_rows(canvas, BLACK, rows)


def _vs_offset(feet_per_minute: float) -> float:
    """The 737 vertical-speed scale: linear to 1000, then twice compressed."""
    magnitude = min(abs(float(feet_per_minute)), 6000.0)
    if magnitude <= 1000.0:
        offset = magnitude / 1000.0 * 29.0
    elif magnitude <= 2000.0:
        offset = 29.0 + (magnitude - 1000.0) / 1000.0 * 29.0
    else:
        offset = 58.0 + (magnitude - 2000.0) / 4000.0 * 38.0
    return math.copysign(offset, feet_per_minute)


def _draw_vertical_speed(canvas: Any, values: Mapping[str, Any]) -> None:
    """Draw the grey V/S wedge, its scale, and the pivoting needle."""
    notched_shape = (
        getattr(_RIGHT_STRIP_TILES, "VERTICAL_SPEED_WEDGE", None)
        if _RIGHT_STRIP_TILES is not None else None
    )
    legacy_shape = False
    if notched_shape is not None:
        _stamp_shape_tiles(canvas, notched_shape, VS_GREY)
    elif _draw_tiles(canvas, "VERTICAL_SPEED_WEDGE", VS_GREY):
        legacy_shape = True
    else:
        _emit_rows(canvas, VS_GREY, vertical_speed_wedge_rows())

    canvas.colour(*WHITE)
    for thousands in (1.0, 2.0, 6.0):
        for sign in (-1.0, 1.0):
            y = int(round(226 - _vs_offset(sign * thousands * 1000.0)))
            canvas.fill(VERTICAL_SPEED_TICK_X, y - 1, 16, 2)
    for thousands in (0.5, 1.5, 4.0):
        for sign in (-1.0, 1.0):
            y = int(round(226 - _vs_offset(sign * thousands * 1000.0)))
            canvas.fill(VERTICAL_SPEED_TICK_X, y - 1, 10, 2)

    for thousands, label in ((6.0, "6"), (2.0, "2"), (1.0, "1")):
        for sign in (-1.0, 1.0):
            y = int(round(226 - _vs_offset(sign * thousands * 1000.0)))
            _draw_number_text(
                canvas,
                _slot("vertical speed label", VERTICAL_SPEED_LABELS.x, y - 14,
                      VERTICAL_SPEED_LABELS.width),
                label,
                WHITE,
                VS_GREY,
            )

    if _finite(values.get("vertical_speed")):
        vertical_speed = float(values["vertical_speed"])
        pointer_y = int(round(226 - _vs_offset(vertical_speed)))
        canvas.colour(*WHITE)
        # The needle pivots at the middle of the V/S strip's far-right edge.
        # Its inboard end follows the scale beside the altitude box; the fixed
        # outboard pivot never rides up to the top or down to the bottom.
        travel = pointer_y - VERTICAL_SPEED_PIVOT_Y
        span = VERTICAL_SPEED_PIVOT_X - VERTICAL_SPEED_NEEDLE_X
        if abs(travel) <= span:
            for run_x, run_width, y in _sloped_runs(
                VERTICAL_SPEED_NEEDLE_X,
                VERTICAL_SPEED_PIVOT_X,
                lambda px: pointer_y + (VERTICAL_SPEED_PIVOT_Y - pointer_y)
                * (px - VERTICAL_SPEED_NEEDLE_X) / float(span),
            ):
                canvas.fill(run_x, y - 1, run_width, 3)
        else:
            steps = abs(travel)
            for step in range(steps):
                first = pointer_y + int(round(-travel * step / steps))
                second = pointer_y + int(round(-travel * (step + 1) / steps))
                x = VERTICAL_SPEED_NEEDLE_X + int(round(span * step / steps))
                canvas.fill(x, min(first, second), 3, max(2, abs(second - first)))
        # End every raster path on the same visible far-right centre point.
        canvas.fill(
            VERTICAL_SPEED_PIVOT_X - 1,
            VERTICAL_SPEED_PIVOT_Y - 1,
            2,
            3,
        )

    # Old resources remain a safe fallback.  Their un-notched slot-6 shape is
    # cut here; the active slot-3 resource already carries the complete void.
    if legacy_shape:
        _clear_vertical_speed_notch(canvas)


def compass_rose_rows() -> list[Tuple[int, int, int]]:
    """The grey heading rose as exact one-pixel rows."""
    rows: list[Tuple[int, int, int]] = []
    for y in range(COMPASS_TOP, HEIGHT):
        half_width = math.sqrt(
            max(0.0, COMPASS_RADIUS * COMPASS_RADIUS - (y + 0.5 - COMPASS_CENTER_Y) ** 2)
        )
        left = int(round(COMPASS_CENTER_X - half_width))
        width = int(round(half_width * 2.0))
        if width > 0:
            rows.append((left, y, width))
    return rows


def _draw_compass(canvas: Any, values: Mapping[str, Any]) -> None:
    """Draw the lower grey heading dial, including its live tape labels."""
    center_x, center_y, radius = COMPASS_CENTER_X, COMPASS_CENTER_Y, COMPASS_RADIUS
    if not _draw_tiles(canvas, "COMPASS_ROSE", TAPE_GREY):
        _emit_rows(canvas, TAPE_GREY, compass_rose_rows())

    canvas.colour(*WHITE)
    for relative in range(-50, 51, 5):
        radians = math.radians(relative)
        x = int(round(center_x + radius * math.sin(radians)))
        y = int(round(center_y - radius * math.cos(radians)))
        length = 10 if relative % 30 == 0 else (8 if relative % 10 == 0 else 5)
        if 0 <= y < HEIGHT:
            canvas.fill(x - 1, y, 2, min(length, HEIGHT - y))

    # Fixed pointer marks share the existing white pass.  Text is written
    # afterwards with a grey background, so it remains clean and unclipped.
    canvas.fill(310, COMPASS_TOP - 16, 20, 2)
    canvas.fill(312, COMPASS_TOP - 14, 16, 2)
    canvas.fill(314, COMPASS_TOP - 12, 12, 2)
    canvas.fill(316, COMPASS_TOP - 10, 8, 2)
    canvas.fill(319, COMPASS_TOP - 8, 2, 6)
    canvas.fill(319, COMPASS_TOP + 28, 2, 31)
    canvas.fill(310, COMPASS_TOP + 41, 20, 2)

    heading = values.get("heading")
    if _finite(heading):
        heading_value = float(heading)
        _draw_number_text(canvas, COMPASS_TEXT, _heading_label(heading_value), WHITE, TAPE_GREY)
        for relative, x in ((-30, 221), (30, 386)):
            _draw_number_text(
                canvas,
                # Raised clear of the selected-heading readout below it: the
                # native cell is opaque, so a four-pixel overlap would clip the
                # bottom of these numbers.
                _slot("compass side label", x, COMPASS_TOP + 30, 34, "center"),
                _heading_label(heading_value + relative),
                WHITE,
                TAPE_GREY,
            )
    _draw_number_text(canvas, MAG_LABEL, "MAG", GREEN, TAPE_GREY)
    target_heading = values.get("target_heading")
    if _finite(target_heading):
        _draw_number_text(
            canvas,
            SELECTED_HEADING,
            _tight_join(f"{int(round(float(target_heading))) % 360:03d}", "H"),
            MAGENTA,
            TAPE_GREY,
        )


def _draw_minimums(canvas: Any, values: Mapping[str, Any]) -> None:
    """Draw the approach minimums reference and its pointer on the tape.

    `BARO` minimums are an altitude, so they also carry a pointer on the
    altitude tape.  `RADIO` minimums are a height above the ground, which no
    barometric tape can show, so those are annunciated as text only - the same
    rule the aircraft follows.

    Both turn amber at or below the setting, so the pilot sees the change
    without reading the number.
    """
    minimums = values.get("minimums")
    if not _finite(minimums) or float(minimums) <= 0.0:
        return
    setting = float(minimums)
    if _finite(values.get("minimums_mode")):
        # Zibo's captain selector is 0=RADIO, 1=BARO.
        radio = float(values["minimums_mode"]) < 0.5
    else:
        radio = _finite(values.get("minimums_is_radio")) and float(values["minimums_is_radio"]) >= 0.5

    altitude = values.get("altitude")
    reference = values.get("radio_altitude") if radio else altitude
    reached = _finite(reference) and float(reference) <= setting
    colour = AMBER if reached else GREEN

    label = f"{'RADIO' if radio else 'BARO'} {int(round(setting))}"
    _draw_number_text(canvas, MINIMUMS_LABEL, label, colour, BLACK)

    if radio or not _finite(altitude):
        return
    y = int(round(226 - (setting - float(altitude)) * 0.22))
    if not ALTITUDE_TAPE.y + 10 <= y <= ALTITUDE_TAPE.bottom - 10:
        return
    canvas.colour(*colour)
    canvas.fill(ALTITUDE_TAPE.right - 8, y - 1, 24, 3)
    canvas.fill(ALTITUDE_TAPE.right + 13, y - 9, 3, 19)


def _slip_skid_geometry(
    pointer_slope: float,
    slip: float,
) -> Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]]:
    """Return centre, tangent and radial axes for the roll-following marker."""
    radial, tangent = _bank_axes(pointer_slope)
    displacement = _clamp(float(slip), -8.0, 8.0) * 3.0
    center = (
        320.0 + 88.0 * radial[0] + displacement * tangent[0],
        226.0 + 88.0 * radial[1] + displacement * tangent[1],
    )
    return center, tangent, radial


def _draw_slip_skid(
    canvas: Any,
    values: Mapping[str, Any],
    pointer_slope: float,
) -> None:
    """Draw the slip/skid marker beneath and aligned with the roll pointer."""
    slip = values.get("slip_skid")
    if not _finite(slip):
        return
    center, tangent, radial = _slip_skid_geometry(pointer_slope, float(slip))
    half_width = 9.0
    left = (
        center[0] - half_width * tangent[0],
        center[1] - half_width * tangent[1],
    )
    right = (
        center[0] + half_width * tangent[0],
        center[1] + half_width * tangent[1],
    )
    canvas.colour(*WHITE)
    for x, y, width, height in _straight_line_rects(*left, *right, 3):
        canvas.fill(x, y, width, height)
    for endpoint in (left, right):
        inward = (
            endpoint[0] - 5.0 * radial[0],
            endpoint[1] - 5.0 * radial[1],
        )
        for x, y, width, height in _straight_line_rects(
            *endpoint, *inward, 2
        ):
            canvas.fill(x, y, width, height)


def _draw_diamond(canvas: Any, x: int, y: int, radius: int,
                  colour: Tuple[int, int, int]) -> None:
    canvas.colour(*colour)
    for offset in range(-radius, radius + 1, 2):
        half = radius - abs(offset)
        canvas.fill(x - half, y + offset, max(2, half * 2 + 1), 2)


def _draw_ils_guidance(canvas: Any, values: Mapping[str, Any]) -> None:
    """Expanded localizer and glideslope scales inside the attitude field."""
    localizer = values.get("localizer_deviation")
    glideslope = values.get("glideslope_deviation")
    localizer_valid = values.get("localizer_valid")
    glideslope_valid = values.get("glideslope_valid")
    approach = (
        _finite(values.get("approach_mode"))
        and float(values["approach_mode"]) >= 0.5
    )

    show_localizer = _finite(localizer) and (
        not _finite(localizer_valid) or float(localizer_valid) >= 0.5
    )
    if show_localizer:
        canvas.colour(*BLACK)
        canvas.fill(244, LOCALIZER_Y - 12, 152, 24)
        canvas.colour(*WHITE)
        canvas.fill(319, LOCALIZER_Y - 9, 3, 18)
        for dot in (-2, -1, 1, 2):
            x = 320 + dot * ILS_DOT_SPACING
            canvas.fill(x - 3, LOCALIZER_Y - 3, 6, 6)
        x = int(round(320 + _clamp(float(localizer), -2.5, 2.5) * ILS_DOT_SPACING))
        _draw_diamond(canvas, x, LOCALIZER_Y, 8, MAGENTA)
    elif approach and _finite(localizer_valid) and float(localizer_valid) < 0.5:
        _draw_text(canvas, _slot("LOC fail", 245, LOCALIZER_Y - 14, 51), "LOC", AMBER, BLACK)

    show_glideslope = _finite(glideslope) and (
        not _finite(glideslope_valid) or float(glideslope_valid) >= 0.5
    )
    if show_glideslope:
        canvas.colour(*BLACK)
        canvas.fill(GLIDESLOPE_X - 12, 150, 24, 152)
        canvas.colour(*WHITE)
        canvas.fill(GLIDESLOPE_X - 9, 225, 18, 3)
        for dot in (-2, -1, 1, 2):
            y = 226 + dot * ILS_DOT_SPACING
            canvas.fill(GLIDESLOPE_X - 3, y - 3, 6, 6)
        y = int(round(226 - _clamp(float(glideslope), -2.5, 2.5) * ILS_DOT_SPACING))
        _draw_diamond(canvas, GLIDESLOPE_X, y, 8, MAGENTA)
    elif approach and _finite(glideslope_valid) and float(glideslope_valid) < 0.5:
        _draw_text(canvas, _slot("GS fail", 395, 153, 34), "GS", AMBER, BLACK)


def _draw_field_elevation(canvas: Any, values: Mapping[str, Any]) -> None:
    """Do not invent a landing-altitude presentation from an FMC value.

    Zibo's ``dest_runway_alt`` tells us the destination elevation, but it does
    not say that the aircraft's PFD is currently displaying a landing/QFE
    altitude band.  Treating the value as a visibility flag painted a false
    green-and-black hatch over most of the BB35/BB36 altitude tape, including
    while the aircraft was below a higher destination field.  Keep sampling
    the value for a future source-verified landing-altitude indication, but
    leave the tape untouched until its real display-enable state is captured.
    """
    del canvas, values


def _draw_auxiliary_text(canvas: Any, values: Mapping[str, Any]) -> None:
    mach = values.get("mach")
    _draw_number_text(canvas, MACH_LABEL, ("M " + _mach(mach)) if _finite(mach) else "", GREEN, BLACK)

    radio = values.get("radio_altitude")
    if _finite(radio) and -20.0 <= float(radio) <= 2500.0:
        minimums = values.get("minimums")
        colour = AMBER if _finite(minimums) and float(radio) <= float(minimums) else WHITE
        _draw_number_text(canvas, RADIO_ALT_LABEL, str(max(0, int(round(float(radio))))), colour, BLACK)

    identifier = str(values.get("nav_identifier") or "").strip().upper()[:5]
    frequency = values.get("nav_frequency")
    ils = identifier
    if _finite(frequency) and float(frequency) > 0.0:
        numeric = float(frequency)
        numeric = numeric / 100.0 if numeric > 1000.0 else numeric
        frequency_text = f"{numeric:.2f}".rstrip("0").rstrip(".")
        ils = _tight_join(identifier or "ILS", frequency_text)
    _draw_number_text(canvas, ILS_LABEL, ils, CYAN, BLACK)

    marker = ""
    marker_colour = WHITE
    if _finite(values.get("marker_outer")) and float(values["marker_outer"]) >= 0.5:
        marker, marker_colour = "OM", CYAN
    elif _finite(values.get("marker_middle")) and float(values["marker_middle"]) >= 0.5:
        marker, marker_colour = "MM", AMBER
    elif _finite(values.get("marker_inner")) and float(values["marker_inner"]) >= 0.5:
        marker = "IM"
    _draw_text(canvas, MARKER_LABEL, marker, marker_colour, BLACK)

    _draw_text(
        canvas, FMA_ARMED_LEFT,
        _fma(values.get("fma_lateral_armed"), FMA_LATERAL_LABELS), WHITE, BLACK,
    )
    _draw_text(
        canvas, FMA_ARMED_RIGHT,
        _fma(values.get("fma_vertical_armed"), FMA_VERTICAL_LABELS), WHITE, BLACK,
    )


def _draw_compass_overlay(canvas: Any, values: Mapping[str, Any]) -> None:
    """Add the moving magenta heading bug after the native text layer."""
    center_x, center_y, radius = COMPASS_CENTER_X, COMPASS_CENTER_Y, COMPASS_RADIUS
    heading = values.get("heading")
    target_heading = values.get("target_heading")
    if not _finite(heading) or not _finite(target_heading):
        return
    relative_target = _heading_delta(float(target_heading), float(heading))
    if abs(relative_target) > 60.0:
        return
    radians = math.radians(relative_target)
    bug_x = int(round(center_x + radius * math.sin(radians)))
    bug_y = int(round(center_y - radius * math.cos(radians)))
    if abs(relative_target) <= 4.0:
        bug_x, bug_y = center_x, COMPASS_TOP - 7
    canvas.colour(*MAGENTA)
    canvas.fill(bug_x - 8, bug_y - 4, 16, 2)
    canvas.fill(bug_x - 6, bug_y - 6, 2, 5)
    canvas.fill(bug_x + 4, bug_y - 6, 2, 5)
    canvas.fill(bug_x - 2, bug_y - 2, 4, 8)


def _draw_text_layer(
    canvas: Any,
    values: Mapping[str, Any],
    speed_labels: list[Tuple[int, int]],
    altitude_labels: list[Tuple[int, int]],
) -> None:
    target_mach = _finite(values.get("target_ias_is_mach")) and float(values["target_ias_is_mach"]) >= 0.5
    selected_speed = _mach(values.get("target_ias")) if target_mach else _speed(values.get("target_ias"))
    _draw_number_text(canvas, SELECTED_SPEED, selected_speed, MAGENTA, BLACK)
    _draw_number_text(canvas, SELECTED_ALTITUDE, _altitude(values.get("target_altitude")), MAGENTA, BLACK)

    _draw_text(canvas, FMA_SPEED, _fma(values.get("fma_speed"), FMA_SPEED_LABELS), GREEN, FMA_GREY)
    _draw_text(canvas, FMA_LATERAL, _fma(values.get("fma_lateral"), FMA_LATERAL_LABELS), GREEN, FMA_GREY)
    _draw_text(canvas, FMA_VERTICAL, _fma(values.get("fma_vertical"), FMA_VERTICAL_LABELS), GREEN, FMA_GREY)

    fd_visible = _finite(values.get("fd_command_visible")) and float(values["fd_command_visible"]) >= 0.5
    fd_command = int(round(float(values["fd_command"]))) if _finite(values.get("fd_command")) else 0
    land_mode = int(round(float(values["land_mode"]))) if _finite(values.get("land_mode")) else 0
    command = ""
    command_colour = WHITE
    if fd_visible:
        if land_mode == 1:
            command, command_colour = "LAND 2", GREEN
        elif land_mode == 2:
            command, command_colour = "LAND 3", GREEN
        elif fd_command == 2:
            command, command_colour = "CMD", GREEN
        elif fd_command == 1:
            command = "FD"
    _draw_text(canvas, COMMAND, command, command_colour, BLACK)

    _draw_speed_readout(canvas, values)
    _draw_altitude_readout(canvas, values)
    for value, y in speed_labels:
        text = _speed_tape(value)
        if text:
            _draw_number_text(
                canvas,
                _slot("speed tape", SPEED_LABEL_X, y - 12, SPEED_TAPE_LABEL_WIDTH),
                text,
                WHITE,
                TAPE_GREY,
            )
    for value, y in altitude_labels:
        # Four compact 17-pixel cells are 68 pixels wide.  Starting at 482
        # leaves a clean two-pixel margin either side of the 72-pixel strip,
        # so real altitude values such as 2,400 remain entirely contained.
        _draw_number_text(
            canvas,
            _slot("altitude tape", 482, y - 12, ALTITUDE_TAPE_LABEL_WIDTH, "right"),
            _altitude(value),
            WHITE,
            TAPE_GREY,
        )


    use_hpa = _finite(values.get("baro_hpa")) and float(values["baro_hpa"]) >= 0.5
    std = _finite(values.get("baro_std")) and float(values["baro_std"]) >= 0.5
    baro_number, baro_unit = _baro(values.get("baro"), use_hpa, std)
    if baro_number == "STD":
        _draw_number_text(canvas, BARO_STD, baro_number, GREEN, BLACK)
        # The 737 boxes STD so a standard setting cannot be read as a local
        # altimeter setting.  The box stays inside the barometer zone.
        canvas.colour(*AMBER)
        _draw_outline(
            canvas,
            Rect(BARO_STD.rect.x - 6, BARO_STD.rect.y - 4,
                 BARO_STD.rect.width + 12, BARO_STD.rect.height + 8),
            2,
        )
    elif use_hpa:
        _draw_number_text(canvas, BARO_VALUE_UNIT, _tight_join(baro_number, baro_unit), GREEN, BLACK)
    else:
        _draw_number_text(canvas, BARO_VALUE_UNIT, _tight_join(baro_number, baro_unit), GREEN, BLACK)


def _draw_speed_readout(canvas: Any, values: Mapping[str, Any]) -> None:
    """Draw the live IAS as two fixed digits and one rolling units drum.

    A native font cell is fully opaque and cannot be clipped, so the drum is
    drawn first and the parts that fall outside its window are painted back in
    afterwards: tape grey outside the readout box, black inside it.  The box
    outline is then redrawn so the drum can never cut through it.
    """
    ias = values.get("ias")
    if not _finite(ias) or float(ias) < 0.0 or float(ias) > 999.0:
        _draw_number_text(canvas, SPEED_VALUE, "--", WHITE, BLACK)
        _draw_number_text(canvas, _slot("live speed units", SPEED_DRUM.x, 211, FONT_CELL_WIDTH), "-", WHITE, BLACK)
        return

    speed = float(ias)
    lead = int(speed) // 10
    _draw_number_text(canvas, SPEED_VALUE, str(lead) if lead else "", WHITE, BLACK)

    units = int(speed) % 10
    fraction = speed - math.floor(speed)
    base_y = 211 - int(round(fraction * SPEED_DRUM_PITCH))
    # Neighbours first, then the live digit over them, so the digit that is
    # actually indicated is never clipped by the one rolling past it.
    for step in (-1, 1, 0):
        digit = (units + step) % 10
        _draw_number_text(
            canvas,
            _slot("live speed drum", SPEED_DRUM.x, base_y + step * SPEED_DRUM_PITCH, FONT_CELL_WIDTH),
            str(digit),
            WHITE,
            BLACK,
        )

    # Trim the drum back to its window: tape grey where the rolling cells
    # spilled onto the tape, black where they spilled inside the readout box.
    # The tape numbers are drawn after this, so a number that shares the
    # column simply repaints its own opaque cell over the trimmed area.
    spill_top = 211 - 2 * SPEED_DRUM_PITCH
    spill_bottom = 211 + SPEED_DRUM_PITCH + FONT_CELL_HEIGHT + 1
    canvas.colour(*TAPE_GREY)
    canvas.fill(SPEED_DRUM.x, spill_top, SPEED_DRUM.width, SPEED_WINDOW.y - spill_top)
    canvas.fill(SPEED_DRUM.x, SPEED_WINDOW.bottom, SPEED_DRUM.width, spill_bottom - SPEED_WINDOW.bottom)
    canvas.colour(*BLACK)
    canvas.fill(SPEED_DRUM.x, SPEED_WINDOW.y + 2, SPEED_DRUM.width, SPEED_DRUM.y - SPEED_WINDOW.y - 2)
    canvas.fill(SPEED_DRUM.x, SPEED_DRUM.bottom, SPEED_DRUM.width, SPEED_WINDOW.bottom - SPEED_DRUM.bottom - 2)
    canvas.colour(*WHITE)
    _draw_speed_window_outline(canvas)


def _draw_altitude_hatch(canvas: Any, rect: Rect) -> None:
    """The green and black hatch shown in the ten-thousands position.

    Boeing marks altitudes below 10,000 feet this way, so a five-figure
    altitude can never be misread as a four-figure one.
    """
    canvas.colour(*GREEN)
    canvas.fill(rect.x + 1, rect.y + 3, rect.width - 2, rect.height - 6)
    canvas.colour(*BLACK)
    for offset in range(0, rect.height - 6, 6):
        canvas.fill(rect.x + 1, rect.y + 3 + offset, rect.width - 2, 3)


def _draw_compact_altitude_digits(
    canvas: Any,
    name: str,
    x: int,
    y: int,
    value: str,
    foreground: Tuple[int, int, int] = WHITE,
) -> None:
    """Draw altitude digits at a safe 10-pixel visual pitch.

    Native cells remain the proven opaque 17x29 size.  The slot-3 aliases move
    their 4-7-pixel ink left inside each cell, where it ends before x=10.
    Painting those cells left-to-right therefore removes the artificial gaps
    without erasing ink, and keeps the last rolling cell out of the V/S dirty
    region so normal altitude motion remains fast.
    """
    for index, character in enumerate(value):
        if character.isdigit():
            encoded = _TIGHT_DIGIT_ALIASES[int(character)]
        elif character == "-":
            encoded = _TIGHT_ALTITUDE_MINUS_ALIAS
        else:
            encoded = character
        _draw_number_text(
            canvas,
            _slot(
                f"{name} {index}",
                x + index * ALTITUDE_DIGIT_PITCH,
                y,
                FONT_CELL_WIDTH,
            ),
            encoded,
            foreground,
            BLACK,
        )


def _draw_altitude_readout(canvas: Any, values: Mapping[str, Any]) -> None:
    """Draw the live altitude: hatch or ten-thousands, two digits, and a drum.

    The last two figures roll in twenty-foot steps exactly as they do on the
    aircraft.  As with the airspeed drum, the rolling cells are drawn first and
    their overspill is painted back afterwards; the whole drum sits over the
    tape, so that trim is a single colour.
    """
    altitude = values.get("altitude")
    if not _finite(altitude) or not -2000.0 <= float(altitude) <= 99999.0:
        _draw_compact_altitude_digits(
            canvas, "unavailable altitude", ALTITUDE_VALUE.rect.x,
            ALTITUDE_VALUE.rect.y, "---",
        )
        return

    value = float(altitude)
    whole = int(abs(value))
    ten_thousands = whole // 10000
    if value < 0.0:
        # The minus takes the ten-thousands position, which cannot be in use
        # below sea level anyway.
        _draw_number_text(
            canvas,
            _slot("altitude sign", ALTITUDE_TEN_THOUSANDS.x, ALTITUDE_TEN_THOUSANDS.y,
                  FONT_CELL_WIDTH),
            "-",
            WHITE,
            BLACK,
        )
    elif ten_thousands == 0:
        _draw_altitude_hatch(canvas, ALTITUDE_TEN_THOUSANDS)
    else:
        _draw_number_text(
            canvas,
            _slot("altitude ten thousands", ALTITUDE_TEN_THOUSANDS.x, ALTITUDE_TEN_THOUSANDS.y,
                  FONT_CELL_WIDTH),
            str(ten_thousands % 10),
            WHITE,
            BLACK,
        )
    _draw_compact_altitude_digits(
        canvas,
        "altitude thousands",
        ALTITUDE_FIXED_X,
        ALTITUDE_TEN_THOUSANDS.y,
        f"{(whole // 1000) % 10}{(whole // 100) % 10}",
    )

    magnitude = abs(value)
    stepped = math.floor(magnitude / ALTITUDE_DRUM_STEP) * ALTITUDE_DRUM_STEP
    fraction = (magnitude - stepped) / ALTITUDE_DRUM_STEP
    base_y = 211 - int(round(fraction * ALTITUDE_DRUM_PITCH))
    for step in (-1, 1, 0):
        pair = int(abs(stepped + step * ALTITUDE_DRUM_STEP)) % 100
        _draw_compact_altitude_digits(
            canvas,
            "altitude drum",
            ALTITUDE_DRUM.x,
            base_y + step * ALTITUDE_DRUM_PITCH,
            f"{pair:02d}",
        )

    spill_top = 211 - 2 * ALTITUDE_DRUM_PITCH
    spill_bottom = 211 + ALTITUDE_DRUM_PITCH + FONT_CELL_HEIGHT + 1
    tape_spill_width = max(0, ALTITUDE_TAPE.right - ALTITUDE_DRUM.x)
    outboard_spill_x = max(ALTITUDE_TAPE.right, ALTITUDE_DRUM.x)
    outboard_spill_width = max(0, ALTITUDE_DRUM.right - outboard_spill_x)
    canvas.colour(*TAPE_GREY)
    canvas.fill(ALTITUDE_DRUM.x, spill_top, tape_spill_width, ALTITUDE_WINDOW.y - spill_top)
    canvas.fill(ALTITUDE_DRUM.x, ALTITUDE_WINDOW.bottom, tape_spill_width,
                spill_bottom - ALTITUDE_WINDOW.bottom)
    canvas.colour(*BLACK)
    canvas.fill(outboard_spill_x, spill_top, outboard_spill_width,
                ALTITUDE_WINDOW.y - spill_top)
    canvas.fill(outboard_spill_x, ALTITUDE_WINDOW.bottom, outboard_spill_width,
                spill_bottom - ALTITUDE_WINDOW.bottom)
    canvas.fill(ALTITUDE_DRUM.x, ALTITUDE_WINDOW.y + 2, ALTITUDE_DRUM.width,
                ALTITUDE_DRUM.y - ALTITUDE_WINDOW.y - 2)
    canvas.fill(ALTITUDE_DRUM.x, ALTITUDE_DRUM.bottom, ALTITUDE_DRUM.width,
                ALTITUDE_WINDOW.bottom - ALTITUDE_DRUM.bottom - 2)
    canvas.colour(*WHITE)
    _draw_altitude_window_outline(canvas)


def _draw_whole_frame(canvas: Any, values: Mapping[str, Any]) -> None:
    """Draw every element of one live PFD frame."""
    canvas.colour(*BLACK)
    canvas.fill(0, 0, WIDTH, HEIGHT)

    # Header zones are explicitly wider than their longest Zibo FMA labels.
    canvas.colour(*FMA_GREY)
    canvas.fill(70, 38, 550, 29)
    canvas.colour(*WHITE)
    canvas.fill(246, 38, 2, 29)
    canvas.fill(420, 38, 2, 29)

    horizon_y, slope = _draw_horizon(canvas, values)
    _draw_bank_and_pitch(canvas, horizon_y, slope)
    _draw_pitch_limit(canvas, values)
    _draw_rising_runway(canvas, values)
    _draw_slip_skid(canvas, values, -slope)
    _draw_flight_path_vector(canvas, values)
    _draw_fd_and_aircraft(canvas, values)
    _draw_ils_guidance(canvas, values)
    speed_labels, altitude_labels = _draw_tapes(canvas, values)
    _draw_field_elevation(canvas, values)
    _draw_altitude_trend(canvas, values)
    _draw_speed_bands(canvas, values)
    _draw_speed_trend(canvas, values)
    speed_bugs = _draw_speed_bugs(canvas, values)
    _draw_vertical_speed(canvas, values)
    _draw_live_windows_and_bugs(canvas, values)
    _draw_compass(canvas, values)
    _draw_text_layer(canvas, values, speed_labels, altitude_labels)
    for mark, y in speed_bugs:
        cell = Rect(SPEED_BUG_LABEL_X, y - 14, SPEED_BUG_LABEL_WIDTH, FONT_CELL_HEIGHT)
        if cell.intersects(SPEED_WINDOW):
            continue  # the readout owns that space; the bug's mark still shows
        _draw_number_text(
            canvas,
            _slot("speed bug", SPEED_BUG_LABEL_X, y - 14, SPEED_BUG_LABEL_WIDTH, "right"),
            mark, GREEN, BLACK,
        )
    _draw_minimums(canvas, values)
    _draw_auxiliary_text(canvas, values)
    _draw_target_bugs_overlay(canvas, values)
    _draw_compass_overlay(canvas, values)


def _attitude_is_moving(values: Mapping[str, Any], state: Any) -> bool:
    """True when pitch or roll changed enough this frame to be worth economy."""
    if state is None or len(state) < 4:
        return False
    previous_pitch, previous_roll = state[3]
    pitch = float(values["pitch"]) if _finite(values.get("pitch")) else 0.0
    roll = float(values["roll"]) if _finite(values.get("roll")) else 0.0
    return (abs(pitch - previous_pitch) + abs(roll - previous_roll)) > MOTION_DEGREES_PER_FRAME


def _steady(values: Mapping[str, Any]) -> Mapping[str, Any]:
    """Round the values whose noise would redraw the display for nothing."""
    steady = dict(values)
    for name, step in QUANTISED_VALUES.items():
        value = steady.get(name)
        if _finite(value):
            steady[name] = round(float(value) / step) * step
    return steady


class _OpRecorder:
    """Collects one frame's native commands instead of sending them."""

    __slots__ = ("ops", "_colour", "_muslimsim_bank_line_font")

    def __init__(self, bank_line_font: bool = False) -> None:
        self.ops: list = []
        self._colour = BLACK
        self._muslimsim_bank_line_font = bool(bank_line_font)

    def colour(self, red: int, green: int, blue: int) -> None:
        self._colour = (int(red), int(green), int(blue))

    def fill(self, x: int, y: int, width: int, height: int) -> None:
        if width > 0 and height > 0:
            self.ops.append(("f", self._colour, int(x), int(y), int(width), int(height)))

    def text(self, x: int, y: int, value: str, foreground, background, font_id: int) -> None:
        self.ops.append(
            ("t", tuple(foreground), tuple(background), int(x), int(y), str(value), int(font_id))
        )


def _op_rect(op: tuple) -> Tuple[int, int, int, int]:
    if op[0] == "f":
        return op[2], op[3], op[4], op[5]
    if op[6] in BANK_LINE_FONT_IDS:
        return (
            op[3], op[4],
            len(op[5]) * BANK_LINE_CELL_WIDTH,
            BANK_LINE_CELL_HEIGHT,
        )
    return op[3], op[4], len(op[5]) * FONT_CELL_WIDTH, FONT_CELL_HEIGHT


def _dirty_boxes(new_ops: list, old_ops: list) -> list:
    """Rectangles covering every pixel this frame can differ in.

    Frames are compared as multisets of commands rather than position by
    position, so a tape number scrolling in or out shifts nothing else.  A
    pixel outside these boxes is covered by exactly the same commands, in the
    same order, as it was last frame, so it cannot have changed.
    """
    changed = Counter(new_ops)
    changed.subtract(Counter(old_ops))
    marks = [op for op, count in changed.items() if count]
    if not marks:
        return []

    columns = (WIDTH + DIRTY_CELL - 1) // DIRTY_CELL
    rows = (HEIGHT + DIRTY_CELL - 1) // DIRTY_CELL
    grid = bytearray(columns * rows)

    def span(op):
        x, y, width, height = _op_rect(op)
        return (
            max(0, x // DIRTY_CELL),
            max(0, y // DIRTY_CELL),
            min(columns - 1, (x + width - 1) // DIRTY_CELL),
            min(rows - 1, (y + height - 1) // DIRTY_CELL),
        )

    def mark(op):
        left, top, right, bottom = span(op)
        for row in range(top, bottom + 1):
            base = row * columns
            for column in range(left, right + 1):
                grid[base + column] = 1

    def touches(op):
        left, top, right, bottom = span(op)
        for row in range(top, bottom + 1):
            base = row * columns
            for column in range(left, right + 1):
                if grid[base + column]:
                    return True
        return False

    for op in marks:
        mark(op)

    # A fill can be clipped to the dirty area, so redrawing it disturbs
    # nothing outside.  A run of opaque font cells cannot: redrawing one
    # repaints its whole width, wiping anything later that was drawn over it -
    # the heading ticks and MAG sit on top of the rose tiles exactly like
    # that.  So any text run reaching into the dirty area drags all of itself
    # in, and that repeats until the area stops growing.
    pending = [op for op in new_ops if op[0] == "t"]
    while pending:
        remaining = []
        grew = False
        for op in pending:
            if touches(op):
                mark(op)
                grew = True
            else:
                remaining.append(op)
        if not grew:
            break
        pending = remaining

    # Merge the marked cells: runs across a row, then identical runs stacked.
    boxes: list = []
    for row in range(rows):
        column = 0
        while column < columns:
            if not grid[row * columns + column]:
                column += 1
                continue
            start = column
            while column < columns and grid[row * columns + column]:
                column += 1
            box = [start * DIRTY_CELL, row * DIRTY_CELL,
                   (column - start) * DIRTY_CELL, DIRTY_CELL]
            previous = boxes[-1] if boxes else None
            if (previous is not None and previous[0] == box[0] and previous[2] == box[2]
                    and previous[1] + previous[3] == box[1]):
                previous[3] += DIRTY_CELL
            else:
                boxes.append(box)
    return [
        (x, y, min(width, WIDTH - x), min(height, HEIGHT - y))
        for x, y, width, height in boxes
    ]


def _emit_frame(canvas: Any, ops: list, boxes: list) -> None:
    """Replay a frame's commands, clipped to the boxes that can have changed."""
    active = None
    pending_fill = None

    def flush_fill() -> None:
        """Send one coalesced solid rectangle without changing draw order."""
        nonlocal active, pending_fill
        if pending_fill is None:
            return
        colour, x, y, width, height = pending_fill
        if active != colour:
            canvas.colour(*colour)
            active = colour
        canvas.fill(x, y, width, height)
        pending_fill = None

    def queue_fill(
        colour: Tuple[int, int, int],
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> None:
        """Join only consecutive same-colour fills whose union is a rectangle.

        Dirty clipping often divides one solid area at cell boundaries.  The
        panel used to receive every resulting piece as a separate native
        command.  Two edge-touching pieces with an exactly rectangular union
        paint precisely the same pixels when joined, while saving one 25-byte
        command.  Anything with a gap, overlap that is not rectangular, colour
        change, or intervening text is flushed unchanged.
        """
        nonlocal pending_fill
        candidate = (tuple(colour), int(x), int(y), int(width), int(height))
        if pending_fill is not None:
            old_colour, old_x, old_y, old_width, old_height = pending_fill
            if (
                old_colour == candidate[0]
                and old_x == candidate[1]
                and old_width == candidate[3]
                and old_y + old_height == candidate[2]
            ):
                pending_fill = (
                    old_colour,
                    old_x,
                    old_y,
                    old_width,
                    old_height + candidate[4],
                )
                return
            if (
                old_colour == candidate[0]
                and old_y == candidate[2]
                and old_height == candidate[4]
                and old_x + old_width == candidate[1]
            ):
                pending_fill = (
                    old_colour,
                    old_x,
                    old_y,
                    old_width + candidate[3],
                    old_height,
                )
                return
            flush_fill()
        pending_fill = candidate

    for op in ops:
        x, y, width, height = _op_rect(op)
        if op[0] == "f":
            for box_x, box_y, box_width, box_height in boxes:
                left = max(x, box_x)
                top = max(y, box_y)
                right = min(x + width, box_x + box_width)
                bottom = min(y + height, box_y + box_height)
                if right <= left or bottom <= top:
                    continue
                queue_fill(op[1], left, top, right - left, bottom - top)
            continue
        flush_fill()
        for box_x, box_y, box_width, box_height in boxes:
            if (x < box_x + box_width and x + width > box_x
                    and y < box_y + box_height and y + height > box_y):
                # An opaque text cell cannot be clipped, but redrawing all of
                # it only repaints pixels that cell already owned.
                canvas.text(op[3], op[4], op[5], op[1], op[2], op[6])
                active = None
                break
    flush_fill()


def draw_live_pfd(canvas: Any, values: Mapping[str, Any]) -> None:
    """Draw one live PFD frame, sending only what changed since the last one.

    The panel holds what it was last sent, so repainting all of it every frame
    spends display traffic on pixels that did not move.  At roughly one
    millisecond per native report, that was the frame rate.

    A canvas that persists between frames carries its own last frame here, so
    the saving appears automatically on the live panel, while the offline tools
    build a fresh canvas per frame and still get a complete picture.
    """
    global _moving, _recovery_frame, _packed_value_phase
    steady = _steady(values)
    state = getattr(canvas, "_muslimsim_pfd_state", None)
    now = time.monotonic()
    # A complete repaint is a lifecycle operation only.  Timed left/right
    # healing looked safe in the retained-frame emulator, but the physical LCD
    # exposed the swap: one refresh showed the left MAG arc and the next the
    # right.  Page entry, reconnect and standby return still arrive with no
    # state and therefore rebuild every pixel in one atomic refresh.
    recovery_repaint = state is None
    force_full = bool(getattr(canvas, "_muslimsim_force_full_repaint", False))
    # A recovery frame uses economical complete geometry; the next ordinary
    # frame replaces only the ladder with its exact continuous angled lines.
    _moving = _attitude_is_moving(steady, state) or (
        recovery_repaint and state is None
    )
    _recovery_frame = recovery_repaint and state is None and not bool(
        getattr(canvas, "_muslimsim_force_precision", False)
    )
    force_precision = bool(
        getattr(canvas, "_muslimsim_force_precision", False)
    )
    previous_packed_phase = (
        int(state[4]) if state is not None and len(state) > 4 else 0
    )
    if force_precision:
        _packed_value_phase = 3
    elif recovery_repaint:
        # Page entry starts with economical intact runs and stages compact
        # values safely over the following refinement frames.
        _packed_value_phase = 0
    else:
        _packed_value_phase = min(3, previous_packed_phase + 1)

    recorder = _OpRecorder(
        bool(getattr(canvas, "_muslimsim_bank_line_font", False))
    )
    _draw_whole_frame(recorder, steady)

    if recovery_repaint and state is None:
        # Page entry and a live return from standby must replace every pixel.
        boxes = [(0, 0, WIDTH, HEIGHT)]
        sequence = 0
    elif force_full:
        boxes = [(0, 0, WIDTH, HEIGHT)]
        sequence = state[2] + 1
    else:
        boxes = _dirty_boxes(recorder.ops, state[0])
        sequence = state[2] + 1

    _emit_frame(canvas, recorder.ops, boxes)
    attitude = (
        float(steady["pitch"]) if _finite(steady.get("pitch")) else 0.0,
        float(steady["roll"]) if _finite(steady.get("roll")) else 0.0,
    )
    try:
        canvas._muslimsim_pfd_state = (
            recorder.ops,
            now,
            sequence,
            attitude,
            _packed_value_phase,
            0,
        )
        canvas._muslimsim_force_full_repaint = False
    except AttributeError:
        pass  # a canvas that cannot hold state simply keeps getting full frames


class _BoundsCanvas:
    """Minimal native-canvas substitute used by the offline layout contract test."""

    def __init__(self) -> None:
        self.text_runs: list[Tuple[int, int, str]] = []

    def colour(self, _red: int, _green: int, _blue: int) -> None:
        return None

    def fill(self, x: int, y: int, width: int, height: int) -> None:
        if x < 0 or y < 0 or x + width > WIDTH or y + height > HEIGHT:
            raise PfdLayoutError(f"fill outside PFD: {(x, y, width, height)}")

    def text(
        self,
        x: int,
        y: int,
        value: str,
        _foreground: Tuple[int, int, int],
        _background: Tuple[int, int, int],
        _font_id: int,
    ) -> None:
        if x < 0 or y < 0 or x + len(value) * FONT_CELL_WIDTH > WIDTH or y + FONT_CELL_HEIGHT > HEIGHT:
            raise PfdLayoutError(f"text outside PFD: {(x, y, value)!r}")
        self.text_runs.append((x, y, value))


def assert_layout_contract() -> None:
    """Offline regression check for normal, extreme, and long-label PFD states."""
    slots = (
        SELECTED_SPEED, SELECTED_ALTITUDE, FMA_SPEED, FMA_LATERAL,
        FMA_VERTICAL, COMMAND, SPEED_VALUE, ALTITUDE_VALUE, COMPASS_TEXT,
        MAG_LABEL, SELECTED_HEADING, BARO_VALUE_UNIT, BARO_STD,
        MINIMUMS_LABEL, MACH_LABEL, ILS_LABEL,
        RADIO_ALT_LABEL, MARKER_LABEL, FMA_ARMED_LEFT, FMA_ARMED_RIGHT,
    )
    for slot in slots:
        if (
            slot.rect.x < 0
            or slot.rect.y < 0
            or slot.rect.right > WIDTH
            or slot.rect.bottom > HEIGHT
            or slot.capacity < 1
        ):
            raise PfdLayoutError(f"Unsafe PFD slot: {slot.name}")
    speed_tape_label = Rect(SPEED_LABEL_X, SPEED_TAPE.y, SPEED_TAPE_LABEL_WIDTH, FONT_CELL_HEIGHT)
    altitude_tape_label = Rect(482, ALTITUDE_TAPE.y, ALTITUDE_TAPE_LABEL_WIDTH, FONT_CELL_HEIGHT)
    if (
        speed_tape_label.x < SPEED_TAPE.x
        or speed_tape_label.right > SPEED_TAPE.right
    ):
        raise PfdLayoutError("Speed tape label is not contained by its tape")
    if (
        altitude_tape_label.x < ALTITUDE_TAPE.x
        or altitude_tape_label.right > ALTITUDE_TAPE.right
    ):
        raise PfdLayoutError("Altitude tape label is not contained by its tape")
    if TAPE_TEXT_TOP_OFFSET + TAPE_TEXT_BOTTOM_OFFSET != FONT_CELL_HEIGHT:
        raise PfdLayoutError("Tape text vertical offsets do not cover one native cell")
    if ALTITUDE_WINDOW.right > VERTICAL_SPEED_WEDGE.x:
        raise PfdLayoutError("Altitude window entered the V/S bounding region")
    if (
        ALTITUDE_WINDOW.x < ALTITUDE_TAPE.x
        or ALTITUDE_WINDOW_BODY_X > ALTITUDE_TAPE.right
        or ALTITUDE_WINDOW.right >= VERTICAL_SPEED_PIVOT_X
        or VERTICAL_SPEED_NOTCH_X - ALTITUDE_WINDOW.right != ALTITUDE_VS_GAP
    ):
        raise PfdLayoutError("Altitude box/tape/V-S notch geometry is unsafe")
    if ALTITUDE_DRUM.right > ALTITUDE_TAPE.right:
        raise PfdLayoutError("Altitude drum entered the V/S dirty region")
    if (
        VERTICAL_SPEED_NEEDLE_X != 578
        or VERTICAL_SPEED_PIVOT_X != 626
        or VERTICAL_SPEED_PIVOT_Y != ALTITUDE_WINDOW.y + ALTITUDE_WINDOW.height // 2
    ):
        raise PfdLayoutError("V/S needle does not pivot at the far-right centre")
    # Required split convention: the aircraft pointer, numbered pitch ladder
    # and black aircraft reference bank together, while the white natural
    # horizon rotates oppositely.
    if HORIZON_EDGE != WHITE:
        raise PfdLayoutError("Natural horizon separator must remain white")
    right_bank_slope = math.tan(math.radians(-20.0))
    if not (
        _world_y(226.0, right_bank_slope, 240.0)
        > _world_y(226.0, right_bank_slope, 400.0)
    ):
        raise PfdLayoutError("Right-bank horizon direction is reversed")
    pointer_slope = -right_bank_slope
    if _bank_pointer_tip(pointer_slope)[0] <= 320:
        raise PfdLayoutError("Right-bank pointer no longer moves right")
    if not (
        _world_y(226.0, pointer_slope, 240.0)
        < _world_y(226.0, pointer_slope, 400.0)
    ):
        raise PfdLayoutError("Right-bank pitch ladder no longer follows pointer")
    left_bank_aircraft_slope = _aircraft_reference_slope({"roll": 20.0})
    if not (
        _world_y(226.0, left_bank_aircraft_slope, 240.0)
        > _world_y(226.0, left_bank_aircraft_slope, 400.0)
    ):
        raise PfdLayoutError(
            "Left-bank aircraft reference must lower its left wing"
        )
    ladder_center = _pitch_ladder_center(226.0, pointer_slope, 20.0)
    _ladder_radial, _ladder_tangent = _bank_axes(pointer_slope)
    if abs(
        (ladder_center[0] - 320.0) * _ladder_radial[1]
        - (ladder_center[1] - 226.0) * _ladder_radial[0]
    ) > 0.01:
        raise PfdLayoutError("Pitch ladder left the moving triangle centreline")
    slip_center, _tangent, radial = _slip_skid_geometry(pointer_slope, 0.0)
    if abs(
        (slip_center[0] - 320.0) * radial[1]
        - (slip_center[1] - 226.0) * radial[0]
    ) > 0.01:
        raise PfdLayoutError("Coordinated slip/skid marker left the roll pointer")
    if SPEED_WINDOW.intersects(ATTITUDE) or Rect(
        SPEED_DRUM.x, SPEED_DRUM.y, SPEED_DRUM.width, SPEED_DRUM.height
    ).intersects(ATTITUDE):
        raise PfdLayoutError("Live speed readout overlaps the attitude field")
    if SPEED_DRUM.y < SPEED_WINDOW.y or SPEED_DRUM.bottom > SPEED_WINDOW.bottom:
        raise PfdLayoutError("Speed drum window is not inside the live speed box")
    if ATTITUDE.x < SPEED_TAPE.right or ATTITUDE.right > ALTITUDE_TAPE.x:
        raise PfdLayoutError("Attitude field crosses a tape body")
    # The reworked live-altitude box now belongs wholly to the right strip:
    # its nipple stays in the altitude tape and its body occupies the V/S
    # notch.  It must no longer reach back over the attitude sphere.
    if ATTITUDE.intersects(ALTITUDE_WINDOW):
        raise PfdLayoutError("Altitude box reached back into the attitude field")
    if MINIMUMS_LABEL.rect.intersects(ALTITUDE_TAPE) or MINIMUMS_LABEL.rect.intersects(
        BARO_VALUE_UNIT.rect
    ):
        raise PfdLayoutError("Minimums label overlaps the tape or the barometer")
    if (
        BARO_VALUE_UNIT.rect.x != ALTITUDE_TAPE.x
        or BARO_VALUE_UNIT.rect.right != ALTITUDE_TAPE.right
        or BARO_VALUE_UNIT.rect.y != ALTITUDE_TAPE.bottom + 4
        or MINIMUMS_LABEL.rect.right != ALTITUDE_TAPE.right
        or MINIMUMS_LABEL.rect.y != BARO_VALUE_UNIT.rect.bottom + 2
    ):
        raise PfdLayoutError("BARO/HPA and minimums are no longer stacked under the altitude tape")
    if (
        MACH_LABEL.rect.x != SPEED_TAPE.x
        or ILS_LABEL.rect.x != SPEED_TAPE.x
        or ILS_LABEL.rect.y != MACH_LABEL.rect.bottom + 2
    ):
        raise PfdLayoutError("Mach and LS rows are no longer aligned with the speed tape")
    if (
        _tight_join("LS", "113.3") != "LSb13.3"
        or _tight_join("1013", "HPA") != "1013kPA"
        or _tight_join("29.92", "IN") != "29.92lN"
        or _tight_join("335", "H") != "335k"
        or _tight_visible(_TIGHT_DIGIT_ALIASES) != "0123456789"
        or _tight_visible(_TIGHT_ALTITUDE_MINUS_ALIAS) != "-"
    ):
        raise PfdLayoutError("Compact value/unit alias contract changed")

    false_field_hatch = _OpRecorder()
    _draw_field_elevation(
        false_field_hatch,
        {"field_elevation": 1200.0, "altitude": 580.0},
    )
    if false_field_hatch.ops:
        raise PfdLayoutError(
            "Destination elevation painted an unsupported full-tape hatch"
        )

    normal = {
        "ias": 175.0, "altitude": 2400.0, "vertical_speed": 600.0,
        "pitch": 5.0, "roll": -12.5, "heading": 320.0,
        "target_ias": 200.0, "target_heading": 350.0, "target_altitude": 2800.0,
        "target_ias_is_mach": 0.0, "target_ias_visible": 1.0,
        "baro": 29.92, "baro_hpa": 0.0, "baro_std": 0.0,
        "fd_pitch": 2.5, "fd_roll": -5.0, "fd_pitch_visible": 1.0,
        "fd_roll_visible": 1.0, "fd_command": 2.0, "fd_command_visible": 1.0,
        "land_mode": 0.0, "fma_speed": 4.0, "fma_lateral": 3.0, "fma_vertical": 9.0,
        # Speed awareness: bands, reference bugs and the trend vector, so a
        # fault in any of them fails this check rather than the cockpit.
        "min_speed": 132.0, "min_speed_show": 1.0,
        "min_maneuver_speed": 140.0, "min_maneuver_speed_show": 1.0,
        "max_maneuver_speed": 244.0, "max_maneuver_speed_show": 1.0,
        "max_speed": 252.0,
        "v1_speed": 141.0, "vr_speed": 146.0, "v2_speed": 152.0,
        "vref_speed": 138.0, "flaps_speed": 190.0, "flap_lever": 0.625,
        "speed_trend": -2.4, "minimums": 800.0, "minimums_is_radio": 0.0,
        "mach": 0.62, "radio_altitude": 420.0,
        "field_elevation": 610.0, "slip_skid": 0.4,
        "localizer_deviation": -0.3, "glideslope_deviation": 0.2,
        "localizer_valid": 1.0, "glideslope_valid": 1.0,
        "approach_mode": 1.0, "nav_identifier": "IABC",
        "nav_frequency": 11030.0, "marker_outer": 1.0,
        "fma_lateral_armed": 1.0, "fma_vertical_armed": 5.0,
        "fpv_on": 1.0, "fpv_horizontal": 2.0, "fpv_vertical": -12.0,
        "stall_pitch": 11.0, "stall_pitch_show": 1.0,
        "runway_show": 1.0, "runway_x": -16.0, "runway_y": -28.0,
    }
    variants = (
        normal,
        {**normal, "ias": 0.0, "altitude": 0.0, "vertical_speed": -3000.0, "pitch": -25.0, "roll": 45.0, "heading": 359.0, "target_ias": 0.0, "target_altitude": 0.0, "fma_lateral": 4.0, "fma_vertical": 4.0},
        {**normal, "ias": 999.0, "altitude": 41000.0, "vertical_speed": 3000.0, "pitch": 25.0, "roll": -45.0, "heading": 0.0, "target_ias": 999.0, "target_altitude": 41000.0, "target_ias_is_mach": 1.0, "target_ias_visible": 0.0, "baro": 29.921, "baro_hpa": 1.0, "fma_speed": 6.0, "fma_lateral": 2.0, "fma_vertical": 8.0, "land_mode": 2.0},
        {**normal, "fma_speed": 3.0, "fma_lateral": 1.0, "fma_vertical": 4.0, "baro_std": 1.0},
    )
    required_labels = {"FMC SPD", "HDG SEL", "ROLLOUT", "VNAV PTH", "ALT HOLD", "LAND 3", "STD"}
    seen: set[str] = set()
    for values in variants:
        canvas = _BoundsCanvas()
        draw_live_pfd(canvas, values)
        seen.update(text for _x, _y, text in canvas.text_runs)
    if not required_labels.issubset(seen):
        missing = ", ".join(sorted(required_labels - seen))
        raise PfdLayoutError(f"PFD layout scenarios failed to render: {missing}")

    grouped = _BoundsCanvas()
    draw_live_pfd(grouped, {
        **normal,
        "target_heading": 335.0,
        "baro": 29.914,
        "baro_hpa": 1.0,
        "nav_identifier": "LS",
        "nav_frequency": 11330.0,
    })
    grouped_runs = {(x, y, text) for x, y, text in grouped.text_runs}
    visible_runs = {(x, y, _tight_visible(text)) for x, y, text in grouped_runs}
    required_groups = {"335H", "MAG", "1013HPA", "LS113.3"}
    visible_text = {text for _x, _y, text in visible_runs}
    # Packed opaque cells are separate native commands whose backgrounds
    # overlap safely after the preceding ink.  Reconstruct touching runs on
    # each row so the layout contract verifies what the pilot sees rather
    # than requiring every value to be one controller command.
    for y in {run_y for _x, run_y, _text in visible_runs}:
        row = sorted(
            (x, text) for x, run_y, text in visible_runs if run_y == y
        )
        combined = ""
        previous_right = -10_000
        for x, text in row:
            if x > previous_right:
                if combined:
                    visible_text.add(combined)
                combined = text
            else:
                combined += text
            previous_right = max(previous_right, x + len(text) * FONT_CELL_WIDTH)
        if combined:
            visible_text.add(combined)
    if not required_groups.issubset(visible_text):
        missing = ", ".join(sorted(
            required_groups - visible_text
        ))
        raise PfdLayoutError(f"PFD value/unit grouping failed: {missing}")
    heading_x = next(x for x, _y, text in visible_runs if text == "335H")
    mag_x = next(x for x, _y, text in visible_runs if text == "MAG")
    if heading_x + 4 * FONT_CELL_WIDTH >= COMPASS_TEXT.rect.x or mag_x <= COMPASS_TEXT.rect.right:
        raise PfdLayoutError("Selected heading and MAG no longer flank the heading box")
