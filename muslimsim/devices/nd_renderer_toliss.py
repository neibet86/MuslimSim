"""Code-native 640x480 ToLiss A320 Navigation Display (ND).

Sibling to muslimsim/devices/nd_renderer.py (Boeing 737 ND), not a reskin of
it: fresh Airbus-native geometry (ROSE with the aeroplane fixed at screen
centre, ARC with the aeroplane low and a forward-looking compass, and a true
north-up PLAN with two scale circles - the real A320 EFIS mode rotary's own
split, driven by `AirbusFBW/NDmodeCapt` rather than a synthetic toggle) plus
a route line built from full `toliss_airbus/flightplan/*` waypoint arrays when
available, or from the installed A321's real `WPT_Crs`/`WPT_Dist` active leg,
an ILS/VOR course+deviation scale,
range ring(s), native ToLiss VOR/ADF single- and double-bearing pointers,
and EFIS-control-panel overlay annunciations
(`AirbusFBW/NDShow*Capt`/`WXRonND1`/`TerrainSelectedND1`). Every value key
this module reads via `values.get(...)` is a flat, already-resolved name
built upstream by `_toliss_nd_values()` in bridge/final.py from the raw feed
in mcdu_bb36_toliss_paths.py's `TOLISS_MCDU_SECONDARY_DATAREFS["nd"]` - this
module never talks to a dataref name directly.

Shares the PFD/ND/systems final-image differential contract (imported, not
reimplemented) with pfp_renderer.py: `_OpRecorder`/`_dirty_boxes`/
`_emit_frame`/`Rect`/`TextSlot`/`_slot`/`_draw_large_text`/`_emit_rows`/
`_filled_triangle_rows`/`_clamp`/`_finite`/`_heading_delta`
are airplane-agnostic and reused directly, exactly as
pfp_renderer_toliss.py/systems_renderer_toliss.py already do for their own
pages.

The bounds-checked stamp and connected-line rasterisers are imported
unmodified from nd_renderer.py. Live ToLiss ARC/PLAN curves use local,
centre-parametric geometry because the Boeing helper is fixed to its own
screen anchor; this lets the Airbus aeroplane sit at (320,432) in ARC and
(320,257) in PLAN without changing any Boeing constant. Every route,
waypoint, scale, EFIS and deviation widget remains Airbus-specific code.

Bandwidth discipline: this page's static content (a full compass, in ROSE
mode) is far larger than the PFD's, so its full-recovery repaint is spaced
out to Boeing ND's own cadence (600 frames / 60s - see
`nd_renderer.ND_FULL_REPAINT_FRAMES`/`ND_FULL_REPAINT_SECONDS`) rather than
the PFD/ECAM's much tighter default (120 frames / 1.5s -
`pfp_renderer.FULL_REPAINT_FRAMES`/`FULL_REPAINT_SECONDS`). Boeing's own
dedicated Boeing BB35 ND stages full repaint bands, but the owner rejected
alternating half-arcs for this ToLiss display. Both ToLiss panels therefore
receive one complete recovery image followed by final-pixel dirty regions;
the offline guard caps recovery at 450 reports and a turn at 375. A mode or
map-validity change forces a full repaint because those layouts share almost
no geometry. The BB35/BB36 live hardware pass remains the final authority.

No TCAS traffic overlay: the catalog has no traffic-target position data
anywhere for ToLiss (searched exhaustively, same conclusion as the plan's
own research) - this renderer never draws one, not even a placeholder.

Every judgment call (NDmodeCapt's enum order, NDrangeCapt's nm table,
current_to_waypoint's indexing convention, the ICAO/waypoint-ident text
decode path, and own-ship lat/lon as the generic X-Plane SDK fallback) is
flagged in-code for live-session confirmation - same
"prove, don't guess" discipline as every other first-pass ToLiss renderer in
this project.
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
    MAGENTA,
    PFD_NUMBER_FONT_ID,
    RED,
    WHITE,
    WIDTH,
    _clamp,
    _dirty_boxes,
    _emit_frame,
    _filled_triangle_rows,
    _finite,
    _heading_delta,
    _OpRecorder,
    _packed_number_cells,
    _slot,
)
from muslimsim.devices.nd_renderer import (
    AIRCRAFT_X as _ARC_CENTER_X,
    AIRCRAFT_Y as _ARC_CENTER_Y,
    _arc_point,
    _block,
    _draw_arc,
    _draw_line,
)

DIM_GREY = (100, 106, 118)
PANEL_LINE = (58, 63, 74)
ECAM_BLUE = CYAN                # see mcdu_bb36_toliss_paths.py's own "b" ->
                                 # COLOR_CYAN precedent for Airbus-blue-as-cyan

# Same physical bezel-masked strip as the ECAM/PFD ToLiss pages - same
# hardware (BB36 F0 mirror canvas), duplicated rather than imported so this
# file stays decoupled from its siblings.
X_SAFE_LEFT = 34
X_SAFE_RIGHT = 606
# Text gets an extra ten-pixel cushion inside the proven bezel-safe strip.
# This is deliberately stricter than geometry: arcs may reach X_SAFE_RIGHT,
# but a final opaque native character cell must never visually kiss the mask.
HEADER_SAFE_RIGHT = X_SAFE_RIGHT - 10

# Compact Airbus header: GS/TAS and wind at the left, PPOS at the right.
# The old three-row title/overlay banner consumed almost one fifth of the map.
GS_LABEL = _slot("nd gs label", X_SAFE_LEFT, 2, 28, "left")
GS_VALUE = _slot("nd gs value", 64, 2, 46, "left")
TAS_LABEL = _slot("nd tas label", 112, 2, 36, "left")
TAS_VALUE = _slot("nd tas value", 151, 2, 50, "left")
PPOS_LABEL = _slot("nd ppos", HEADER_SAFE_RIGHT - 66, 2, 66, "right")
WIND_LABEL = _slot("nd wind", X_SAFE_LEFT, 31, 116, "left")
MODE_LABEL = _slot("nd mode", 420, 31, 82, "right")
RANGE_LABEL = _slot("nd range", HEADER_SAFE_RIGHT - 92, 31, 92, "right")

# The real ToLiss ND keeps tuned bearing-source identification at the lower
# corners.  Three compact rows fit beside (not beneath) the centred GPS
# message box: source, station ident, then DME where the selected source is
# a VOR.  NAV1 is always the single needle and NAV2 the double needle.
BEARING1_LABEL = _slot("nd bearing 1 source", X_SAFE_LEFT, 392, 126, "left")
BEARING1_ID = _slot("nd bearing 1 id", X_SAFE_LEFT, 421, 126, "left")
BEARING1_DME = _slot("nd bearing 1 dme", X_SAFE_LEFT, 450, 126, "left")
BEARING2_LABEL = _slot("nd bearing 2 source", X_SAFE_RIGHT - 126, 392, 126, "right")
BEARING2_ID = _slot("nd bearing 2 id", X_SAFE_RIGHT - 126, 421, 126, "right")
BEARING2_DME = _slot("nd bearing 2 dme", X_SAFE_RIGHT - 126, 450, 126, "right")

# Retained names are aliases only for compatibility with older offline tools.
TO_WPT_LABEL = _slot("nd to waypoint compatibility", 205, 2, 180, "center")
DEP_DEST_LABEL = _slot("nd dep dest compatibility", 205, 31, 180, "center")
OVERLAY_ROW_Y = 76
_OVERLAY_LABELS: Tuple[Tuple[str, str], ...] = (
    ("show_cstr", "CSTR"), ("show_wpt", "WPT"),
    ("show_vord", "VOR.D"), ("show_ndb", "NDB"),
    ("show_arpt", "ARPT"), ("show_wxr", "WXR"),
    ("show_terr", "TERR"),
)
OVERLAY_SLOTS: Tuple[Any, ...] = tuple()

_ALL_FIXED_SLOTS: Tuple[Any, ...] = (
    GS_LABEL, GS_VALUE, TAS_LABEL, TAS_VALUE, PPOS_LABEL,
    WIND_LABEL, MODE_LABEL, RANGE_LABEL,
)

COMPASS_TOP = 62

# ROSE mode: aeroplane fixed at this screen point, full 360-degree rose.
ROSE_CENTER_X = 320
ROSE_CENTER_Y = 268
ROSE_RADIUS = 178

# ARC mode: reuses nd_renderer.py's own AIRCRAFT_X/AIRCRAFT_Y anchor via the
# imported _arc_point/_draw_arc (see module docstring) - radius/half-angle
# are ordinary call parameters, so this Airbus geometry differs from
# Boeing's own 250px/65deg even though the anchor point is shared screen
# real estate.
ARC_RADIUS = 300.0
ARC_HALF_ANGLE = 60.0

# PLAN is a true north-up map with two distance circles, not a ROSE fallback.
PLAN_CENTER_X = 320
PLAN_CENTER_Y = 257
PLAN_RADIUS = 174.0

# A 3px sample stride exactly meets the 3px outer-arc stamps: continuous on
# the LCD without the redundant overlap that consumed bearing-pointer budget.
ARC_SEGMENT = 3.0

# A full rose repaint is expensive - pace it like Boeing's own dedicated ND
# (600 frames / 60s), not the smaller PFD/ECAM ToLiss pages' tighter cadence.
TOLISS_ND_FULL_REPAINT_FRAMES = 600
TOLISS_ND_FULL_REPAINT_SECONDS = 60.0

_ND_QUANTISED_STEPS = {"heading": 0.25}

# Real A320 EFIS control-panel rotary order.  ILS/VOR/NAV share the centred
# ROSE geometry, ARC is heading-up with the aircraft low on the display, and
# PLAN is a separate north-up double-range-ring presentation.
_ND_MODE_LABELS = {0: "ROSE ILS", 1: "ROSE VOR", 2: "ROSE NAV", 3: "ARC", 4: "PLAN"}
_ND_ARC_MODE_INDEX = 3
_ND_PLAN_MODE_INDEX = 4

# JUDGMENT CALL: real A320 range rotary steps (10/20/40/80/160/320nm),
# index order guessed the same way - not documented in the catalog. Falls
# back to 10nm for anything unmapped rather than fabricating a scale.
_ND_RANGE_TABLE = {0: 10.0, 1: 20.0, 2: 40.0, 3: 80.0, 4: 160.0, 5: 320.0}
_ND_DEFAULT_RANGE_NM = 10.0

# X-Plane's published FMS contract permits at most 100 waypoints.  Keep that
# same hard ceiling for the ToLiss autosave source; range clipping below means
# only visible legs emit HID drawing operations.
_ND_ROUTE_MAX_LEGS = 100
_NM_PER_DEGREE = 60.0            # a degree of latitude is sixty nautical miles


class TolissNdLayoutError(RuntimeError):
    """A ToLiss ND primitive left the physical LCD or collided with another."""


def _text(canvas: Any, slot: Any, value: str, colour: Tuple[int, int, int] = WHITE,
          background: Tuple[int, int, int] = BLACK) -> None:
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


def _bool(value: Any) -> bool:
    return _finite(value) and float(value) >= 0.5


def _fmt(value: Any, decimals: int = 0, fallback: str = "---") -> str:
    if not _finite(value):
        return fallback
    if decimals <= 0:
        return str(int(round(float(value))))
    return f"{float(value):.{decimals}f}"


def _airbus_heading_label(value: float) -> str:
    """Airbus compass labels are numeric tens; never Boeing N/E/S/W."""
    return str((int(round(float(value))) % 360) // 10)


def _line(canvas: Any, start: Tuple[float, float], end: Tuple[float, float],
          colour: Tuple[int, int, int], thickness: int = 2) -> None:
    canvas.colour(*colour)
    _draw_line(canvas, start, end, thickness)


def _dashed_line(
    canvas: Any,
    start: Tuple[float, float],
    end: Tuple[float, float],
    colour: Tuple[int, int, int],
    thickness: int = 2,
    dash: float = 13.0,
    gap: float = 8.0,
) -> None:
    """Draw the native ToLiss selected-heading flight-plan dash pattern."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 0.5:
        return
    ux, uy = dx / length, dy / length
    offset = 0.0
    while offset < length:
        stop = min(length, offset + dash)
        _line(
            canvas,
            (start[0] + ux * offset, start[1] + uy * offset),
            (start[0] + ux * stop, start[1] + uy * stop),
            colour,
            thickness,
        )
        offset += dash + gap


