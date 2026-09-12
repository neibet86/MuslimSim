"""Photo-based 2-D Studio faceplates for MUSLIMRTP and MUSLIMATC V4.

All coordinates are authored in fixed reference spaces based on the owner's
D201/D203 photographs.  The whole faceplate scales uniformly; individual
labels do not reflow into controls or separator lines.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from .howalt_v4_protocol import prepare_display_payload


D201_REFERENCE_SIZE: Tuple[int, int] = (760, 666)
D203_REFERENCE_SIZE: Tuple[int, int] = (888, 472)

PANEL_FACE = "#565765"
PANEL_EDGE = "#292a31"
LEGEND = "#ffc66d"
SCREEN_BG = "#03070d"
SCREEN_EDGE = "#171d29"
SCREEN_BLUE = "#91baff"
KNOB = "#e7e0c6"
KNOB_EDGE = "#aca58e"
BUTTON_FACE = "#090b0e"
BUTTON_EDGE = "#5a5b62"
LAMP_OFF = "#d1d2ca"
LAMP_ON = "#ff8a32"


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


# Authored label reservations.  They are deliberately separate from every
# clickable/control box.  This validator catches accidental future moves that
# put text through a knob, screen, screw, separator, or another label.
D201_LABEL_REGIONS: Tuple[Rect, ...] = (
    Rect("active_top", 188, 8, 307, 31),
    Rect("standby_top", 502, 8, 646, 31),
    Rect("pnl", 29, 126, 54, 194),
    Rect("hf_sens", 62, 307, 165, 329),
    Rect("vhf", 548, 205, 598, 229),
    Rect("active_nav", 190, 349, 308, 369),
    Rect("standby_nav", 500, 349, 647, 369),
    Rect("ter", 350, 370, 410, 388),
    Rect("nav", 29, 442, 55, 530),
    Rect("test_nav", 166, 487, 259, 511),
)
D201_CONTROL_REGIONS: Tuple[Rect, ...] = (
    Rect("screen1", 80, 35, 330, 120),
    Rect("screen2", 430, 35, 680, 120),
    Rect("transfer1", 351, 58, 409, 111),
    Rect("off", 72, 145, 141, 196),
    Rect("hf_knob", 63, 212, 162, 304),
    Rect("radio_keys", 208, 144, 520, 332),
    Rect("vhf_test", 548, 144, 623, 195),
    Rect("vhf_knob", 608, 214, 720, 324),
    Rect("screen3", 80, 378, 330, 457),
    Rect("screen4", 430, 378, 680, 457),
    Rect("transfer2", 351, 393, 409, 447),
    Rect("nav_test", 178, 523, 243, 590),
    Rect("nav_knob", 607, 520, 722, 640),
)
D201_DECOR_REGIONS: Tuple[Rect, ...] = (
    Rect("seam", 0, 337, 760, 347),
)

D203_LABEL_REGIONS: Tuple[Rect, ...] = (
    Rect("xpndr_12", 108, 12, 206, 42),
    Rect("xpndr_label", 110, 159, 217, 187),
    Rect("alt_12", 110, 216, 205, 246),
    Rect("alt_label", 92, 394, 230, 425),
    Rect("xpndr_top", 360, 12, 452, 42),
    Rect("fail_top", 510, 12, 572, 42),
    Rect("ident", 411, 280, 502, 309),
    Rect("atc", 7, 185, 48, 275),
    Rect("tcas", 839, 170, 883, 280),
)
D203_CONTROL_REGIONS: Tuple[Rect, ...] = (
    Rect("xpndr_src", 103, 48, 210, 153),
    Rect("alt_src", 105, 250, 211, 360),
    Rect("screen", 333, 70, 565, 270),
    Rect("mode", 668, 52, 835, 220),
    Rect("ident_button", 420, 315, 487, 382),
    Rect("left_encoder", 277, 337, 392, 454),
    Rect("right_encoder", 581, 337, 696, 454),
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
                raise AssertionError(f"label/control collision: {left.name}/{control.name}")


validate_reserved_regions(D201_LABEL_REGIONS, D201_CONTROL_REGIONS + D201_DECOR_REGIONS)
validate_reserved_regions(D203_LABEL_REGIONS, D203_CONTROL_REGIONS)


def active_digit_bits(mask: int) -> Tuple[int, ...]:
    return tuple(bit for bit in range(7, -1, -1) if int(mask) & (1 << bit))


def visual_display_text(state: Mapping[str, Any], fallback: str = "") -> str:
    try:
        if int(state.get("brightness", 1) or 0) <= 0:
            return fallback
    except (TypeError, ValueError):
        pass
    mask = int(state.get("mask", 0xFF) or 0xFF) & 0xFF
    points = int(state.get("points", 0) or 0) & 0xFF
    bits = active_digit_bits(mask)
    text = str(state.get("text", "") or "")
    if "." in text or "," in text:
        natural = text.replace(",", ".").strip()
        return natural or fallback
    if bits:
        text = text[:len(bits)].rjust(len(bits))
    rendered = []
    for char, bit in zip(text, bits):
        rendered.append(char)
        if points & (1 << bit):
            rendered.append(".")
    value = "".join(rendered).strip()
    return value or fallback


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


def _display_state(
    mirror: Mapping[str, Any], raw_name: str, *, mask: int, brightness: int
) -> Dict[str, Any]:
    displays = mirror.get("displays")
    state: Dict[str, Any] = {}
    if isinstance(displays, Mapping):
        raw = displays.get(raw_name)
        if isinstance(raw, Mapping):
            state.update(dict(raw))
    state.setdefault("text", "")
    state.setdefault("points", 0)
    state.setdefault("mask", mask)
    state.setdefault("brightness", brightness)
    return state


def _output_on(mirror: Mapping[str, Any], raw_name: str) -> bool:
    outputs = mirror.get("outputs")
    if not isinstance(outputs, Mapping):
        return False
    try:
        return float(outputs.get(raw_name, 0) or 0) > 0
    except Exception:
        return False


def _pressed(mirror: Mapping[str, Any], raw_name: str) -> bool:
    inputs = mirror.get("inputs")
    if not isinstance(inputs, Mapping):
        return False
    item = inputs.get(raw_name)
    if not isinstance(item, Mapping):
        return False
    return bool(item.get("pressed", False))


def _fit(width: int, height: int, ref: Tuple[int, int]) -> Tuple[float, float, float]:
    rw, rh = ref
    scale = min(max(1, width - 24) / rw, max(1, height - 24) / rh)
    scale = max(0.45, scale)
    return (width - rw * scale) / 2.0, (height - rh * scale) / 2.0, scale


def _xy(origin_x: float, origin_y: float, scale: float, x: float, y: float) -> Tuple[float, float]:
    return origin_x + x * scale, origin_y + y * scale


def _tag(studio: Any, canvas: Any, item: int, key: str) -> None:
    try:
        studio._tag(canvas, item, key)
    except Exception:
        canvas.addtag_withtag(f"control:{key}", item)


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


def _text(canvas: Any, x: float, y: float, text: str, scale: float, *,
          size: int = 10, anchor: str = "center", fill: str = LEGEND,
          weight: str = "bold", width: Optional[float] = None) -> int:
    font = ("Segoe UI Semibold" if weight == "bold" else "Segoe UI",
            max(6, int(size * scale)))
    kwargs: Dict[str, Any] = {
        "text": text, "fill": fill, "font": font, "anchor": anchor,
    }
    if width is not None:
        kwargs["width"] = max(20, int(width * scale))
    return canvas.create_text(x, y, **kwargs)


def _screw(canvas: Any, x: float, y: float, scale: float) -> None:
    r = 10 * scale
    canvas.create_oval(x-r, y-r, x+r, y+r, fill="#25272d", outline="#060708", width=1)
    canvas.create_line(x-r*.70, y+r*.30, x+r*.70, y-r*.30, fill="#777b80", width=max(1, int(2*scale)))


def _screen(canvas: Any, x: float, y: float, w: float, h: float, value: str,
            scale: float, *, digits: int) -> None:
    x1, y1, x2, y2 = x-w/2, y-h/2, x+w/2, y+h/2
    canvas.create_round_rect(x1, y1, x2, y2, radius=max(4, 7*scale),
                             fill=SCREEN_EDGE, outline="#161922", width=2)
    inset = 8*scale
    canvas.create_round_rect(x1+inset, y1+inset, x2-inset, y2-inset,
                             radius=max(2, 4*scale), fill=SCREEN_BG,
                             outline="#02040a", width=1)
    display = str(value or "").strip()
    if not display:
        display = "-" * max(1, digits)
    canvas.create_text(
        x, y+2*scale, text=display, fill=SCREEN_BLUE,
        font=("Consolas", max(14, int((30 if digits <= 4 else 26)*scale)), "bold"),
    )


def _push_button(studio: Any, canvas: Any, x: float, y: float, w: float, h: float,
                 label: str, key: str, scale: float, *, pressed: bool = False) -> None:
    color = _control_color(studio, key)
    fill = "#2f343b" if pressed else _control_fill(studio, key, BUTTON_FACE)
    item = canvas.create_round_rect(
        x-w/2, y-h/2, x+w/2, y+h/2, radius=max(3, 5*scale),
        fill=fill, outline=color if pressed else BUTTON_EDGE,
        width=max(1, int(2*scale)),
    )
    _tag(studio, canvas, item, key)
    label_item = canvas.create_text(
        x, y, text=label, fill="#f1f0e9",
        font=("Segoe UI Semibold", max(6, int(10*scale))),
    )
    _tag(studio, canvas, label_item, key)


def _lamp(canvas: Any, x: float, y: float, w: float, h: float,
          scale: float, *, on: bool) -> None:
    fill = LAMP_ON if on else LAMP_OFF
    canvas.create_round_rect(
        x-w/2, y-h/2, x+w/2, y+h/2, radius=max(2, 5*scale),
        fill=fill, outline="#8d8f8a", width=1,
    )


def _knob_angle(
    studio: Any, mirror: Mapping[str, Any], raw_name: str, semantic_key: str
) -> float:
    """Accumulate encoder pulses into a persistent visual knob angle.

    HOWALT encoders are relative, so there is no absolute shaft angle to read.
    Each *new* left/right event advances the ball around its circular channel.
    The event timestamp prevents redraws from moving the ball more than once.
    """
    cache = getattr(studio, "_howalt_v47_knob_motion", None)
    if not isinstance(cache, dict):
        cache = {}
        try:
            setattr(studio, "_howalt_v47_knob_motion", cache)
        except Exception:
            pass
    state = cache.setdefault(
        semantic_key, {"angle": -90.0, "event_time": -1.0}
    )

    event = mirror.get("last_event")
    if isinstance(event, Mapping):
        control = str(event.get("control") or "")
        try:
            event_time = float(event.get("time") or 0.0)
        except Exception:
            event_time = 0.0
        if control == raw_name and event_time > float(state["event_time"]):
            phase = str(event.get("phase") or "")
            delta = {
                "left": -22.0, "left-fast": -44.0,
                "right": 22.0, "right-fast": 44.0,
                "press": 22.0,
            }.get(phase, 0.0)
            if delta:
                state["angle"] = (float(state["angle"]) + delta) % 360.0
            state["event_time"] = event_time
    return float(state["angle"])


def _channel_ball(
    canvas: Any, x: float, y: float, radius: float, angle_deg: float,
    scale: float, *, channel: str, ball: str,
) -> None:
    canvas.create_oval(
        x-radius, y-radius, x+radius, y+radius,
        fill="", outline=channel, width=max(3, int(7*scale)),
    )
    angle = math.radians(angle_deg)
    bx = x + radius * math.cos(angle)
    by = y + radius * math.sin(angle)
    br = max(4.0, 6.0*scale)
    canvas.create_oval(
        bx-br, by-br, bx+br, by+br,
        fill=ball, outline="#f4f2e8", width=max(1, int(2*scale)),
    )


def _single_rotary(
    studio: Any, canvas: Any, x: float, y: float, r: float,
    key: str, scale: float, mirror: Mapping[str, Any], raw_name: str,
    *, push_key: Optional[str] = None,
) -> None:
    color = _control_color(studio, key)
    angle = _knob_angle(studio, mirror, raw_name, key)

    # Large circular hit surface for rotation.
    hit = canvas.create_oval(x-r, y-r, x+r, y+r, fill="", outline="")
    _tag(studio, canvas, hit, key)

    # Recessed round channel and a highly visible moving ball.
    channel_r = r*.86
    _channel_ball(
        canvas, x, y, channel_r, angle, scale,
        channel="#343944", ball=color,
    )

    body_r = r*.61
    body = canvas.create_oval(
        x-body_r, y-body_r, x+body_r, y+body_r,
        fill=KNOB, outline=KNOB_EDGE, width=max(1, int(2*scale)),
    )
    _tag(studio, canvas, body, push_key or key)

    # A pushable encoder gets an independent centre target.
    if push_key:
        push_r = body_r*.43
        push = canvas.create_oval(
            x-push_r, y-push_r, x+push_r, y+push_r,
            fill=_control_fill(studio, push_key, "#d8d0b7"),
            outline=_control_color(studio, push_key),
            width=max(2, int(3*scale)),
        )
        _tag(studio, canvas, push, push_key)
        label = canvas.create_text(
            x, y, text="PUSH", fill="#343128",
            font=("Segoe UI Semibold", max(5, int(7*scale))),
        )
        _tag(studio, canvas, label, push_key)


def _dual_rotary(
    studio: Any, canvas: Any, x: float, y: float, r: float,
    outer_key: str, inner_key: str, scale: float,
    mirror: Mapping[str, Any], outer_raw: str, inner_raw: str,
) -> None:
    outer_color = _control_color(studio, outer_key)
    inner_color = _control_color(studio, inner_key)
    outer_angle = _knob_angle(studio, mirror, outer_raw, outer_key)
    inner_angle = _knob_angle(studio, mirror, inner_raw, inner_key)

    # Outer knob: outer circular groove + its own ball.
    outer_r = r*.86
    outer_hit = canvas.create_oval(
        x-r, y-r, x+r, y+r, fill="", outline=""
    )
    _tag(studio, canvas, outer_hit, outer_key)
    _channel_ball(
        canvas, x, y, outer_r, outer_angle, scale,
        channel="#303640", ball=outer_color,
    )

    body_r = r*.66
    body = canvas.create_oval(
        x-body_r, y-body_r, x+body_r, y+body_r,
        fill=KNOB, outline=KNOB_EDGE, width=max(1, int(2*scale)),
    )
    _tag(studio, canvas, body, outer_key)

    # Inner knob: separate inner circular groove + separate ball.
    inner_channel_r = r*.43
    _channel_ball(
        canvas, x, y, inner_channel_r, inner_angle, scale,
        channel="#bbb39c", ball=inner_color,
    )
    inner_body_r = r*.24
    inner = canvas.create_oval(
        x-inner_body_r, y-inner_body_r,
        x+inner_body_r, y+inner_body_r,
        fill="#eee6cf", outline=inner_color,
        width=max(2, int(3*scale)),
    )
    _tag(studio, canvas, inner, inner_key)


def _two_position_selector(
    studio: Any, canvas: Any, x: float, y: float, r: float,
    key: str, labels: Tuple[str, str], active: int, scale: float,
) -> None:
    """Round two-detent knob with one ball travelling in its circular groove."""
    active = 0 if int(active) <= 0 else 1
    angle_deg = -145.0 if active == 0 else -35.0
    color = _control_color(studio, key)

    hit = canvas.create_oval(x-r, y-r, x+r, y+r, fill="", outline="")
    _tag(studio, canvas, hit, key)

    _channel_ball(
        canvas, x, y, r*.82, angle_deg, scale,
        channel="#353944", ball=color,
    )
    body_r = r*.58
    body = canvas.create_oval(
        x-body_r, y-body_r, x+body_r, y+body_r,
        fill=KNOB, outline=KNOB_EDGE, width=max(1, int(2*scale)),
    )
    _tag(studio, canvas, body, key)

    for label, label_angle in ((labels[0], -145.0), (labels[1], -35.0)):
        a = math.radians(label_angle)
        lr = r + 22*scale
        item = canvas.create_text(
            x + lr*math.cos(a), y + lr*math.sin(a),
            text=label, fill=LEGEND,
            font=("Segoe UI Semibold", max(6, int(10*scale))),
        )
        _tag(studio, canvas, item, key)


def _mode_selector(
    studio: Any, canvas: Any, x: float, y: float, r: float,
    mirror: Mapping[str, Any], scale: float,
) -> None:
    """ATC/TCAS rotary with a ball that travels to the selected detent."""
    detents = (
        ("STBY", "stby", "STBY", -155.0),
        ("ALT RPTG\nOFF", "rptgoff", "RPTGOFF", -126.0),
        ("XPNDR", "xpndr", "XPNDR", -96.0),
        ("TA ONLY", "only", "ONLY", -66.0),
        ("TA/RA", "ta_ra", "TA-RA", -36.0),
    )
    active_key = "stby"
    active_angle = -155.0
    for _label, key, raw, angle in detents:
        if _pressed(mirror, raw):
            active_key = key
            active_angle = angle
            break

    # The detent selection owns the outer channel; TEST remains the independent
    # push target on the knob's centre.
    outer_hit = canvas.create_oval(x-r, y-r, x+r, y+r, fill="", outline="")
    _tag(studio, canvas, outer_hit, active_key)
    _channel_ball(
        canvas, x, y, r*.84, active_angle, scale,
        channel="#343944", ball=_control_color(studio, active_key),
    )

    body_r = r*.59
    body = canvas.create_oval(
        x-body_r, y-body_r, x+body_r, y+body_r,
        fill=KNOB, outline=KNOB_EDGE, width=max(1, int(2*scale)),
    )
    _tag(studio, canvas, body, "atc_test")

    test_r = body_r*.44
    test = canvas.create_oval(
        x-test_r, y-test_r, x+test_r, y+test_r,
        fill=_control_fill(studio, "atc_test", "#ddd4bc"),
        outline=_control_color(studio, "atc_test"),
        width=max(2, int(3*scale)),
    )
    _tag(studio, canvas, test, "atc_test")
    test_text = canvas.create_text(
        x, y, text="TEST", fill="#33312b",
        font=("Segoe UI Semibold", max(6, int(9*scale))),
    )
    _tag(studio, canvas, test_text, "atc_test")

    for label, key, _raw, angle_deg in detents:
        a = math.radians(angle_deg)
        label_r = r + 43*scale
        lx = x + label_r*math.cos(a)
        ly = y + label_r*math.sin(a)
        item = canvas.create_text(
            lx, ly, text=label,
            fill="#fff0b1" if key == active_key else LEGEND,
            justify="center",
            font=("Segoe UI Semibold", max(6, int(10*scale))),
        )
        _tag(studio, canvas, item, key)
        hit = canvas.create_rectangle(
            lx-32*scale, ly-15*scale, lx+32*scale, ly+15*scale,
            fill="", outline="",
        )
        _tag(studio, canvas, hit, key)


def draw_muslimrtp(studio: Any, canvas: Any, width: int, height: int) -> None:
    ox, oy, s = _fit(width, height, D201_REFERENCE_SIZE)
    mirror = _mirror(studio, "muslimrtp_d201")
    def p(x: float, y: float) -> Tuple[float, float]:
        return _xy(ox, oy, s, x, y)

    x1, y1 = p(18, 5); x2, y2 = p(742, 646)
    canvas.create_round_rect(x1, y1, x2, y2, radius=max(5, 8*s),
                             fill=PANEL_FACE, outline=PANEL_EDGE, width=max(2, int(3*s)))
    seam_y = p(0, 341)[1]
    canvas.create_line(p(20, 341)[0], seam_y, p(740, 341)[0], seam_y,
                       fill="#272830", width=max(2, int(5*s)))

    # Screws match the visible perimeter and centre fasteners.
    for x, y in ((22,70),(22,226),(22,410),(22,610),(738,70),(738,226),(738,410),(738,610),(380,20),(380,360)):
        _screw(canvas, *p(x,y), s)

    # Four actual display windows. The top pair's six-digit mask is confirmed
    # by D201RTPLCD.pcapng. The lower five-position NAV presentation follows
    # the photographed panel and remains isolated from the capture-proven pair.
    d1 = visual_display_text(_display_state(mirror, "SMG-1", mask=0x3F, brightness=7), "")
    d2 = visual_display_text(_display_state(mirror, "SMG-2", mask=0x3F, brightness=7), "")
    d3 = visual_display_text(_display_state(mirror, "SMG-3", mask=0x1F, brightness=7), "")
    d4 = visual_display_text(_display_state(mirror, "SMG-4", mask=0x1F, brightness=7), "")
    _text(canvas, *p(205,20), "ACTIVE", s, size=13)
    _text(canvas, *p(555,20), "STANDBY", s, size=13)
    _screen(canvas, *p(205,77), 246*s, 76*s, d1, s, digits=6)
    _screen(canvas, *p(555,77), 246*s, 76*s, d2, s, digits=6)
    _push_button(studio, canvas, *p(380,84), 52*s, 38*s, "↔", "tfr1", s, pressed=_pressed(mirror,"TFR1"))

    # Upper radio-control field.
    _text(canvas, *p(42,160), "P\nN\nL", s, size=10)
    _push_button(studio, canvas, *p(106,170), 67*s, 44*s, "OFF", "off", s, pressed=_pressed(mirror,"OFF"))
    _single_rotary(studio, canvas, *p(111,255), 45*s, "bmq1", s, mirror, "BMQ1", push_key="hf_sens_push")
    _text(canvas, *p(112,316), "HF SENS", s, size=11)

    for x, label, key, raw, ledraw in (
        (285,"VHF1","vhf1","VHF1","VHF1-L"),
        (380,"VHF2","vhf2","VHF2","VHF2-L"),
        (475,"VHF3","vhf3","VHF3","VHF3-L"),
    ):
        _lamp(canvas, *p(x,166), 56*s, 17*s, s, on=_output_on(mirror,ledraw))
        _push_button(studio, canvas, *p(x,207), 72*s, 39*s, label, key, s, pressed=_pressed(mirror,raw))
    for x, label, key, raw, ledraw in (
        (285,"HF1","hf1","HF1","HF1-L"),
        (380,"AM","am","AM","AM-L"),
        (475,"HF2","hf2","HF2","HF2-L"),
    ):
        _lamp(canvas, *p(x,250), 56*s, 17*s, s, on=_output_on(mirror,ledraw))
        _push_button(studio, canvas, *p(x,291), 72*s, 39*s, label, key, s, pressed=_pressed(mirror,raw))

    _push_button(studio, canvas, *p(586,170), 72*s, 43*s, "TEST", "test1", s, pressed=_pressed(mirror,"TEST1"))
    _text(canvas, *p(586,222), "VHF", s, size=12)
    _dual_rotary(studio, canvas, *p(663,257), 51*s, "bmq2_1", "bmq2_2", s, mirror, "BMQ2-1", "BMQ2-2")

    # Lower NAV section.
    _text(canvas, *p(205,357), "ACTIVE", s, size=13)
    _text(canvas, *p(555,357), "STANDBY", s, size=13)
    _text(canvas, *p(380,378), "TER", s, size=9)
    _screen(canvas, *p(205,418), 246*s, 72*s, d3, s, digits=5)
    _screen(canvas, *p(555,418), 246*s, 72*s, d4, s, digits=5)
    _push_button(studio, canvas, *p(380,419), 52*s, 38*s, "↔", "tfr2", s, pressed=_pressed(mirror,"TFR2"))
    _text(canvas, *p(42,482), "N\nA\nV", s, size=12)
    _text(canvas, *p(210,500), "TEST", s, size=12)
    _push_button(studio, canvas, *p(210,554), 53*s, 53*s, "", "test2", s, pressed=_pressed(mirror,"TEST2"))
    _dual_rotary(studio, canvas, *p(663,580), 53*s, "bmq3_1", "bmq3_2", s, mirror, "BMQ3-1", "BMQ3-2")


def draw_muslimatc(studio: Any, canvas: Any, width: int, height: int) -> None:
    ox, oy, s = _fit(width, height, D203_REFERENCE_SIZE)
    mirror = _mirror(studio, "muslimatc_d203")
    def p(x: float, y: float) -> Tuple[float, float]:
        return _xy(ox, oy, s, x, y)

    x1,y1=p(14,7); x2,y2=p(874,448)
    canvas.create_round_rect(x1,y1,x2,y2,radius=max(5,8*s),
                             fill=PANEL_FACE, outline=PANEL_EDGE, width=max(2,int(3*s)))
    for x,y in ((19,82),(19,299),(869,82),(869,299),(321,30),(590,30),(518,427)):
        _screw(canvas,*p(x,y),s)

    canvas.create_text(*p(135,25), text="1", fill=(LAMP_ON if _output_on(mirror,"1-LED") else LEGEND), font=("Segoe UI Semibold", max(6, int(12*s))))
    canvas.create_text(*p(181,25), text="2", fill=(LAMP_ON if _output_on(mirror,"2-LED") else LEGEND), font=("Segoe UI Semibold", max(6, int(12*s))))
    _text(canvas,*p(158,178),"XPNDR",s,size=11)
    _two_position_selector(
        studio,canvas,*p(158,96),43*s,"xpn_1_2",("1","2"),
        0 if _pressed(mirror,"XPN1-2") else 1,s,
    )

    _text(canvas,*p(158,232),"1   2",s,size=12)
    _text(canvas,*p(158,413),"ALT SOURCE",s,size=11)
    _two_position_selector(
        studio,canvas,*p(158,304),43*s,"alt_1_2",("1","2"),
        0 if _pressed(mirror,"ALT1-2") else 1,s,
    )

    _text(canvas,*p(406,27),"XPNDR",s,size=12)
    _lamp(canvas,*p(466,27),18*s,18*s,s,on=_output_on(mirror,"ATC-LED"))
    _text(canvas,*p(540,27),"FAIL",s,size=12)
    _lamp(canvas,*p(494,27),18*s,18*s,s,on=_output_on(mirror,"FAIL-LED"))

    display = visual_display_text(
        _display_state(mirror,"SMG",mask=0x0F,brightness=15),""
    )
    _screen(canvas,*p(449,170),230*s,174*s,display,s,digits=4)
    # The reference panel carries a small blue ATC1 legend in the upper-left
    # of the code window. It is static faceplate/display decoration, not a
    # fifth MAX7219 digit and therefore never enters the serial command.
    _text(canvas,*p(363,102),"ATC1",s,size=9,anchor="w",fill=SCREEN_BLUE)

    _text(canvas,*p(27,229),"A\nT\nC",s,size=13)
    _text(canvas,*p(861,224),"T\nC\nA\nS",s,size=13)

    _mode_selector(studio,canvas,*p(749,142),46*s,mirror,s)

    _text(canvas,*p(453,292),"IDENT",s,size=12)
    _push_button(studio,canvas,*p(453,348),46*s,46*s,"","ident",s,pressed=_pressed(mirror,"IDENT"))

    _dual_rotary(studio,canvas,*p(333,394),51*s,"bmq1_1","bmq1_2",s,mirror,"BMQ1-1","BMQ1-2")
    _dual_rotary(studio,canvas,*p(638,394),51*s,"bmq2_1","bmq2_2",s,mirror,"BMQ2-1","BMQ2-2")


def draw_howalt_faceplate(studio: Any, canvas: Any, width: int, height: int) -> None:
    key = str(getattr(studio, "_selected_device", ""))
    if key == "muslimrtp_d201":
        draw_muslimrtp(studio, canvas, width, height)
    elif key == "muslimatc_d203":
        draw_muslimatc(studio, canvas, width, height)
    else:
        raise KeyError(key)

MUSLIMSIM_HOWALT_V47_KNOB_BALL_CHANNELS = True
