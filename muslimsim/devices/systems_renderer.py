"""Code-native 640x480 Boeing engine and hydraulic display pages.

The BB35 and BB36 controllers are command displays, not bitmap framebuffers.
Every mark on these pages is therefore made from native rectangles and the
installed 17x29 cockpit font.  No image is loaded or uploaded at runtime.

The renderer follows the PFD/ND final-image differential contract: a complete
page is recorded in memory, only changed pixel regions are emitted, and an
occasional recovery frame repairs a missed USB region.  It opens no hardware
and never writes simulator state.
"""

from __future__ import annotations

import math
import time
from typing import Any, Mapping, Sequence, Tuple

from muslimsim.devices.pfp_renderer import (
    AMBER,
    BLACK,
    CYAN,
    FONT_CELL_HEIGHT,
    FONT_CELL_WIDTH,
    GREEN,
    HEIGHT,
    MAGENTA,
    RED,
    TAPE_GREY,
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


DEEP_NAVY = (6, 7, 21)
SOFT_GREY = (74, 82, 104)
DIM_CYAN = (0, 91, 118)
ELECTRIC_BLUE = (39, 143, 255)
LIME = (77, 255, 134)
SYSTEM_FULL_REPAINT_FRAMES = 600
SYSTEM_SAFE_LEFT = 34
SYSTEM_SAFE_RIGHT = 606

SYSTEM_PAGE_VALUE_KEYS = {
    "eng_pri": (
        "tat", "thrust_mode", "target_n1_0", "target_n1_1",
        "eng_n1_0", "eng_n1_1", "eng_egt_0", "eng_egt_1",
        "eng_ff_0", "eng_ff_1", "eng_oil_pressure_0",
        "eng_oil_pressure_1", "eng_running_0", "eng_running_1",
        "eng_low_oil_0", "eng_low_oil_1", "fuel_total",
    ),
    "mfd": (
        "eng_n2_0", "eng_n2_1", "eng_ff_0", "eng_ff_1",
        "eng_oil_pressure_0", "eng_oil_pressure_1",
        "eng_oil_temp_0", "eng_oil_temp_1", "eng_oil_qty_0",
        "eng_oil_qty_1", "eng_vibration_0", "eng_vibration_1",
    ),
    "hyd": (
        "hyd_qty_a", "hyd_qty_b", "hyd_press_a", "hyd_press_b",
        "brake_temp_lo", "brake_temp_li", "brake_temp_ri",
        "brake_temp_ro", "aileron_left", "aileron_right",
        "spoiler_left", "spoiler_right", "elevator_left",
        "elevator_right", "rudder", "flap_ratio", "speedbrake_ratio",
        "control_roll", "control_pitch", "control_yaw",
        "left_brake_ratio", "right_brake_ratio",
    ),
}


class SystemsLayoutError(RuntimeError):
    """A systems page primitive left the physical LCD."""


def _text(
    canvas: Any,
    x: int,
    y: int,
    value: str,
    colour: Tuple[int, int, int] = WHITE,
    width_cells: int | None = None,
    align: str = "left",
    background: Tuple[int, int, int] = DEEP_NAVY,
) -> None:
    value = str(value)
    cells = width_cells if width_cells is not None else max(1, len(value))
    _draw_text(
        canvas,
        _slot("systems text", int(x), int(y), int(cells) * FONT_CELL_WIDTH, align),
        value[:cells], colour, background,
    )


def _center(canvas: Any, x: int, y: int, value: str,
            colour: Tuple[int, int, int] = WHITE, cells: int | None = None,
            background: Tuple[int, int, int] = DEEP_NAVY) -> None:
    value = str(value)
    width = cells if cells is not None else max(1, len(value))
    _text(canvas, int(x - width * FONT_CELL_WIDTH / 2), y, value,
          colour, width, "center", background)


def _fill(canvas: Any, x: int, y: int, w: int, h: int,
          colour: Tuple[int, int, int]) -> None:
    canvas.colour(*colour)
    canvas.fill(int(x), int(y), max(1, int(w)), max(1, int(h)))


def _outline(canvas: Any, x: int, y: int, w: int, h: int,
             colour: Tuple[int, int, int] = WHITE, thickness: int = 2) -> None:
    _fill(canvas, x, y, w, thickness, colour)
    _fill(canvas, x, y + h - thickness, w, thickness, colour)
    _fill(canvas, x, y, thickness, h, colour)
    _fill(canvas, x + w - thickness, y, thickness, h, colour)


def _line(canvas: Any, x0: float, y0: float, x1: float, y1: float,
          colour: Tuple[int, int, int] = WHITE, thickness: int = 2,
          dashed: bool = False) -> None:
    dx, dy = x1 - x0, y1 - y0
    steps = max(1, int(max(abs(dx), abs(dy)) / 2.0))
    canvas.colour(*colour)
    for index in range(steps + 1):
        if dashed and index % 4 in (2, 3):
            continue
        fraction = index / steps
        x = int(round(x0 + dx * fraction))
        y = int(round(y0 + dy * fraction))
        if 0 <= x < WIDTH - thickness and 0 <= y < HEIGHT - thickness:
            canvas.fill(x, y, thickness, thickness)


def _arc(
    canvas: Any,
    cx: int,
    cy: int,
    radius: int,
    start_deg: float,
    end_deg: float,
    colour: Tuple[int, int, int],
    thickness: int = 3,
    fraction: float = 1.0,
    dashed: bool = False,
) -> None:
    fraction = _clamp(float(fraction), 0.0, 1.0)
    stop = start_deg + (end_deg - start_deg) * fraction
    count = max(2, int(abs(stop - start_deg) * max(radius, 1) / 125.0))
    canvas.colour(*colour)
    for index in range(count + 1):
        if dashed and index % 5 in (3, 4):
            continue
        angle = math.radians(start_deg + (stop - start_deg) * index / count)
        x = int(round(cx + radius * math.cos(angle)))
        y = int(round(cy + radius * math.sin(angle)))
        if 0 <= x < WIDTH - thickness and 0 <= y < HEIGHT - thickness:
            canvas.fill(x, y, thickness, thickness)


def _diamond(canvas: Any, x: int, y: int, radius: int,
             colour: Tuple[int, int, int], filled: bool = False) -> None:
    if filled:
        for offset in range(-radius, radius + 1, 2):
            half = radius - abs(offset)
            _fill(canvas, x - half, y + offset, max(2, half * 2 + 1), 2, colour)
    else:
        _line(canvas, x, y - radius, x + radius, y, colour, 2)
        _line(canvas, x + radius, y, x, y + radius, colour, 2)
        _line(canvas, x, y + radius, x - radius, y, colour, 2)
        _line(canvas, x - radius, y, x, y - radius, colour, 2)


def _value(value: Any, decimals: int = 0, fallback: str = "---") -> str:
    if not _finite(value):
        return fallback
    if decimals <= 0:
        return str(int(round(float(value))))
    return f"{float(value):.{decimals}f}"


def _engine_arc(
    canvas: Any,
    cx: int,
    cy: int,
    value: Any,
    maximum: float,
    label: str,
    warning_fraction: float = 0.90,
    decimals: int = 1,
    radius: int = 58,
) -> None:
    start, end = 140.0, 400.0
    _arc(canvas, cx, cy, radius, start, end, SOFT_GREY, 3)
    for tick in range(0, 11):
        angle = math.radians(start + (end - start) * tick / 10.0)
        inner = radius - (10 if tick % 5 == 0 else 6)
        _line(
            canvas,
            cx + inner * math.cos(angle), cy + inner * math.sin(angle),
            cx + radius * math.cos(angle), cy + radius * math.sin(angle),
            WHITE, 2,
        )
    fraction = _clamp(float(value) / maximum, 0.0, 1.0) if _finite(value) else 0.0
    colour = RED if fraction >= 0.98 else (AMBER if fraction >= warning_fraction else LIME)
    _arc(canvas, cx, cy, radius, start, end, colour, 4, fraction)
    if _finite(value):
        angle = math.radians(start + (end - start) * fraction)
        _line(canvas, cx, cy, cx + (radius - 8) * math.cos(angle),
              cy + (radius - 8) * math.sin(angle), WHITE, 3)
    _center(canvas, cx, cy - 18, _value(value, decimals), WHITE, 6)
    _center(canvas, cx, cy + 17, label, CYAN, max(3, len(label)))


def _header(canvas: Any, title: str, accent: Tuple[int, int, int]) -> None:
    _fill(canvas, 0, 0, WIDTH, HEIGHT, DEEP_NAVY)
    _fill(canvas, 0, 0, WIDTH, 4, accent)
    _fill(canvas, 0, 36, WIDTH, 2, DIM_CYAN)
    # The command canvas is 640 pixels wide, but the BB35/BB36 bezel hides a
    # small strip at both sides.  Keep all header glyphs inside the measured
    # safe area instead of relying on the logical edge of the LCD.
    _text(
        canvas,
        SYSTEM_SAFE_LEFT,
        6,
        title,
        accent,
        min(20, max(8, len(title))),
    )
    _text(
        canvas,
        SYSTEM_SAFE_RIGHT - 9 * FONT_CELL_WIDTH,
        6,
        "MUSLIMSIM",
        SOFT_GREY,
        9,
        "right",
    )


def _draw_eng_pri(canvas: Any, values: Mapping[str, Any]) -> None:
    """Futuristic primary-engine page, still organized like the aircraft."""
    _header(canvas, "ENG PRI", ELECTRIC_BLUE)
    tat = values.get("tat")
    _text(canvas, 18, 43, "TAT", CYAN, 3)
    _text(canvas, 70, 43, (_value(tat, 0) + " C") if _finite(tat) else "---", WHITE, 5)
    raw_mode = values.get("thrust_mode")
    if _finite(raw_mode):
        mode = {1: "TO", 2: "R-TO", 3: "CLB", 4: "MCT", 5: "CRZ", 6: "GA"}.get(
            int(round(float(raw_mode))), "THR"
        )
    else:
        mode = "THRUST"
    _center(canvas, 320, 43, mode, GREEN, 6)
    _text(canvas, 520, 43, "FUEL", CYAN, 4)
    fuel = values.get("fuel_total")
    _text(canvas, 520, 70, _value(fuel, 0), WHITE, 6)

    # Symmetric luminous engine pods.  The nested rings and accent rails are
    # intentionally more modern than the photographed legacy page while the
    # information hierarchy remains immediately Boeing-readable.
    for index, cx in ((0, 180), (1, 460)):
        _outline(canvas, cx - 126, 96, 252, 324, DIM_CYAN, 2)
        _fill(canvas, cx - 126, 96, 252, 5, ELECTRIC_BLUE)
        _center(canvas, cx, 103, f"ENGINE {index + 1}", CYAN, 8)
        target = values.get(f"target_n1_{index}")
        _text(canvas, cx - 102, 133, "REF", SOFT_GREY, 3)
        _text(canvas, cx - 47, 133, _value(target, 1), GREEN, 6)

        _engine_arc(canvas, cx, 223, values.get(f"eng_n1_{index}"), 110.0,
                    "N1 %", 0.94, 1, 70)
        _engine_arc(canvas, cx, 346, values.get(f"eng_egt_{index}"), 1000.0,
                    "EGT", 0.82, 0, 48)

        ff = values.get(f"eng_ff_{index}")
        ff_hour = float(ff) * 3600.0 if _finite(ff) and abs(float(ff)) < 100.0 else ff
        oil = values.get(f"eng_oil_pressure_{index}")
        _text(canvas, cx - 105, 386, "FF", CYAN, 2)
        _text(canvas, cx - 61, 386, _value(ff_hour, 0), GREEN, 6)
        _text(canvas, cx + 35, 386, "OIL", CYAN, 3)
        oil_colour = AMBER if _finite(oil) and float(oil) < 13.0 else WHITE
        _text(canvas, cx + 88, 386, _value(oil, 0), oil_colour, 3, "right")

        running = values.get(f"eng_running_{index}")
        low_oil = values.get(f"eng_low_oil_{index}")
        if _finite(low_oil) and float(low_oil) >= 0.5:
            _fill(canvas, cx - 85, 72, 170, 24, AMBER)
            _center(canvas, cx, 70, "LOW OIL", BLACK, 7, AMBER)
        elif _finite(running) and float(running) < 0.5:
            _center(canvas, cx, 70, "OFF", SOFT_GREY, 3)

    _fill(canvas, 293, 94, 54, 2, MAGENTA)
    _diamond(canvas, 320, 94, 7, MAGENTA, True)
    _center(canvas, 320, 440, "FUEL FLOW  KG/H", CYAN, 15)


def _vertical_bar(canvas: Any, x: int, y: int, h: int, value: Any,
                  low: float, high: float, colour: Tuple[int, int, int] = WHITE,
                  amber_below: float | None = None,
                  amber_above: float | None = None) -> None:
    _outline(canvas, x, y, 18, h, SOFT_GREY, 2)
    if not _finite(value):
        return
    numeric = float(value)
    fraction = _clamp((numeric - low) / max(0.001, high - low), 0.0, 1.0)
    bar_colour = colour
    if amber_below is not None and numeric < amber_below:
        bar_colour = AMBER
    if amber_above is not None and numeric > amber_above:
        bar_colour = AMBER
    filled = max(2, int(round((h - 4) * fraction)))
    _fill(canvas, x + 3, y + h - 2 - filled, 12, filled, bar_colour)


def _draw_engine_secondary(canvas: Any, values: Mapping[str, Any]) -> None:
    """Secondary engine page modelled on the supplied aircraft photograph."""
    _header(canvas, "ENGINE", CYAN)
    for index, cx in ((0, 190), (1, 450)):
        _engine_arc(canvas, cx, 110, values.get(f"eng_n2_{index}"), 110.0,
                    "N2", 0.96, 1, 58)
        _outline(canvas, cx - 47, 174, 94, 31, WHITE, 2)
        ff = values.get(f"eng_ff_{index}")
        ff_hour = float(ff) * 3600.0 if _finite(ff) and abs(float(ff)) < 100.0 else ff
        _center(canvas, cx, 176, _value(ff_hour, 0), GREEN, 5)

    labels = (("FF", 177), ("OIL", 225), ("PRESS", 250),
              ("OIL", 292), ("TEMP", 317), ("OIL QTY", 359), ("VIB", 410))
    for label, y in labels:
        _center(canvas, 320, y, label, CYAN, max(3, len(label)))

    for index, cx in ((0, 190), (1, 450)):
        pressure = values.get(f"eng_oil_pressure_{index}")
        temperature = values.get(f"eng_oil_temp_{index}")
        quantity = values.get(f"eng_oil_qty_{index}")
        vibration = values.get(f"eng_vibration_{index}")
        _vertical_bar(canvas, cx - 45, 222, 62, pressure, 0.0, 100.0,
                      WHITE, amber_below=13.0)
        _text(canvas, cx - 19, 237, _value(pressure, 0), WHITE, 4)
        _vertical_bar(canvas, cx - 45, 289, 62, temperature, 0.0, 180.0,
                      WHITE, amber_above=150.0)
        _text(canvas, cx - 19, 304, _value(temperature, 0), WHITE, 4)

        qty_percent = float(quantity) * 100.0 if _finite(quantity) and float(quantity) <= 1.5 else quantity
        _outline(canvas, cx - 43, 357, 86, 31, WHITE, 2)
        _center(canvas, cx, 359, _value(qty_percent, 0), WHITE, 4)
        _vertical_bar(canvas, cx - 45, 407, 52, vibration, 0.0, 5.0,
                      WHITE, amber_above=4.0)
        _outline(canvas, cx - 16, 413, 64, 31, WHITE, 2)
        _center(canvas, cx + 16, 415, _value(vibration, 1), WHITE, 4)


def _surface_symbol(canvas: Any, x: int, y: int, value: Any, label: str,
                    height: int = 68) -> None:
    _line(canvas, x, y, x, y + height, WHITE, 3)
    _line(canvas, x - 9, y + height // 2, x + 9, y + height // 2, SOFT_GREY, 2)
    if _finite(value):
        normalized = _clamp(float(value), -1.0, 1.0)
        marker_y = int(round(y + height / 2.0 - normalized * (height / 2.0 - 5)))
        _line(canvas, x - 13, marker_y, x + 13, marker_y, GREEN, 3)
        _diamond(canvas, x, marker_y, 4, GREEN, True)
    # Font 6 is the smallest verified native font on these controllers.  A
    # two-line spoiler caption keeps each opaque 17x29 glyph cell clear of the
    # adjacent AIL/ELEV captions without installing or guessing another font.
    if label == "FLT SPLR":
        _center(canvas, x, y + height, "FLT", CYAN, 3)
        _center(canvas, x, y + height + FONT_CELL_HEIGHT, "SPLR", CYAN, 4)
    else:
        _center(canvas, x, y + height + 3, label, CYAN, max(3, len(label)))


def _wheel(canvas: Any, cx: int, cy: int, left_temp: Any, right_temp: Any,
           side: str, brake_ratio: Any = math.nan) -> None:
    for offset, value in ((-28, left_temp), (28, right_temp)):
        _outline(canvas, cx + offset - 14, cy - 24, 28, 48, WHITE, 3)
        if _finite(brake_ratio):
            marker_y = int(round(
                cy + 18 - _clamp(float(brake_ratio), 0.0, 1.0) * 36.0
            ))
            _line(
                canvas,
                cx + offset - 10,
                marker_y,
                cx + offset + 10,
                marker_y,
                GREEN,
                3,
            )
        colour = AMBER if _finite(value) and float(value) >= 5.0 else WHITE
        _center(canvas, cx + offset, cy + 29, _value(value, 1), colour, 4)
    _center(canvas, cx, cy - 52, side, CYAN, 1)


def _draw_hyd(canvas: Any, values: Mapping[str, Any]) -> None:
    """Hydraulic/brake/flight-control page from the supplied aircraft layout."""
    _header(canvas, "HYDRAULIC / FLT CTRL", CYAN)
    _outline(canvas, 138, 45, 364, 96, CYAN, 3)
    _center(canvas, 320, 48, "HYDRAULIC", CYAN, 9)
    _text(canvas, 160, 78, "QTY %", CYAN, 5)
    _text(canvas, 160, 107, "PRESS", CYAN, 5)
    _center(canvas, 315, 72, "A", CYAN, 1)
    _center(canvas, 430, 72, "B", CYAN, 1)
    for key, x, y, decimals in (
        ("hyd_qty_a", 288, 82, 0), ("hyd_qty_b", 403, 82, 0),
        ("hyd_press_a", 270, 108, 0), ("hyd_press_b", 385, 108, 0),
    ):
        value = values.get(key)
        if "hyd_qty" in key and _finite(value) and abs(float(value)) <= 1.5:
            value = float(value) * 100.0
        colour = AMBER if _finite(value) and (("qty" in key and float(value) < 76.0) or ("press" in key and float(value) < 2400.0)) else WHITE
        _text(canvas, x, y, _value(value, decimals), colour, 5)

    _center(canvas, 320, 150, "BRAKE TEMP", CYAN, 10)
    _line(canvas, 178, 177, 462, 177, CYAN, 2)
    _wheel(
        canvas, 205, 214,
        values.get("brake_temp_lo"), values.get("brake_temp_li"), "L",
        values.get("left_brake_ratio"),
    )
    _wheel(
        canvas, 435, 214,
        values.get("brake_temp_ri"), values.get("brake_temp_ro"), "R",
        values.get("right_brake_ratio"),
    )

    roll = values.get("control_roll")
    pitch = values.get("control_pitch")
    yaw = values.get("control_yaw")
    aileron_left = -float(roll) if _finite(roll) else values.get("aileron_left")
    aileron_right = float(roll) if _finite(roll) else values.get("aileron_right")
    elevator_left = float(pitch) if _finite(pitch) else values.get("elevator_left")
    elevator_right = float(pitch) if _finite(pitch) else values.get("elevator_right")
    rudder = float(yaw) if _finite(yaw) else values.get("rudder")

    _surface_symbol(canvas, 85, 292, aileron_left, "AIL")
    _surface_symbol(canvas, 180, 292, values.get("spoiler_left"), "FLT SPLR", 63)
    _surface_symbol(canvas, 275, 292, elevator_left, "ELEV")
    _surface_symbol(canvas, 365, 292, elevator_right, "ELEV")
    _surface_symbol(canvas, 460, 292, values.get("spoiler_right"), "FLT SPLR", 63)
    _surface_symbol(canvas, 555, 292, aileron_right, "AIL")

    _line(canvas, 248, 447, 392, 447, WHITE, 3)
    _line(canvas, 320, 439, 320, 455, SOFT_GREY, 2)
    if _finite(rudder):
        marker_x = int(round(320 + _clamp(float(rudder), -1.0, 1.0) * 64.0))
        _diamond(canvas, marker_x, 447, 6, GREEN, True)
    _center(canvas, 320, 414, "RUDDER", CYAN, 6)


def draw_system_frame(canvas: Any, page: str, values: Mapping[str, Any]) -> None:
    page = str(page).strip().lower()
    if page == "eng_pri":
        _draw_eng_pri(canvas, values)
    elif page == "mfd":
        _draw_engine_secondary(canvas, values)
    elif page == "hyd":
        _draw_hyd(canvas, values)
    else:
        _header(canvas, "DISPLAY PAGE ERROR", AMBER)


def draw_live_system_page(canvas: Any, page: str, values: Mapping[str, Any]) -> bool:
    """Emit changed regions for one systems page; return True if it drew."""
    page = str(page).strip().lower()
    recorder = _OpRecorder()
    draw_system_frame(recorder, page, values)
    operations = recorder.ops
    state = getattr(canvas, "_muslimsim_systems_state", None)
    now = time.monotonic()
    stale = (
        state is None
        or state[0] != page
        or now - state[2] > FULL_REPAINT_SECONDS
        or state[3] >= SYSTEM_FULL_REPAINT_FRAMES
    )
    if stale:
        boxes = [(0, 0, WIDTH, HEIGHT)]
        sequence = 0
    else:
        boxes = _dirty_boxes(operations, state[1])
        sequence = state[3] + 1
    _emit_frame(canvas, operations, boxes)
    try:
        canvas._muslimsim_systems_state = (page, operations, now, sequence)
    except AttributeError:
        pass
    return bool(boxes)


def invalidate(canvas: Any) -> None:
    try:
        del canvas._muslimsim_systems_state
    except (AttributeError, TypeError):
        pass


class _BoundsCanvas:
    def colour(self, _red: int, _green: int, _blue: int) -> None:
        return None

    def fill(self, x: int, y: int, width: int, height: int) -> None:
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > WIDTH or y + height > HEIGHT:
            raise SystemsLayoutError(f"fill outside display: {(x, y, width, height)}")

    def text(self, x: int, y: int, value: str, _foreground, _background, _font_id) -> None:
        if x < 0 or y < 0 or x + len(value) * FONT_CELL_WIDTH > WIDTH or y + FONT_CELL_HEIGHT > HEIGHT:
            raise SystemsLayoutError(f"text outside display: {(x, y, value)!r}")


def assert_layout_contract() -> None:
    sample = {
        "tat": 27.0, "thrust_mode": "TO", "fuel_total": 7400.0,
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
        "aileron_left": -0.1, "aileron_right": 0.1,
        "spoiler_left": 0.0, "spoiler_right": 0.0,
        "elevator_left": 0.05, "elevator_right": 0.05, "rudder": -0.15,
        "control_roll": 0.4, "control_pitch": -0.3, "control_yaw": 0.6,
        "left_brake_ratio": 0.25, "right_brake_ratio": 0.8,
    }
    for page in ("eng_pri", "mfd", "hyd"):
        draw_system_frame(_BoundsCanvas(), page, sample)

    neutral = dict(sample)
    neutral.update({
        "control_roll": 0.0,
        "control_pitch": 0.0,
        "control_yaw": 0.0,
        "left_brake_ratio": 0.0,
        "right_brake_ratio": 0.0,
    })
    base = _OpRecorder()
    draw_system_frame(base, "hyd", neutral)
    for key, deflection in (
        ("control_roll", 0.75),
        ("control_pitch", -0.75),
        ("control_yaw", 0.75),
        ("left_brake_ratio", 0.75),
        ("right_brake_ratio", 0.75),
    ):
        moved_values = dict(neutral)
        moved_values[key] = deflection
        moved = _OpRecorder()
        draw_system_frame(moved, "hyd", moved_values)
        if moved.ops == base.ops:
            raise SystemsLayoutError(f"HYD control marker is static: {key}")


__all__ = (
    "SYSTEM_PAGE_VALUE_KEYS", "assert_layout_contract", "draw_live_system_page",
    "draw_system_frame", "invalidate",
)