# ---------------------------------------------------------------------------
# Header: mode + range (row 1), active-leg identifier + dep/dest (row 2),
# EFIS overlay toggle annunciations (row 3) - all from real datarefs.
# ---------------------------------------------------------------------------
def _mode_index(values: Mapping[str, Any]) -> int:
    value = values.get("mode")
    if not _finite(value):
        return 2  # unknown -> safe ROSE NAV-style fallback, not ARC
    # Clamp before formatting so a garbage sensor value can never build an
    # oversized "MODE n" fallback string that TextSlot.position_for would
    # then silently drop (see this project's own PFD-step discovery of that
    # failure class) - bounded by construction instead of by luck.
    return int(round(_clamp(float(value), -99.0, 999.0)))


def _mode_label(mode: int) -> str:
    return _ND_MODE_LABELS.get(mode, f"MODE {mode}")


def _is_arc_mode(values: Mapping[str, Any]) -> bool:
    return _mode_index(values) == _ND_ARC_MODE_INDEX


def _range_nm(values: Mapping[str, Any]) -> float:
    # "range_index" is the RAW AirbusFBW/NDrangeCapt rotary reading (an
    # enum position), not yet a nautical-mile value - see _ND_RANGE_TABLE.
    value = values.get("range_index")
    if not _finite(value):
        return _ND_DEFAULT_RANGE_NM
    index = int(round(_clamp(float(value), 0.0, 5.0)))
    return _ND_RANGE_TABLE.get(index, _ND_DEFAULT_RANGE_NM)


def _icao(value: Any, width: int = 6) -> str:
    text = str(value or "").strip().upper()
    # Defensive clip: the real identifier is 3-4 characters, but the decode
    # path (_ws_decode_text) is shared with a text dataref whose exact shape
    # is unconfirmed - clip well short of DEP_DEST_LABEL's capacity rather
    # than trust the source never sends anything longer.
    return text[:width]


def _draw_header(canvas: Any, values: Mapping[str, Any]) -> None:
    canvas.colour(*BLACK)
    canvas.fill(0, 0, WIDTH, COMPASS_TOP)
    canvas.colour(*PANEL_LINE)
    canvas.fill(0, COMPASS_TOP - 2, WIDTH, 1)

    map_valid = _map_available(values)
    _text(canvas, GS_LABEL, "GS", WHITE)
    _text(
        canvas, GS_VALUE,
        _fmt(values.get("ground_speed"), 0) if map_valid else "---",
        GREEN,
    )
    _text(canvas, TAS_LABEL, "TAS", WHITE)
    _text(
        canvas, TAS_VALUE,
        _fmt(values.get("true_air_speed"), 0) if map_valid else "---",
        GREEN,
    )
    _text(canvas, PPOS_LABEL, "PPOS", WHITE)

    if map_valid and _bool(values.get("wind_available")):
        _text(
            canvas, WIND_LABEL,
            f"{_fmt(values.get('wind_direction'), 0)}/{_fmt(values.get('wind_speed'), 0)}",
            GREEN,
        )
    else:
        _text(canvas, WIND_LABEL, "---/--", GREEN)

    mode = _mode_index(values)
    _text(canvas, MODE_LABEL, _ND_MODE_LABELS.get(mode, "ROSE NAV").replace("ROSE ", ""), WHITE)
    _text(canvas, RANGE_LABEL, f"{_fmt(_range_nm(values), 0)}NM", CYAN)


def _draw_active_overlays(canvas: Any, values: Mapping[str, Any]) -> None:
    enabled = [
        label for key, label in _OVERLAY_LABELS if _bool(values.get(key))
    ]
    for index, label in enumerate(enabled[:5]):
        _text(
            canvas,
            _slot(f"nd active overlay {index}", X_SAFE_LEFT, 76 + index * 24, 70, "left"),
            label,
            GREEN if label in {"WXR", "TERR"} else CYAN,
        )


