"""Draw the MuslimSim Boeing 737 PFD design to PNG reference sheets.

This tool is display-design only.  It never opens the PFP HID device, COM5,
the WinCtrl hardware, or X-Plane.  It renders the agreed 737 PFD design to
image files so the layout, colours, and symbol set can be reviewed away from
the cockpit, and so the live renderer has one fixed drawing target.

Every element uses the same 640x480 coordinate contract as the live renderer
in muslimsim/devices/pfp_renderer.py.  A tape, live window, or scale that is
moved here must be moved there by the same number of pixels, which is what
keeps the protected-zone rule intact.

Usage:
    python tools/build_pfd_design_png.py                # every sheet into PNG/
    python tools/build_pfd_design_png.py --only approach
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont

PROJECT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT / "PNG"

WIDTH = 640
HEIGHT = 480
SUPERSAMPLE = 4

# ---------------------------------------------------------------------------
# Colours.  These are the live renderer's constants, so a design sheet and the
# PFP screen cannot quietly drift apart.
# ---------------------------------------------------------------------------
BLACK = (6, 7, 13)
WHITE = (245, 246, 249)
CYAN = (0, 225, 255)
GREEN = (0, 255, 82)
MAGENTA = (255, 99, 255)
AMBER = (255, 183, 0)
RED = (255, 64, 52)
TAPE_GREY = (64, 66, 71)
FMA_GREY = (39, 40, 46)
VS_GREY = (52, 53, 58)
SKY = (20, 101, 211)
EARTH = (121, 65, 20)

FONT_CANDIDATES = {
    "bold": ("arialbd.ttf", "ArialNova-Bold.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"),
    "regular": ("arial.ttf", "ArialNova.ttf", "segoeui.ttf", "DejaVuSans.ttf"),
}


@lru_cache(maxsize=512)
def _font(kind: str, pixels: int) -> ImageFont.FreeTypeFont:
    for name in FONT_CANDIDATES[kind]:
        try:
            return ImageFont.truetype(name, max(1, int(pixels)))
        except OSError:
            continue
    return ImageFont.load_default()


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def cx(self) -> float:
        return self.x + self.width / 2.0

    @property
    def cy(self) -> float:
        return self.y + self.height / 2.0


# ---------------------------------------------------------------------------
# The 640x480 zone contract shared with muslimsim/devices/pfp_renderer.py.
# ---------------------------------------------------------------------------
DATUM_Y = 226.0  # attitude centre, speed pointer, altitude pointer, V/S zero
FMA_BAND = Rect(0, 26, WIDTH, 52)
FMA_COLUMNS = (Rect(76, 26, 170, 52), Rect(250, 26, 170, 52), Rect(424, 26, 196, 52))
FMA_ACTIVE_Y = 40.0
FMA_ARMED_Y = 64.0
SELECTED_SPEED = Rect(50, 2, 110, 22)
SELECTED_ALTITUDE = Rect(462, 2, 156, 22)
COMMAND = Rect(251, 52, 138, 24)

SPEED_TAPE = Rect(90, 72, 70, 328)
ALTITUDE_TAPE = Rect(480, 72, 72, 328)
SPEED_WINDOW = Rect(44, 200, 100, 52)
SPEED_WINDOW_POINT = 16
ALTITUDE_WINDOW = Rect(446, 200, 112, 52)
ALTITUDE_WINDOW_POINT = 16
ATTITUDE = Rect(194, 100, 252, 252)
ATTITUDE_RADIUS = 24.0

VS_SCALE = Rect(566, 116, 68, 220)
VS_CHAMFER = 34.0
VS_LABEL_X = 574.0
VS_TICK_X = 590.0
VS_PIVOT_X = 566.0
VS_TIP_X = 626.0

COMPASS_CENTER = (320.0, 583.0)
COMPASS_RADIUS = 193.0
COMPASS_TOP = COMPASS_CENTER[1] - COMPASS_RADIUS  # y = 390
HEADING_WINDOW = Rect(289, 356, 62, 27)   # kept for the zone map's history
HEADING_READOUT = Rect(180, 451, 85, 29)  # selected heading, magenta, on the rose
MAG_LABEL_ZONE = Rect(286, 451, 69, 29)
LOCALIZER_Y = 336.0       # expanded localizer sits inside the attitude display
GLIDESLOPE_X = 434.0      # expanded glideslope inside the attitude display
RADIO_ALTITUDE_Y = 310.0
BARO_ZONE = Rect(462, 428, 156, 26)
MINIMUMS_ZONE = Rect(462, 404, 156, 22)
APPROACH_REF = Rect(16, 428, 210, 26)
MACH_ZONE = Rect(78, 404, 94, 24)

# Moving-scale rates.
# These are the live renderer's own tape rates.  The sheets used to run at a
# more generous scale, which made a measurement taken from a sheet wrong by
# nearly a factor of two when it was implemented on the panel.
PX_PER_KNOT = 2.15
PX_PER_FOOT = 0.22
PX_PER_PITCH_DEGREE = 5.0
PX_PER_FD_ROLL_DEGREE = 2.2
COMPASS_ARC_PER_DEGREE = 1.0  # the panel draws the arc one for one with heading

# Western "sky pointer" convention: the bank pointer is painted on the moving
# sky, so it stays normal to the horizon and leans toward the raised wing.
# Set this False only if the Zibo reference is confirmed to do the opposite.
BANK_POINTER_FOLLOWS_SKY = True


class Canvas:
    """A supersampled drawing surface addressed in native 640x480 pixels."""

    def __init__(self, width: int, height: int, scale: int, background=(0, 0, 0, 0)):
        self.width = width
        self.height = height
        self.scale = scale
        if len(background) == 3:
            background = tuple(background) + (255,)
        self.img = Image.new("RGBA", (int(width * scale), int(height * scale)), background)
        self.draw = ImageDraw.Draw(self.img, "RGBA")

    def _s(self, value: float) -> float:
        return value * self.scale

    def _pts(self, points: Iterable[Sequence[float]]):
        return [(self._s(x), self._s(y)) for x, y in points]

    def _w(self, width: float) -> int:
        return max(1, int(round(width * self.scale)))

    def rect(self, rect: Rect, fill=None, outline=None, width: float = 1.0):
        self.draw.rectangle(
            [self._s(rect.x), self._s(rect.y), self._s(rect.right), self._s(rect.bottom)],
            fill=fill, outline=outline, width=self._w(width),
        )

    def round_rect(self, rect: Rect, radius: float, fill=None, outline=None, width: float = 1.0):
        self.draw.rounded_rectangle(
            [self._s(rect.x), self._s(rect.y), self._s(rect.right), self._s(rect.bottom)],
            radius=self._s(radius), fill=fill, outline=outline, width=self._w(width),
        )

    def line(self, points: Iterable[Sequence[float]], fill, width: float = 1.0):
        self.draw.line(self._pts(points), fill=fill, width=self._w(width), joint="curve")

    def polygon(self, points: Iterable[Sequence[float]], fill=None, outline=None, width: float = 1.0):
        pts = self._pts(points)
        if fill is not None:
            self.draw.polygon(pts, fill=fill)
        if outline is not None:
            self.draw.line(pts + [pts[0]], fill=outline, width=self._w(width), joint="curve")

    def dot(self, x: float, y: float, radius: float, fill=None, outline=None, width: float = 1.0):
        self.draw.ellipse(
            [self._s(x - radius), self._s(y - radius), self._s(x + radius), self._s(y + radius)],
            fill=fill, outline=outline, width=self._w(width),
        )

    def pieslice(self, cx: float, cy: float, radius: float, start: float, end: float, fill):
        self.draw.pieslice(
            [self._s(cx - radius), self._s(cy - radius), self._s(cx + radius), self._s(cy + radius)],
            start=start, end=end, fill=fill,
        )

    def arc(self, cx: float, cy: float, radius: float, start: float, end: float, fill, width: float = 1.0):
        self.draw.arc(
            [self._s(cx - radius), self._s(cy - radius), self._s(cx + radius), self._s(cy + radius)],
            start=start, end=end, fill=fill, width=self._w(width),
        )

    def text(self, x: float, y: float, value: str, size: float, fill,
             anchor: str = "lm", kind: str = "bold", tracking: float = 0.0):
        if not value:
            return
        if tracking:
            self._tracked_text(x, y, value, size, fill, anchor, kind, tracking)
            return
        self.draw.text((self._s(x), self._s(y)), value, font=_font(kind, self._s(size)),
                       fill=fill, anchor=anchor)

    def _tracked_text(self, x, y, value, size, fill, anchor, kind, tracking):
        font = _font(kind, self._s(size))
        widths = [self.draw.textlength(ch, font=font) for ch in value]
        total = sum(widths) + self._s(tracking) * (len(value) - 1)
        left = self._s(x)
        if anchor[0] == "m":
            left -= total / 2.0
        elif anchor[0] == "r":
            left -= total
        vertical = anchor[1] if len(anchor) > 1 else "m"
        for char, width in zip(value, widths):
            self.draw.text((left, self._s(y)), char, font=font, fill=fill, anchor="l" + vertical)
            left += width + self._s(tracking)

    def text_width(self, value: str, size: float, kind: str = "bold") -> float:
        return self.draw.textlength(value, font=_font(kind, self._s(size))) / self.scale

    def finish(self, output_scale: int = 1) -> Image.Image:
        target = (self.width * output_scale, self.height * output_scale)
        return self.img.convert("RGB").resize(target, Image.LANCZOS)


# ---------------------------------------------------------------------------
# Small shared helpers.
# ---------------------------------------------------------------------------
def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def heading_delta(target: float, live: float) -> float:
    return (target - live + 540.0) % 360.0 - 180.0


def heading_label(heading: float) -> str:
    tens = int(round(heading / 10.0)) % 36
    return {0: "N", 9: "E", 18: "S", 27: "W"}.get(tens, f"{tens:02d}")


def clipped(canvas: Canvas, rect: Rect):
    """Return a child canvas whose contents are clipped to `rect` on paste."""
    return Canvas(int(round(rect.width)), int(round(rect.height)), canvas.scale)


def paste_clipped(canvas: Canvas, child: Canvas, rect: Rect) -> None:
    canvas.img.alpha_composite(child.img, (int(rect.x * canvas.scale), int(rect.y * canvas.scale)))


def arrow_head(canvas: Canvas, x: float, y: float, direction: int, colour, size: float = 5.0) -> None:
    canvas.polygon([(x - size, y + direction * size), (x + size, y + direction * size), (x, y)], fill=colour)


# ---------------------------------------------------------------------------
# Flight-mode annunciator strip.
# ---------------------------------------------------------------------------
def draw_fma(canvas: Canvas, state: dict) -> None:
    canvas.rect(FMA_BAND, fill=FMA_GREY + (255,))
    for x in (248.0, 422.0):
        canvas.line([(x, FMA_BAND.y + 3), (x, FMA_BAND.bottom - 3)], (150, 152, 160), 1)

    active = state["fma_active"]
    armed = state["fma_armed"]
    for column, label in zip(FMA_COLUMNS, active):
        canvas.text(column.cx, FMA_ACTIVE_Y, label, 17, GREEN, anchor="mm")
    for column, label in zip(FMA_COLUMNS, armed):
        if label:
            canvas.text(column.cx, FMA_ARMED_Y, label, 14, WHITE, anchor="mm")

    boxed = state.get("fma_boxed")
    if boxed is not None and active[boxed]:
        column = FMA_COLUMNS[boxed]
        half = max(canvas.text_width(active[boxed], 17) / 2.0 + 6.0, 24.0)
        canvas.rect(Rect(column.cx - half, FMA_ACTIVE_Y - 12, half * 2, 24), outline=GREEN, width=2)

    if state.get("autoland"):
        canvas.text(COMMAND.cx, FMA_ARMED_Y, state["autoland"], 14, WHITE, anchor="mm")
        canvas.rect(Rect(COMMAND.cx - 32, FMA_ARMED_Y - 11, 64, 22), outline=WHITE, width=1)
    elif state.get("command"):
        canvas.text(COMMAND.cx, FMA_ARMED_Y, state["command"], 15, WHITE, anchor="mm")


# ---------------------------------------------------------------------------
# Airspeed tape.
# ---------------------------------------------------------------------------
def speed_y(value: float, ias: float) -> float:
    return DATUM_Y - (value - ias) * PX_PER_KNOT


def draw_speed_tape(canvas: Canvas, state: dict) -> None:
    ias = state["ias"]
    tape = clipped(canvas, SPEED_TAPE)
    tape.rect(Rect(0, 0, SPEED_TAPE.width, SPEED_TAPE.height), fill=TAPE_GREY + (235,))

    def local_y(value: float) -> float:
        return speed_y(value, ias) - SPEED_TAPE.y

    first = int((ias - 50) // 10) * 10
    for value in range(max(0, first), int(ias + 60), 10):
        y = local_y(value)
        if not -20 <= y <= SPEED_TAPE.height + 20:
            continue
        if value % 20 == 0:
            tape.line([(SPEED_TAPE.width - 15, y), (SPEED_TAPE.width, y)], WHITE, 2)
            # A number is only drawn where its whole height fits the strip, the
            # same protected-zone rule the live renderer uses.
            if value >= 40 and 13 <= y <= SPEED_TAPE.height - 13:
                tape.text(SPEED_TAPE.width - 19, y, f"{value:03d}", 18, WHITE, anchor="rm", tracking=-0.6)
        else:
            tape.line([(SPEED_TAPE.width - 9, y), (SPEED_TAPE.width, y)], WHITE, 2)

    # Minimum manoeuvring speed and the amber low-speed band.
    minimum = state.get("min_speed")
    if minimum is not None:
        y = local_y(minimum)
        tape.line([(SPEED_TAPE.width - 7, y), (SPEED_TAPE.width - 7, SPEED_TAPE.height)], AMBER, 5)
        tape.line([(SPEED_TAPE.width - 12, y), (SPEED_TAPE.width, y)], AMBER, 3)

    # Never-exceed barber pole above VMO/MMO.
    vmo = state.get("vmo")
    if vmo is not None:
        top = local_y(vmo)
        if top > -20:
            stripe = clipped(canvas, Rect(0, 0, 10, max(1.0, min(top, SPEED_TAPE.height))))
            for offset in range(-40, int(top) + 12, 8):
                stripe.polygon([(0, offset), (10, offset - 10), (10, offset - 4), (0, offset + 6)], fill=RED)
            paste_clipped(tape, stripe, Rect(SPEED_TAPE.width - 11, 0, stripe.width, stripe.height))
            tape.line([(SPEED_TAPE.width - 11, top), (SPEED_TAPE.width, top)], RED, 2)

    paste_clipped(canvas, tape, SPEED_TAPE)

    # Reference speeds sit in the gutter beside the tape so they never cover a
    # tape number.
    for bug in state.get("speed_marks", ()):
        y = speed_y(bug["speed"], ias)
        if not SPEED_TAPE.y + 6 <= y <= SPEED_TAPE.bottom - 6:
            continue
        colour = bug.get("colour", GREEN)
        canvas.line([(SPEED_TAPE.right - 6, y), (SPEED_TAPE.right + 8, y)], colour, 2)
        # Close to the live-speed window the label would sit on the window's
        # pointer, so the mark is kept and the text is dropped.
        if abs(y - DATUM_Y) > 30:
            canvas.text(SPEED_TAPE.right + 11, y, bug["label"], 13, colour, anchor="lm")

    # The selected-speed bug faces the attitude display, like the 737 tape.
    target = state.get("target_ias")
    if target is not None and target > 10.0:
        y = clamp(speed_y(target, ias), SPEED_TAPE.y + 12, SPEED_TAPE.bottom - 12)
        tip, left, right = SPEED_TAPE.right - 8, SPEED_TAPE.right + 6, SPEED_TAPE.right + 30
        canvas.polygon([(tip, y), (left, y - 11), (right, y - 11), (right, y + 11), (left, y + 11)],
                       fill=None, outline=MAGENTA, width=2)

    draw_speed_window(canvas, state)
    draw_speed_trend(canvas, state)

    if state.get("mach"):
        canvas.text(MACH_ZONE.cx, MACH_ZONE.cy, state["mach"], 19, WHITE, anchor="mm", tracking=-0.5)


def draw_speed_trend(canvas: Canvas, state: dict) -> None:
    trend = state.get("speed_trend")
    if not trend:
        return
    x = SPEED_TAPE.right + 16
    end = clamp(DATUM_Y - trend * PX_PER_KNOT, SPEED_TAPE.y + 10, SPEED_TAPE.bottom - 10)
    canvas.line([(x, DATUM_Y), (x, end)], GREEN, 2)
    arrow_head(canvas, x, end, 1 if end < DATUM_Y else -1, GREEN, 4.5)


def draw_speed_window(canvas: Canvas, state: dict) -> None:
    box = SPEED_WINDOW
    tip = box.right + SPEED_WINDOW_POINT
    canvas.polygon(
        [(box.x, box.y), (box.right, box.y), (box.right, box.y + 12), (tip, box.cy),
         (box.right, box.bottom - 12), (box.right, box.bottom), (box.x, box.bottom)],
        fill=BLACK + (255,), outline=WHITE, width=2,
    )
    ias = max(0.0, state["ias"])
    lead = f"{int(ias) // 10:d}" if ias >= 10 else ""
    lead_width = (canvas.text_width(lead, 29) - 1.0 * len(lead)) if lead else 0.0
    drum_width = 18.0
    left = (box.x + box.right - 12) / 2.0 - (lead_width + drum_width) / 2.0
    if lead:
        canvas.text(left, box.cy, lead, 29, WHITE, anchor="lm", tracking=-1.0)
    draw_digit_drum(canvas, Rect(left + lead_width, box.cy - 15, drum_width, 30), ias, 1.0,
                    lambda value: f"{int(abs(value)) % 10:d}", 29, WHITE, spacing=30.0)


def draw_digit_drum(canvas: Canvas, rect: Rect, value: float, step: float,
                    label, size: float, colour, spacing: float | None = None) -> None:
    """A vertically scrolling digit column, clipped to its own window.

    `label` turns a scale value into the characters shown for it, so the drum
    can carry one rolling digit (airspeed) or a rolling pair (altitude).
    """
    child = clipped(canvas, rect)
    pitch = spacing if spacing is not None else size * 1.15
    base = math.floor(value / step) * step
    fraction = (value - base) / step
    for index in (-1, 0, 1):
        y = rect.height / 2.0 + (fraction - index) * pitch
        child.text(rect.width / 2.0, y, label(base + index * step), size, colour,
                   anchor="mm", tracking=-0.6)
    paste_clipped(canvas, child, rect)


# ---------------------------------------------------------------------------
# Altitude tape.
# ---------------------------------------------------------------------------
def altitude_y(value: float, altitude: float) -> float:
    return DATUM_Y - (value - altitude) * PX_PER_FOOT


def draw_altitude_tape(canvas: Canvas, state: dict) -> None:
    altitude = state["altitude"]
    tape = clipped(canvas, ALTITUDE_TAPE)
    tape.rect(Rect(0, 0, ALTITUDE_TAPE.width, ALTITUDE_TAPE.height), fill=TAPE_GREY + (235,))

    def local_y(value: float) -> float:
        return altitude_y(value, altitude) - ALTITUDE_TAPE.y

    first = int((altitude - 600) // 100) * 100
    for value in range(first, int(altitude + 700), 100):
        y = local_y(value)
        if not -20 <= y <= ALTITUDE_TAPE.height + 20:
            continue
        if value % 200 == 0:
            tape.line([(0, y), (12, y)], WHITE, 2)
            if not 13 <= y <= ALTITUDE_TAPE.height - 13:
                continue
            label = f"{value // 1000}" if abs(value) >= 1000 else ""
            hundreds = f"{abs(value) % 1000:03d}"
            text_x = 16.0
            if label:
                tape.text(text_x, y, label, 19, WHITE, anchor="lm", tracking=-0.6)
                text_x += tape.text_width(label, 19) - 0.5
            tape.text(text_x, y, hundreds, 15, WHITE, anchor="lm", tracking=-0.4)
        else:
            tape.line([(0, y), (7, y)], WHITE, 2)

    field = state.get("field_elevation")
    if field is not None:
        y = local_y(field)
        if -20 <= y <= ALTITUDE_TAPE.height + 20:
            ground = clipped(canvas, Rect(0, 0, ALTITUDE_TAPE.width, ALTITUDE_TAPE.height))
            for offset in range(int(y), int(ALTITUDE_TAPE.height) + 14, 7):
                ground.line([(0, offset), (14, offset - 14)], AMBER, 2)
            ground.line([(0, y), (ALTITUDE_TAPE.width, y)], AMBER, 2)
            paste_clipped(tape, ground, Rect(0, 0, ALTITUDE_TAPE.width, ALTITUDE_TAPE.height))

    paste_clipped(canvas, tape, ALTITUDE_TAPE)

    # The selected-altitude bug faces the attitude display.
    target = state.get("target_altitude")
    if target is not None:
        y = clamp(altitude_y(target, altitude), ALTITUDE_TAPE.y + 26, ALTITUDE_TAPE.bottom - 26)
        left, right = ALTITUDE_TAPE.x - 12, ALTITUDE_TAPE.x + 22
        canvas.polygon([(left, y - 24), (right, y - 24), (right, y - 8), (right + 8, y),
                        (right, y + 8), (right, y + 24), (left, y + 24)],
                       fill=None, outline=MAGENTA, width=2)

    minimums = state.get("minimums")
    if minimums is not None:
        y = altitude_y(minimums, altitude)
        if ALTITUDE_TAPE.y + 4 <= y <= ALTITUDE_TAPE.bottom - 4:
            canvas.line([(ALTITUDE_TAPE.right, y), (ALTITUDE_TAPE.right + 10, y)], AMBER, 3)
            canvas.line([(ALTITUDE_TAPE.right + 10, y - 6), (ALTITUDE_TAPE.right + 10, y + 6)], AMBER, 3)
        if state.get("minimums_label"):
            canvas.text(MINIMUMS_ZONE.cx, MINIMUMS_ZONE.cy, state["minimums_label"], 15, GREEN,
                        anchor="mm", tracking=-0.4)

    draw_altitude_window(canvas, state)
    draw_baro(canvas, state)


def draw_altitude_window(canvas: Canvas, state: dict) -> None:
    """Box with an inboard chevron, a ten-thousands hatch, and a rolling pair."""
    box = ALTITUDE_WINDOW
    tip = box.x - ALTITUDE_WINDOW_POINT
    canvas.polygon(
        [(box.right, box.y), (box.x, box.y), (box.x, box.y + 12), (tip, box.cy),
         (box.x, box.bottom - 12), (box.x, box.bottom), (box.right, box.bottom)],
        fill=BLACK + (255,), outline=WHITE, width=2,
    )
    altitude = max(0.0, state["altitude"])
    whole = int(altitude)
    left = box.x + 18

    if whole < 10000:
        # Boeing hatches the ten-thousands position below 10,000 ft so a
        # five-figure altitude can never be read as a four-figure one.
        hatch = Rect(left, box.cy - 13, 15, 26)
        canvas.rect(hatch, fill=GREEN)
        for offset in range(0, int(hatch.height), 6):
            canvas.rect(Rect(hatch.x, hatch.y + offset, hatch.width, 3), fill=BLACK + (255,))
    else:
        canvas.text(left, box.cy, str((whole // 10000) % 10), 27, WHITE, anchor="lm", tracking=-0.8)
    left += 17

    lead = f"{(whole // 1000) % 10}{(whole // 100) % 10}"
    canvas.text(left, box.cy, lead, 27, WHITE, anchor="lm", tracking=-0.8)
    left += canvas.text_width(lead, 27) + 1.0
    draw_digit_drum(canvas, Rect(left, box.cy - 15, 34, 30), altitude, 20.0,
                    lambda value: f"{int(abs(value)) % 100:02d}", 21, WHITE, spacing=26.0)


def draw_baro(canvas: Canvas, state: dict) -> None:
    baro = state.get("baro")
    if not baro:
        return
    if baro == "STD":
        canvas.text(BARO_ZONE.cx, BARO_ZONE.cy, "STD", 20, GREEN, anchor="mm")
        canvas.rect(Rect(BARO_ZONE.cx - 30, BARO_ZONE.y, 60, BARO_ZONE.height), outline=AMBER, width=1)
        return
    canvas.text(BARO_ZONE.cx, BARO_ZONE.cy, baro, 19, GREEN, anchor="mm", tracking=-0.4)


# ---------------------------------------------------------------------------
# Vertical speed scale.
# ---------------------------------------------------------------------------
def vs_y(feet_per_minute: float) -> float:
    """Linear to 1000 fpm, then compressed twice, as on the 737 scale."""
    magnitude = min(abs(feet_per_minute), 6000.0)
    if magnitude <= 1000.0:
        offset = magnitude / 1000.0 * 29.0
    elif magnitude <= 2000.0:
        offset = 29.0 + (magnitude - 1000.0) / 1000.0 * 29.0
    else:
        offset = 58.0 + (magnitude - 2000.0) / 4000.0 * 38.0
    return DATUM_Y - math.copysign(offset, feet_per_minute)


def draw_vertical_speed(canvas: Canvas, state: dict) -> None:
    """Grey wedge with chamfered outer corners, numbers inboard, ticks outboard."""
    canvas.polygon(
        [(VS_SCALE.x, VS_SCALE.y), (VS_SCALE.right - VS_CHAMFER, VS_SCALE.y),
         (VS_SCALE.right, VS_SCALE.y + VS_CHAMFER),
         (VS_SCALE.right, VS_SCALE.bottom - VS_CHAMFER),
         (VS_SCALE.right - VS_CHAMFER, VS_SCALE.bottom), (VS_SCALE.x, VS_SCALE.bottom)],
        fill=VS_GREY + (235,),
    )
    for thousands, label in ((6.0, "6"), (2.0, "2"), (1.0, "1")):
        for sign in (-1.0, 1.0):
            y = vs_y(sign * thousands * 1000.0)
            canvas.line([(VS_TICK_X, y), (VS_TICK_X + 16, y)], WHITE, 2)
            canvas.text(VS_LABEL_X + 8, y, label, 15, WHITE, anchor="mm")
    for thousands in (0.5, 1.5, 4.0):
        for sign in (-1.0, 1.0):
            y = vs_y(sign * thousands * 1000.0)
            canvas.line([(VS_TICK_X, y), (VS_TICK_X + 10, y)], WHITE, 2)

    vertical_speed = state.get("vertical_speed")
    if vertical_speed is None:
        return
    tip_y = vs_y(clamp(vertical_speed, -6000.0, 6000.0))
    colour = MAGENTA if state.get("vs_selected") else WHITE
    canvas.line([(VS_PIVOT_X, DATUM_Y), (VS_TIP_X, tip_y)], colour, 3)


# ---------------------------------------------------------------------------
# Attitude display.
# ---------------------------------------------------------------------------
def draw_attitude(canvas: Canvas, state: dict) -> None:
    pitch = state["pitch"]
    roll = state["roll"]
    side = 430
    layer = Canvas(side, side, canvas.scale)
    centre = side / 2.0
    horizon = centre + pitch * PX_PER_PITCH_DEGREE

    layer.rect(Rect(0, 0, side, horizon), fill=SKY + (255,))
    layer.rect(Rect(0, horizon, side, side - horizon), fill=EARTH + (255,))
    layer.line([(0, horizon), (side, horizon)], WHITE, 2)

    step = 25  # tenths of a degree, i.e. 2.5 degree ladder spacing
    for tenths in range(-300, 301, step):
        degrees = tenths / 10.0
        if degrees == 0.0:
            continue
        y = centre + (pitch - degrees) * PX_PER_PITCH_DEGREE
        if not 30 <= y <= side - 30:
            continue
        if tenths % 100 == 0:
            half = 30.0
        elif tenths % 50 == 0:
            half = 16.0
        else:
            half = 8.0
        layer.line([(centre - half, y), (centre + half, y)], WHITE, 2)
        if degrees < 0:
            tick = 5.0
            layer.line([(centre - half, y), (centre - half, y - tick)], WHITE, 2)
            layer.line([(centre + half, y), (centre + half, y - tick)], WHITE, 2)
        if tenths % 100 == 0:
            label = str(int(abs(degrees)))
            layer.text(centre - half - 5, y, label, 14, WHITE, anchor="rm")
            layer.text(centre + half + 5, y, label, 14, WHITE, anchor="lm")

    rotated = layer.img.rotate(roll, resample=Image.BICUBIC, center=(centre * canvas.scale, centre * canvas.scale))
    sphere = Image.new("RGBA", canvas.img.size, (0, 0, 0, 0))
    sphere.paste(rotated, (int((ATTITUDE.cx - centre) * canvas.scale), int((DATUM_Y - centre) * canvas.scale)))
    mask = Image.new("L", canvas.img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [ATTITUDE.x * canvas.scale, ATTITUDE.y * canvas.scale,
         ATTITUDE.right * canvas.scale, ATTITUDE.bottom * canvas.scale],
        radius=ATTITUDE_RADIUS * canvas.scale, fill=255,
    )
    canvas.img.paste(sphere, (0, 0), mask)

    draw_bank_scale(canvas, state)
    draw_flight_director(canvas, state)
    draw_aircraft_symbol(canvas)
    draw_ils(canvas, state)
    draw_radio_altitude(canvas, state)


def bank_point(angle_degrees: float, radius: float) -> tuple[float, float]:
    radians = math.radians(angle_degrees)
    return ATTITUDE.cx + radius * math.sin(radians), DATUM_Y - radius * math.cos(radians)


def draw_bank_scale(canvas: Canvas, state: dict) -> None:
    for angle in (-60, -45, -30, -20, -10, 10, 20, 30, 45, 60):
        length = 13.0 if abs(angle) in (30, 60) else 9.0
        inner = bank_point(angle, 113.0)
        outer = bank_point(angle, 113.0 + length)
        canvas.line([inner, outer], WHITE, 2)
    apex = bank_point(0, 113.0)
    canvas.polygon([(apex[0] - 9, apex[1] - 14), (apex[0] + 9, apex[1] - 14), (apex[0], apex[1])],
                   fill=None, outline=WHITE, width=2)

    roll = state["roll"]
    pointer_angle = -roll if BANK_POINTER_FOLLOWS_SKY else roll
    tip = bank_point(pointer_angle, 110.0)
    base_left = bank_point(pointer_angle - 5.6, 92.0)
    base_right = bank_point(pointer_angle + 5.6, 92.0)
    colour = AMBER if abs(roll) > 35.0 else WHITE
    canvas.polygon([tip, base_left, base_right], fill=colour)

    slip = clamp(state.get("slip", 0.0), -1.0, 1.0) * 14.0
    radians = math.radians(pointer_angle)
    shift = (math.cos(radians) * slip, math.sin(radians) * slip)
    quad = [
        (base_left[0] + shift[0], base_left[1] + shift[1]),
        (base_right[0] + shift[0], base_right[1] + shift[1]),
        (base_right[0] + shift[0] - math.sin(radians) * 7, base_right[1] + shift[1] + math.cos(radians) * 7),
        (base_left[0] + shift[0] - math.sin(radians) * 7, base_left[1] + shift[1] + math.cos(radians) * 7),
    ]
    canvas.polygon(quad, fill=None, outline=colour, width=2)


def draw_flight_director(canvas: Canvas, state: dict) -> None:
    """Split command bars: each bar shows the remaining command deviation."""
    if not state.get("fd_visible"):
        return
    pitch_error = state.get("fd_pitch", 0.0) - state["pitch"]
    roll_error = state.get("fd_roll", 0.0) - state["roll"]
    pitch_bar = clamp(DATUM_Y - pitch_error * PX_PER_PITCH_DEGREE, ATTITUDE.y + 26, ATTITUDE.bottom - 26)
    roll_bar = clamp(ATTITUDE.cx + roll_error * PX_PER_FD_ROLL_DEGREE, ATTITUDE.x + 26, ATTITUDE.right - 26)
    canvas.line([(ATTITUDE.cx - 52, pitch_bar), (ATTITUDE.cx + 52, pitch_bar)], MAGENTA, 3)
    canvas.line([(roll_bar, DATUM_Y - 52), (roll_bar, DATUM_Y + 52)], MAGENTA, 3)


def draw_aircraft_symbol(canvas: Canvas) -> None:
    cx, cy = ATTITUDE.cx, DATUM_Y
    for direction in (-1, 1):
        outer = cx + direction * 88
        inner = cx + direction * 26
        wing = [
            (outer, cy - 3), (inner, cy - 3), (inner, cy + 16),
            (inner - direction * 16, cy + 16), (inner - direction * 16, cy + 12),
            (inner - direction * 4, cy + 12), (inner - direction * 4, cy + 4), (outer, cy + 4),
        ]
        canvas.polygon(wing, fill=WHITE, outline=BLACK + (255,), width=1.5)
    canvas.rect(Rect(cx - 4, cy - 4, 8, 8), fill=WHITE, outline=BLACK + (255,), width=1)


def draw_ils(canvas: Canvas, state: dict) -> None:
    glideslope = state.get("glideslope")
    if glideslope is not None:
        canvas.rect(Rect(GLIDESLOPE_X - 8, DATUM_Y - 68, 16, 136), fill=(0, 0, 0, 70))
        canvas.line([(GLIDESLOPE_X - 7, DATUM_Y), (GLIDESLOPE_X + 7, DATUM_Y)], WHITE, 2)
        for offset in (-58, -29, 29, 58):
            canvas.dot(GLIDESLOPE_X, DATUM_Y + offset, 2.6, outline=WHITE, width=1.5)
        y = DATUM_Y - clamp(glideslope, -1.2, 1.2) * 58.0
        canvas.polygon([(GLIDESLOPE_X, y - 7), (GLIDESLOPE_X + 8, y), (GLIDESLOPE_X, y + 7),
                        (GLIDESLOPE_X - 8, y)], fill=None, outline=MAGENTA, width=2)

    localizer = state.get("localizer")
    if localizer is not None:
        canvas.rect(Rect(ATTITUDE.cx - 72, LOCALIZER_Y - 10, 144, 20), fill=(0, 0, 0, 90))
        canvas.line([(ATTITUDE.cx, LOCALIZER_Y - 7), (ATTITUDE.cx, LOCALIZER_Y + 7)], WHITE, 2)
        for offset in (-58, -29, 29, 58):
            canvas.dot(ATTITUDE.cx + offset, LOCALIZER_Y, 3.0, outline=WHITE, width=1.5)
        x = ATTITUDE.cx + clamp(localizer, -1.2, 1.2) * 58.0
        canvas.polygon([(x - 7, LOCALIZER_Y), (x, LOCALIZER_Y - 8), (x + 7, LOCALIZER_Y),
                        (x, LOCALIZER_Y + 8)], fill=None, outline=MAGENTA, width=2)


def draw_radio_altitude(canvas: Canvas, state: dict) -> None:
    radio = state.get("radio_altitude")
    if radio is None:
        return
    value = int(round(radio / 10.0)) * 10 if radio >= 100 else int(round(radio))
    minimums = state.get("minimums")
    colour = AMBER if minimums is not None and radio <= minimums else WHITE
    canvas.rect(Rect(ATTITUDE.cx - 34, RADIO_ALTITUDE_Y - 15, 68, 30), fill=(0, 0, 0, 90))
    canvas.text(ATTITUDE.cx, RADIO_ALTITUDE_Y, str(value), 25, colour, anchor="mm", tracking=-0.8)


# ---------------------------------------------------------------------------
# Heading arc.
# ---------------------------------------------------------------------------
def compass_point(delta_degrees: float, radius: float) -> tuple[float, float]:
    angle = math.radians(delta_degrees * COMPASS_ARC_PER_DEGREE)
    return (COMPASS_CENTER[0] + radius * math.sin(angle),
            COMPASS_CENTER[1] - radius * math.cos(angle))


def draw_compass(canvas: Canvas, state: dict) -> None:
    heading = state["heading"]
    canvas.pieslice(COMPASS_CENTER[0], COMPASS_CENTER[1], COMPASS_RADIUS, 214, 326, TAPE_GREY + (235,))
    canvas.arc(COMPASS_CENTER[0], COMPASS_CENTER[1], COMPASS_RADIUS, 214, 326, WHITE, 2)

    first = int((heading - 45) // 5) * 5
    for tick in range(first, int(heading + 50), 5):
        delta = heading_delta(tick, heading)
        if abs(delta) > 40:
            continue
        # Numbers stop at thirty degrees, where the panel's own opaque cells
        # stop, so the sheet cannot promise labels the panel cannot draw.
        labelled = abs(delta) <= 30
        length = 14.0 if tick % 30 == 0 else (11.0 if tick % 10 == 0 else 7.0)
        inner = compass_point(delta, COMPASS_RADIUS - length)
        outer = compass_point(delta, COMPASS_RADIUS)
        canvas.line([inner, outer], WHITE, 2)
        if tick % 10 == 0 and labelled:
            label_point = compass_point(delta, COMPASS_RADIUS - 26)
            canvas.text(label_point[0], label_point[1], heading_label(tick), 17, WHITE, anchor="mm", tracking=-0.5)

    target = state.get("target_heading")
    if target is not None:
        delta = clamp(heading_delta(target, heading), -40.0, 40.0)
        tip = compass_point(delta, COMPASS_RADIUS - 1)
        left = compass_point(delta - 2.4, COMPASS_RADIUS + 12)
        right = compass_point(delta + 2.4, COMPASS_RADIUS + 12)
        canvas.polygon([tip, left, right], fill=MAGENTA)

    canvas.polygon([(ATTITUDE.cx - 8, COMPASS_TOP - 8), (ATTITUDE.cx + 8, COMPASS_TOP - 8),
                    (ATTITUDE.cx, COMPASS_TOP + 2)], fill=WHITE)
    # No heading box: the aircraft reads its heading from the arc under the
    # lubber line, and shows the selected heading in magenta below the rose.
    if target is not None:
        canvas.text(HEADING_READOUT.right, HEADING_READOUT.cy,
                    f"{int(round(target)) % 360:03d} H", 19, MAGENTA, anchor="rm", tracking=-0.5)
    canvas.text(MAG_LABEL_ZONE.cx, MAG_LABEL_ZONE.cy, "MAG", 17, GREEN, anchor="mm")

    if state.get("approach_reference"):
        canvas.text(APPROACH_REF.x, APPROACH_REF.cy, state["approach_reference"], 15, CYAN, anchor="lm")


# ---------------------------------------------------------------------------
# Selected values above the tapes.
# ---------------------------------------------------------------------------
def draw_selected_values(canvas: Canvas, state: dict) -> None:
    target = state.get("target_ias")
    if target is not None:
        text = state.get("target_ias_text") or f"{int(round(target)):d}"
        canvas.text(SELECTED_SPEED.x, SELECTED_SPEED.cy, text, 21, MAGENTA, anchor="lm", tracking=-0.6)
    target_altitude = state.get("target_altitude")
    if target_altitude is not None:
        canvas.text(SELECTED_ALTITUDE.right, SELECTED_ALTITUDE.cy, f"{int(round(target_altitude)):d}",
                    21, MAGENTA, anchor="rm", tracking=-0.6)


def draw_pfd(state: dict, scale: int = SUPERSAMPLE) -> Canvas:
    canvas = Canvas(WIDTH, HEIGHT, scale, BLACK)
    draw_fma(canvas, state)
    draw_selected_values(canvas, state)
    draw_attitude(canvas, state)
    draw_speed_tape(canvas, state)
    draw_altitude_tape(canvas, state)
    draw_vertical_speed(canvas, state)
    draw_compass(canvas, state)
    canvas.text(WIDTH - 8, HEIGHT - 8, "MuslimSim", 11, (110, 112, 120), anchor="rb", kind="regular")
    return canvas


# ---------------------------------------------------------------------------
# Offline / standby page.
# ---------------------------------------------------------------------------
def draw_offline(scale: int = SUPERSAMPLE) -> Canvas:
    canvas = Canvas(WIDTH, HEIGHT, scale, BLACK)
    canvas.round_rect(Rect(60, 120, 520, 240), 18, outline=AMBER, width=2)
    canvas.text(WIDTH / 2, 178, "MuslimSim PFD", 34, WHITE, anchor="mm")
    canvas.text(WIDTH / 2, 226, "SIMULATOR DATA UNAVAILABLE", 22, AMBER, anchor="mm")
    canvas.text(WIDTH / 2, 264, "Flight data is not being received.", 16, WHITE, anchor="mm", kind="regular")
    canvas.text(WIDTH / 2, 288, "The last flight frame is not shown as live.", 16, WHITE, anchor="mm", kind="regular")
    canvas.text(WIDTH / 2, 330, "Start X-Plane and the MuslimSim bridge", 15, CYAN, anchor="mm", kind="regular")
    canvas.text(WIDTH / 2, 420, "MuslimSim  -  WinCtrl PFP  -  B737 PFD", 14, (150, 152, 160),
                anchor="mm", kind="regular")
    return canvas


# ---------------------------------------------------------------------------
# Protected-zone map.
# ---------------------------------------------------------------------------
ZONES = (
    ("selected speed", SELECTED_SPEED, CYAN),
    ("selected altitude", SELECTED_ALTITUDE, CYAN),
    ("FMA A/T", FMA_COLUMNS[0], GREEN),
    ("FMA roll", FMA_COLUMNS[1], GREEN),
    ("FMA pitch", FMA_COLUMNS[2], GREEN),
    ("speed tape", SPEED_TAPE, AMBER),
    ("speed window", SPEED_WINDOW, MAGENTA),
    ("mach", MACH_ZONE, CYAN),
    ("attitude", ATTITUDE, AMBER),
    ("altitude tape", ALTITUDE_TAPE, AMBER),
    ("altitude window", ALTITUDE_WINDOW, MAGENTA),
    ("V/S scale", VS_SCALE, AMBER),
    ("selected heading", HEADING_READOUT, MAGENTA),
    ("MAG", MAG_LABEL_ZONE, GREEN),
    ("minimums", MINIMUMS_ZONE, CYAN),
    ("baro", BARO_ZONE, CYAN),
    ("approach ref", APPROACH_REF, CYAN),
)


ZONE_HEADER = 34
ZONE_FOOTER = 26


def draw_zone_map(state: dict, scale: int = SUPERSAMPLE) -> Canvas:
    """The PFD dimmed under its zone rectangles, with a header and footer."""
    base = draw_pfd(state, scale)
    base.img.alpha_composite(Image.new("RGBA", base.img.size, (0, 0, 0, 170)))

    for name, rect, colour in ZONES:
        base.rect(rect, outline=colour + (255,), width=1)
        label = f"{name}  {int(rect.x)},{int(rect.y)}  {int(rect.width)}x{int(rect.height)}"
        label_width = base.text_width(label, 9, kind="regular")
        label_x = clamp(rect.x, 3.0, WIDTH - label_width - 3.0)
        label_y = rect.y - 6 if rect.y > 14 else rect.y + 8
        base.text(label_x, label_y, label, 9, colour, anchor="lm", kind="regular")

    sheet = Canvas(WIDTH, HEIGHT + ZONE_HEADER + ZONE_FOOTER, scale, (14, 15, 20))
    sheet.img.alpha_composite(base.img, (0, ZONE_HEADER * scale))
    sheet.text(12, ZONE_HEADER / 2.0, "MuslimSim B737 PFD  -  640x480 protected zone map", 15, WHITE)
    sheet.text(WIDTH - 12, ZONE_HEADER / 2.0, "tools/build_pfd_design_png.py", 11, (140, 142, 150),
               anchor="rm", kind="regular")
    sheet.text(12, HEIGHT + ZONE_HEADER + ZONE_FOOTER / 2.0,
               f"datum y={int(DATUM_Y)}    speed {PX_PER_KNOT:g} px/kt    altitude {PX_PER_FOOT:g} px/ft    "
               f"pitch {PX_PER_PITCH_DEGREE:g} px/deg    compass {COMPASS_ARC_PER_DEGREE:g} arc-deg per "
               f"heading deg", 11, (185, 187, 195), anchor="lm", kind="regular")
    return sheet


# ---------------------------------------------------------------------------
# Design scenarios.
# ---------------------------------------------------------------------------
def base_state() -> dict:
    return {
        "ias": 175.0,
        "altitude": 2400.0,
        "vertical_speed": 600.0,
        "pitch": 5.0,
        "roll": 12.5,
        "slip": 0.15,
        "heading": 320.0,
        "target_ias": 200.0,
        "target_altitude": 2800.0,
        "target_heading": 350.0,
        "speed_trend": 9.0,
        "min_speed": 132.0,
        "vmo": 340.0,
        "mach": "",
        "baro": "29.92 IN",
        "fd_visible": True,
        "fd_pitch": 6.4,
        "fd_roll": 9.0,
        "command": "CMD",
        "fma_active": ("N1", "LNAV", "VNAV SPD"),
        "fma_armed": ("", "", "VNAV PTH"),
        "fma_boxed": 2,
        "speed_marks": ({"speed": 158.0, "label": "R", "colour": GREEN},
                        {"speed": 148.0, "label": "1", "colour": GREEN}),
    }


def scenario_climb() -> dict:
    return base_state()


def scenario_cruise() -> dict:
    state = base_state()
    state.update({
        "ias": 282.0,
        "altitude": 28000.0,
        "vertical_speed": -1800.0,
        "pitch": -3.0,
        "roll": -18.0,
        "slip": -0.1,
        "heading": 5.0,
        "target_ias": 0.78,
        "target_ias_text": ".78",
        "target_altitude": 12000.0,
        "target_heading": 350.0,
        "speed_trend": -14.0,
        "min_speed": 218.0,
        "vmo": 330.0,
        "mach": ".784",
        "baro": "STD",
        "fd_pitch": -2.0,
        "fd_roll": -12.0,
        "fma_active": ("MCP SPD", "LNAV", "VNAV PTH"),
        "fma_armed": ("", "", "ALT ACQ"),
        "fma_boxed": 0,
        "speed_marks": (),
        "vs_selected": False,
    })
    return state


def scenario_approach() -> dict:
    state = base_state()
    state.update({
        "ias": 141.0,
        "altitude": 780.0,
        "vertical_speed": -700.0,
        "pitch": -1.2,
        "roll": -2.5,
        "slip": 0.05,
        "heading": 90.0,
        "target_ias": 145.0,
        "target_altitude": 2000.0,
        "target_heading": 92.0,
        "speed_trend": -4.0,
        "min_speed": 126.0,
        "vmo": 250.0,
        "mach": "",
        "baro": "29.92 IN",
        "fd_pitch": -1.0,
        "fd_roll": -3.0,
        "command": "CMD",
        "autoland": "LAND 3",
        "fma_active": ("MCP SPD", "VOR LOC", "G/S"),
        "fma_armed": ("", "", ""),
        "fma_boxed": None,
        "glideslope": 0.35,
        "localizer": -0.2,
        "radio_altitude": 440.0,
        "minimums": 540.0,
        "minimums_label": "RADIO   200",
        "field_elevation": 340.0,
        "approach_reference": "ILS  110.30   DME 5.4",
        "speed_marks": ({"speed": 138.0, "label": "REF", "colour": GREEN},),
    })
    return state


SCENARIOS = {
    "climb": ("pfd-737-climb", scenario_climb, "Take-off climb, LNAV/VNAV, MCP 200 kt and 2800 ft."),
    "cruise": ("pfd-737-descent", scenario_cruise, "High-level descent, Mach and STD baro presentation."),
    "approach": ("pfd-737-approach", scenario_approach, "ILS approach, LAND 3, glideslope and localizer."),
}


def write_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG", optimize=True)
    print(f"  {path.name:<28} {image.width}x{image.height}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=tuple(SCENARIOS) + ("offline", "zones"),
                        help="Build a single sheet instead of the whole set.")
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR, help="Output folder (default: PNG/).")
    args = parser.parse_args()

    wanted = (args.only,) if args.only else tuple(SCENARIOS) + ("offline", "zones")
    print(f"MuslimSim B737 PFD design sheets -> {args.out}")

    for name in wanted:
        if name in SCENARIOS:
            stem, builder, _ = SCENARIOS[name]
            canvas = draw_pfd(builder())
            write_png(canvas.finish(1), args.out / f"{stem}.png")
            write_png(canvas.finish(2), args.out / f"{stem}-2x.png")
        elif name == "offline":
            canvas = draw_offline()
            write_png(canvas.finish(1), args.out / "pfd-737-offline.png")
            write_png(canvas.finish(2), args.out / "pfd-737-offline-2x.png")
        elif name == "zones":
            canvas = draw_zone_map(scenario_climb())
            write_png(canvas.finish(2), args.out / "pfd-737-zone-map-2x.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
