"""Native 640x480 Boeing 737-800 Navigation Display for the WinCtrl screens.

The ND is laid out the way the aeroplane lays it out in expanded map mode: the
aeroplane symbol sits low and centred, the compass arc sweeps across the top
around it, and the corners carry the numbers - ground speed and true airspeed
at the top left with the wind under them, the range and mode at the top right.

It shares the PFD renderer's rules and machinery: the same protected-zone
contract, the same opaque 17x29 native font cells, and the same differential
output, so a static arc costs display traffic once rather than every frame.

Nothing here opens hardware.  The caller owns the canvas and the refresh.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Tuple

from muslimsim.devices.pfp_renderer import (
    AMBER,
    BLACK,
    CYAN,
    FONT_CELL_HEIGHT,
    FONT_CELL_WIDTH,
    GREEN,
    HEIGHT,
    MAGENTA,
    PFD_NUMBER_FONT_ID,
    RED,
    Rect,
    TAPE_GREY,
    WHITE,
    WIDTH,
    _clamp,
    _dirty_boxes,
    _emit_frame,
    _finite,
    _heading_delta,
    _heading_label,
    _OpRecorder,
    _packed_number_cells,
    _packed_value_advance,
    _slot,
    _tight_visible,
    FULL_REPAINT_FRAMES,
)
import time


# Both physical panels now use the PFD's proven slot-3 micro glyphs.  Drawing
# each character at its actual ink advance removes the old fixed 17-pixel gaps
# and makes enough room for real waypoint names without clipping either bezel.
BB35_IDENTIFIER = 0x31
ND_COMPACT_FONT_ID = PFD_NUMBER_FONT_ID


def _bb35_boeing_layout(canvas: Any) -> bool:
    """True only for BB35 or for an explicitly marked offline recorder."""
    if bool(getattr(canvas, "_muslimsim_nd_bb35", False)):
        return True
    try:
        return int(getattr(canvas, "identifier", -1)) == BB35_IDENTIFIER
    except (TypeError, ValueError):
        return False


def _draw_text(canvas: Any, slot, value: str, foreground, background) -> None:
    """Draw the same tightly packed micro typography used by the live PFD."""
    if not value:
        return
    cells = _packed_number_cells(slot, value)
    if cells is None:
        return
    for x, character in cells:
        canvas.text(
            x, slot.rect.y, character, foreground, background, ND_COMPACT_FONT_ID
        )


def _compact_text_width(value: str) -> int:
    """Exact opaque-cell width of one compact ND label."""
    visible = _tight_visible(value)
    if not visible:
        return 0
    advances = [_packed_value_advance(character) for character in visible]
    return sum(advances[:-1]) + FONT_CELL_WIDTH


class _NdOpRecorder(_OpRecorder):
    """Operation recorder that carries the source panel's ND identity."""

    __slots__ = ("_muslimsim_nd_bb35",)

    def __init__(self, bb35: bool = False) -> None:
        super().__init__()
        self._muslimsim_nd_bb35 = bool(bb35)

# ---------------------------------------------------------------------------
# The 640x480 zone contract.  The aeroplane sits low so the map ahead of it
# fills the screen, which is the whole point of the expanded mode.
# ---------------------------------------------------------------------------
# Each display's bezel masks a different strip of the physical panel, so a
# page centred on the frame's own middle can sit left of the middle the pilot
# sees.  The finished frame is shifted right by this many pixels.  A display
# that needs its own amount carries `_muslimsim_nd_shift_x` on its canvas;
# this is only the default, which suits the PFP.
ND_SHIFT_X = 24
# Text is kept farther inside than raw geometry because the BB35 and BB36
# bezels hide their outermost LCD columns.  These are pre-shift coordinates;
# the 24-pixel fitted-display shift is applied after the frame is complete.
ND_TEXT_LEFT = 16
ND_TEXT_RIGHT = 592

AIRCRAFT_X = 320
AIRCRAFT_Y = 400
COMPASS_RADIUS = 250
COMPASS_HALF_ANGLE = 65          # degrees either side of the lubber line
RANGE_ARC_RADIUS = 125           # the half-range arc
# Three-pixel blocks stepped every 2.4 px still overlap, so the arc reads as a
# continuous line while costing little more than half the segments.  The arc
# never moves, so this is paid on page entry and on each periodic recovery
# frame, not per frame.
ARC_SEGMENT = 2.4
ARC_THICKNESS = 3

GROUND_SPEED_LABEL = _slot("GS label", ND_TEXT_LEFT, 16, FONT_CELL_WIDTH * 2)
GROUND_SPEED_VALUE = _slot("GS value", 50, 16, FONT_CELL_WIDTH * 3)
TRUE_AIRSPEED_LABEL = _slot("TAS label", 110, 16, FONT_CELL_WIDTH * 3)
TRUE_AIRSPEED_VALUE = _slot("TAS value", 163, 16, FONT_CELL_WIDTH * 3)
WIND_TEXT = _slot("wind", ND_TEXT_LEFT, 52, FONT_CELL_WIDTH * 7)
WIND_ARROW_X = 30
WIND_ARROW_Y = 104
HEADING_BOX = Rect(286, 8, 69, 30)
MAG_LABEL = _slot("MAG", 360, 12, FONT_CELL_WIDTH * 3)
MODE_LABEL = _slot("mode", 470, 16, FONT_CELL_WIDTH * 4)
RANGE_VALUE = _slot("range", 470, 52, FONT_CELL_WIDTH * 3)
RANGE_UNIT = _slot("range unit", 521, 52, FONT_CELL_WIDTH * 2)
HALF_RANGE_LABEL_Y = AIRCRAFT_Y - RANGE_ARC_RADIUS - 22

MAP_MODES = {0: "APP", 1: "VOR", 2: "MAP", 3: "PLAN"}

# The ND's static content is far larger than the PFD's - a full compass rose
# is most of a complete frame - so its periodic recovery frame is spaced out
# rather than inherited. It still heals a missed region, just once a minute
# instead of every few seconds.
ND_FULL_REPAINT_FRAMES = 600
ND_FULL_REPAINT_SECONDS = 60.0

# Every value this renderer reads.  The bridge asserts that its live snapshot
# requests all of them: a value that is sampled but never handed over draws
# nothing and looks exactly like a broken switch.
ND_VALUE_KEYS = (
    "heading", "track", "target_heading", "groundspeed", "true_airspeed",
    "wind_speed", "wind_direction", "map_range_nm", "map_mode", "ctr",
    "wxr", "sta", "wpt", "arpt", "data", "pos", "terr", "tfc",
    "nav_course", "nav_deviation", "nav_frequency", "nav_dme", "nav_identifier",
    "latitude", "longitude", "route_lat", "route_lon",
    "altitude", "vertical_speed", "roll", "target_altitude",
    "nav_vdeviation", "nav_to_from", "marker_outer", "marker_middle",
    "marker_inner", "next_waypoint_name", "next_waypoint_distance", "next_waypoint_eta",
    "rnp", "anp", "vsd", "approach_mode",
    "map_fail", "vtk_fail", "mode_disagree", "range_disagree",
    "vor_fail", "loc_fail", "gs_fail", "tcas_fail", "wxr_fail", "pws_fail",
    "terr_fail", "unable_rnp", "tcas_alert",
    "tcas_bearing", "tcas_distance", "tcas_altitude", "tcas_vertical",
    "tcas_ids", "route_name", "route_altitude", "route_speed",
    "route_eta", "route_kind", "route_altitude2", "route_altitude_type",
    "route_radius", "route_radius_lat", "route_radius_lon", "route_turn",
    "route_hold_time", "route_hold_distance", "route_distance",
    "bearing_selector_1", "bearing_selector_2", "nav1_bearing", "nav2_bearing",
    "adf1_bearing", "adf2_bearing", "fuel_total", "eng_ff_0", "eng_ff_1",
    "terrain_profile", "weather_cells", "database_stations",
    "database_waypoints", "database_airports",
)

BLUE = (58, 104, 255)
YELLOW = (255, 235, 0)

# A degree of latitude is sixty nautical miles; a degree of longitude is that
# shrunk by the cosine of the latitude.  Good to a fraction of a pixel over a
# map range, which is all the ND needs.
NAUTICAL_MILES_PER_DEGREE = 60.0
ROUTE_STEP = 3.0                 # pixels between blocks along a route leg
ROUTE_MAX_LEGS = 40              # beyond the range there is nothing to see

# Centred mode puts the aeroplane in the middle of a full compass rose.  The
# radius is what fits the display once the corner readouts have their room.
CENTRE_X = 320
CENTRE_Y = 268
CENTRE_RADIUS = 186

# The EFIS overlay switches, in the order the panel carries them.  Their map
# content - weather, terrain, traffic, navaids, airports - needs navigation
# data the bridge does not read, so selecting one is annunciated rather than
# drawn.  An annunciation is honest: the switch plainly did something, and
# nothing is invented on a navigation display.
OVERLAY_SWITCHES = (
    ("wxr", "WXR"), ("sta", "STA"), ("wpt", "WPT"),
    ("arpt", "ARPT"), ("data", "DATA"), ("pos", "POS"),
    ("terr", "TERR"), ("tfc", "TFC"),
)
# Under the wind readout, which is clear of the compass in every mode and of
# the navaid block that owns the bottom left corner in VOR and APP.
OVERLAY_ROW_Y = 146
DEVIATION_DOT_SPACING = 30
NAV_BLOCK_LEFT_Y = 404
NAV_BLOCK_RIGHT_X = 380


class NdLayoutError(RuntimeError):
    """An ND change would place content outside its protected zone."""


def _block(canvas: Any, x: float, y: float, size: int = 3) -> None:
    """Draw one square of a curve, dropped if it would leave the display.

    Curves here are stepped as small squares, so the bound that matters is the
    far corner, not the first pixel.  Testing the first pixel let a square at
    the bottom edge run off it.
    """
    left = int(round(x)) - 1
    top = int(round(y)) - 1
    if left < 0 or top < 0 or left + size > WIDTH or top + size > HEIGHT:
        return
    canvas.fill(left, top, size, size)


def _arc_point(bearing: float, radius: float) -> Tuple[float, float]:
    """A point on the compass, `bearing` degrees from the lubber line."""
    radians = math.radians(bearing)
    return (
        AIRCRAFT_X + radius * math.sin(radians),
        AIRCRAFT_Y - radius * math.cos(radians),
    )


def _draw_arc(canvas: Any, radius: float, half_angle: float, colour, thickness: int = ARC_THICKNESS,
              dashed: bool = False) -> None:
    """Draw a compass arc as short segments along its true radius."""
    step = math.degrees(ARC_SEGMENT / radius)
    canvas.colour(*colour)
    bearing = -half_angle
    index = 0
    while bearing <= half_angle:
        index += 1
        if not dashed or index % 3:
            x, y = _arc_point(bearing, radius)
            _block(canvas, x, y, thickness)
        bearing += step