# ---------------------------------------------------------------------------
# ROSE mode compass: full 360-degree ring, ticks every 5deg, labelled every
# 30deg - local bearing/radius-to-xy math (see module docstring for why this
# cannot reuse nd_renderer.py's _arc_point).
# ---------------------------------------------------------------------------
def _rose_point(bearing: float, radius: float) -> Tuple[float, float]:
    radians = math.radians(bearing)
    return (
        ROSE_CENTER_X + radius * math.sin(radians),
        ROSE_CENTER_Y - radius * math.cos(radians),
    )


def _draw_rose_ring(canvas: Any, radius: float, colour: Tuple[int, int, int],
                     thickness: int = 3, dashed: bool = False) -> None:
    step = math.degrees(ARC_SEGMENT / max(1.0, radius))
    canvas.colour(*colour)
    bearing = 0.0
    index = 0
    while bearing < 360.0:
        index += 1
        if not dashed or index % 3:
            x, y = _rose_point(bearing, radius)
            _block(canvas, x, y, thickness)
        bearing += step


def _draw_rose_compass(canvas: Any, values: Mapping[str, Any]) -> None:
    _draw_rose_ring(canvas, ROSE_RADIUS, WHITE, 3)
    heading = values.get("heading")
    if not _finite(heading):
        return
    hdg = float(heading) % 360.0
    for tick in range(0, 360, 5):
        delta = _heading_delta(float(tick), hdg)
        length = 14 if tick % 30 == 0 else (9 if tick % 10 == 0 else 5)
        inner = _rose_point(delta, ROSE_RADIUS - length)
        outer = _rose_point(delta, ROSE_RADIUS)
        _line(canvas, inner, outer, WHITE, 2)
        if tick % 30 == 0:
            label = _airbus_heading_label(float(tick))
            lx, ly = _rose_point(delta, ROSE_RADIUS - length - 16)
            slot = _slot("nd rose tick", int(round(lx - 17)), int(round(ly - 14)), 34, "center")
            if slot.rect.y >= COMPASS_TOP:
                _text(canvas, slot, label, WHITE, BLACK)


# ---------------------------------------------------------------------------
# ARC mode compass: forward-looking half-angle arc at the shared BB36 anchor
# (see module docstring). _draw_arc/_arc_point reused directly for the
# primitive stepping; the tick/label loop is new Airbus-specific code.
# ---------------------------------------------------------------------------
def _draw_arc_compass(canvas: Any, values: Mapping[str, Any]) -> None:
    _draw_arc(canvas, ARC_RADIUS, ARC_HALF_ANGLE, WHITE, 3)
    heading = values.get("heading")
    if not _finite(heading):
        return
    hdg = float(heading) % 360.0
    first = int((hdg - ARC_HALF_ANGLE) // 5) * 5
    for tick in range(first, int(hdg + ARC_HALF_ANGLE) + 5, 5):
        delta = _heading_delta(float(tick), hdg)
        if abs(delta) > ARC_HALF_ANGLE:
            continue
        length = 16 if tick % 30 == 0 else (10 if tick % 10 == 0 else 6)
        inner = _arc_point(delta, ARC_RADIUS - length)
        outer = _arc_point(delta, ARC_RADIUS)
        _line(canvas, inner, outer, WHITE, 2)
        if tick % 30 == 0:
            label = _airbus_heading_label(float(tick % 360))
            lx, ly = _arc_point(delta, ARC_RADIUS - length - 16)
            slot = _slot("nd arc tick", int(round(lx - 17)), int(round(ly - 14)), 34, "center")
            if slot.rect.y >= COMPASS_TOP:
                _text(canvas, slot, label, WHITE, BLACK)


# ---------------------------------------------------------------------------
# Range ring(s): one ring at half the selected range, labelled. ARC mode
# reuses _draw_arc directly (its centre already matches); ROSE mode needs
# its own ring loop (see module docstring).
# ---------------------------------------------------------------------------
def _draw_range_ring(canvas: Any, values: Mapping[str, Any], arc_mode: bool) -> None:
    range_nm = _range_nm(values)
    radius = ARC_RADIUS if arc_mode else ROSE_RADIUS
    half_radius = radius / 2.0
    if arc_mode:
        _draw_arc(canvas, half_radius, ARC_HALF_ANGLE, DIM_GREY, 2, dashed=True)
        lx, ly = _arc_point(0.0, half_radius)
    else:
        _draw_rose_ring(canvas, half_radius, DIM_GREY, 2, dashed=True)
        lx, ly = _rose_point(0.0, half_radius)
    label = _fmt(range_nm / 2.0, 0)
    slot = _slot("nd half range", int(round(lx - len(label) * FONT_CELL_WIDTH / 2)),
                 int(round(ly - 22)), len(label) * FONT_CELL_WIDTH + 4, "left")
    if slot.rect.y >= COMPASS_TOP:
        _text(canvas, slot, label, DIM_GREY, BLACK)


def _draw_aircraft_symbol(canvas: Any, cx: int, cy: int) -> None:
    canvas.colour(*WHITE)
    canvas.fill(cx - 1, cy - 14, 2, 22)   # fuselage
    canvas.fill(cx - 16, cy - 2, 32, 3)   # wings
    canvas.fill(cx - 8, cy + 11, 16, 3)   # tail


# ---------------------------------------------------------------------------
# Route: full per-waypoint arrays when a ToLiss version publishes them. The
# installed A321 1.8 does not; in that case WPT_Crs/WPT_Dist computes the real
# active-leg endpoint from own-ship position. Own-ship position projects every
# fix heading-up around the aeroplane.
# ---------------------------------------------------------------------------
def _route_points(values: Mapping[str, Any]) -> list:
    latitudes = values.get("route_lat") or ()
    longitudes = values.get("route_lon") or ()
    no_wp = values.get("route_no_wp")
    # Real active-leg count (toliss_airbus/flightplan/no_wp): trims stale
    # tail entries the array can carry past the end of the real route,
    # rather than drawing whatever garbage/zeroed slots sit beyond it.
    limit = int(round(float(no_wp))) if _finite(no_wp) and float(no_wp) > 0.0 else None
    points = []
    for source_index, (latitude, longitude) in enumerate(zip(latitudes, longitudes)):
        if limit is not None and source_index >= limit:
            break
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(latitude) and math.isfinite(longitude)):
            continue
        if abs(latitude) < 0.001 and abs(longitude) < 0.001:
            continue          # (0,0) reads as an unset slot, not really Africa
        if abs(latitude) > 90.0 or abs(longitude) > 180.0:
            continue
        points.append((source_index, latitude, longitude))
        if len(points) >= _ND_ROUTE_MAX_LEGS:
            break
    if not points and _bool(values.get("route_active_leg_fallback")):
        own_lat = values.get("own_lat")
        own_lon = values.get("own_lon")
        course = values.get("waypoint_course")
        distance = values.get("waypoint_distance")
        if all(_finite(value) for value in (own_lat, own_lon, course, distance)) and float(distance) > 0:
            lat1 = math.radians(float(own_lat))
            lon1 = math.radians(float(own_lon))
            bearing = math.radians(float(course) % 360.0)
            angular = float(distance) / 3440.065
            lat2 = math.asin(
                math.sin(lat1) * math.cos(angular)
                + math.cos(lat1) * math.sin(angular) * math.cos(bearing)
            )
            lon2 = lon1 + math.atan2(
                math.sin(bearing) * math.sin(angular) * math.cos(lat1),
                math.cos(angular) - math.sin(lat1) * math.sin(lat2),
            )
            points = [
                (0, float(own_lat), float(own_lon)),
                (1, math.degrees(lat2), ((math.degrees(lon2) + 180.0) % 360.0) - 180.0),
            ]
    return points


def _route_leg_broken(
    values: Mapping[str, Any],
    first_source_index: int,
    second_source_index: int,
) -> bool:
    """True when no FMGS connector belongs between two retained points."""
    if second_source_index != first_source_index + 1:
        # A missing source slot is the QPS representation of a flight-plan
        # discontinuity.  Filtering invalid coordinates must never heal it.
        return True
    breaks = values.get("route_breaks") or ()
    try:
        return bool(breaks[second_source_index])
    except (IndexError, TypeError):
        return False


