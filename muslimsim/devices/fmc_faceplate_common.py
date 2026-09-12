"""Shared drawing helpers for authored BB35/BB36 Studio faceplates.

These helpers are presentation-only. They never open HID, send simulator
commands, or alter the existing BB35/BB36 hardware owners.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

SCREEN_BLACK = "#05080b"
SCREEN_INNER = "#06110f"
SCREEN_TEXT = "#b9f7df"
KEY_FACE = "#37383a"
KEY_EDGE = "#17191c"
KEY_TEXT = "#f3f1eb"
KEY_SELECTED = "#4c3915"
METAL_DARK = "#34393f"
SCREW = "#aab0b5"
SCREW_DARK = "#50565b"


@dataclass(frozen=True)
class Rect:
    name: str
    x1: float
    y1: float
    x2: float
    y2: float

    def inside(self, width: float, height: float) -> bool:
        return (
            0 <= self.x1 < self.x2 <= width
            and 0 <= self.y1 < self.y2 <= height
        )

    def overlaps(self, other: "Rect", gap: float = 0.0) -> bool:
        return not (
            self.x2 + gap <= other.x1
            or other.x2 + gap <= self.x1
            or self.y2 + gap <= other.y1
            or other.y2 + gap <= self.y1
        )


def fit(
    width: int,
    height: int,
    reference: Tuple[int, int],
    *,
    margin: int = 16,
) -> Tuple[float, float, float]:
    rw, rh = reference
    scale = min(
        max(1.0, float(width) - margin * 2.0) / float(rw),
        max(1.0, float(height) - margin * 2.0) / float(rh),
    )
    scale = max(0.42, scale)
    return (
        (float(width) - rw * scale) / 2.0,
        (float(height) - rh * scale) / 2.0,
        scale,
    )


def xy(
    ox: float, oy: float, scale: float, x: float, y: float
) -> Tuple[float, float]:
    return ox + x * scale, oy + y * scale


def tag(studio: Any, canvas: Any, item: int, key: str) -> None:
    try:
        studio._tag(canvas, item, key)
    except Exception:
        try:
            canvas.addtag_withtag(f"control:{key}", item)
        except Exception:
            pass


def control_color(studio: Any, key: str) -> str:
    try:
        return studio._control_color(key)
    except Exception:
        return "#5aa9ff"


def control_fill(studio: Any, key: str, default: str) -> str:
    try:
        return studio._control_fill(key, default)
    except Exception:
        return default


def mirror(studio: Any, device: str) -> Dict[str, Any]:
    try:
        value = studio._device_mirror(device)
    except Exception:
        value = {}
    if not isinstance(value, Mapping):
        return {}
    result = dict(value)
    nested = result.get("mirror")
    if isinstance(nested, Mapping):
        result.update(dict(nested))
    return result


def display_lines(
    studio: Any,
    device: str,
    *,
    label: str,
) -> Sequence[str]:
    """Return exactly the same kind of screen source the old Studio grid used."""

    current = mirror(studio, device)

    detected = getattr(studio, "_detected", {}).get(device)
    states = getattr(studio, "_device_states", {})
    state_record = states.get(device, {}) if isinstance(states, Mapping) else {}
    if not isinstance(state_record, Mapping):
        state_record = {}
    service_state = str(state_record.get("state") or "").strip().lower()

    offline_states = {
        "pfp3n_bb35": {
            "disconnected",
            "offline",
            "waiting-for-pfp3n",
            "reconnecting",
            "stopped",
        },
        "mcdu32_bb36": {
            "disconnected",
            "offline",
            "waiting-for-bb36",
            "reconnecting",
            "stopped",
        },
    }
    if device in offline_states:
        physical_offline = bool(
            detected is None
            or (
                isinstance(detected, Mapping)
                and detected.get("source") == "bridge"
                and service_state in offline_states[device]
            )
        )
        if physical_offline:
            product = (
                "WINCTRL 3N PFP CAPTAIN"
                if device == "pfp3n_bb35"
                else "WINCTRL 32 MCDU CAPTAIN"
            )
            pid = "BB35" if device == "pfp3n_bb35" else "BB36"
            return (
                f"{label}  OFFLINE",
                "",
                f"{product} disconnected.",
                f"Waiting for USB 4098:{pid}...",
            )

    lines = list(current.get("lines") or ())
    if lines:
        return tuple(str(line) for line in lines[:14])

    if str(current.get("state") or "").strip().lower() == "pfd":
        pfd = current.get("pfd")
        if isinstance(pfd, Mapping):
            values = pfd.get("values")
            values = dict(values) if isinstance(values, Mapping) else {}
            return (
                f"{label}  {str(pfd.get('page') or 'PFD').upper()} LIVE",
                "",
                f"IAS {values.get('ias', '---')}   HDG {values.get('heading', '---')}",
                f"ALT {values.get('altitude', '---')}   VS {values.get('vertical_speed', '---')}",
                "",
                "Read-only PFD telemetry",
                "mirrored from the physical display path.",
            )

    return (
        "MUSLIMSIM STUDIO",
        "",
        "Waiting for physical display stream...",
    )


def text(
    canvas: Any,
    x: float,
    y: float,
    value: str,
    scale: float,
    *,
    size: int = 10,
    fill: str = KEY_TEXT,
    anchor: str = "center",
    weight: str = "bold",
    width: Optional[float] = None,
) -> int:
    kwargs: Dict[str, Any] = {
        "text": str(value),
        "fill": fill,
        "anchor": anchor,
        "font": (
            "Segoe UI Semibold" if weight == "bold" else "Segoe UI",
            max(6, int(size * scale)),
        ),
    }
    if width is not None:
        kwargs["width"] = max(16, int(width * scale))
    return canvas.create_text(x, y, **kwargs)


def screw(canvas: Any, x: float, y: float, scale: float, *, large: bool = False) -> None:
    r = (11 if large else 7) * scale
    canvas.create_oval(
        x - r,
        y - r,
        x + r,
        y + r,
        fill=SCREW,
        outline="#4e5357",
        width=max(1, int(scale)),
    )
    canvas.create_oval(
        x - r * .55,
        y - r * .55,
        x + r * .55,
        y + r * .55,
        fill=SCREW_DARK,
        outline="#25282a",
        width=1,
    )
    canvas.create_line(
        x - r * .42,
        y + r * .24,
        x + r * .42,
        y - r * .24,
        fill="#d9dcdf",
        width=max(1, int(1.4 * scale)),
    )


def screen(
    canvas: Any,
    ox: float,
    oy: float,
    scale: float,
    rect: Tuple[float, float, float, float],
    lines: Sequence[str],
    *,
    bezel: str,
    edge: str,
    line_color: str = SCREEN_TEXT,
) -> None:
    x1, y1, x2, y2 = rect
    ax1, ay1 = xy(ox, oy, scale, x1, y1)
    ax2, ay2 = xy(ox, oy, scale, x2, y2)
    radius = max(4, int(12 * scale))
    canvas.create_round_rect(
        ax1,
        ay1,
        ax2,
        ay2,
        radius=radius,
        fill=bezel,
        outline=edge,
        width=max(1, int(2 * scale)),
    )
    inset = 12 * scale
    ix1, iy1 = ax1 + inset, ay1 + inset
    ix2, iy2 = ax2 - inset, ay2 - inset
    canvas.create_round_rect(
        ix1,
        iy1,
        ix2,
        iy2,
        radius=max(3, int(8 * scale)),
        fill=SCREEN_BLACK,
        outline="#050608",
        width=max(1, int(scale)),
    )

    rows = tuple(str(value) for value in lines[:14])
    if not rows:
        return
    usable_h = max(20.0, iy2 - iy1 - 14 * scale)
    line_h = usable_h / max(14, len(rows))
    font_size = max(6, min(11, int(line_h / max(scale, 0.1) - 1)))
    for index, value in enumerate(rows):
        canvas.create_text(
            ix1 + 10 * scale,
            iy1 + 7 * scale + index * line_h,
            text=str(value)[:42],
            anchor="nw",
            fill=line_color,
            font=("Consolas", max(6, int(font_size * scale))),
        )


def rectangular_key(
    studio: Any,
    canvas: Any,
    ox: float,
    oy: float,
    scale: float,
    *,
    key_index: int,
    center: Tuple[float, float],
    size: Tuple[float, float],
    label: str,
    face: str = KEY_FACE,
    outline: str = KEY_EDGE,
    font_size: int = 13,
    white_outline: bool = False,
    blank: bool = False,
) -> None:
    key = f"key_{int(key_index)}"
    cx, cy = xy(ox, oy, scale, *center)
    w, h = size[0] * scale, size[1] * scale
    selected = control_color(studio, key)
    fill = control_fill(studio, key, face)
    item = canvas.create_round_rect(
        cx - w / 2,
        cy - h / 2,
        cx + w / 2,
        cy + h / 2,
        radius=max(2, int(4 * scale)),
        fill=fill,
        outline=selected if fill != face else outline,
        width=max(1, int(2 * scale)),
    )
    tag(studio, canvas, item, key)
    if white_outline:
        border = canvas.create_rectangle(
            cx - w * .35,
            cy - h * .36,
            cx + w * .35,
            cy + h * .36,
            fill="",
            outline="#f4f2ea",
            width=max(1, int(2 * scale)),
        )
        tag(studio, canvas, border, key)
    if not blank and label:
        item_text = canvas.create_text(
            cx,
            cy,
            text=label,
            fill=KEY_TEXT,
            justify="center",
            font=("Segoe UI Semibold", max(6, int(font_size * scale))),
        )
        tag(studio, canvas, item_text, key)


def round_key(
    studio: Any,
    canvas: Any,
    ox: float,
    oy: float,
    scale: float,
    *,
    key_index: int,
    center: Tuple[float, float],
    radius: float,
    label: str,
    face: str = "#454243",
    font_size: int = 16,
) -> None:
    key = f"key_{int(key_index)}"
    cx, cy = xy(ox, oy, scale, *center)
    r = radius * scale
    fill = control_fill(studio, key, face)
    item = canvas.create_oval(
        cx - r,
        cy - r,
        cx + r,
        cy + r,
        fill=fill,
        outline=control_color(studio, key) if fill != face else "#252426",
        width=max(1, int(2 * scale)),
    )
    tag(studio, canvas, item, key)
    item_text = canvas.create_text(
        cx,
        cy,
        text=label,
        fill=KEY_TEXT,
        font=("Segoe UI Semibold", max(7, int(font_size * scale))),
    )
    tag(studio, canvas, item_text, key)


def lsk(
    studio: Any,
    canvas: Any,
    ox: float,
    oy: float,
    scale: float,
    *,
    key_index: int,
    center: Tuple[float, float],
    size: Tuple[float, float] = (42, 31),
) -> None:
    key = f"key_{int(key_index)}"
    cx, cy = xy(ox, oy, scale, *center)
    w, h = size[0] * scale, size[1] * scale
    fill = control_fill(studio, key, "#252528")
    item = canvas.create_round_rect(
        cx - w / 2,
        cy - h / 2,
        cx + w / 2,
        cy + h / 2,
        radius=max(2, int(3 * scale)),
        fill=fill,
        outline=control_color(studio, key) if fill != "#252528" else "#111214",
        width=max(1, int(2 * scale)),
    )
    tag(studio, canvas, item, key)
    dash = canvas.create_rectangle(
        cx - w * .28,
        cy - h * .08,
        cx + w * .28,
        cy + h * .08,
        fill="#f4f1ea",
        outline="",
    )
    tag(studio, canvas, dash, key)


def speaker_grille(
    canvas: Any,
    ox: float,
    oy: float,
    scale: float,
    x: float,
    y1: float,
    y2: float,
) -> None:
    ax, ay1 = xy(ox, oy, scale, x, y1)
    _, ay2 = xy(ox, oy, scale, x, y2)
    w = 14 * scale
    canvas.create_round_rect(
        ax - w / 2,
        ay1,
        ax + w / 2,
        ay2,
        radius=max(2, int(4 * scale)),
        fill="#3a3837",
        outline="#7b7470",
        width=max(1, int(scale)),
    )
    for frac in (.18, .36, .54, .72, .90):
        y = ay1 + (ay2 - ay1) * frac
        canvas.create_line(
            ax - w * .32,
            y,
            ax + w * .32,
            y,
            fill="#171718",
            width=max(1, int(scale)),
        )
