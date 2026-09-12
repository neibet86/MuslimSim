"""Photo-based 2-D Studio faceplate for the WINCTRL 32 AGP Metal.

The approved panel geometry stays photo-derived. The CHR/UTC/ET windows now
have exactly two bridge-owned operating modes:

``radio``       fallback COM/transponder head.
``navigation``  selected MCP speed / altitude / heading head.

TERR ON ND is the only native mode switch. Studio follows the bridge-owned
mode; there is no independent clock/display-page toggle that can drift away
from the physical AGP.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

AGP_REFERENCE_SIZE: Tuple[int, int] = (900, 660)

PANEL_FACE = "#4c5560"
PANEL_EDGE = "#22262b"
PANEL_INNER = "#464f59"
LEGEND = "#f0a93c"
SEPARATOR = "#f0a93c"
SCREEN_BG = "#04080c"
SCREEN_EDGE = "#141a20"
SCREEN_BLUE = "#7fc4ff"
GEAR_GREEN = "#2ad07a"
GEAR_GLASS = "#0d2318"
KNOB = "#eceade"
KNOB_EDGE = "#a9a698"
BUTTON_FACE = "#14181c"
BUTTON_EDGE = "#5d6873"
LAMP_OFF = "#1b2026"
LAMP_ON = "#ffb648"
METAL = "#cfc8b4"
METAL_EDGE = "#7d786a"


@dataclass(frozen=True)
class Rect:
    name: str
    x1: float
    y1: float
    x2: float
    y2: float

    def overlaps(self, other: "Rect", gap: float = 0.0) -> bool:
        return not (
            self.x2 + gap <= other.x1 or other.x2 + gap <= self.x1
            or self.y2 + gap <= other.y1 or other.y2 + gap <= self.y1
        )


# Label reservations, deliberately separate from every clickable box.  The
# validator below catches a future move that puts text through a screen, knob,
# switch or another label.
AGP_LABEL_REGIONS: Tuple[Rect, ...] = (
    Rect("ldg_gear", 366, 26, 508, 54),
    Rect("brk_fan", 726, 26, 838, 54),
    Rect("auto_brk", 366, 182, 494, 210),
    Rect("askid", 706, 176, 858, 232),
    Rect("lo", 306, 214, 352, 238),
    Rect("med", 386, 214, 446, 238),
    Rect("max", 494, 214, 544, 238),
    Rect("terr", 738, 330, 862, 362),
    Rect("chr_label", 448, 330, 514, 354),
    Rect("utc_label", 448, 424, 514, 448),
    Rect("et_label", 430, 568, 532, 596),
    Rect("rst_label", 262, 328, 310, 352),
    Rect("set_label", 262, 462, 312, 486),
    Rect("chr_knob_label", 646, 326, 702, 348),
    Rect("gear_updown", 60, 300, 132, 610),
)
AGP_CONTROL_REGIONS: Tuple[Rect, ...] = (
    Rect("gear_screen", 286, 60, 640, 150),
    Rect("brk_fan_button", 736, 60, 826, 146),
    Rect("autobrake_lo_med", 296, 244, 452, 316),
    Rect("autobrake_max", 484, 244, 562, 316),
    Rect("askid_switch", 700, 240, 790, 320),
    Rect("chr_screen", 396, 358, 566, 412),
    Rect("utc_screen", 396, 452, 566, 506),
    Rect("et_screen", 396, 508, 566, 562),
    Rect("rst_knob", 250, 356, 330, 436),
    Rect("date_knob", 250, 490, 330, 570),
    Rect("chr_knob", 636, 352, 700, 416),
    Rect("utc_selector", 632, 432, 718, 504),
    Rect("timer_selector", 632, 516, 718, 588),
    Rect("terr_button", 762, 370, 842, 446),
    Rect("gear_lever", 24, 300, 56, 620),
)


def validate_reserved_regions(
    labels: Sequence[Rect], controls: Sequence[Rect], *, gap: float = 1.0
) -> None:
    for i, left in enumerate(labels):
        for right in labels[i + 1:]:
            if left.overlaps(right, gap):
                raise AssertionError(f"label collision: {left.name}/{right.name}")
        for control in controls:
            if left.overlaps(control, gap):
                raise AssertionError(
                    f"label/control collision: {left.name}/{control.name}"
                )


validate_reserved_regions(AGP_LABEL_REGIONS, AGP_CONTROL_REGIONS)


# --------------------------------------------------------------------------
# Shared helpers, the same shapes the HOWALT faceplates use.
# --------------------------------------------------------------------------

def _fit(width: int, height: int, ref: Tuple[int, int]) -> Tuple[float, float, float]:
    rw, rh = ref
    scale = min(max(1, width - 24) / rw, max(1, height - 24) / rh)
    scale = max(0.45, scale)
    return (width - rw * scale) / 2.0, (height - rh * scale) / 2.0, scale


def _xy(ox: float, oy: float, s: float, x: float, y: float) -> Tuple[float, float]:
    return ox + x * s, oy + y * s


def _tag(studio: Any, canvas: Any, item: int, key: str) -> None:
    try:
        studio._tag(canvas, item, key)
    except Exception:
        try:
            canvas.addtag_withtag(f"control:{key}", item)
        except Exception:
            pass


def _control_color(studio: Any, key: str) -> str:
    try:
        return studio._control_color(key)
    except Exception:
        return "#5aa9ff"


def _control_fill(studio: Any, key: str, default: str) -> str:
    try:
        return studio._control_fill(key, default)
    except Exception:
        return default


def _mirror(studio: Any, device_key: str) -> Dict[str, Any]:
    try:
        value = studio._device_mirror(device_key)
    except Exception:
        value = {}
    if not isinstance(value, Mapping):
        return {}
    result = dict(value)
    nested = result.get("mirror")
    if isinstance(nested, Mapping):
        result.update(dict(nested))
    return result


def _text(canvas: Any, x: float, y: float, text: str, scale: float, *,
          size: int = 10, anchor: str = "center", fill: str = LEGEND,
          weight: str = "bold") -> int:
    font = ("Segoe UI Semibold" if weight == "bold" else "Segoe UI",
            max(6, int(size * scale)))
    return canvas.create_text(
        x, y, text=text, fill=fill, font=font, anchor=anchor
    )


def _screw(canvas: Any, x: float, y: float, scale: float) -> None:
    r = 9 * scale
    canvas.create_oval(x - r, y - r, x + r, y + r,
                       fill="#2a2e33", outline="#0a0c0e", width=1)
    canvas.create_line(x - r * .65, y + r * .28, x + r * .65, y - r * .28,
                       fill="#828a92", width=max(1, int(2 * scale)))


def _screen(canvas: Any, cx: float, cy: float, w: float, h: float,
            value: str, scale: float, *, size: int = 26,
            fill: str = SCREEN_BLUE) -> None:
    x1, y1, x2, y2 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    canvas.create_round_rect(x1, y1, x2, y2, radius=max(3, 5 * scale),
                             fill=SCREEN_EDGE, outline="#0b0e12", width=2)
    inset = 5 * scale
    canvas.create_round_rect(x1 + inset, y1 + inset, x2 - inset, y2 - inset,
                             radius=max(2, 3 * scale), fill=SCREEN_BG,
                             outline="#02040a", width=1)
    display = str(value or "").strip()
    if not display:
        display = "----"
    canvas.create_text(cx, cy, text=display, fill=fill,
                       font=("Consolas", max(11, int(size * scale)), "bold"))


def _square_button(studio: Any, canvas: Any, cx: float, cy: float,
                   w: float, h: float, key: str, scale: float, *,
                   lit: bool = False, label: str = "") -> None:
    color = _control_color(studio, key)
    fill = LAMP_ON if lit else _control_fill(studio, key, BUTTON_FACE)
    item = canvas.create_round_rect(
        cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2,
        radius=max(2, 4 * scale), fill=fill,
        outline=color if lit else BUTTON_EDGE, width=max(1, int(2 * scale)),
    )
    _tag(studio, canvas, item, key)
    if label:
        t = canvas.create_text(cx, cy, text=label,
                               fill="#101418" if lit else "#8a949e",
                               font=("Segoe UI Semibold", max(6, int(9 * scale))))
        _tag(studio, canvas, t, key)


def _press_rotary(studio: Any, canvas: Any, cx: float, cy: float, r: float,
                  scale: float, *, raw: int, dec: str, press: str,
                  inc: str) -> None:
    """White round encoder with a recessed channel and a travelling ball.

    The AGP encoders are relative like the HOWALT ones, so the ball shows
    accumulated movement, not an absolute shaft angle.
    """
    canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                       fill="#2b3037", outline="#171b1f", width=max(1, int(2 * scale)))
    body = canvas.create_oval(cx - r * .82, cy - r * .82, cx + r * .82, cy + r * .82,
                              fill=_control_fill(studio, press, KNOB),
                              outline=KNOB_EDGE, width=max(1, int(2 * scale)))
    _tag(studio, canvas, body, press)
    # The channel the ball runs in.
    cr = r * .62
    canvas.create_oval(cx - cr, cy - cr, cx + cr, cy + cr,
                       fill="", outline="#b3ae9c", width=max(1, int(1.5 * scale)))
    angle = math.radians(-90.0 + (int(raw) % 24) * 15.0)
    bx, by = cx + cr * math.cos(angle), cy + cr * math.sin(angle)
    br = max(2.0, r * .16)
    canvas.create_oval(bx - br, by - br, bx + br, by + br,
                       fill=_control_color(studio, press), outline="#2b2b2b", width=1)
    # Two hit targets for the directions, drawn as thin arcs either side.
    for key, start in ((dec, 150), (inc, 30)):
        item = canvas.create_arc(
            cx - r, cy - r, cx + r, cy + r, start=start, extent=60,
            style="arc", outline=_control_color(studio, key),
            width=max(2, int(3 * scale)),
        )
        _tag(studio, canvas, item, key)


def _three_way(studio: Any, canvas: Any, cx: float, cy: float, h: float,
               scale: float, keys: Tuple[str, str, str],
               labels: Tuple[str, str, str], active: int) -> None:
    """Vertical three-position paddle: up / centre / down."""
    w = h * 0.42
    canvas.create_round_rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2,
                             radius=max(3, 6 * scale), fill="#20252b",
                             outline="#0e1115", width=max(1, int(2 * scale)))
    step = h / 3.0
    for index, (key, label) in enumerate(zip(keys, labels)):
        y = cy - step + index * step
        on = index == active
        item = canvas.create_round_rect(
            cx - w * .38, y - step * .38, cx + w * .38, y + step * .38,
            radius=max(2, 3 * scale),
            fill=METAL if on else "#333a41",
            outline=_control_color(studio, key) if on else METAL_EDGE,
            width=max(1, int(2 * scale)),
        )
        _tag(studio, canvas, item, key)
        t = _text(canvas, cx + w * .78, y, label, scale, size=9,
                  anchor="w", fill=LEGEND if on else "#9aa3ac")
        _tag(studio, canvas, t, key)


def _metal_toggle(studio: Any, canvas: Any, cx: float, cy: float, h: float,
                  scale: float, on_key: str, off_key: str, *, on: bool) -> None:
    """The A/SKID metal toggle: a bat handle leaning to ON or OFF."""
    base = h * 0.34
    canvas.create_oval(cx - base, cy - base * .62, cx + base, cy + base * .62,
                       fill="#918a76", outline="#4d493f",
                       width=max(1, int(2 * scale)))
    lean = -1.0 if on else 1.0
    tipx = cx + lean * h * 0.30
    tipy = cy - h * 0.34
    canvas.create_line(cx, cy, tipx, tipy, fill=METAL,
                       width=max(3, int(7 * scale)), capstyle="round")
    tip = max(3.0, h * .13)
    item = canvas.create_oval(tipx - tip, tipy - tip, tipx + tip, tipy + tip,
                              fill=METAL, outline=METAL_EDGE,
                              width=max(1, int(2 * scale)))
    _tag(studio, canvas, item, on_key if on else off_key)
    hit_on = canvas.create_rectangle(cx - h * .5, cy - h * .62, cx + h * .5, cy,
                                     fill="", outline="")
    _tag(studio, canvas, hit_on, on_key)
    hit_off = canvas.create_rectangle(cx - h * .5, cy, cx + h * .5, cy + h * .5,
                                      fill="", outline="")
    _tag(studio, canvas, hit_off, off_key)


# --------------------------------------------------------------------------
# The faceplate
# --------------------------------------------------------------------------

def _values(mirror: Mapping[str, Any]) -> Tuple[str, str, str]:
    shown = list(mirror.get("values") or ())
    if len(shown) != 3:
        return ("----", "------", "----")
    return (str(shown[0]), str(shown[1]), str(shown[2]))


def _controls(mirror: Mapping[str, Any]) -> Dict[str, Any]:
    value = mirror.get("controls")
    return dict(value) if isinstance(value, Mapping) else {}


def _rotary_raw(mirror: Mapping[str, Any]) -> Dict[str, int]:
    raw = mirror.get("rotary_raw")
    out = {"rst": 0, "chr": 0, "date": 0}
    if isinstance(raw, Mapping):
        for name in out:
            try:
                out[name] = int(raw.get(name, 0))
            except Exception:
                pass
    return out


def agp_display_mode(
    studio: Any, mirror: Optional[Mapping[str, Any]] = None
) -> str:
    """Return the bridge-owned RADIO/NAV mode shown by the real panel."""
    if isinstance(mirror, Mapping):
        page = str(mirror.get("page") or "").strip().lower()
        if page == "navigation":
            return "navigation"
        if page == "radio":
            return "radio"
    # Radio is the useful and safe fallback when no mirror has arrived yet.
    return "radio"


def draw_agp_faceplate(studio: Any, canvas: Any, width: int, height: int) -> None:
    mirror = _mirror(studio, "agp_bb80")
    controls = _controls(mirror)
    raws = _rotary_raw(mirror)
    mode = agp_display_mode(studio, mirror)

    ox, oy, s = _fit(width, height, AGP_REFERENCE_SIZE)

    def p(x: float, y: float) -> Tuple[float, float]:
        return _xy(ox, oy, s, x, y)

    gear = str(controls.get("gear", "DOWN")).upper()
    autobrake = str(controls.get("autobrake", "OFF")).upper()
    brake_fan = bool(controls.get("brake_fan", False))
    anti_skid = bool(controls.get("anti_skid", True))
    terrain = mode == "navigation"

    # ---- main panel body -------------------------------------------------
    x1, y1 = p(200, 8)
    x2, y2 = p(880, 622)
    canvas.create_round_rect(x1, y1, x2, y2, radius=max(6, 26 * s),
                             fill=PANEL_FACE, outline=PANEL_EDGE,
                             width=max(2, int(4 * s)))
    ix1, iy1 = p(214, 20)
    ix2, iy2 = p(866, 610)
    canvas.create_round_rect(ix1, iy1, ix2, iy2, radius=max(5, 20 * s),
                             fill=PANEL_INNER, outline="#5c6672",
                             width=max(1, int(2 * s)))
    for sx, sy in ((228, 36), (852, 36), (228, 594), (852, 594)):
        _screw(canvas, *p(sx, sy), s)

    # ---- LDG GEAR --------------------------------------------------------
    _text(canvas, *p(437, 40), "LDG GEAR", s, size=17)
    gx1, gy1 = p(286, 60)
    gx2, gy2 = p(640, 150)
    canvas.create_round_rect(gx1, gy1, gx2, gy2, radius=max(2, 4 * s),
                             fill=GEAR_GLASS, outline="#1d3a2b",
                             width=max(1, int(2 * s)))
    down = gear != "UP"
    for index in range(3):
        cx, cy = p(345 + index * 88, 105)
        item = canvas.create_polygon(
            cx - 26 * s, cy - 16 * s, cx + 26 * s, cy - 16 * s, cx, cy + 20 * s,
            fill=GEAR_GREEN if down else "#0f2a1e",
            outline=GEAR_GREEN if down else "#20402f", width=max(1, int(2 * s)),
        )
        _tag(studio, canvas, item, "gear_down" if down else "gear_up")
    hit = canvas.create_rectangle(gx1, gy1, gx2, gy2, fill="", outline="")
    _tag(studio, canvas, hit, "gear_down" if down else "gear_up")

    # ---- BRK FAN ---------------------------------------------------------
    _text(canvas, *p(781, 40), "BRK FAN", s, size=17)
    _square_button(studio, canvas, *p(781, 103), 90 * s, 86 * s,
                   "brake_fan_on" if not brake_fan else "brake_fan_off", s,
                   lit=brake_fan)
    canvas.create_line(*p(694, 28), *p(694, 152),
                       fill=SEPARATOR, width=max(1, int(2 * s)))

    # ---- separator -------------------------------------------------------
    canvas.create_line(*p(238, 168), *p(842, 168),
                       fill=SEPARATOR, width=max(1, int(2 * s)))

    # ---- AUTO BRK --------------------------------------------------------
    _text(canvas, *p(430, 196), "AUTO BRK", s, size=17)
    _text(canvas, *p(329, 226), "LO", s, size=12)
    _text(canvas, *p(416, 226), "MED", s, size=12)
    _text(canvas, *p(519, 226), "MAX", s, size=12)
    _square_button(studio, canvas, *p(335, 280), 76 * s, 70 * s,
                   "autobrake_low", s, lit=autobrake == "LOW")
    _square_button(studio, canvas, *p(413, 280), 76 * s, 70 * s,
                   "autobrake_med", s, lit=autobrake == "MED")
    _square_button(studio, canvas, *p(523, 280), 76 * s, 70 * s,
                   "autobrake_max", s, lit=autobrake == "MAX")

    # ---- A/SKID & N/W STRG ----------------------------------------------
    _text(canvas, *p(782, 190), "A/SKID&", s, size=15)
    _text(canvas, *p(782, 216), "N/W STRG", s, size=15)
    _metal_toggle(studio, canvas, *p(745, 282), 78 * s, s,
                  "anti_skid_on", "anti_skid_off", on=anti_skid)
    _text(canvas, *p(800, 254), "ON", s, size=12, anchor="w")
    _text(canvas, *p(800, 312), "OFF", s, size=12, anchor="w")
    canvas.create_line(*p(694, 176), *p(694, 320),
                       fill=SEPARATOR, width=max(1, int(2 * s)))

    # ---- separator -------------------------------------------------------
    canvas.create_line(*p(238, 322), *p(720, 322),
                       fill=SEPARATOR, width=max(1, int(2 * s)))

    # ---- chronometer / radio sub-panel -----------------------------------
    sx1, sy1 = p(238, 334)
    sx2, sy2 = p(724, 600)
    canvas.create_round_rect(sx1, sy1, sx2, sy2, radius=max(5, 18 * s),
                             fill="#3f4852", outline="#5c6672",
                             width=max(1, int(2 * s)))

    chr_text, utc_text, et_text = _values(mirror)
    if mode == "navigation":
        top_label, mid_label, bottom_label = "SPD", "ALT", "HDG"
        sub_top = ("MCP", "KTS/MACH")
        sub_mid = ("SELECTED", "", "FT")
        sub_bottom = ("SELECTED", "DEG")
        rst_role, set_role, chr_role = "SPD", "HDG", "ALT"
    else:
        try:
            digit = int(mirror.get("squawk_digit", 0)) % 4 + 1
        except Exception:
            digit = 1
        squawk_editing = bool(mirror.get("squawk_editing", False))
        top_label, mid_label, bottom_label = (
            "RADIO", "FREQ",
            f"ATC D{digit}" if squawk_editing else "ATC",
        )
        sub_top = ("VHF", "D#")
        sub_mid = ("MHz", "", "STBY")
        sub_bottom = ("SQUAWK", "CODE")
        rst_role, set_role, chr_role = "FINE/XFR", "ATC", "COARSE"

    _text(canvas, *p(481, 342), top_label, s, size=13)
    _screen(canvas, *p(481, 385), 170 * s, 54 * s, chr_text, s, size=26)
    _text(canvas, *p(420, 418), sub_top[0], s, size=9, fill="#c9d2da")
    _text(canvas, *p(542, 418), sub_top[1], s, size=9, fill="#c9d2da")

    _text(canvas, *p(481, 436), mid_label, s, size=13)
    _screen(canvas, *p(481, 479), 170 * s, 54 * s, utc_text, s, size=26)
    _text(canvas, *p(414, 512), sub_mid[0], s, size=8, fill="#c9d2da")
    _text(canvas, *p(481, 512), sub_mid[1], s, size=8, fill="#c9d2da")
    _text(canvas, *p(548, 512), sub_mid[2], s, size=8, fill="#c9d2da")

    _screen(canvas, *p(481, 546), 170 * s, 50 * s, et_text, s, size=24)
    _text(canvas, *p(481, 582), bottom_label, s, size=13)
    _text(canvas, *p(396, 582), sub_bottom[0], s, size=9, anchor="w",
          fill="#c9d2da")
    _text(canvas, *p(566, 582), sub_bottom[1], s, size=9, anchor="e",
          fill="#c9d2da")

    # left encoders
    _text(canvas, *p(286, 340), f"RST / {rst_role}", s, size=11)
    _press_rotary(studio, canvas, *p(290, 396), 40 * s, s,
                  raw=raws["rst"], dec="rst_ccw", press="rst", inc="rst_cw")
    _text(canvas, *p(287, 474), f"SET / {set_role}", s, size=11)
    _press_rotary(studio, canvas, *p(290, 530), 40 * s, s,
                  raw=raws["date"], dec="date_ccw", press="date_press",
                  inc="date_cw")

    # right encoder and the two paddles
    _text(canvas, *p(674, 337), f"CHR / {chr_role}", s, size=11)
    _press_rotary(studio, canvas, *p(668, 384), 32 * s, s,
                  raw=raws["chr"], dec="chr_left", press="chr_press",
                  inc="chr_right")
    try:
        vhf = int(mirror.get("vhf", controls.get("vhf", 1)) or 1)
    except Exception:
        vhf = 1
    _three_way(
        studio, canvas, *p(668, 468), 72 * s, s,
        ("utc_gps", "utc_int", "utc_set"), ("GPS", "INT", "SET"),
        {1: 0, 2: 1, 3: 2}.get(vhf, 0) if mode == "radio" else 1,
    )
    xpdr_mode = str(
        mirror.get("xpdr_mode", controls.get("xpdr_mode", "off"))
        or "off"
    ).lower()
    _three_way(
        studio, canvas, *p(668, 552), 72 * s, s,
        ("timer_run", "timer_stop", "timer_reset"),
        ("RUN", "STP", "RST"),
        0 if xpdr_mode == "stby" else 1,
    )
    xpdr_label = {
        "stby": "ATC: STBY",
        "off": "ATC: ALT OFF",
        "on": "ATC: ALT ON",
        "ta": "ATC: TA",
        "tara": "ATC: TA/RA",
    }.get(xpdr_mode, "ATC")
    _text(canvas, *p(668, 614), xpdr_label, s, size=9, fill="#d6e0ee")

    # ---- TERR ON ND ------------------------------------------------------
    _text(canvas, *p(800, 344), "TERR ON ND", s, size=14)
    _square_button(studio, canvas, *p(802, 408), 80 * s, 76 * s,
                   "terr_on_nd", s, lit=terrain)

    # ---- bridge-owned mode status ----------------------------------------
    # Informational only. TERR ON ND above is the only mode control.
    _text(
        canvas, *p(316, 619),
        f"MODE: {'NAV' if mode == 'navigation' else 'RADIO'}  •  TERR ON ND",
        s, size=9, fill="#d6e0ee",
    )

    # ---- landing gear lever ---------------------------------------------
    lx1, ly1 = p(24, 300)
    lx2, ly2 = p(190, 640)
    canvas.create_round_rect(lx1, ly1, lx2, ly2, radius=max(5, 18 * s),
                             fill=PANEL_FACE, outline=PANEL_EDGE,
                             width=max(2, int(4 * s)))
    canvas.create_round_rect(*p(38, 316), *p(176, 624), radius=max(4, 14 * s),
                             fill=PANEL_INNER, outline="#5c6672",
                             width=max(1, int(2 * s)))
    _screw(canvas, *p(58, 332), s)
    _screw(canvas, *p(156, 610), s)
    slot_x1, slot_y1 = p(52, 336)
    slot_x2, slot_y2 = p(92, 552)
    canvas.create_round_rect(slot_x1, slot_y1, slot_x2, slot_y2,
                             radius=max(3, 8 * s), fill="#101418",
                             outline="#2b3138", width=max(1, int(2 * s)))
    _text(canvas, *p(133, 330), "UP", s, size=14)
    up_item = canvas.create_polygon(
        *p(133, 352), *p(148, 384), *p(140, 384), *p(140, 452),
        *p(126, 452), *p(126, 384), *p(118, 384),
        fill="", outline=LEGEND, width=max(1, int(2 * s)),
    )
    _tag(studio, canvas, up_item, "gear_up")
    down_item = canvas.create_polygon(
        *p(133, 596), *p(148, 564), *p(140, 564), *p(140, 496),
        *p(126, 496), *p(126, 564), *p(118, 564),
        fill="", outline=LEGEND, width=max(1, int(2 * s)),
    )
    _tag(studio, canvas, down_item, "gear_down")
    _text(canvas, *p(133, 612), "DOWN", s, size=14)
    lever_y = 366 if gear == "UP" else 524
    lcx, lcy = p(72, lever_y)
    canvas.create_line(lcx, lcy, *p(72, lever_y + (60 if gear == "UP" else -60)),
                       fill="#9aa2aa", width=max(3, int(9 * s)), capstyle="round")
    knob_r = max(4.0, 15 * s)
    lever = canvas.create_oval(lcx - knob_r, lcy - knob_r, lcx + knob_r, lcy + knob_r,
                               fill="#d8d3c4", outline="#6f6a5e",
                               width=max(1, int(2 * s)))
    _tag(studio, canvas, lever, "gear_up" if gear != "UP" else "gear_down")


MUSLIMSIM_AGP_FACEPLATE_V1 = True

MUSLIMSIM_AGP_RADIO_NAV_V2_FACEPLATE = True

MUSLIMSIM_AGP_RADIO_NAV_V2_2_FACEPLATE = True

MUSLIMSIM_AGP_RADIO_NAV_V2_3_FACEPLATE = True