def _route_id(values: Mapping[str, Any], source_index: int) -> str:
    ids = values.get("route_ids") or ()
    try:
        return _icao(ids[source_index], 9)
    except (IndexError, TypeError):
        return ""


def _project(latitude: float, longitude: float, own_lat: float, own_lon: float,
             heading: float, cx: int, cy: int, px_per_nm: float) -> Tuple[float, float]:
    north = (latitude - own_lat) * _NM_PER_DEGREE
    east = (longitude - own_lon) * _NM_PER_DEGREE * math.cos(math.radians(own_lat))
    radians = math.radians(heading)
    ahead = north * math.cos(radians) + east * math.sin(radians)
    right = east * math.cos(radians) - north * math.sin(radians)
    return cx + right * px_per_nm, cy - ahead * px_per_nm


def _leg_bbox_visible(start: Tuple[float, float], end: Tuple[float, float],
                       margin: float = 40.0) -> bool:
    """Cheap reject for a leg with both ends nowhere near the screen.

    _draw_line already bounds-checks every run it emits internally, so this
    only exists to avoid stepping across a leg's full (possibly enormous,
    off-screen) pixel span for no visible result.
    """
    x0, y0 = start
    x1, y1 = end
    left, right = (x0, x1) if x0 <= x1 else (x1, x0)
    top, bottom = (y0, y1) if y0 <= y1 else (y1, y0)
    return not (right < -margin or left > WIDTH + margin
                or bottom < -margin or top > HEIGHT + margin)


def _clip_segment_to_circle(
    start: Tuple[float, float],
    end: Tuple[float, float],
    cx: float,
    cy: float,
    radius: float,
) -> Tuple[Tuple[float, float], Tuple[float, float]] | None:
    """Clip one route leg to the selected ND range circle.

    Without this, a distant waypoint made the renderer continue the green
    plan line through the header and lower tuned-source text.  The aircraft
    display clips map content at the compass boundary, and doing the same
    also avoids sending hundreds of invisible/off-map native fill commands.
    """
    x0, y0 = start
    dx, dy = end[0] - x0, end[1] - y0
    a = dx * dx + dy * dy
    if a < 1e-9:
        return (start, end) if math.hypot(x0 - cx, y0 - cy) <= radius else None
    fx, fy = x0 - cx, y0 - cy
    b = 2.0 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - radius * radius
    discriminant = b * b - 4.0 * a * c
    inside_start = c <= 0.0
    inside_end = (end[0] - cx) ** 2 + (end[1] - cy) ** 2 <= radius * radius
    if discriminant < 0.0:
        return (start, end) if inside_start and inside_end else None
    root = math.sqrt(max(0.0, discriminant))
    first = (-b - root) / (2.0 * a)
    second = (-b + root) / (2.0 * a)
    low = max(0.0, min(first, second))
    high = min(1.0, max(first, second))
    if high < low or (not inside_start and not inside_end and not (low <= high)):
        return None
    return (
        (x0 + dx * low, y0 + dy * low),
        (x0 + dx * high, y0 + dy * high),
    )


def _inside_circle(x: float, y: float, cx: float, cy: float, radius: float) -> bool:
    return (x - cx) ** 2 + (y - cy) ** 2 <= (radius + 3.0) ** 2


def _draw_route(
    canvas: Any,
    values: Mapping[str, Any],
    cx: int,
    cy: int,
    px_per_nm: float,
    clip_radius: float,
) -> None:
    own_lat = values.get("own_lat")
    own_lon = values.get("own_lon")
    heading = values.get("heading")
    if not (_finite(own_lat) and _finite(own_lon) and _finite(heading) and px_per_nm > 0.0):
        return
    points = _route_points(values)
    if not points:
        return
    own_lat_f, own_lon_f, heading_f = float(own_lat), float(own_lon), float(heading)
    screen = [
        _project(latitude, longitude, own_lat_f, own_lon_f, heading_f, cx, cy, px_per_nm)
        for _source_index, latitude, longitude in points
    ]

    dashed = _bool(values.get("route_dashed"))
    drew_route = False
    for first, second, start, end in zip(points, points[1:], screen, screen[1:]):
        if _route_leg_broken(values, first[0], second[0]):
            continue
        clipped = _clip_segment_to_circle(start, end, float(cx), float(cy), clip_radius)
        if clipped is not None and _leg_bbox_visible(*clipped):
            (_dashed_line if dashed else _line)(canvas, clipped[0], clipped[1], GREEN, 2)
            drew_route = True
    if drew_route:
        record = getattr(canvas, "_record_feature", None)
        if callable(record):
            record("FLIGHT_PLAN_DASHED" if dashed else "FLIGHT_PLAN_SOLID")

    to_wp = values.get("route_to_wp")
    # JUDGMENT CALL: current_to_waypoint treated as a 0-based index into the
    # latitude/longitude arrays - the catalog carries no indexing metadata
    # for this array family at all (flagged in the module docstring and in
    # mcdu_bb36_toliss_paths.py's own "nd" comment). Confirm live.
    to_index = int(round(float(to_wp))) if _finite(to_wp) else (
        1 if _bool(values.get("route_active_leg_fallback")) and len(points) == 2 else -1
    )
    wpt_id = _icao(values.get("wpt_id"), 7)
    route_alt = values.get("route_alt") or ()

    for (source_index, _latitude, _longitude), (x, y) in zip(points, screen):
        if not _inside_circle(x, y, float(cx), float(cy), clip_radius):
            continue
        active = source_index == to_index
        colour = GREEN if active else WHITE
        canvas.colour(*colour)
        for offset_x, offset_y in ((0, -5), (5, 0), (0, 5), (-5, 0)):
            _block(canvas, x + offset_x, y + offset_y, 3)
        point_id = wpt_id if active and wpt_id else _route_id(values, source_index)
        if not point_id:
            continue
        label_x = int(round(_clamp(x - 60.0, float(X_SAFE_LEFT), float(X_SAFE_RIGHT - 150))))
        label_y = int(round(y)) - 30 if y > float(COMPASS_TOP) + 40.0 else int(round(y)) + 16
        label_y = max(COMPASS_TOP, min(HEIGHT - FONT_CELL_HEIGHT, label_y))
        waypoint_label = point_id
        distance = values.get("waypoint_distance")
        if active and _finite(distance) and float(distance) >= 0.0:
            waypoint_label += f" {_fmt(distance, 1)}NM"
        _text(
            canvas,
            _slot("nd active waypoint", label_x, label_y, 150, "left"),
            waypoint_label,
            GREEN if active else WHITE,
            BLACK,
        )
        try:
            altitude = float(route_alt[source_index])
        except (IndexError, TypeError, ValueError):
            altitude = float("nan")
        if _finite(altitude) and altitude > 0.0:
            alt_y = min(HEIGHT - FONT_CELL_HEIGHT, label_y + FONT_CELL_HEIGHT)
            _text(canvas, _slot("nd active alt", label_x, alt_y, 120, "left"),
                  _fmt(altitude, 0), CYAN, BLACK)


# ---------------------------------------------------------------------------
# ILS/VOR course + raw deviation, drawn as a rotated scale through the
# compass centre (a real Airbus ND convention, not a Boeing PFD-style
# vertical strip) - only when actually tuned (AirbusFBW/ILSonCapt).
# ---------------------------------------------------------------------------
def _draw_course_deviation(canvas: Any, values: Mapping[str, Any], cx: int, cy: int, radius: float) -> None:
    if not _bool(values.get("ils_on")):
        return
    course = values.get("ils_crs")
    heading = values.get("heading")
    if not (_finite(course) and _finite(heading)):
        return
    relative = _heading_delta(float(course), float(heading))
    radians = math.radians(relative)
    dx, dy = math.sin(radians), -math.cos(radians)
    half_span = radius * 0.85
    _line(canvas, (cx - dx * half_span, cy - dy * half_span),
          (cx + dx * half_span, cy + dy * half_span), WHITE, 2)

    perp_x, perp_y = dy, -dx
    base = radius * 0.42
    canvas.colour(*WHITE)
    for offset in (-2, -1, 1, 2):
        px = cx + dx * base + perp_x * offset * 18.0
        py = cy + dy * base + perp_y * offset * 18.0
        _block(canvas, px, py, 3)

    deviation = values.get("ils_loc")
    if _finite(deviation):
        d = _clamp(float(deviation), -1.0, 1.0)
        px = cx + dx * base + perp_x * d * 36.0
        py = cy + dy * base + perp_y * d * 36.0
        canvas.colour(*MAGENTA)
        _block(canvas, px, py, 6)