def _draw_compass(canvas: Any, values: Mapping[str, Any]) -> None:
    """The heading arc: ticks every five degrees, numbers every thirty."""
    heading = values.get("heading")
    _draw_arc(canvas, COMPASS_RADIUS, COMPASS_HALF_ANGLE, WHITE)

    if not _finite(heading):
        return
    live = float(heading)
    first = int((live - COMPASS_HALF_ANGLE) // 5) * 5
    for tick in range(first, int(live + COMPASS_HALF_ANGLE) + 5, 5):
        delta = _heading_delta(float(tick), live)
        if abs(delta) > COMPASS_HALF_ANGLE:
            continue
        length = 16 if tick % 30 == 0 else (11 if tick % 10 == 0 else 7)
        inner = _arc_point(delta, COMPASS_RADIUS - length)
        outer = _arc_point(delta, COMPASS_RADIUS)
        canvas.colour(*WHITE)
        # Step along the tick at the same density as the arc, or it reads as a
        # row of dots rather than a mark.
        steps = max(2, int(length / 2.0))
        for step in range(steps + 1):
            fraction = step / steps
            x = inner[0] + (outer[0] - inner[0]) * fraction
            y = inner[1] + (outer[1] - inner[1]) * fraction
            canvas.fill(int(round(x)) - 1, int(round(y)) - 1, 3, 3)
        if tick % 30 == 0:
            label = _arc_point(delta, COMPASS_RADIUS - length - 30)
            _draw_text(
                canvas,
                _slot("arc label", int(round(label[0])) - FONT_CELL_WIDTH,
                      int(round(label[1])) - FONT_CELL_HEIGHT // 2, FONT_CELL_WIDTH * 2, "center"),
                _heading_label(float(tick)),
                WHITE,
                BLACK,
            )


def _draw_range_arc(canvas: Any, values: Mapping[str, Any]) -> None:
    """Quarter/half range arcs and labels at every EFIS range setting."""
    if _bb35_boeing_layout(canvas):
        # The Boeing ND carries clean solid white range arcs.  This is BB35
        # only; BB36 keeps its established dashed Airbus-panel guides.
        _draw_arc(canvas, RANGE_ARC_RADIUS, COMPASS_HALF_ANGLE - 12, WHITE, 2)
        _draw_arc(canvas, RANGE_ARC_RADIUS / 2.0, COMPASS_HALF_ANGLE - 12, WHITE, 2)
    else:
        _draw_arc(canvas, RANGE_ARC_RADIUS, COMPASS_HALF_ANGLE - 12, TAPE_GREY, 2, dashed=True)
        _draw_arc(canvas, RANGE_ARC_RADIUS / 2.0, COMPASS_HALF_ANGLE - 12, TAPE_GREY, 2, dashed=True)
        # (kept two pixels: a dashed guide should not out-weigh the compass arc)
    span = values.get("map_range_nm")
    if not _finite(span) or float(span) <= 0.0:
        return
    half = float(span) / 2.0
    text = f"{half:g}"
    for side in (-1, 1):
        point = _arc_point(side * (COMPASS_HALF_ANGLE - 12), RANGE_ARC_RADIUS)
        _draw_text(
            canvas,
            _slot("half range", int(round(point[0])) - FONT_CELL_WIDTH * 3 // 2,
                  int(round(point[1])) - FONT_CELL_HEIGHT // 2, FONT_CELL_WIDTH * 3, "center"),
            text,
            WHITE,
            BLACK,
        )
    _draw_text(
        canvas,
        _slot("quarter range", AIRCRAFT_X - FONT_CELL_WIDTH * 3 // 2,
              AIRCRAFT_Y - RANGE_ARC_RADIUS // 2 - 22, FONT_CELL_WIDTH * 3, "center"),
        f"{float(span) / 4.0:g}",
        WHITE,
        BLACK,
    )


def _draw_aircraft(canvas: Any) -> None:
    """The fixed aeroplane symbol at the centre of the compass."""
    canvas.colour(*WHITE)
    for offset in range(10):
        canvas.fill(AIRCRAFT_X - offset, AIRCRAFT_Y - 10 + offset, 2, 2)
        canvas.fill(AIRCRAFT_X + offset, AIRCRAFT_Y - 10 + offset, 2, 2)
    canvas.fill(AIRCRAFT_X - 9, AIRCRAFT_Y, 20, 2)
    canvas.fill(AIRCRAFT_X - 1, AIRCRAFT_Y - 10, 2, 14)


def _draw_lubber(canvas: Any) -> None:
    """The fixed pointer the heading is read against."""
    canvas.colour(*WHITE)
    top = AIRCRAFT_Y - COMPASS_RADIUS
    for step in range(9):
        canvas.fill(AIRCRAFT_X - step, top - 14 + step, 2, 2)
        canvas.fill(AIRCRAFT_X + step, top - 14 + step, 2, 2)
    canvas.fill(AIRCRAFT_X - 8, top - 6, 18, 2)


def _draw_track_and_bug(
    canvas: Any,
    values: Mapping[str, Any],
    centre_x: int = AIRCRAFT_X,
    centre_y: int = AIRCRAFT_Y,
    radius: int = COMPASS_RADIUS,
    limit: float = COMPASS_HALF_ANGLE,
) -> None:
    """The track line the aeroplane is following, and the MCP heading bug.

    Both belong on the centred rose as much as on the arc, so the compass
    geometry is passed in rather than assumed.
    """
    heading = values.get("heading")
    if not _finite(heading):
        return
    live = float(heading)

    def point(bearing: float, distance: float) -> Tuple[float, float]:
        radians = math.radians(bearing)
        return centre_x + distance * math.sin(radians), centre_y - distance * math.cos(radians)

    track = values.get("track")
    if _finite(track):
        delta = _clamp(_heading_delta(float(track), live), -limit, limit)
        canvas.colour(*WHITE)
        for distance in range(30, int(radius), 12):
            x, y = point(delta, distance)
            _block(canvas, x, y + 1, 2)
            _block(canvas, x, y - 2, 2)

    selected = values.get("target_heading")
    if _finite(selected):
        delta = _clamp(_heading_delta(float(selected), live), -limit, limit)
        canvas.colour(*MAGENTA)
        for step in range(8):
            distance = radius + step * 2.0
            width = 2 + step
            x, y = point(delta, distance)
            left = int(round(x - width / 2))
            top = int(round(y)) - 1
            if left >= 0 and top >= 0 and left + width <= WIDTH and top + 2 <= HEIGHT:
                canvas.fill(left, top, width, 2)


def _draw_wind(canvas: Any, values: Mapping[str, Any]) -> None:
    """Wind direction and speed, with an arrow pointing the way it blows."""
    speed = values.get("wind_speed")
    direction = values.get("wind_direction")
    heading = values.get("heading")
    if not _finite(speed) or not _finite(direction):
        return
    _draw_text(
        canvas,
        WIND_TEXT,
        f"{int(round(float(direction))) % 360:03d}/{int(round(float(speed))):02d}",
        WHITE,
        BLACK,
    )
    if not _finite(heading):
        return
    # The arrow is drawn relative to the aeroplane, as on the aircraft: it
    # shows where the wind is going, not where it comes from.
    bearing = math.radians(_heading_delta(float(direction) + 180.0, float(heading)))
    canvas.colour(*WHITE)
    length = 22
    for step in range(length):
        x = WIND_ARROW_X + math.sin(bearing) * step
        y = WIND_ARROW_Y - math.cos(bearing) * step
        canvas.fill(int(round(x)) - 1, int(round(y)) - 1, 2, 2)
    tip_x = WIND_ARROW_X + math.sin(bearing) * length
    tip_y = WIND_ARROW_Y - math.cos(bearing) * length
    for step in range(6):
        for side in (-1, 1):
            angle = bearing + side * 2.5
            x = tip_x + math.sin(angle) * step
            y = tip_y - math.cos(angle) * step
            canvas.fill(int(round(x)) - 1, int(round(y)) - 1, 2, 2)


def _eta_text(value: Any) -> str:
    """Format Zibo decimal-hour, legacy minute, or second ETA values."""
    if not _finite(value):
        return ""
    numeric = float(value)
    if 0.0 <= numeric < 24.0:
        total_minutes = int(round(numeric * 60.0))
    elif abs(numeric) < 1440.0:
        total_minutes = int(round(numeric))
    else:
        total_minutes = int(round(numeric / 60.0))
    total_minutes %= 1440
    return f"{total_minutes // 60:02d}{total_minutes % 60:02d}"


def _draw_bb35_readouts(canvas: Any, values: Mapping[str, Any]) -> None:
    """Boeing-organized top band for the BB35 native display."""
    groundspeed = values.get("groundspeed")
    true_airspeed = values.get("true_airspeed")

    def three_digits(value: Any) -> str:
        if not _finite(value):
            return "---"
        return f"{max(0, min(999, int(round(float(value))))):03d}"

    _draw_text(
        canvas,
        _slot("BB35 speed band", ND_TEXT_LEFT, 16, FONT_CELL_WIDTH * 12),
        f"GS{three_digits(groundspeed)} TAS{three_digits(true_airspeed)}",
        WHITE,
        BLACK,
    )

    # Boeing places the live track in the top box.  Heading remains available
    # on the compass arc, and selected heading remains the magenta bug.
    _draw_text(canvas, _slot("BB35 TRK", 230, 12, FONT_CELL_WIDTH * 3),
               "TRK", GREEN, BLACK)
    track = values.get("track")
    heading = values.get("heading")
    boxed_value = track if _finite(track) else heading
    canvas.colour(*WHITE)
    for x, y, width, height in (
        (HEADING_BOX.x, HEADING_BOX.y, HEADING_BOX.width, 2),
        (HEADING_BOX.x, HEADING_BOX.bottom - 2, HEADING_BOX.width, 2),
        (HEADING_BOX.x, HEADING_BOX.y, 2, HEADING_BOX.height),
        (HEADING_BOX.right - 2, HEADING_BOX.y, 2, HEADING_BOX.height),
    ):
        canvas.fill(int(x), int(y), int(width), int(height))
    _draw_text(
        canvas,
        _slot("BB35 track", int(HEADING_BOX.x) + 6, int(HEADING_BOX.y) + 1,
              FONT_CELL_WIDTH * 3, "center"),
        f"{int(round(float(boxed_value))) % 360:03d}" if _finite(boxed_value) else "---",
        WHITE,
        BLACK,
    )
    _draw_text(canvas, MAG_LABEL, "MAG", GREEN, BLACK)

    waypoint = str(values.get("next_waypoint_name") or "").strip().upper()[:7]
    if waypoint:
        _draw_text(canvas, _slot("BB35 next waypoint", 462, 8, FONT_CELL_WIDTH * 7),
                   waypoint, MAGENTA, BLACK)
        eta = values.get("next_waypoint_eta")
        if _finite(eta):
            _draw_text(canvas, _slot("BB35 waypoint ETA", 480, 38, FONT_CELL_WIDTH * 5),
                       _eta_text(eta) + "Z", WHITE, BLACK)
        distance = values.get("next_waypoint_distance")
        if _finite(distance):
            _draw_text(canvas, _slot("BB35 waypoint distance", 462, 68, FONT_CELL_WIDTH * 7),
                       f"{float(distance):.1f}NM"[:7], WHITE, BLACK)

    mode = values.get("map_mode")
    if _finite(mode):
        _draw_text(canvas, _slot("BB35 mode", 462, 108, FONT_CELL_WIDTH * 4),
                   MAP_MODES.get(int(round(float(mode))), ""), GREEN, BLACK)
    span = values.get("map_range_nm")
    if _finite(span) and float(span) > 0.0:
        range_text = f"{float(span):g}"
        range_x = 520
        range_width = _compact_text_width(range_text)
        _draw_text(canvas, _slot("BB35 range", range_x, 108, range_width),
                   range_text, WHITE, BLACK)
        _draw_text(canvas, _slot("BB35 range unit", range_x + range_width + 3, 108,
                                _compact_text_width("NM")),
                   "NM", CYAN, BLACK)


def _draw_readouts(canvas: Any, values: Mapping[str, Any]) -> None:
    """Ground speed, true airspeed, heading, mode and range."""
    if _bb35_boeing_layout(canvas):
        _draw_bb35_readouts(canvas, values)
        return
    groundspeed = values.get("groundspeed")
    true_airspeed = values.get("true_airspeed")

    def three_digits(value: Any) -> str:
        return (
            f"{max(0, min(999, int(round(float(value))))):03d}"
            if _finite(value) else "---"
        )

    _draw_text(
        canvas,
        _slot("speed band", ND_TEXT_LEFT, 16, FONT_CELL_WIDTH * 12),
        f"GS{three_digits(groundspeed)} TAS{three_digits(true_airspeed)}",
        WHITE,
        BLACK,
    )

    heading = values.get("heading")
    canvas.colour(*WHITE)
    for x, y, width, height in (
        (HEADING_BOX.x, HEADING_BOX.y, HEADING_BOX.width, 2),
        (HEADING_BOX.x, HEADING_BOX.bottom - 2, HEADING_BOX.width, 2),
        (HEADING_BOX.x, HEADING_BOX.y, 2, HEADING_BOX.height),
        (HEADING_BOX.right - 2, HEADING_BOX.y, 2, HEADING_BOX.height),
    ):
        canvas.fill(int(x), int(y), int(width), int(height))
    _draw_text(
        canvas,
        _slot("heading", int(HEADING_BOX.x) + 6, int(HEADING_BOX.y) + 1, FONT_CELL_WIDTH * 3, "center"),
        f"{int(round(float(heading))) % 360:03d}" if _finite(heading) else "---",
        WHITE,
        BLACK,
    )
    _draw_text(canvas, MAG_LABEL, "MAG", GREEN, BLACK)

    selected = values.get("target_heading")
    if _finite(selected):
        _draw_text(
            canvas,
            _slot("selected heading", 196, 12, FONT_CELL_WIDTH * 5, "right"),
            f"H{int(round(float(selected))) % 360:03d}",
            MAGENTA,
            BLACK,
        )

    mode = values.get("map_mode")
    if _finite(mode):
        _draw_text(canvas, MODE_LABEL, MAP_MODES.get(int(round(float(mode))), ""), GREEN, BLACK)
    span = values.get("map_range_nm")
    if _finite(span) and float(span) > 0.0:
        range_text = f"{float(span):g}"
        range_width = _compact_text_width(range_text)
        _draw_text(canvas, _slot("range", 470, 52, range_width),
                   range_text, WHITE, BLACK)
        _draw_text(canvas, _slot("range unit", 470 + range_width + 3, 52,
                                _compact_text_width("NM")),
                   "NM", CYAN, BLACK)

    waypoint = str(values.get("next_waypoint_name") or "").strip().upper()[:7]
    if waypoint:
        _draw_text(canvas, _slot("next waypoint", 442, 87, FONT_CELL_WIDTH * 7),
                   waypoint, MAGENTA, BLACK)
        distance = values.get("next_waypoint_distance")
        eta = values.get("next_waypoint_eta")
        detail = []
        if _finite(distance):
            detail.append(f"{float(distance):.1f}")
        if _finite(eta):
            detail.append(_eta_text(eta) + "Z")
        if detail:
            text = " ".join(detail)[:9]
            _draw_text(canvas, _slot("next waypoint data", 425, 116, FONT_CELL_WIDTH * 9),
                       text, WHITE, BLACK)


def _draw_line(canvas: Any, start: Tuple[float, float], end: Tuple[float, float],
               thickness: int = 3) -> None:
    """Draw a straight line as runs along its major axis.

    Stepping a line in fixed blocks costs a command every few pixels.  Walking
    the major axis and emitting one fill per run of constant minor coordinate
    costs a command per pixel the line actually steps, which for a shallow
    leg crossing the display is a small fraction of the same line.
    """
    x0, y0 = start
    x1, y1 = end
    if abs(x1 - x0) >= abs(y1 - y0):
        span = int(round(abs(x1 - x0)))
        if span < 1:
            _block(canvas, x0, y0, thickness)
            return
        step = (x1 - x0) / span
        slope = (y1 - y0) / span
        run_start = 0
        current = int(round(y0))
        for index in range(1, span + 1):
            value = int(round(y0 + slope * index))
            if value != current or index == span:
                left = int(round(x0 + step * run_start))
                right = int(round(x0 + step * index))
                if right < left:
                    left, right = right, left
                width = max(thickness, right - left)
                if 0 <= left and left + width <= WIDTH and 0 <= current and current + thickness <= HEIGHT:
                    canvas.fill(left, current, width, thickness)
                run_start, current = index, value
        return

    span = int(round(abs(y1 - y0)))
    if span < 1:
        _block(canvas, x0, y0, thickness)
        return
    step = (y1 - y0) / span
    slope = (x1 - x0) / span
    run_start = 0
    current = int(round(x0))
    for index in range(1, span + 1):
        value = int(round(x0 + slope * index))
        if value != current or index == span:
            top = int(round(y0 + step * run_start))
            bottom = int(round(y0 + step * index))
            if bottom < top:
                top, bottom = bottom, top
            height = max(thickness, bottom - top)
            if 0 <= current and current + thickness <= WIDTH and 0 <= top and top + height <= HEIGHT:
                canvas.fill(current, top, thickness, height)
            run_start, current = index, value


def _draw_dashed_line(canvas: Any, start: Tuple[float, float], end: Tuple[float, float],
                      thickness: int = 3) -> None:
    """Draw a clipped dashed leg with a stable six-pixel cadence."""
    x0, y0 = start
    x1, y1 = end
    distance = math.hypot(x1 - x0, y1 - y0)
    if distance < 1.0:
        return
    steps = max(1, int(distance / 3.0))
    for index in range(steps + 1):
        if index % 4 in (2, 3):
            continue
        fraction = index / steps
        _block(canvas, x0 + (x1 - x0) * fraction, y0 + (y1 - y0) * fraction, thickness)


def _clip_to_display(start: Tuple[float, float], end: Tuple[float, float]):
    """Trim a leg to the part that is on screen, or None if none of it is.

    A route leg can be hundreds of miles long while the display shows ten, so
    stepping along the whole leg would spend thousands of commands drawing
    off-screen.  Only the visible span is drawn.
    """
    margin = 8.0
    left, top = -margin, -margin
    right, bottom = WIDTH + margin, HEIGHT + margin
    x0, y0 = start
    x1, y1 = end
    delta_x = x1 - x0
    delta_y = y1 - y0
    enter, leave = 0.0, 1.0
    for direction, offset in (
        (-delta_x, x0 - left), (delta_x, right - x0),
        (-delta_y, y0 - top), (delta_y, bottom - y0),
    ):
        if abs(direction) < 1e-9:
            if offset < 0:
                return None          # parallel to this edge and outside it
            continue
        crossing = offset / direction
        if direction < 0:
            if crossing > leave:
                return None
            enter = max(enter, crossing)
        else:
            if crossing < enter:
                return None
            leave = min(leave, crossing)
    if enter > leave:
        return None
    return (
        (x0 + delta_x * enter, y0 + delta_y * enter),
        (x0 + delta_x * leave, y0 + delta_y * leave),
    )


def _map_geometry(values: Mapping[str, Any]) -> Tuple[int, int, float] | None:
    """Where the aeroplane sits on screen, and how many pixels a mile is.

    The compass radius stands for the selected range, exactly as it does on
    the aeroplane, so the map scale follows the EFIS range switch.
    """
    span = values.get("map_range_nm")
    if not _finite(span) or float(span) <= 0.0:
        return None
    if _centred(values):
        return CENTRE_X, CENTRE_Y, CENTRE_RADIUS / float(span)
    return AIRCRAFT_X, AIRCRAFT_Y, COMPASS_RADIUS / float(span)


def _project(
    latitude: float,
    longitude: float,
    values: Mapping[str, Any],
    geometry: Tuple[int, int, float],
) -> Tuple[float, float] | None:
    """Put a coordinate on the map, heading up around the aeroplane."""
    own_lat = values.get("latitude")
    own_lon = values.get("longitude")
    heading = values.get("heading")
    if not (_finite(own_lat) and _finite(own_lon) and _finite(heading)):
        return None
    centre_x, centre_y, pixels_per_mile = geometry
    north = (latitude - float(own_lat)) * NAUTICAL_MILES_PER_DEGREE
    east = (
        (longitude - float(own_lon))
        * NAUTICAL_MILES_PER_DEGREE
        * math.cos(math.radians(float(own_lat)))
    )
    radians = math.radians(float(heading))
    ahead = north * math.cos(radians) + east * math.sin(radians)
    right = east * math.cos(radians) - north * math.sin(radians)
    return centre_x + right * pixels_per_mile, centre_y - ahead * pixels_per_mile


def _route_points(values: Mapping[str, Any]) -> list:
    """The route's waypoints as (source index, latitude, longitude).

    A leg with no coordinate reads as zero, which is a real place in the
    Atlantic, so those are dropped rather than drawn.
    """
    latitudes = values.get("route_lat") or ()
    longitudes = values.get("route_lon") or ()
    points = []
    for source_index, (latitude, longitude) in enumerate(zip(latitudes, longitudes)):
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (TypeError, ValueError):
            continue
        if abs(latitude) < 0.001 and abs(longitude) < 0.001:
            continue
        if abs(latitude) > 90.0 or abs(longitude) > 180.0:
            continue
        points.append((source_index, latitude, longitude))
        if len(points) >= ROUTE_MAX_LEGS:
            break
    return points


def _draw_route(canvas: Any, values: Mapping[str, Any]) -> None:
    """The active route: the line the aeroplane is following, and its fixes."""
    geometry = _map_geometry(values)
    if geometry is None:
        return
    points = _route_points(values)
    if len(points) < 1:
        return

    screen = []
    for _source_index, latitude, longitude in points:
        placed = _project(latitude, longitude, values, geometry)
        if placed is None:
            return
        screen.append(placed)

    kinds = values.get("route_kind") or ()
    palette = {
        0: (MAGENTA, False),   # active/executed route
        1: (WHITE, True),      # modification awaiting EXEC
        2: (CYAN, False),      # missed approach
        3: (BLUE, False),      # alternate route
        4: (MAGENTA, True),    # lateral offset/or selected heading track
    }
    radii = values.get("route_radius") or ()
    radius_latitudes = values.get("route_radius_lat") or ()
    radius_longitudes = values.get("route_radius_lon") or ()
    turns = values.get("route_turn") or ()
    for leg_index, (start, end) in enumerate(zip(screen, screen[1:])):
        source_index = points[leg_index + 1][0]
        visible = _clip_to_display(start, end)
        if visible is None:
            continue
        try:
            kind = int(round(float(kinds[source_index])))
        except (IndexError, TypeError, ValueError):
            kind = 0
        colour, dashed = palette.get(kind, (MAGENTA, False))
        canvas.colour(*colour)
        # Radius-to-fix legs carry an exact turn centre in Zibo.  Draw their
        # arc instead of reducing it to a straight chord.
        curved = False
        try:
            radius_nm = float(radii[source_index])
            centre = _project(
                float(radius_latitudes[source_index]),
                float(radius_longitudes[source_index]),
                values, geometry,
            )
            turn = float(turns[source_index])
        except (IndexError, TypeError, ValueError):
            centre, radius_nm, turn = None, 0.0, 0.0
        if centre is not None and radius_nm > 0.01:
            start_angle = math.atan2(start[1] - centre[1], start[0] - centre[0])
            end_angle = math.atan2(end[1] - centre[1], end[0] - centre[0])
            direction = -1.0 if turn < 0.0 else 1.0
            delta = (end_angle - start_angle) % (2.0 * math.pi)
            if direction < 0.0:
                delta = -((-delta) % (2.0 * math.pi))
            radius_pixels = (math.hypot(start[0] - centre[0], start[1] - centre[1])
                             + math.hypot(end[0] - centre[0], end[1] - centre[1])) / 2.0
            steps = min(100, max(8, int(abs(delta) * max(1.0, radius_pixels) / 4.0)))
            for step in range(steps + 1):
                if dashed and step % 5 in (3, 4):
                    continue
                angle = start_angle + delta * step / steps
                _block(canvas, centre[0] + radius_pixels * math.cos(angle),
                       centre[1] + radius_pixels * math.sin(angle), 3)
            curved = True
        if curved:
            pass
        elif dashed:
            _draw_dashed_line(canvas, visible[0], visible[1], 3)
        else:
            _draw_line(canvas, visible[0], visible[1], 3)

    # Boeing draws a fix as a four-pointed star; at this size an open diamond
    # reads the same and costs four blocks.
    names = values.get("route_name") or ()
    altitudes = values.get("route_altitude") or ()
    altitudes2 = values.get("route_altitude2") or ()
    altitude_types = values.get("route_altitude_type") or ()
    speeds = values.get("route_speed") or ()
    etas = values.get("route_eta") or ()
    hold_times = values.get("route_hold_time") or ()
    hold_distances = values.get("route_hold_distance") or ()
    show_data = _finite(values.get("data")) and float(values["data"]) >= 0.5
    # Native text cells are opaque.  Keep route labels out of the aircraft,
    # next-waypoint, overlay and RNP/ANP zones, then reserve each accepted
    # label for the following fixes.  The line and fix symbols always remain;
    # only lower-priority text is omitted when the map is genuinely crowded.
    plan_mode = _mode_name(values) == "PLAN"
    occupied = [
        # PLAN is centred around its north-up reference, while expanded MAP
        # protects the larger aircraft/trend/traffic cluster near the bottom.
        Rect(CENTRE_X - 42, CENTRE_Y - 42, 84, 84)
        if plan_mode else Rect(AIRCRAFT_X - 70, AIRCRAFT_Y - 155, 180, 195),
    ]
    if _bb35_boeing_layout(canvas):
        occupied.extend((
            Rect(450, 78, 166, 72),       # mode/range and active-fix block
            Rect(0, OVERLAY_ROW_Y - 4, 120, 258),
            Rect(528, 252, 88, 204),      # vertical RNP/ANP block
            Rect(0, 438, 120, 42),        # FMC source
        ))
    else:
        occupied.extend((
            Rect(420, 78, 200, 72),
            Rect(0, OVERLAY_ROW_Y - 4, 360, FONT_CELL_HEIGHT + 8),
            Rect(220, 438, 260, 42),
        ))
    for index, (x, y) in enumerate(screen):
        source_index = points[index][0]
        if not (-20 <= x <= WIDTH + 20 and -20 <= y <= HEIGHT + 20):
            continue
        canvas.colour(*(MAGENTA if index == 0 else WHITE))
        for offset_x, offset_y in ((0, -6), (6, 0), (0, 6), (-6, 0)):
            _block(canvas, x + offset_x, y + offset_y, 3)
        try:
            name = str(names[source_index]).strip().upper()[:7]
        except (IndexError, TypeError):
            name = ""
        fields = []
        if show_data:
            try:
                altitude = float(altitudes[source_index])
                altitude_type = int(round(float(altitude_types[source_index])))
                second = float(altitudes2[source_index])
            except (IndexError, TypeError, ValueError):
                altitude, altitude_type, second = 0.0, 0, 0.0
            if math.isfinite(altitude) and altitude > 0.0:
                altitude_number = (
                    f"{int(round(altitude / 100.0)):03d}"
                    if altitude >= 10000.0 else f"{int(round(altitude))}"
                )
                altitude_text = altitude_number
                if altitude_type == 1:
                    altitude_text += "B"
                elif altitude_type == 2:
                    altitude_text += "A"
                elif altitude_type == 3 and math.isfinite(second) and second > 0.0:
                    second_text = (
                        f"{int(round(second / 100.0)):03d}"
                        if second >= 10000.0 else f"{int(round(second))}"
                    )
                    altitude_text = f"{second_text}A{altitude_number}B"
                fields.append(altitude_text)
            try:
                speed = float(speeds[source_index])
                if math.isfinite(speed) and speed > 0.0:
                    fields.append(f"{int(round(speed))}K")
            except (IndexError, TypeError, ValueError):
                pass
            try:
                eta_text = _eta_text(etas[source_index])
                if eta_text and not fields:
                    fields.append(eta_text + "Z")
            except (IndexError, TypeError, ValueError):
                pass
        data_text = "/".join(fields)[:9]
        if name or data_text:
            label_width = max(
                _compact_text_width(name), _compact_text_width(data_text),
                FONT_CELL_WIDTH,
            )
            label_height = FONT_CELL_HEIGHT * (2 if name and data_text else 1)
            candidates = (
                (int(x + 10), int(y - 13)),
                (int(x - label_width - 10), int(y - 13)),
                (int(x + 10), int(y - label_height - 10)),
                (int(x - label_width - 10), int(y - label_height - 10)),
                (int(x + 10), int(y + 10)),
                (int(x - label_width - 10), int(y + 10)),
            )
            label_rect = None
            for left, top in candidates:
                candidate = Rect(left, top, label_width, label_height)
                if (
                    left >= ND_TEXT_LEFT
                    and top >= 82
                    and candidate.right <= ND_TEXT_RIGHT
                    and candidate.bottom <= HEIGHT - 36
                    and not any(candidate.intersects(rect) for rect in occupied)
                ):
                    label_rect = candidate
                    break
            if label_rect is not None:
                text_y = label_rect.y
                if name:
                    _draw_text(
                        canvas,
                        _slot("waypoint", label_rect.x, text_y, label_rect.width),
                        name, MAGENTA if index == 0 else WHITE, BLACK,
                    )
                    text_y += FONT_CELL_HEIGHT
                if data_text:
                    _draw_text(
                        canvas,
                        _slot("waypoint data", label_rect.x, text_y, label_rect.width),
                        data_text, CYAN, BLACK,
                    )
                occupied.append(label_rect)
        # Zibo exports hold time/distance per leg.  A compact racetrack next
        # to that fix makes the procedure visible without bitmap artwork.
        try:
            has_hold = float(hold_times[source_index]) > 0.0 or float(hold_distances[source_index]) > 0.0
        except (IndexError, TypeError, ValueError):
            has_hold = False
        if has_hold and 30 <= x <= WIDTH - 55 and 40 <= y <= HEIGHT - 55:
            canvas.colour(*MAGENTA)
            _draw_line(canvas, (x + 12, y - 10), (x + 35, y - 10), 3)
            _draw_line(canvas, (x + 12, y + 10), (x + 35, y + 10), 3)
            for degree in range(-90, 91, 15):
                angle = math.radians(degree)
                _block(canvas, x + 35 + 10 * math.cos(angle), y + 10 * math.sin(angle), 3)


def _mode_name(values: Mapping[str, Any]) -> str:
    mode = values.get("map_mode")
    if not _finite(mode):
        return "MAP"
    return MAP_MODES.get(int(round(float(mode))), "MAP")


def _centred(values: Mapping[str, Any]) -> bool:
    """True when the CTR switch is in: the rose closes around the aeroplane."""
    selected = values.get("ctr")
    return _finite(selected) and float(selected) >= 0.5


def _draw_centred_rose(canvas: Any, values: Mapping[str, Any]) -> None:
    """A full compass rose with the aeroplane at its centre."""
    canvas.colour(*WHITE)
    step = math.degrees(ARC_SEGMENT / CENTRE_RADIUS)
    bearing = 0.0
    while bearing < 360.0:
        radians = math.radians(bearing)
        x = CENTRE_X + CENTRE_RADIUS * math.sin(radians)
        y = CENTRE_Y - CENTRE_RADIUS * math.cos(radians)
        _block(canvas, x, y, ARC_THICKNESS)
        bearing += step

    heading = values.get("heading")
    if not _finite(heading):
        return
    live = float(heading)
    for tick in range(0, 360, 5):
        delta = _heading_delta(float(tick), live)
        length = 16 if tick % 30 == 0 else (11 if tick % 10 == 0 else 7)
        radians = math.radians(delta)
        for step_index in range(max(2, int(length / 2.0)) + 1):
            radius = CENTRE_RADIUS - length + length * step_index / max(2, int(length / 2.0))
            x = CENTRE_X + radius * math.sin(radians)
            y = CENTRE_Y - radius * math.cos(radians)
            _block(canvas, x, y)
        if tick % 30 == 0:
            radius = CENTRE_RADIUS - length - 26
            x = CENTRE_X + radius * math.sin(radians)
            y = CENTRE_Y - radius * math.cos(radians)
            _draw_text(
                canvas,
                _slot("rose label", int(round(x)) - FONT_CELL_WIDTH,
                      int(round(y)) - FONT_CELL_HEIGHT // 2, FONT_CELL_WIDTH * 2, "center"),
                _heading_label(float(tick)),
                WHITE,
                BLACK,
            )

    canvas.colour(*WHITE)
    for step_index in range(9):
        canvas.fill(CENTRE_X - step_index, CENTRE_Y - CENTRE_RADIUS - 14 + step_index, 2, 2)
        canvas.fill(CENTRE_X + step_index, CENTRE_Y - CENTRE_RADIUS - 14 + step_index, 2, 2)
    for offset in range(10):
        canvas.fill(CENTRE_X - offset, CENTRE_Y - 10 + offset, 2, 2)
        canvas.fill(CENTRE_X + offset, CENTRE_Y - 10 + offset, 2, 2)
    canvas.fill(CENTRE_X - 9, CENTRE_Y, 20, 2)


def _draw_plan_range_rings(canvas: Any, values: Mapping[str, Any]) -> None:
    """Add the half/full-distance circles and labels to north-up PLAN."""
    span = values.get("map_range_nm")
    if not _finite(span) or float(span) <= 0.0:
        return

    for ring_radius in (CENTRE_RADIUS / 2.0, float(CENTRE_RADIUS)):
        step = math.degrees(ARC_SEGMENT / ring_radius)
        bearing = 0.0
        canvas.colour(*WHITE)
        while bearing < 360.0:
            radians = math.radians(bearing)
            _block(
                canvas,
                CENTRE_X + ring_radius * math.sin(radians),
                CENTRE_Y - ring_radius * math.cos(radians),
                2,
            )
            bearing += step

    for name, distance, ring_radius in (
        ("PLAN half range", float(span) / 2.0, CENTRE_RADIUS / 2.0),
        ("PLAN full range", float(span), float(CENTRE_RADIUS)),
    ):
        text = f"{distance:g}"
        width = max(FONT_CELL_WIDTH, _compact_text_width(text))
        _draw_text(
            canvas,
            _slot(
                name,
                int(round(CENTRE_X + ring_radius - width / 2.0)),
                CENTRE_Y - FONT_CELL_HEIGHT // 2,
                width,
                "center",
            ),
            text,
            WHITE,
            BLACK,
        )
    _draw_text(
        canvas,
        _slot("PLAN north", CENTRE_X - FONT_CELL_WIDTH, CENTRE_Y - CENTRE_RADIUS + 8,
              FONT_CELL_WIDTH * 2, "center"),
        "N",
        WHITE,
        BLACK,
    )


def _draw_course_and_deviation(canvas: Any, values: Mapping[str, Any]) -> None:
    """The tuned course and its deviation bar, as APP and VOR modes show it."""
    heading = values.get("heading")
    course = values.get("nav_course")
    if not _finite(heading) or not _finite(course):
        return
    delta = _heading_delta(float(course), float(heading))
    centre_x, centre_y, radius = (
        (CENTRE_X, CENTRE_Y, CENTRE_RADIUS) if _centred(values)
        else (AIRCRAFT_X, AIRCRAFT_Y, COMPASS_RADIUS)
    )
    radians = math.radians(delta)
    canvas.colour(*MAGENTA)
    near = (centre_x + (-radius + 40) * math.sin(radians),
            centre_y - (-radius + 40) * math.cos(radians))
    far = (centre_x + (radius - 40) * math.sin(radians),
           centre_y - (radius - 40) * math.cos(radians))
    visible = _clip_to_display(near, far)
    if visible is not None:
        _draw_line(canvas, visible[0], visible[1], 3)

    deviation = values.get("nav_deviation")
    if not _finite(deviation):
        return
    dots = _clamp(float(deviation), -2.5, 2.5)
    across = radians + math.pi / 2.0
    canvas.colour(*WHITE)
    for index in (-2, -1, 1, 2):
        offset = index * DEVIATION_DOT_SPACING
        x = centre_x + offset * math.sin(across)
        y = centre_y - offset * math.cos(across)
        _block(canvas, x, y, 4)
    canvas.colour(*MAGENTA)
    bar_offset = dots * DEVIATION_DOT_SPACING
    for step in range(-34, 35, 3):
        x = centre_x + bar_offset * math.sin(across) + step * math.sin(radians)
        y = centre_y - bar_offset * math.cos(across) - step * math.cos(radians)
        _block(canvas, x, y)


def _draw_navaid_block(canvas: Any, values: Mapping[str, Any]) -> None:
    """The tuned station, its course and its distance."""
    frequency = values.get("nav_frequency")
    course = values.get("nav_course")
    distance = values.get("nav_dme")
    label = "ILS" if _mode_name(values) == "APP" else "VOR"
    identifier = str(values.get("nav_identifier") or "").strip().upper()[:5]
    heading = (identifier + " " + label).strip() if identifier else label
    _draw_text(canvas, _slot("nav label", ND_TEXT_LEFT, NAV_BLOCK_LEFT_Y,
                             FONT_CELL_WIDTH * min(9, max(3, len(heading)))),
               heading[:9], CYAN, BLACK)
    if _finite(frequency) and float(frequency) > 0.0:
        _draw_text(
            canvas,
            _slot("nav freq", ND_TEXT_LEFT, NAV_BLOCK_LEFT_Y + 30, FONT_CELL_WIDTH * 6),
            f"{float(frequency) / 100.0:.2f}",
            WHITE, BLACK,
        )
    if _finite(course):
        _draw_text(
            canvas,
            _slot("nav course", NAV_BLOCK_RIGHT_X, NAV_BLOCK_LEFT_Y, FONT_CELL_WIDTH * 6),
            f"CRS{int(round(float(course))) % 360:03d}",
            WHITE, BLACK,
        )
    if _finite(distance) and float(distance) > 0.0:
        _draw_text(
            canvas,
            _slot("nav dme", NAV_BLOCK_RIGHT_X, NAV_BLOCK_LEFT_Y + 30, FONT_CELL_WIDTH * 8),
            f"DME{float(distance) / 1852.0:5.1f}",
            GREEN, BLACK,
        )


def _draw_overlay_annunciations(canvas: Any, values: Mapping[str, Any]) -> None:
    """Name the EFIS overlays that are switched on."""
    selected = [
        text for key, text in OVERLAY_SWITCHES
        if _finite(values.get(key)) and float(values[key]) >= 0.5
    ]
    if not selected:
        return
    if _bb35_boeing_layout(canvas):
        for index, text in enumerate(selected[:8]):
            _draw_text(
                canvas,
                _slot("BB35 overlay", ND_TEXT_LEFT, OVERLAY_ROW_Y + index * FONT_CELL_HEIGHT,
                      FONT_CELL_WIDTH * min(len(text), 5)),
                text[:5],
                CYAN,
                BLACK,
            )
        return
    line = " ".join(selected)
    _draw_text(
        canvas,
        _slot("overlays", ND_TEXT_LEFT, OVERLAY_ROW_Y, FONT_CELL_WIDTH * min(len(line), 20)),
        line[:20],
        CYAN,
        BLACK,
    )


def _draw_plan(canvas: Any, values: Mapping[str, Any]) -> None:
    """PLAN mode: north-up route, zoom-scaled waypoints and distance rings."""
    # PLAN is always centred.  Keeping CTR true here is essential: otherwise
    # route projection silently uses expanded-MAP's low aircraft origin and
    # appears not to react correctly when the range selector changes.
    north_up = {**dict(values), "heading": 0.0, "ctr": 1.0}
    _draw_plan_range_rings(canvas, north_up)
    _draw_database_overlays(canvas, north_up)
    _draw_route(canvas, north_up)

    heading = values.get("heading")
    if _finite(heading):
        # The aeroplane keeps its true orientation on a north-up page, shown
        # as a stub from the centre along the heading.
        radians = math.radians(float(heading))
        canvas.colour(*WHITE)
        for distance in range(8, 42, 3):
            _block(
                canvas,
                CENTRE_X + distance * math.sin(radians),
                CENTRE_Y - distance * math.cos(radians),
                3,
            )

    # The rose labels north itself; a second N above it only repeated that.


def _draw_altitude_intercept(canvas: Any, values: Mapping[str, Any]) -> None:
    """The green altitude-intercept arc ("banana") on the projected track."""
    altitude = values.get("altitude")
    target = values.get("target_altitude")
    vertical_speed = values.get("vertical_speed")
    groundspeed = values.get("groundspeed")
    span = values.get("map_range_nm")
    if not all(_finite(v) for v in (altitude, target, vertical_speed, groundspeed, span)):
        return
    rate = float(vertical_speed)
    delta = float(target) - float(altitude)
    if abs(rate) < 100.0 or delta * rate <= 0.0 or float(span) <= 0.0:
        return
    minutes = abs(delta / rate)
    distance_nm = max(0.0, float(groundspeed)) * minutes / 60.0
    geometry = _map_geometry(values)
    if geometry is None:
        return
    cx, cy, pixels_per_nm = geometry
    distance = distance_nm * pixels_per_nm
    if distance < 20.0 or distance > max(WIDTH, HEIGHT) * 1.4:
        return
    # The arc is normal to the current track and curves toward the selected
    # altitude exactly where the present vertical trend reaches it.
    y = cy - distance
    canvas.colour(*GREEN)
    for degree in range(205, 336, 4):
        angle = math.radians(degree)
        _block(canvas, cx + 28 * math.cos(angle), y + 12 * math.sin(angle), 3)


def _draw_track_trend(canvas: Any, values: Mapping[str, Any]) -> None:
    """Three 30-second track-prediction segments driven by current bank."""
    roll = values.get("roll")
    groundspeed = values.get("groundspeed")
    if not (_finite(roll) and _finite(groundspeed)) or float(groundspeed) < 30.0:
        return
    centre_x, centre_y, _scale = _map_geometry(values) or (AIRCRAFT_X, AIRCRAFT_Y, 1.0)
    bank = _clamp(float(roll), -35.0, 35.0)
    canvas.colour(*GREEN)
    for segment in range(1, 4):
        distance = 30 + segment * 23
        bend = math.tan(math.radians(bank)) * segment * segment * 4.2
        for step in range(7):
            fraction = step / 6.0
            y = centre_y - (distance - 14 + fraction * 12)
            x = centre_x + bend * fraction
            _block(canvas, x, y, 3)


def _draw_bearing_pointers(canvas: Any, values: Mapping[str, Any]) -> None:
    """Captain EFIS VOR/ADF pointers, selected exactly as on the panel."""
    heading = values.get("heading")
    geometry = _map_geometry(values)
    if not _finite(heading) or geometry is None:
        return
    cx, cy, _pixels_per_nm = geometry
    radius = 120.0 if _centred(values) else 94.0
    for number, colour in ((1, GREEN), (2, CYAN)):
        selector = values.get(f"bearing_selector_{number}")
        if not _finite(selector) or abs(float(selector)) < 0.5:
            continue
        source = "nav" if float(selector) > 0.0 else "adf"
        bearing = values.get(f"{source}{number}_bearing")
        if not _finite(bearing):
            continue
        angle = math.radians(_heading_delta(float(bearing), float(heading)))
        dx, dy = radius * math.sin(angle), -radius * math.cos(angle)
        canvas.colour(*colour)
        _draw_line(canvas, (cx - dx, cy - dy), (cx + dx, cy + dy), 2)
        tip_x, tip_y = cx + dx, cy + dy
        for side in (-1.0, 1.0):
            wing = angle + math.pi + side * 0.48
            _draw_line(canvas, (tip_x, tip_y),
                       (tip_x + 18 * math.sin(wing), tip_y - 18 * math.cos(wing)), 2)
        label = ("VOR" if source == "nav" else "ADF") + str(number)
        _draw_text(
            canvas,
            _slot(f"bearing source {number}", ND_TEXT_LEFT if number == 1 else 525,
                  340, FONT_CELL_WIDTH * 4),
            label, colour, BLACK,
        )


def _draw_fuel_range_ring(canvas: Any, values: Mapping[str, Any]) -> None:
    """Computed 30-minute-reserve range ring from fuel, flow and ground speed."""
    fuel = values.get("fuel_total")
    flow_1 = values.get("eng_ff_0")
    flow_2 = values.get("eng_ff_1")
    groundspeed = values.get("groundspeed")
    geometry = _map_geometry(values)
    if geometry is None or not all(_finite(item) for item in (fuel, flow_1, flow_2, groundspeed)):
        return
    total_flow = max(0.0, float(flow_1)) + max(0.0, float(flow_2))
    if total_flow < 0.001 or float(fuel) <= 0.0 or float(groundspeed) < 30.0:
        return
    endurance_hours = max(0.0, float(fuel) / total_flow / 3600.0 - 0.5)
    range_nm = endurance_hours * float(groundspeed)
    cx, cy, pixels_per_nm = geometry
    radius = range_nm * pixels_per_nm
    if radius < 18.0 or radius > 720.0:
        return
    canvas.colour(*GREEN)
    for degree in range(0, 360, 2):
        if degree % 12 in (8, 10):
            continue
        angle = math.radians(degree)
        _block(canvas, cx + radius * math.sin(angle), cy - radius * math.cos(angle), 2)
    label_y = int(round(cy - radius - 15))
    if radius >= 100.0 and 120 <= label_y <= HEIGHT - 40:
        _draw_text(canvas, _slot("fuel range", int(cx - 42), label_y,
                                 FONT_CELL_WIDTH * 5, "center"),
                   "RANGE", GREEN, BLACK)


def _draw_glideslope_scale(canvas: Any, values: Mapping[str, Any]) -> None:
    if _mode_name(values) != "APP":
        return
    deviation = values.get("nav_vdeviation")
    failed = _finite(values.get("gs_fail")) and float(values["gs_fail"]) >= 0.5
    x, center_y = 590, 290
    if failed:
        _draw_text(canvas, _slot("GS fail", 520, 220, FONT_CELL_WIDTH * 4), "GS", AMBER, BLACK)
        return
    if not _finite(deviation):
        return
    canvas.colour(*WHITE)
    canvas.fill(x - 9, center_y - 1, 18, 3)
    for index in (-2, -1, 1, 2):
        _block(canvas, x, center_y + index * 30, 5)
    y = int(round(center_y - _clamp(float(deviation), -2.5, 2.5) * 30.0))
    canvas.colour(*MAGENTA)
    for offset in range(-8, 9, 2):
        half = 8 - abs(offset)
        canvas.fill(x - half, y + offset, max(2, half * 2 + 1), 2)

    marker = ""
    colour = WHITE
    if _finite(values.get("marker_outer")) and float(values["marker_outer"]) >= 0.5:
        marker, colour = "OM", CYAN
    elif _finite(values.get("marker_middle")) and float(values["marker_middle"]) >= 0.5:
        marker, colour = "MM", AMBER
    elif _finite(values.get("marker_inner")) and float(values["marker_inner"]) >= 0.5:
        marker = "IM"
    if marker:
        _draw_text(canvas, _slot("marker", 540, 90, FONT_CELL_WIDTH * 3), marker, colour, BLACK)


def _draw_to_from(canvas: Any, values: Mapping[str, Any]) -> None:
    if _mode_name(values) != "VOR" or not _finite(values.get("nav_to_from")):
        return
    state = int(round(float(values["nav_to_from"])))
    if state not in (1, 2):
        return
    x, y = 350, 420
    canvas.colour(*GREEN)
    direction = -1 if state == 1 else 1
    for width in range(2, 14, 2):
        canvas.fill(x - width // 2, y + direction * (width // 2), width, 2)
    _draw_text(canvas, _slot("TO FROM", 374, 410, FONT_CELL_WIDTH * 4),
               "TO" if state == 1 else "FROM", GREEN, BLACK)


def _draw_tcas(canvas: Any, values: Mapping[str, Any]) -> None:
    selected = _finite(values.get("tfc")) and float(values["tfc"]) >= 0.5
    if not selected:
        return
    if _finite(values.get("tcas_fail")) and float(values["tcas_fail"]) >= 0.5:
        return
    geometry = _map_geometry(values)
    if geometry is None:
        return
    cx, cy, pixels_per_nm = geometry
    bearings = values.get("tcas_bearing") or ()
    distances = values.get("tcas_distance") or ()
    altitudes = values.get("tcas_altitude") or ()
    verticals = values.get("tcas_vertical") or ()
    ids = values.get("tcas_ids") or ()
    targets = []
    for index, (bearing, distance) in enumerate(zip(bearings, distances)):
        try:
            if ids and index < len(ids) and int(ids[index]) == 0:
                continue
            bearing = float(bearing)
            distance_nm = float(distance) / 1852.0
            relative_altitude_ft = float(altitudes[index]) * 3.28084 if index < len(altitudes) else 0.0
        except (TypeError, ValueError, IndexError):
            continue
        if not (math.isfinite(bearing) and math.isfinite(distance_nm)) or distance_nm <= 0.0:
            continue
        radius = distance_nm * pixels_per_nm
        if radius > 380.0:
            continue
        angle = math.radians(bearing)
        x = cx + radius * math.sin(angle)
        y = cy - radius * math.cos(angle)
        if 18 <= x <= WIDTH - ND_SHIFT_X - 10 - FONT_CELL_WIDTH * 4 and 18 <= y <= HEIGHT - 45:
            targets.append((distance_nm, x, y, relative_altitude_ft, index))
    alert = _finite(values.get("tcas_alert")) and float(values["tcas_alert"]) >= 0.5
    closest = min((item[0] for item in targets), default=999.0)
    for distance_nm, x, y, altitude_ft, index in targets[:24]:
        proximate = distance_nm <= 6.0 or abs(altitude_ft) <= 1200.0
        threat = alert and abs(distance_nm - closest) < 0.01
        colour = RED if threat else (AMBER if distance_nm <= 3.0 else CYAN)
        canvas.colour(*colour)
        if threat:
            canvas.fill(int(x) - 7, int(y) - 7, 15, 15)
        elif distance_nm <= 3.0:
            for row in range(-7, 8, 2):
                half = int(round(math.sqrt(max(0.0, 49.0 - row * row))))
                canvas.fill(int(x) - half, int(y) + row, max(2, half * 2), 2)
        elif proximate:
            for row in range(-7, 8, 2):
                half = 7 - abs(row)
                canvas.fill(int(x) - half, int(y) + row, max(2, half * 2), 2)
        else:
            for dx, dy in ((0, -7), (7, 0), (0, 7), (-7, 0)):
                _block(canvas, x + dx, y + dy, 3)
        relative = int(round(altitude_ft / 100.0))
        arrow = ""
        try:
            vertical = float(verticals[index])
            arrow = "+" if vertical > 2.5 else ("-" if vertical < -2.5 else "")
        except (TypeError, ValueError, IndexError):
            pass
        text = f"{relative:+03d}{arrow}"[:4]
        _draw_text(canvas, _slot("traffic altitude", int(x + 10), int(y - 13), FONT_CELL_WIDTH * 4),
                   text, colour, BLACK)


def _draw_rnp(canvas: Any, values: Mapping[str, Any]) -> None:
    rnp = values.get("rnp")
    anp = values.get("anp")
    if not (_finite(rnp) or _finite(anp)):
        return
    if _bb35_boeing_layout(canvas):
        canvas.colour(*WHITE)
        canvas.fill(610, 260, 3, 195)
        canvas.fill(600, 260, 13, 3)
        canvas.fill(604, 356, 9, 3)
        canvas.fill(600, 452, 13, 3)
        if _finite(rnp):
            _draw_text(canvas, _slot("BB35 RNP label", 538, 260, FONT_CELL_WIDTH * 3),
                       "RNP", GREEN, BLACK)
            _draw_text(canvas, _slot("BB35 RNP value", 538, 289, FONT_CELL_WIDTH * 4),
                       f"{float(rnp):.2f}"[:4], WHITE, BLACK)
        if _finite(anp):
            colour = AMBER if _finite(rnp) and float(anp) > float(rnp) else WHITE
            _draw_text(canvas, _slot("BB35 ANP label", 538, 397, FONT_CELL_WIDTH * 3),
                       "ANP", GREEN, BLACK)
            _draw_text(canvas, _slot("BB35 ANP value", 538, 426, FONT_CELL_WIDTH * 4),
                       f"{float(anp):.2f}"[:4], colour, BLACK)
        return
    if _finite(rnp):
        _draw_text(canvas, _slot("RNP", 238, 445, FONT_CELL_WIDTH * 7),
                   f"RNP{float(rnp):.2f}"[:7], CYAN, BLACK)
    if _finite(anp):
        colour = AMBER if _finite(rnp) and float(anp) > float(rnp) else WHITE
        _draw_text(canvas, _slot("ANP", 365, 445, FONT_CELL_WIDTH * 7),
                   f"ANP{float(anp):.2f}"[:7], colour, BLACK)


def _draw_weather_terrain(canvas: Any, values: Mapping[str, Any]) -> None:
    geometry = _map_geometry(values)
    if geometry is None:
        return
    cx, cy, _scale = geometry
    weather = values.get("weather_cells") or ()
    if _finite(values.get("wxr")) and float(values["wxr"]) >= 0.5:
        colours = (GREEN, YELLOW, RED, MAGENTA)
        for item in weather:
            try:
                bearing, fraction, severity = float(item[0]), float(item[1]), int(item[2])
            except (TypeError, ValueError, IndexError):
                continue
            angle = math.radians(bearing)
            radius = _clamp(fraction, 0.0, 1.0) * COMPASS_RADIUS
            x = cx + radius * math.sin(angle)
            y = cy - radius * math.cos(angle)
            canvas.colour(*colours[min(3, max(0, severity))])
            _block(canvas, x, y, 4 + min(4, max(0, severity)))

    terrain = values.get("terrain_profile") or ()
    if _finite(values.get("terr")) and float(values["terr"]) >= 0.5:
        for item in terrain:
            try:
                bearing, fraction, delta = float(item[0]), float(item[1]), float(item[2])
            except (TypeError, ValueError, IndexError):
                continue
            colour = RED if delta > 2000.0 else (AMBER if delta > -500.0 else (GREEN if delta > -5000.0 else BLACK))
            if colour == BLACK:
                continue
            angle = math.radians(bearing)
            radius = _clamp(fraction, 0.0, 1.0) * COMPASS_RADIUS
            canvas.colour(*colour)
            _block(canvas, cx + radius * math.sin(angle), cy - radius * math.cos(angle), 4)


def _draw_vsd(canvas: Any, values: Mapping[str, Any]) -> None:
    if not (_finite(values.get("vsd")) and float(values["vsd"]) >= 0.5):
        return
    top, bottom = 354, 479
    canvas.colour(*BLACK)
    canvas.fill(0, top, WIDTH, bottom - top)
    canvas.colour(*CYAN)
    canvas.fill(0, top, WIDTH, 2)
    _draw_text(canvas, _slot("VSD", ND_TEXT_LEFT, top + 5, FONT_CELL_WIDTH * 3), "VSD", CYAN, BLACK)
    profile = values.get("terrain_profile") or ()
    points = []
    for index, item in enumerate(profile[:48]):
        try:
            delta = float(item[2]) if isinstance(item, (tuple, list)) else float(item)
        except (TypeError, ValueError, IndexError):
            continue
        x = 80 + int(index * 510 / max(1, min(47, len(profile) - 1)))
        y = int(round(447 - _clamp(delta, -5000.0, 5000.0) / 5000.0 * 70.0))
        points.append((x, y))
    canvas.colour(*GREEN)
    for start, end in zip(points, points[1:]):
        _draw_line(canvas, start, end, 3)
    # Aircraft profile and the current vertical projection.
    canvas.colour(*WHITE)
    canvas.fill(55, 415, 28, 3)
    canvas.fill(67, 407, 3, 18)
    vs = values.get("vertical_speed")
    slope = _clamp(float(vs) / 3000.0, -1.0, 1.0) if _finite(vs) else 0.0
    canvas.colour(*MAGENTA)
    _draw_line(canvas, (82, 415), (590, 415 - slope * 75), 3)


def _draw_failures(canvas: Any, values: Mapping[str, Any]) -> bool:
    """Draw failure/disagree annunciations. Return True for MAP FAIL blanking."""
    map_failed = _finite(values.get("map_fail")) and float(values["map_fail"]) >= 0.5
    alerts = []
    for key, label in (
        ("vtk_fail", "VTK FAIL"), ("mode_disagree", "MODE DISAGREE"),
        ("range_disagree", "RANGE DISAGREE"), ("tcas_fail", "TCAS FAIL"),
        ("wxr_fail", "WXR FAIL"), ("pws_fail", "PWS FAIL"),
        ("terr_fail", "TERR FAIL"),
        ("unable_rnp", "UNABLE RNP"),
    ):
        if _finite(values.get(key)) and float(values[key]) >= 0.5:
            alerts.append(label)
    if map_failed:
        canvas.colour(*BLACK)
        canvas.fill(120, 130, 400, 230)
        canvas.colour(*AMBER)
        canvas.fill(220, 215, 200, 3)
        canvas.fill(220, 265, 200, 3)
        canvas.fill(220, 215, 3, 53)
        canvas.fill(417, 215, 3, 53)
        _draw_text(canvas, _slot("MAP FAIL", 252, 226, FONT_CELL_WIDTH * 8, "center"),
                   "MAP FAIL", AMBER, BLACK)
    for index, label in enumerate(alerts[:4]):
        width = min(14, max(5, len(label)))
        _draw_text(canvas, _slot("ND alert", 200, 150 + index * 30, FONT_CELL_WIDTH * width, "center"),
                   label[:width], AMBER, BLACK)
    mode = _mode_name(values)
    radio_fail = (
        (mode == "VOR" and _finite(values.get("vor_fail")) and float(values["vor_fail"]) >= 0.5)
        or (mode == "APP" and _finite(values.get("loc_fail")) and float(values["loc_fail"]) >= 0.5)
    )
    if radio_fail:
        label = "VOR FAIL" if mode == "VOR" else "LOC FAIL"
        _draw_text(canvas, _slot("radio fail", ND_TEXT_LEFT, 375, FONT_CELL_WIDTH * 8), label, AMBER, BLACK)
    return map_failed


def _draw_database_overlays(canvas: Any, values: Mapping[str, Any]) -> None:
    """Draw real nearby STA/WPT/ARPT entries supplied by X-Plane's database."""
    if _mode_name(values) not in ("MAP", "PLAN"):
        return
    geometry = _map_geometry(values)
    if geometry is None:
        return
    span = float(values["map_range_nm"]) if _finite(values.get("map_range_nm")) else 640.0
    label_points = span <= 80.0
    occupied = [
        Rect(0, 0, WIDTH, 150),
        Rect(AIRCRAFT_X - 70, AIRCRAFT_Y - 80, 140, 120),
    ]
    if _bb35_boeing_layout(canvas):
        occupied.extend((
            Rect(0, OVERLAY_ROW_Y - 4, 120, 258),
            Rect(528, 252, 88, 204),
            Rect(0, 438, 120, 42),
        ))
    else:
        occupied.append(Rect(220, 438, 260, 42))

    def position(point: Any) -> Tuple[float, float] | None:
        try:
            return _project(float(point[0]), float(point[1]), values, geometry)
        except (IndexError, TypeError, ValueError):
            return None

    def label(x: float, y: float, text: str) -> None:
        if not label_points or not text:
            return
        text = text.strip().upper()[:7]
        width = _compact_text_width(text)
        candidates = (
            Rect(int(x + 9), int(y - 13), width, FONT_CELL_HEIGHT),
            Rect(int(x - width - 9), int(y - 13), width, FONT_CELL_HEIGHT),
            Rect(int(x + 9), int(y + 8), width, FONT_CELL_HEIGHT),
        )
        for rect in candidates:
            if (
                rect.x >= ND_TEXT_LEFT and rect.y >= 150
                and rect.right <= ND_TEXT_RIGHT
                and rect.bottom <= HEIGHT - 35
                and not any(rect.intersects(other) for other in occupied)
            ):
                _draw_text(canvas, _slot("database label", rect.x, rect.y, rect.width),
                           text, CYAN, BLACK)
                occupied.append(rect)
                return

    if _finite(values.get("sta")) and float(values["sta"]) >= 0.5:
        for point in values.get("database_stations") or ():
            placed = position(point)
            if placed is None:
                continue
            x, y = placed
            if not (ND_TEXT_LEFT <= x <= ND_TEXT_RIGHT and 150 <= y <= HEIGHT - 35):
                continue
            kind = str(point[3]).upper() if len(point) > 3 else "VOR"
            canvas.colour(*CYAN)
            if kind == "NDB":
                for degree in range(0, 360, 45):
                    angle = math.radians(degree)
                    _block(canvas, x + 6 * math.cos(angle), y + 6 * math.sin(angle), 2)
            else:
                _block(canvas, x, y, 4)
                for dx, dy in ((0, -7), (7, 0), (0, 7), (-7, 0)):
                    _block(canvas, x + dx, y + dy, 2)
            label(x, y, str(point[2]) if len(point) > 2 else "")

    if _finite(values.get("wpt")) and float(values["wpt"]) >= 0.5 and span <= 80.0:
        for point in values.get("database_waypoints") or ():
            placed = position(point)
            if placed is None:
                continue
            x, y = placed
            if not (ND_TEXT_LEFT <= x <= ND_TEXT_RIGHT and 150 <= y <= HEIGHT - 35):
                continue
            canvas.colour(*CYAN)
            for dx, dy in ((0, -5), (5, 0), (0, 5), (-5, 0)):
                _block(canvas, x + dx, y + dy, 2)
            label(x, y, str(point[2]) if len(point) > 2 else "")

    if _finite(values.get("arpt")) and float(values["arpt"]) >= 0.5:
        for point in values.get("database_airports") or ():
            placed = position(point)
            if placed is None:
                continue
            x, y = placed
            if not (ND_TEXT_LEFT <= x <= ND_TEXT_RIGHT and 150 <= y <= HEIGHT - 35):
                continue
            canvas.colour(*CYAN)
            canvas.fill(int(x) - 7, int(y) - 2, 15, 4)
            canvas.fill(int(x) - 2, int(y) - 7, 4, 15)
            label(x, y, str(point[2]) if len(point) > 2 else "")


def _draw_fmc_source(canvas: Any, values: Mapping[str, Any]) -> None:
    """Show the Boeing route source when real FMC route data is present."""
    if not _bb35_boeing_layout(canvas):
        return
    if not (_route_points(values) or str(values.get("next_waypoint_name") or "").strip()):
        return
    _draw_text(canvas, _slot("BB35 FMC source", ND_TEXT_LEFT, 445, FONT_CELL_WIDTH * 5),
               "FMC L", GREEN, BLACK)


def draw_nd_frame(canvas: Any, values: Mapping[str, Any]) -> None:
    """Draw one complete ND page in whichever mode the EFIS panel selects."""
    canvas.colour(*BLACK)
    canvas.fill(0, 0, WIDTH, HEIGHT)
    mode = _mode_name(values)
    _draw_readouts(canvas, values)
    _draw_wind(canvas, values)
    _draw_overlay_annunciations(canvas, values)
    if mode != "PLAN":
        _draw_weather_terrain(canvas, values)
    _draw_fuel_range_ring(canvas, values)

    if mode == "PLAN":
        _draw_plan(canvas, values)
        _draw_rnp(canvas, values)
        _draw_fmc_source(canvas, values)
        _draw_vsd(canvas, values)
        _draw_failures(canvas, values)
        return

    if _centred(values):
        if mode == "MAP":
            _draw_database_overlays(canvas, values)
            _draw_route(canvas, values)
        _draw_centred_rose(canvas, values)
        _draw_track_and_bug(canvas, values, CENTRE_X, CENTRE_Y, CENTRE_RADIUS, 180.0)
    else:
        if mode == "MAP":
            _draw_database_overlays(canvas, values)
            _draw_route(canvas, values)
        _draw_range_arc(canvas, values)
        _draw_compass(canvas, values)
        _draw_track_and_bug(canvas, values)
        _draw_lubber(canvas)
        _draw_aircraft(canvas)

    _draw_altitude_intercept(canvas, values)
    _draw_track_trend(canvas, values)
    _draw_bearing_pointers(canvas, values)
    _draw_tcas(canvas, values)

    if mode in ("APP", "VOR"):
        _draw_course_and_deviation(canvas, values)
        _draw_navaid_block(canvas, values)
    _draw_glideslope_scale(canvas, values)
    _draw_to_from(canvas, values)
    _draw_rnp(canvas, values)
    _draw_fmc_source(canvas, values)
    _draw_vsd(canvas, values)
    _draw_failures(canvas, values)


def draw_live_nd(canvas: Any, values: Mapping[str, Any]) -> bool:
    """Draw the ND, sending only what changed.  True if anything was sent.

    The compass arc never moves, so on a canvas that persists between frames
    it is paid for once rather than every frame, exactly as on the PFD.
    """
    recorder = _NdOpRecorder(_bb35_boeing_layout(canvas))
    draw_nd_frame(recorder, values)
    shift = int(getattr(canvas, "_muslimsim_nd_shift_x", ND_SHIFT_X))
    operations = _shift_operations(recorder.ops, shift)

    state = getattr(canvas, "_muslimsim_nd_state", None)
    now = time.monotonic()
    mode = _mode_name(values)
    pending = getattr(canvas, "_muslimsim_nd_pending", None)

    # A page entry, recovery, or MAP/PLAN geometry change is larger than one
    # safe BB36 drawing burst. Paint it in three vertical bands into the
    # controller's back
    # surface on consecutive display-loop passes, flushing commands but never
    # issuing 0x103 between them. Only the completed page becomes visible.
    state_mode = state[3] if state is not None and len(state) > 3 else None
    recovery_due = bool(
        state is not None
        and (
            (now - state[1]) > ND_FULL_REPAINT_SECONDS
            or state[2] >= ND_FULL_REPAINT_FRAMES
        )
    )
    begins_staged_frame = state is None or state_mode != mode or recovery_due
    if pending is not None and pending[1] != mode:
        pending = None
    if pending is None and begins_staged_frame:
        pending = (operations, mode, 0)
    if pending is not None:
        pending_operations, pending_mode, band = pending
        band_width = (WIDTH + 2) // 3
        left = band * band_width
        right = min(WIDTH, left + band_width)
        box = (left, 0, right - left, HEIGHT)
        _emit_frame(canvas, pending_operations, [box])
        if band < 2:
            flush = getattr(canvas, "flush", None)
            if callable(flush):
                flush()
            try:
                canvas._muslimsim_nd_pending = (
                    pending_operations, pending_mode, band + 1
                )
            except AttributeError:
                pass
            return False
        try:
            del canvas._muslimsim_nd_pending
        except (AttributeError, TypeError):
            pass
        try:
            canvas._muslimsim_nd_state = (pending_operations, now, 0, pending_mode)
        except AttributeError:
            pass
        return True

    stale = recovery_due
    if stale:
        boxes = [(0, 0, WIDTH, HEIGHT)]
        sequence = 0
    else:
        boxes = _dirty_boxes(operations, state[0])
        sequence = state[2] + 1

    _emit_frame(canvas, operations, boxes)
    try:
        canvas._muslimsim_nd_state = (operations, now, sequence, mode)
    except AttributeError:
        pass
    return bool(boxes)


def _shift_operations(operations: list, shift: int) -> list:
    """Move a finished frame sideways, dropping whatever leaves the display.

    Working on the finished frame rather than on the geometry keeps one set of
    coordinates for every display, and lets two panels with different bezels
    show the same page at their own offsets.
    """
    if not shift:
        return operations
    moved = []
    for operation in operations:
        if operation[0] == "f":
            # A fill spanning the whole width is the background, and must go
            # on covering the whole display: shifted, it would leave a strip
            # of the previous page standing.
            if operation[2] <= 0 and operation[4] >= WIDTH:
                moved.append(operation)
                continue
            x = operation[2] + shift
            left = max(0, x)
            right = min(WIDTH, x + operation[4])
            if right <= left:
                continue
            moved.append((operation[0], operation[1], left, operation[3], right - left, operation[5]))
            continue
        # An opaque text cell cannot be clipped, so a run that no longer fits
        # is dropped whole.  The layout contract rejects a shift that does
        # this, so it should never happen in practice.
        x = operation[3] + shift
        if x < 0 or x + len(operation[5]) * FONT_CELL_WIDTH > WIDTH:
            continue
        moved.append(
            (operation[0], operation[1], operation[2], x, operation[4], operation[5], operation[6])
        )
    return moved


def invalidate(canvas: Any) -> None:
    """Forget the last ND frame, so the next one is drawn complete."""
    try:
        del canvas._muslimsim_nd_state
    except (AttributeError, TypeError):
        pass
    try:
        del canvas._muslimsim_nd_pending
    except (AttributeError, TypeError):
        pass


class _BoundsCanvas:
    """Minimal canvas substitute for the offline layout check."""

    def __init__(self, bb35: bool = False) -> None:
        self.text_runs: list = []
        self.font_ids: list = []
        self._muslimsim_nd_bb35 = bool(bb35)

    def colour(self, _red: int, _green: int, _blue: int) -> None:
        return None

    def fill(self, x: int, y: int, width: int, height: int) -> None:
        if x < 0 or y < 0 or x + width > WIDTH or y + height > HEIGHT:
            raise NdLayoutError(f"fill outside ND: {(x, y, width, height)}")

    def text(self, x, y, value, _foreground, _background, _font_id) -> None:
        if x < 0 or y < 0 or x + len(value) * FONT_CELL_WIDTH > WIDTH or y + FONT_CELL_HEIGHT > HEIGHT:
            raise NdLayoutError(f"text outside ND: {(x, y, value)!r}")
        self.text_runs.append((x, y, value))
        self.font_ids.append(int(_font_id))


def assert_layout_contract() -> None:
    """Offline check that every ND state stays inside the display."""
    base = {
        "heading": 330.0, "track": 336.0, "target_heading": 350.0,
        "groundspeed": 288.0, "true_airspeed": 301.0,
        "wind_speed": 14.0, "wind_direction": 346.0,
        "map_range_nm": 10.0, "map_mode": 2.0,
        "altitude": 12000.0, "target_altitude": 16000.0,
        "vertical_speed": 1400.0, "roll": 18.0,
    }
    variants = (
        base,
        {**base, "map_mode": 0.0, "nav_course": 268.0, "nav_deviation": -1.4,
         "nav_frequency": 11030.0, "nav_dme": 14820.0},
        {**base, "map_mode": 1.0, "ctr": 1.0, "nav_course": 12.0, "nav_deviation": 2.5,
         "nav_frequency": 11330.0, "nav_dme": 0.0},
        {**base, "map_mode": 3.0},
        {**base, "ctr": 1.0, "wxr": 1.0, "sta": 1.0, "wpt": 1.0, "arpt": 1.0,
         "data": 1.0, "pos": 1.0, "terr": 1.0, "tfc": 1.0},
        {**base, "map_mode": 2.0, "latitude": 32.88, "longitude": -97.03,
         "route_lat": [32.90, 32.89, 32.71, 33.60, 0.0, 41.0],
         "route_lon": [-97.04, -97.05, -97.05, -98.90, 0.0, -100.0],
         "route_name": ["KDFW", "TTT", "JPOOL", "ADM"],
         "route_altitude": [0, 12000, 18000, 24000],
         "route_altitude2": [0, 0, 16000, 0],
         "route_altitude_type": [0, 2, 3, 1],
         "route_speed": [0, 250, 280, 0], "route_eta": [0, 13.20, 13.50, 14.25],
         "route_kind": [0, 1, 2, 3], "data": 1.0,
         "route_hold_time": [0, 1.0, 0, 0], "route_hold_distance": [0, 0, 0, 0],
         "next_waypoint_name": "JPOOL", "next_waypoint_distance": 8.4,
         "next_waypoint_eta": 13.50, "rnp": 0.30, "anp": 0.08},
        {**base, "map_mode": 2.0, "ctr": 1.0, "latitude": 32.88, "longitude": -97.03,
         "map_range_nm": 5.0,
         "route_lat": [32.90, 32.89, 32.71], "route_lon": [-97.04, -97.05, -97.05]},
        {**base, "map_mode": 3.0, "latitude": 32.88, "longitude": -97.03,
         "route_lat": [32.90, 32.89], "route_lon": [-97.04, -97.05]},
        {**base, "heading": 0.5, "track": 359.0, "target_heading": 12.0, "map_mode": 3.0,
         "map_range_nm": 640.0, "groundspeed": 0.0, "true_airspeed": 0.0,
         "wind_speed": 199.0, "wind_direction": 1.0},
        {**base, "heading": 179.9, "track": 180.0, "target_heading": 179.0, "map_mode": 0.0,
         "map_range_nm": 5.0, "nav_vdeviation": -0.8, "marker_middle": 1.0,
         "nav_to_from": 1.0},
        {**base, "tfc": 1.0, "tcas_alert": 1.0,
         "tcas_bearing": [15.0, -30.0, 85.0],
         "tcas_distance": [3704.0, 9260.0, 14816.0],
         "tcas_altitude": [90.0, -300.0, 800.0],
         "tcas_vertical": [3.0, -4.0, 0.0], "tcas_ids": [1, 2, 3],
         "wxr": 1.0, "weather_cells": [(10, .3, 0), (-20, .5, 1), (30, .7, 2)]},
        {**base, "bearing_selector_1": 1.0, "bearing_selector_2": -1.0,
         "nav1_bearing": 22.0, "adf2_bearing": 280.0,
         "fuel_total": 4200.0, "eng_ff_0": 0.55, "eng_ff_1": 0.57},
        {**base, "latitude": 32.88, "longitude": -97.03,
         "sta": 1.0, "wpt": 1.0, "arpt": 1.0,
         "database_stations": [(32.869, -97.040, "TTT", "VOR")],
         "database_waypoints": [(32.955, -96.950, "FINGR")],
         "database_airports": [(32.899, -97.040, "KDFW")]},
        {**base, "terr": 1.0, "vsd": 1.0,
         "terrain_profile": [(-50 + index * 5, index / 20.0, -4000 + index * 400)
                             for index in range(20)]},
        {**base, "map_fail": 1.0, "vtk_fail": 1.0, "mode_disagree": 1.0,
         "range_disagree": 1.0, "tcas_fail": 1.0, "wxr_fail": 1.0,
         "terr_fail": 1.0, "unable_rnp": 1.0},
        {key: math.nan for key in base},
    )
    for bb35 in (False, True):
        for values in variants:
            canvas = _BoundsCanvas(bb35)
            draw_nd_frame(canvas, values)
            if any(font_id != ND_COMPACT_FONT_ID for font_id in canvas.font_ids):
                raise NdLayoutError(
                    f"{'BB35' if bb35 else 'BB36'} ND lost compact PFD typography"
                )
    if AIRCRAFT_Y + 2 > HEIGHT or AIRCRAFT_Y - COMPASS_RADIUS - 16 < 0:
        raise NdLayoutError("Compass arc does not fit the display")

    # A shift that pushes anything off the right edge would drop it silently,
    # which is how a readout goes missing without anyone noticing.
    for bb35 in (False, True):
        for values in variants:
            recorder = _NdOpRecorder(bb35)
            draw_nd_frame(recorder, values)
            shifted = _shift_operations(recorder.ops, ND_SHIFT_X)
            lost = len(recorder.ops) - len(shifted)
            if lost:
                raise NdLayoutError(
                    f"A shift of {ND_SHIFT_X} px drops {lost} "
                    f"{'BB35' if bb35 else 'BB36'} item(s) off the display"
                )
            for operation in shifted:
                if operation[0] != "t":
                    continue
                left = int(operation[3])
                right = left + len(operation[5]) * FONT_CELL_WIDTH
                if left < ND_TEXT_LEFT + ND_SHIFT_X or right > ND_TEXT_RIGHT + ND_SHIFT_X:
                    raise NdLayoutError(
                        f"{'BB35' if bb35 else 'BB36'} text entered a bezel zone: "
                        f"{(left, right, operation[5])!r}"
                    )

    bb35 = _NdOpRecorder(True)
    draw_nd_frame(bb35, variants[5])

    def recorded_rows(recorder: _NdOpRecorder) -> dict[int, str]:
        rows: dict[int, list] = {}
        for operation in recorder.ops:
            if operation[0] == "t":
                rows.setdefault(int(operation[4]), []).append(
                    (int(operation[3]), str(operation[5]))
                )
        return {
            y: "".join(text for _x, text in sorted(cells))
            for y, cells in rows.items()
        }

    bb35_rows = recorded_rows(bb35)
    if "TRK" not in bb35_rows.get(12, ""):
        raise NdLayoutError("BB35 Boeing top band lost its TRK readout")
    if "FMC L" not in bb35_rows.get(445, ""):
        raise NdLayoutError("BB35 Boeing ND lost its FMC source annunciation")
    if "RNP" not in bb35_rows.get(260, ""):
        raise NdLayoutError("BB35 Boeing ND RNP block left its right-side zone")

    # PLAN must use the centred geometry and the same live selected range as
    # MAP.  A four-times wider range must therefore reduce every projected
    # route distance by exactly four while retaining waypoint text and both
    # range values.
    plan_near = {**variants[5], "map_mode": 3.0, "map_range_nm": 10.0, "ctr": 0.0}
    plan_far = {**plan_near, "map_range_nm": 40.0}
    near_geometry = _map_geometry({**plan_near, "heading": 0.0, "ctr": 1.0})
    far_geometry = _map_geometry({**plan_far, "heading": 0.0, "ctr": 1.0})
    if near_geometry is None or far_geometry is None or not math.isclose(
        near_geometry[2] / far_geometry[2], 4.0, rel_tol=0.0, abs_tol=1e-9
    ):
        raise NdLayoutError("PLAN range selector no longer controls route scale")
    plan_canvas = _NdOpRecorder(True)
    draw_nd_frame(plan_canvas, plan_near)
    plan_text = " ".join(recorded_rows(plan_canvas).values())
    if "JPOOL" not in plan_text or "10" not in plan_text or "5" not in plan_text:
        raise NdLayoutError("PLAN lost its waypoint or half/full range labels")
    if _compact_text_width("KDFW") >= FONT_CELL_WIDTH * 4:
        raise NdLayoutError("ND waypoint typography is no longer compact")

    # Prove the live path recognizes the physical identifier before it builds
    # its private operation recorder.  A direct-frame test alone would not
    # catch losing the identifier at that boundary.
    for identifier in (BB35_IDENTIFIER, 0x32):
        live_canvas = _BoundsCanvas()
        live_canvas.identifier = identifier
        live_canvas._muslimsim_nd_shift_x = ND_SHIFT_X
        draw_live_nd(live_canvas, variants[5])
        if not live_canvas.font_ids or any(
            font_id != ND_COMPACT_FONT_ID for font_id in live_canvas.font_ids
        ):
            raise NdLayoutError(
                f"Live ND identifier 0x{identifier:02X} selected the wrong font/layout"
            )
    for slot in (GROUND_SPEED_VALUE, TRUE_AIRSPEED_VALUE, WIND_TEXT, MODE_LABEL,
                 RANGE_VALUE, RANGE_UNIT, MAG_LABEL):
        if slot.rect.right > WIDTH or slot.rect.bottom > HEIGHT:
            raise NdLayoutError(f"ND slot leaves the display: {slot.name}")