# ---------------------------------------------------------------------------
# EFIS VOR/ADF bearing pointers.  The selector datarefs are absolute
# 0=ADF/1=OFF/2=VOR positions.  ToLiss publishes magnetic bearings in paired
# arrays plus separate validity and station-ident outputs.  The captain's
# first selector drives the single needle; the second drives the double
# needle, matching the panel and the ToLiss tutorial screenshots.
# ---------------------------------------------------------------------------
_BEARING_ADF = 0
_BEARING_OFF = 1
_BEARING_VOR = 2


def _bearing_source(values: Mapping[str, Any], number: int):
    selector = values.get(f"bearing{number}_selector")
    if not _finite(selector):
        return None
    position = int(round(float(selector)))
    if position == _BEARING_VOR:
        return {
            "kind": "VOR",
            "bearing": values.get(f"vor{number}_bearing"),
            "valid": _bool(values.get(f"vor{number}_valid")),
            "ident": _icao(values.get(f"vor{number}_id"), 5),
            "dme": values.get(f"vor{number}_dme"),
            "colour": WHITE,
        }
    if position == _BEARING_ADF:
        return {
            "kind": "ADF",
            "bearing": values.get(f"adf{number}_bearing"),
            "valid": _bool(values.get(f"adf{number}_valid")),
            "ident": _icao(values.get(f"adf{number}_id"), 5),
            "dme": None,
            "colour": GREEN,
        }
    return None


def _draw_bearing_needle(
    canvas: Any,
    *,
    cx: float,
    cy: float,
    relative: float,
    radius: float,
    colour: Tuple[int, int, int],
    double: bool,
    arc: bool,
) -> None:
    if arc and abs(relative) > ARC_HALF_ANGLE + 2.0:
        return
    radians = math.radians(relative)
    dx, dy = math.sin(radians), -math.cos(radians)
    px, py = -dy, dx
    tip_distance = radius - 24.0
    tail_distance = 12.0 if arc else -(radius - 34.0)
    tip = (cx + dx * tip_distance, cy + dy * tip_distance)
    tail = (cx + dx * tail_distance, cy + dy * tail_distance)
    def shaft(first: Tuple[float, float], second: Tuple[float, float]) -> None:
        # Seven short solid pieces preserve the unmistakable full-diameter
        # needle while keeping arbitrary-angle updates within the BB35/BB36
        # native report budget.  The real ToLiss pointer is broken around
        # the aeroplane symbol, so a segmented shaft is also visually honest.
        sx, sy = second[0] - first[0], second[1] - first[1]
        length = math.hypot(sx, sy)
        if length < 1.0:
            return
        ux, uy = sx / length, sy / length
        count = 5
        dash_length = min(14.0, length / (count * 3.5))
        for index in range(count):
            centre = length * (index + 0.5) / count
            half = dash_length / 2.0
            _line(
                canvas,
                (first[0] + ux * (centre - half), first[1] + uy * (centre - half)),
                (first[0] + ux * (centre + half), first[1] + uy * (centre + half)),
                colour,
                2,
            )

    if double:
        for offset in (-4.0, 4.0):
            shaft(
                (tail[0] + px * offset, tail[1] + py * offset),
                (tip[0] + px * offset, tip[1] + py * offset),
            )
        wing = 16.0
        back = 20.0
        _line(canvas, tip, (tip[0] - dx * back + px * wing, tip[1] - dy * back + py * wing), colour, 2)
        _line(canvas, tip, (tip[0] - dx * back - px * wing, tip[1] - dy * back - py * wing), colour, 2)
    else:
        shaft(tail, tip)
        wing = 13.0
        back = 18.0
        _line(canvas, tip, (tip[0] - dx * back + px * wing, tip[1] - dy * back + py * wing), colour, 2)
        _line(canvas, tip, (tip[0] - dx * back - px * wing, tip[1] - dy * back - py * wing), colour, 2)


def _draw_bearing_sources(
    canvas: Any,
    values: Mapping[str, Any],
    mode: int,
    cx: int,
    cy: int,
    radius: float,
) -> None:
    # PLAN is north-up and, on the ToLiss/Airbus display, deliberately omits
    # the aircraft-relative VOR/ADF needles.  Source labels remain available
    # only in the modes where the bearing pointers themselves are meaningful.
    if mode == _ND_PLAN_MODE_INDEX:
        return
    heading = values.get("heading")
    if not _finite(heading):
        return
    label_slots = (
        (BEARING1_LABEL, BEARING1_ID, BEARING1_DME),
        (BEARING2_LABEL, BEARING2_ID, BEARING2_DME),
    )
    for number, slots in enumerate(label_slots, start=1):
        source = _bearing_source(values, number)
        if source is None:
            continue
        colour = source["colour"]
        _text(canvas, slots[0], f"{source['kind']}{number}", WHITE)
        _text(canvas, slots[1], source["ident"] if source["valid"] and source["ident"] else "---", colour)
        if source["kind"] == "VOR" and source["valid"] and _finite(source["dme"]):
            _text(canvas, slots[2], f"{float(source['dme']):.1f}NM", GREEN)
        if not (source["valid"] and _finite(source["bearing"])):
            continue
        relative = _heading_delta(float(source["bearing"]), float(heading))
        _draw_bearing_needle(
            canvas,
            cx=float(cx),
            cy=float(cy),
            relative=relative,
            radius=radius,
            colour=colour,
            double=number == 2,
            arc=mode == _ND_ARC_MODE_INDEX,
        )
        record = getattr(canvas, "_record_feature", None)
        if callable(record):
            record("BEARING_DOUBLE" if number == 2 else "BEARING_SINGLE")


# ---------------------------------------------------------------------------
# Refined Airbus geometries.  These stay local because nd_renderer.py's
# legacy arc primitive has a hard-coded Boeing aircraft anchor.
# ---------------------------------------------------------------------------
TOLISS_ARC_CENTER_X = 320
TOLISS_ARC_CENTER_Y = 432


def _toliss_point(cx: float, cy: float, angle: float, radius: float) -> Tuple[float, float]:
    radians = math.radians(angle)
    return cx + radius * math.sin(radians), cy - radius * math.cos(radians)


def _toliss_curve(
    canvas: Any,
    cx: float,
    cy: float,
    radius: float,
    start: float,
    end: float,
    colour: Tuple[int, int, int],
    thickness: int = 2,
    dashed: bool = False,
) -> None:
    step = max(0.35, math.degrees(ARC_SEGMENT / max(1.0, radius)))
    canvas.colour(*colour)
    angle = float(start)
    index = 0
    while angle <= end + 1e-6:
        if not dashed or index % 5 < 3:
            x, y = _toliss_point(cx, cy, angle, radius)
            if 0.0 <= x < WIDTH and 0.0 <= y < HEIGHT:
                _block(canvas, x, y, thickness)
        angle += step
        index += 1


def _toliss_range_label(
    canvas: Any,
    x: float,
    y: float,
    value: float,
    colour: Tuple[int, int, int] = CYAN,
) -> None:
    label = f"{value:g}"
    left = int(round(_clamp(x - 22.0, X_SAFE_LEFT, X_SAFE_RIGHT - 48)))
    top = int(round(_clamp(y - 14.0, COMPASS_TOP, HEIGHT - FONT_CELL_HEIGHT)))
    _text(canvas, _slot("nd range ring", left, top, 48, "center"), label, colour)


def _draw_toliss_arc_compass(canvas: Any, values: Mapping[str, Any]) -> None:
    _toliss_curve(
        canvas, TOLISS_ARC_CENTER_X, TOLISS_ARC_CENTER_Y, ARC_RADIUS,
        -ARC_HALF_ANGLE, ARC_HALF_ANGLE, WHITE, 3,
    )
    heading = (
        float(values["heading"]) % 360.0
        if _finite(values.get("heading")) else 0.0
    )
    first = int((heading - ARC_HALF_ANGLE) // 5) * 5
    for tick in range(first, int(heading + ARC_HALF_ANGLE) + 6, 5):
        delta = _heading_delta(float(tick), heading)
        if abs(delta) > ARC_HALF_ANGLE:
            continue
        length = 17 if tick % 10 == 0 else 8
        _line(
            canvas,
            _toliss_point(TOLISS_ARC_CENTER_X, TOLISS_ARC_CENTER_Y, delta, ARC_RADIUS - length),
            _toliss_point(TOLISS_ARC_CENTER_X, TOLISS_ARC_CENTER_Y, delta, ARC_RADIUS),
            WHITE,
            2,
        )
        if tick % 10 == 0:
            x, y = _toliss_point(
                TOLISS_ARC_CENTER_X, TOLISS_ARC_CENTER_Y, delta, ARC_RADIUS - 34,
            )
            left = int(round(_clamp(x - 19.0, X_SAFE_LEFT, X_SAFE_RIGHT - 42)))
            top = int(round(_clamp(y - 14.0, COMPASS_TOP, HEIGHT - FONT_CELL_HEIGHT)))
            _text(
                canvas, _slot("nd arc heading", left, top, 42, "center"),
                _airbus_heading_label(float(tick % 360)), WHITE,
            )


def _draw_toliss_arc_ranges(
    canvas: Any,
    values: Mapping[str, Any],
    colour: Tuple[int, int, int] = DIM_GREY,
) -> None:
    selected = _range_nm(values)
    for fraction in (1.0 / 3.0, 2.0 / 3.0):
        radius = ARC_RADIUS * fraction
        _toliss_curve(
            canvas, TOLISS_ARC_CENTER_X, TOLISS_ARC_CENTER_Y, radius,
            -ARC_HALF_ANGLE, ARC_HALF_ANGLE, colour, 2, True,
        )
        label_colour = RED if colour == RED else CYAN
        for side in (-52.0, 52.0):
            x, y = _toliss_point(
                TOLISS_ARC_CENTER_X, TOLISS_ARC_CENTER_Y, side, radius,
            )
            _toliss_range_label(canvas, x, y, selected * fraction, label_colour)


def _draw_plan_route(canvas: Any, values: Mapping[str, Any], px_per_nm: float) -> None:
    points = _route_points(values)
    to_wp = values.get("route_to_wp")
    to_index = int(round(float(to_wp))) if _finite(to_wp) else -1
    reference = next((point for point in points if point[0] == to_index), None)
    if reference is None and _finite(values.get("own_lat")) and _finite(values.get("own_lon")):
        reference = (-1, float(values["own_lat"]), float(values["own_lon"]))
    if reference is None:
        return

    ref_lat, ref_lon = reference[1], reference[2]
    screen = [
        (
            source_index,
            *_project(
                latitude, longitude, ref_lat, ref_lon, 0.0,
                PLAN_CENTER_X, PLAN_CENTER_Y, px_per_nm,
            ),
        )
        for source_index, latitude, longitude in points
    ]
    dashed = _bool(values.get("route_dashed"))
    drew_route = False
    for first, second in zip(screen, screen[1:]):
        if _route_leg_broken(values, first[0], second[0]):
            continue
        start, end = (first[1], first[2]), (second[1], second[2])
        clipped = _clip_segment_to_circle(
            start, end, PLAN_CENTER_X, PLAN_CENTER_Y, PLAN_RADIUS,
        )
        if clipped is not None and _leg_bbox_visible(*clipped):
            (_dashed_line if dashed else _line)(canvas, clipped[0], clipped[1], GREEN, 2)
            drew_route = True
    if drew_route:
        record = getattr(canvas, "_record_feature", None)
        if callable(record):
            record("FLIGHT_PLAN_DASHED" if dashed else "FLIGHT_PLAN_SOLID")
    for source_index, x, y in screen:
        if not _inside_circle(x, y, PLAN_CENTER_X, PLAN_CENTER_Y, PLAN_RADIUS):
            continue
        active = source_index == to_index
        colour = GREEN if active else WHITE
        canvas.colour(*colour)
        for dx, dy in ((0, -5), (5, 0), (0, 5), (-5, 0)):
            _block(canvas, x + dx, y + dy, 3)
        point_id = (
            _icao(values.get("wpt_id"), 7)
            if active and values.get("wpt_id")
            else _route_id(values, source_index)
        )
        if point_id:
            left = int(round(_clamp(x + 10, X_SAFE_LEFT, X_SAFE_RIGHT - 150)))
            top = int(round(_clamp(y - 25, COMPASS_TOP, HEIGHT - FONT_CELL_HEIGHT)))
            distance = values.get("waypoint_distance")
            label = point_id
            if active and _finite(distance) and float(distance) >= 0.0:
                label += f" {_fmt(distance, 1)}NM"
            _text(
                canvas, _slot("nd plan waypoint", left, top, 150, "left"),
                label, GREEN if active else WHITE,
            )

    if _finite(values.get("own_lat")) and _finite(values.get("own_lon")):
        aircraft_x, aircraft_y = _project(
            float(values["own_lat"]), float(values["own_lon"]),
            ref_lat, ref_lon, 0.0, PLAN_CENTER_X, PLAN_CENTER_Y, px_per_nm,
        )
        if 20 <= aircraft_x <= WIDTH - 20 and 20 <= aircraft_y <= HEIGHT - 20:
            _draw_aircraft_symbol(canvas, int(round(aircraft_x)), int(round(aircraft_y)))


def _draw_toliss_plan(canvas: Any, values: Mapping[str, Any]) -> None:
    selected = _range_nm(values)
    for fraction in (0.5, 1.0):
        radius = PLAN_RADIUS * fraction
        _toliss_curve(
            canvas, PLAN_CENTER_X, PLAN_CENTER_Y, radius,
            -180.0, 180.0, WHITE if fraction == 1.0 else DIM_GREY,
            2, fraction < 1.0,
        )
        _toliss_range_label(
            canvas,
            PLAN_CENTER_X + radius * 0.70,
            PLAN_CENTER_Y - radius * 0.70,
            selected * fraction,
        )
    for label, angle in (("N", 0.0), ("E", 90.0), ("S", 180.0), ("W", -90.0)):
        x, y = _toliss_point(PLAN_CENTER_X, PLAN_CENTER_Y, angle, PLAN_RADIUS - 17)
        left = int(round(_clamp(x - 18.0, X_SAFE_LEFT, X_SAFE_RIGHT - 40)))
        top = int(round(_clamp(y - 14.0, COMPASS_TOP, HEIGHT - FONT_CELL_HEIGHT)))
        _text(canvas, _slot("nd plan cardinal", left, top, 40, "center"), label, WHITE)
    _draw_plan_route(
        canvas, values, PLAN_RADIUS / selected if selected > 0.0 else 0.0,
    )


def _gps_message(values: Mapping[str, Any]) -> Tuple[str, Tuple[int, int, int]] | None:
    raw = values.get("gps_primary_message")
    if not _finite(raw):
        return None
    state = int(round(float(raw)))
    if state == 2:
        return "GPS PRIMARY LOST", AMBER
    if state == 1:
        return "GPS PRIMARY", GREEN
    return None


def _draw_gps_message(canvas: Any, values: Mapping[str, Any]) -> None:
    message = _gps_message(values)
    if message is None:
        return
    text, colour = message
    # Leave a true inset around the native 29px text cell. Drawing text on
    # the old 29px-high border made its opaque black cell erase the top and
    # bottom rules through the middle of the annunciation.
    x, y, width, height = 175, 443, 290, 35
    canvas.colour(*WHITE)
    canvas.fill(x, y, width, 2)
    canvas.fill(x, y + height - 2, width, 2)
    canvas.fill(x, y, 2, height)
    canvas.fill(x + width - 2, y, 2, height)
    _text(
        canvas,
        _slot("nd gps message", x + 6, y + 3, width - 12, "center"),
        text,
        colour,
    )


def _map_available(values: Mapping[str, Any]) -> bool:
    explicit = values.get("map_available")
    if _finite(explicit):
        return _bool(explicit)
    return all(_finite(values.get(key)) for key in ("heading", "own_lat", "own_lon"))


def _draw_map_not_available(canvas: Any, values: Mapping[str, Any]) -> None:
    _toliss_curve(
        canvas, TOLISS_ARC_CENTER_X, TOLISS_ARC_CENTER_Y, ARC_RADIUS,
        -ARC_HALF_ANGLE, ARC_HALF_ANGLE, RED, 3,
    )
    _draw_toliss_arc_ranges(canvas, values, RED)
    _text(canvas, _slot("nd invalid heading", 270, 101, 100, "center"), "HDG", RED)
    _text(canvas, _slot("nd map unavailable", 202, 164, 236, "center"), "MAP NOT AVAIL", RED)


# ---------------------------------------------------------------------------
# Frame assembly + live diff-engine wrapper.
# ---------------------------------------------------------------------------
def draw_toliss_nd_frame(canvas: Any, values: Mapping[str, Any]) -> None:
    canvas.colour(*BLACK)
    canvas.fill(0, 0, WIDTH, HEIGHT)

    _draw_header(canvas, values)

    if not _map_available(values):
        _draw_map_not_available(canvas, values)
        _draw_gps_message(canvas, values)
        return

    mode = _mode_index(values)
    range_nm = _range_nm(values)
    if mode == _ND_ARC_MODE_INDEX:
        px_per_nm = ARC_RADIUS / range_nm if range_nm > 0.0 else 0.0
        _draw_toliss_arc_compass(canvas, values)
        _draw_toliss_arc_ranges(canvas, values)
        _draw_route(
            canvas, values, TOLISS_ARC_CENTER_X, TOLISS_ARC_CENTER_Y,
            px_per_nm, ARC_RADIUS,
        )
        _draw_bearing_sources(
            canvas, values, mode, TOLISS_ARC_CENTER_X, TOLISS_ARC_CENTER_Y,
            ARC_RADIUS,
        )
        _draw_aircraft_symbol(canvas, TOLISS_ARC_CENTER_X, TOLISS_ARC_CENTER_Y)
    elif mode == _ND_PLAN_MODE_INDEX:
        _draw_toliss_plan(canvas, values)
    else:
        px_per_nm = ROSE_RADIUS / range_nm if range_nm > 0.0 else 0.0
        _draw_rose_compass(canvas, values)
        _draw_range_ring(canvas, values, False)
        # The flight plan belongs to ROSE NAV, ARC and PLAN.  Dedicated ROSE
        # ILS/VOR modes carry their course/deviation presentation instead.
        if mode == 2:
            _draw_route(
                canvas, values, ROSE_CENTER_X, ROSE_CENTER_Y, px_per_nm,
                ROSE_RADIUS,
            )
        # A course/deviation rose belongs only to the dedicated ROSE ILS and
        # ROSE VOR selector positions.  Suppressing it in ROSE NAV also avoids
        # spending a large block of USB reports on geometry the real mode does
        # not show.
        if mode in (0, 1):
            _draw_course_deviation(
                canvas, values, ROSE_CENTER_X, ROSE_CENTER_Y, ROSE_RADIUS,
            )
        _draw_bearing_sources(
            canvas, values, mode, ROSE_CENTER_X, ROSE_CENTER_Y, ROSE_RADIUS,
        )
        _draw_aircraft_symbol(canvas, ROSE_CENTER_X, ROSE_CENTER_Y)

    _draw_active_overlays(canvas, values)
    _draw_gps_message(canvas, values)

    # No traffic overlay: no TCAS position dataref exists anywhere in the
    # catalog for ToLiss (searched exhaustively) - shipping without one
    # rather than fabricating symbols, per the plan's own explicit decision.


def _steady(values: Mapping[str, Any]) -> Mapping[str, Any]:
    steady = dict(values)
    for name, step in _ND_QUANTISED_STEPS.items():
        value = steady.get(name)
        if _finite(value):
            steady[name] = round(float(value) / step) * step
    return steady


def draw_live_toliss_nd(canvas: Any, values: Mapping[str, Any]) -> bool:
    """Emit changed regions for one ND frame; return True if it drew."""
    steady = _steady(values)
    recorder = _OpRecorder()
    draw_toliss_nd_frame(recorder, steady)
    operations = recorder.ops

    state = getattr(canvas, "_muslimsim_toliss_nd_state", None)
    now = time.monotonic()
    mode = _mode_index(steady)
    map_available = _map_available(steady)
    state_mode = state[3] if state is not None else None
    state_map_available = state[4] if state is not None and len(state) > 4 else None
    stale = (
        state is None
        or state_mode != mode
        or state_map_available != map_available
        or now - state[1] > TOLISS_ND_FULL_REPAINT_SECONDS
        or state[2] >= TOLISS_ND_FULL_REPAINT_FRAMES
    )
    if stale:
        boxes = [(0, 0, WIDTH, HEIGHT)]
        sequence = 0
    else:
        boxes = _dirty_boxes(operations, state[0])
        sequence = state[2] + 1
    _emit_frame(canvas, operations, boxes)
    try:
        canvas._muslimsim_toliss_nd_state = (
            operations, now, sequence, mode, map_available,
        )
    except AttributeError:
        pass
    return bool(boxes)


def invalidate(canvas: Any) -> None:
    try:
        del canvas._muslimsim_toliss_nd_state
    except (AttributeError, TypeError):
        pass


# ---------------------------------------------------------------------------
# Value-key contract - documented for bridge/final.py's _toliss_nd_values()
# translator, matching TOLISS_PFD_VALUE_KEYS'/TOLISS_SYSTEM_PAGE_VALUE_KEYS'
# own documentation role.
# ---------------------------------------------------------------------------
TOLISS_ND_VALUE_KEYS: Tuple[str, ...] = (
    "heading", "own_lat", "own_lon", "mode", "range_index",
    "map_available", "heading_valid", "gps_primary_message",
    "ground_speed", "true_air_speed", "wind_available",
    "wind_direction", "wind_speed", "waypoint_distance", "waypoint_course",
    "route_lat", "route_lon", "route_alt", "route_ids", "route_breaks", "route_no_wp", "route_to_wp", "route_dashed", "route_active_leg_fallback",
    "wpt_id", "departure_icao", "destination_icao",
    "bearing1_selector", "bearing2_selector",
    "vor1_bearing", "vor2_bearing", "adf1_bearing", "adf2_bearing",
    "vor1_valid", "vor2_valid", "adf1_valid", "adf2_valid",
    "vor1_id", "vor2_id", "adf1_id", "adf2_id", "vor1_dme", "vor2_dme",
    "ils_loc", "ils_crs", "ils_on",
    "show_arpt", "show_cstr", "show_vord", "show_wpt", "show_ndb",
    "show_wxr", "show_terr",
)


class _BoundsCanvas:
    def colour(self, _red: int, _green: int, _blue: int) -> None:
        return None

    def fill(self, x: int, y: int, width: int, height: int) -> None:
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > WIDTH or y + height > HEIGHT:
            raise TolissNdLayoutError(f"fill outside display: {(x, y, width, height)}")

    def text(self, x: int, y: int, value: str, _foreground, _background, _font_id) -> None:
        if x < 0 or y < 0 or x + len(value) * FONT_CELL_WIDTH > WIDTH or y + FONT_CELL_HEIGHT > HEIGHT:
            raise TolissNdLayoutError(f"text outside display: {(x, y, value)!r}")


class _CaptureCanvas(_BoundsCanvas):
    """Bounds-checking canvas that also records every text run drawn.

    TextSlot.position_for silently drops (no exception, no canvas.text call
    at all) any value too wide for its slot - see pfp_renderer_toliss.py's
    own _CaptureCanvas docstring for the bug class this specifically exists
    to catch (found for real during the PFD step of this same plan pass).
    """

    def __init__(self) -> None:
        super().__init__()
        self.texts: list = []
        self.font_ids: list = []
        self.features: list = []

    def _record_logical_text(self, value: str) -> None:
        self.texts.append(value)

    def _record_feature(self, value: str) -> None:
        self.features.append(value)

    def text(self, x: int, y: int, value: str, foreground, background, font_id) -> None:
        super().text(x, y, value, foreground, background, font_id)
        self.font_ids.append(int(font_id))


def assert_layout_contract() -> None:
    for slot in _ALL_FIXED_SLOTS:
        if (
            slot.rect.x < X_SAFE_LEFT or slot.rect.y < 0
            or slot.rect.right > X_SAFE_RIGHT
            or slot.rect.bottom > COMPASS_TOP
            or slot.capacity < 1
        ):
            raise TolissNdLayoutError(f"Unsafe ND slot: {slot.name}")

    for i, a in enumerate(_ALL_FIXED_SLOTS):
        for b in _ALL_FIXED_SLOTS[i + 1:]:
            if a.rect.intersects(b.rect):
                raise TolissNdLayoutError(f"ND slots overlap: {a.name!r} / {b.name!r}")

    if ROSE_CENTER_Y - ROSE_RADIUS < COMPASS_TOP or ROSE_CENTER_Y + ROSE_RADIUS > HEIGHT:
        raise TolissNdLayoutError("ROSE compass does not fit the display")
    if ROSE_CENTER_X - ROSE_RADIUS < X_SAFE_LEFT or ROSE_CENTER_X + ROSE_RADIUS > X_SAFE_RIGHT:
        raise TolissNdLayoutError("ROSE compass left the bezel-safe strip")
    if TOLISS_ARC_CENTER_Y - ARC_RADIUS < COMPASS_TOP or TOLISS_ARC_CENTER_Y > HEIGHT:
        raise TolissNdLayoutError("ARC compass does not fit the display")
    arc_half_width = ARC_RADIUS * math.sin(math.radians(ARC_HALF_ANGLE))
    if (
        TOLISS_ARC_CENTER_X - arc_half_width < X_SAFE_LEFT
        or TOLISS_ARC_CENTER_X + arc_half_width > X_SAFE_RIGHT
    ):
        raise TolissNdLayoutError("ARC compass left the bezel-safe strip")
    if (
        PLAN_CENTER_X - PLAN_RADIUS < X_SAFE_LEFT
        or PLAN_CENTER_X + PLAN_RADIUS > X_SAFE_RIGHT
        or PLAN_CENTER_Y - PLAN_RADIUS < COMPASS_TOP
        or PLAN_CENTER_Y + PLAN_RADIUS > HEIGHT
    ):
        raise TolissNdLayoutError("PLAN circles do not fit the display")

    normal_route = {
        "route_lat": [32.90, 32.89, 32.71, 33.60],
        "route_lon": [-97.04, -97.05, -97.05, -98.90],
        "route_alt": [0, 12000, 18000, 24000],
        "route_no_wp": 4.0, "route_to_wp": 1.0,
        "route_dashed": 0.0,
        "wpt_id": "JPOOL", "departure_icao": "KDFW", "destination_icao": "KJFK",
    }
    normal = {
        "heading": 268.0, "own_lat": 32.88, "own_lon": -97.03,
        "mode": 2.0, "range_index": 1.0,
        "map_available": 1.0, "heading_valid": 1.0,
        "gps_primary_message": 1.0,
        "ground_speed": 154.0, "true_air_speed": 162.0,
        "wind_available": 1.0, "wind_direction": 310.0, "wind_speed": 18.0,
        "waypoint_distance": 12.4,
        "ils_loc": 0.2, "ils_crs": 250.0, "ils_on": 1.0,
        "bearing1_selector": 2.0, "bearing2_selector": 2.0,
        "vor1_bearing": 250.0, "vor2_bearing": 300.0,
        "adf1_bearing": 90.0, "adf2_bearing": 90.0,
        "vor1_valid": 1.0, "vor2_valid": 1.0,
        "adf1_valid": 0.0, "adf2_valid": 0.0,
        "vor1_id": "CVE", "vor2_id": "TTT",
        "adf1_id": "", "adf2_id": "",
        "vor1_dme": 6.7, "vor2_dme": 1.1,
        "show_arpt": 1.0, "show_cstr": 0.0, "show_vord": 1.0,
        "show_wpt": 1.0, "show_ndb": 0.0, "show_wxr": 1.0, "show_terr": 0.0,
        **normal_route,
    }
    variants = (
        normal,
        {},
        {**normal, "mode": 3.0},
        {**normal, "mode": 4.0},
        {**normal, "map_available": 0.0, "gps_primary_message": 2.0},
        {**normal, "heading": 0.5, "route_to_wp": 99.0},
        {**normal, "ils_on": 0.0},
        {**normal, "wpt_id": "", "route_lat": [], "route_lon": []},
        {**normal, "bearing1_selector": 0.0, "adf1_valid": 1.0, "adf1_id": "NDB"},
        {**normal, "bearing1_selector": 1.0, "bearing2_selector": 1.0},
    )
    for values in variants:
        canvas = _BoundsCanvas()
        draw_toliss_nd_frame(canvas, values)
        draw_live_toliss_nd(canvas, values)
        draw_live_toliss_nd(canvas, values)

    for mode, label in ((2.0, "NAV"), (3.0, "ARC"), (4.0, "PLAN")):
        capture = _CaptureCanvas()
        draw_toliss_nd_frame(capture, {**normal, "mode": mode})
        required = {
            "GS", "154", "TAS", "162", "PPOS", label,
            "20NM", "JPOOL 12.4NM",
        }
        missing = required - set(capture.texts)
        if missing:
            raise TolissNdLayoutError(
                f"ND {label} required labels did not render: {sorted(missing)}"
            )
        if set(capture.font_ids) != {PFD_NUMBER_FONT_ID}:
            raise TolissNdLayoutError("ToLiss ND escaped compact slot-3 typography")

    rose_capture = _CaptureCanvas()
    draw_toliss_nd_frame(rose_capture, {**normal, "mode": 2.0})
    if not {"FLIGHT_PLAN_SOLID", "BEARING_SINGLE", "BEARING_DOUBLE"}.issubset(
        set(rose_capture.features)
    ):
        raise TolissNdLayoutError("ND NAV lost its flight plan or bearing pointers")
    if not {"VOR1", "CVE", "6.7NM", "VOR2", "TTT", "1.1NM"}.issubset(
        set(rose_capture.texts)
    ):
        raise TolissNdLayoutError("ND tuned VOR identification did not render")

    dashed_capture = _CaptureCanvas()
    draw_toliss_nd_frame(dashed_capture, {**normal, "mode": 3.0, "route_dashed": 1.0})
    if "FLIGHT_PLAN_DASHED" not in dashed_capture.features:
        raise TolissNdLayoutError("ND ignored ToLiss FlightPlanDashed")

    plan_capture = _CaptureCanvas()
    draw_toliss_nd_frame(plan_capture, {**normal, "mode": 4.0})
    if "FLIGHT_PLAN_SOLID" not in plan_capture.features:
        raise TolissNdLayoutError("ND PLAN did not render the loaded flight plan")
    if {"BEARING_SINGLE", "BEARING_DOUBLE"}.intersection(plan_capture.features):
        raise TolissNdLayoutError("ND PLAN incorrectly rendered heading-relative bearing needles")

    invalid_capture = _CaptureCanvas()
    draw_toliss_nd_frame(
        invalid_capture,
        {**normal, "map_available": 0.0, "gps_primary_message": 2.0},
    )
    required_invalid = {"HDG", "MAP NOT AVAIL", "GPS PRIMARY LOST"}
    missing = required_invalid - set(invalid_capture.texts)
    if missing:
        raise TolissNdLayoutError(
            f"ND invalid presentation is incomplete: {sorted(missing)}"
        )


__all__ = (
    "TOLISS_ND_VALUE_KEYS",
    "TolissNdLayoutError",
    "assert_layout_contract",
    "draw_live_toliss_nd",
    "draw_toliss_nd_frame",
    "invalidate",
)
