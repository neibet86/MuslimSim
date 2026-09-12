"""Photo-authored 2-D Studio faceplate for WINCTRL 32 MCDU CAPTAIN (BB36).

Reference: owner-supplied 20260902_220747.jpg.

This module is presentation-only. Every clickable surface keeps the existing
captured ``key_N`` identity from ``devices.mcdu_bb36.MCDU_KEY_MAP``.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence, Tuple

from .fmc_faceplate_common import (
    Rect,
    control_color,
    control_fill,
    display_lines,
    fit,
    lsk,
    rectangular_key,
    round_key,
    screen,
    screw,
    speaker_grille,
    tag,
    text,
    xy,
)

MCDU_REFERENCE_SIZE: Tuple[int, int] = (620, 980)

PANEL_BLUE = "#697aa1"
PANEL_BLUE_DARK = "#52627f"
PANEL_BLUE_EDGE = "#2d3b57"
BEZEL = "#657796"
BEZEL_EDGE = "#2b374c"
KEY_FACE = "#4b4749"
KEY_EDGE = "#29272a"
KEY_TEXT = "#f5f3ec"
WHITE = "#f6f4eb"

# Physical legends from the uploaded faceplate. The existing simulator action
# can intentionally differ (for example OVEY/triangle keeps key_72's proven
# DEL action). Studio draws the *physical* legend, while key_N stays stable.
MCDU_PHYSICAL_LABELS: Dict[int, str] = {
    12: "DIR",
    13: "PROG",
    14: "PERF",
    15: "INIT",
    16: "DATA",
    17: "",
    18: "BRT",
    19: "F-PLN",
    20: "RAD\nNAV",
    21: "FUEL\nPRED",
    22: "SEC\nF-PLN",
    23: "ATC\nCOMM",
    24: "MCDU\nMENU",
    25: "DIM",
    26: "AIR\nPORT",
    27: "",
    28: "←",
    29: "↑",
    30: "→",
    31: "↓",
    32: "1", 33: "2", 34: "3",
    35: "4", 36: "5", 37: "6",
    38: "7", 39: "8", 40: "9",
    41: ".", 42: "0", 43: "+/-",
    44: "A", 45: "B", 46: "C", 47: "D", 48: "E",
    49: "F", 50: "G", 51: "H", 52: "I", 53: "J",
    54: "K", 55: "L", 56: "M", 57: "N", 58: "O",
    59: "P", 60: "Q", 61: "R", 62: "S", 63: "T",
    64: "U", 65: "V", 66: "W", 67: "X", 68: "Y",
    69: "Z", 70: "/", 71: "SP", 72: "OVEY\n△", 73: "CLR",
}

# The white square outlines visible around E/N/S/W on the physical unit.
MCDU_COMPASS_OUTLINE_KEYS = frozenset({48, 57, 62, 66})

# Exposed for deterministic geometry tests.
MCDU_SCREEN_RECT = Rect("screen", 82, 86, 532, 432)
MCDU_LSK_REGIONS = tuple(
    Rect(f"lsk_l_{i+1}", 16, 120 + i * 52, 62, 154 + i * 52)
    for i in range(6)
) + tuple(
    Rect(f"lsk_r_{i+1}", 558, 120 + i * 52, 604, 154 + i * 52)
    for i in range(6)
)


def _panel_shell(canvas: Any, ox: float, oy: float, s: float) -> None:
    x1, y1 = xy(ox, oy, s, 10, 8)
    x2, y2 = xy(ox, oy, s, 610, 972)
    canvas.create_round_rect(
        x1,
        y1,
        x2,
        y2,
        radius=max(10, int(22 * s)),
        fill=PANEL_BLUE,
        outline=PANEL_BLUE_EDGE,
        width=max(1, int(3 * s)),
    )

    # Upper crown and the worn rectangular light/label windows in the photo.
    canvas.create_round_rect(
        *xy(ox, oy, s, 25, 18),
        *xy(ox, oy, s, 595, 72),
        radius=max(5, int(12 * s)),
        fill=PANEL_BLUE_DARK,
        outline="#4b5d80",
        width=max(1, int(s)),
    )
    for x in (170, 240, 310, 380, 450):
        ax1, ay1 = xy(ox, oy, s, x - 20, 30)
        ax2, ay2 = xy(ox, oy, s, x + 20, 44)
        canvas.create_round_rect(
            ax1,
            ay1,
            ax2,
            ay2,
            radius=max(2, int(4 * s)),
            fill="#3b383a",
            outline="#625c5d",
            width=1,
        )

    # Two white round plugs visible in the top crown.
    for x in (74, 535):
        cx, cy = xy(ox, oy, s, x, 38)
        r = 17 * s
        canvas.create_oval(
            cx - r,
            cy - r,
            cx + r,
            cy + r,
            fill="#f4f4e8",
            outline="#d4d5c8",
            width=max(1, int(s)),
        )

    # Structural screws/bolts.
    for x, y, large in (
        (24, 22, False),
        (596, 22, False),
        (22, 66, True),
        (598, 66, True),
        (22, 454, False),
        (598, 454, False),
        (22, 870, False),
        (598, 870, False),
    ):
        cx, cy = xy(ox, oy, s, x, y)
        screw(canvas, cx, cy, s, large=large)


def _function_key(
    studio: Any,
    canvas: Any,
    ox: float,
    oy: float,
    s: float,
    index: int,
    x: float,
    y: float,
    *,
    width: float = 66,
    height: float = 40,
    font: int = 12,
) -> None:
    label = MCDU_PHYSICAL_LABELS.get(index, "")
    rectangular_key(
        studio,
        canvas,
        ox,
        oy,
        s,
        key_index=index,
        center=(x, y),
        size=(width, height),
        label=label,
        face=KEY_FACE,
        outline=KEY_EDGE,
        font_size=font,
        blank=not bool(label),
    )


def draw_mcdu32_faceplate(
    studio: Any,
    canvas: Any,
    width: int,
    height: int,
) -> None:
    ox, oy, s = fit(width, height, MCDU_REFERENCE_SIZE, margin=14)
    _panel_shell(canvas, ox, oy, s)

    # Display bezel and 12 side line-select keys.
    lines = display_lines(studio, "mcdu32_bb36", label="MCDU32")
    screen(
        canvas,
        ox,
        oy,
        s,
        (78, 82, 542, 438),
        lines,
        bezel=BEZEL,
        edge=BEZEL_EDGE,
        line_color="#b9f7df",
    )
    for row in range(6):
        y = 139 + row * 52
        lsk(studio, canvas, ox, oy, s, key_index=row, center=(39, y))
        lsk(studio, canvas, ox, oy, s, key_index=row + 6, center=(581, y))

    # Keypad surround below the screen.
    x1, y1 = xy(ox, oy, s, 58, 462)
    x2, y2 = xy(ox, oy, s, 533, 618)
    canvas.create_round_rect(
        x1,
        y1,
        x2,
        y2,
        radius=max(5, int(10 * s)),
        fill="#607093",
        outline="#3d4b69",
        width=max(1, int(2 * s)),
    )

    # Row 1: DIR / PROG / PERF / INIT / DATA / blank
    row_x = (101, 180, 259, 338, 417, 496)
    for index, x in zip(range(12, 18), row_x):
        _function_key(studio, canvas, ox, oy, s, index, x, 492)

    # BRT / DIM on the photo's right-hand vertical strip.
    _function_key(
        studio, canvas, ox, oy, s, 18, 564, 493,
        width=58, height=40, font=12,
    )
    _function_key(
        studio, canvas, ox, oy, s, 25, 564, 544,
        width=58, height=40, font=12,
    )

    # Row 2: F-PLN ... MCDU MENU
    row2_indices = (19, 20, 21, 22, 23, 24)
    for index, x in zip(row2_indices, row_x):
        _function_key(studio, canvas, ox, oy, s, index, x, 544)

    # Left lower function/navigation block: AIR PORT, blank, arrows.
    _function_key(
        studio, canvas, ox, oy, s, 26, 100, 602,
        width=72, height=46, font=12,
    )
    _function_key(
        studio, canvas, ox, oy, s, 27, 183, 602,
        width=72, height=46, font=12,
    )
    _function_key(
        studio, canvas, ox, oy, s, 28, 100, 655,
        width=72, height=46, font=18,
    )
    _function_key(
        studio, canvas, ox, oy, s, 29, 183, 655,
        width=72, height=46, font=18,
    )
    _function_key(
        studio, canvas, ox, oy, s, 30, 100, 708,
        width=72, height=46, font=18,
    )
    _function_key(
        studio, canvas, ox, oy, s, 31, 183, 708,
        width=72, height=46, font=18,
    )

    # Round numeric keypad, as on the physical MCDU.
    num_positions = (
        (32, 76, 760), (33, 142, 760), (34, 208, 760),
        (35, 76, 822), (36, 142, 822), (37, 208, 822),
        (38, 76, 884), (39, 142, 884), (40, 208, 884),
        (41, 76, 946), (42, 142, 946), (43, 208, 946),
    )
    for index, x, y in num_positions:
        round_key(
            studio,
            canvas,
            ox,
            oy,
            s,
            key_index=index,
            center=(x, y),
            radius=25,
            label=MCDU_PHYSICAL_LABELS[index],
            face="#494447",
            font_size=16,
        )

    # Alphabetic 6x5 matrix.
    alpha_x = (302, 367, 432, 497, 562)
    alpha_y = (640, 700, 760, 820, 880, 940)
    index = 44
    for y in alpha_y:
        for x in alpha_x:
            label = MCDU_PHYSICAL_LABELS[index]
            rectangular_key(
                studio,
                canvas,
                ox,
                oy,
                s,
                key_index=index,
                center=(x, y),
                size=(52, 46),
                label=label,
                face=KEY_FACE,
                outline=KEY_EDGE,
                font_size=15 if "\n" not in label else 10,
                white_outline=index in MCDU_COMPASS_OUTLINE_KEYS,
            )
            index += 1

    # Vertical speaker/grille strips beside the lower keypad.
    speaker_grille(canvas, ox, oy, s, 32, 702, 854)
    speaker_grille(canvas, ox, oy, s, 602, 702, 854)

    # A subtle physical identity legend; not clickable.
    cx, cy = xy(ox, oy, s, 310, 966)
    text(
        canvas,
        cx,
        cy,
        "WINCTRL 32 MCDU CAPTAIN",
        s,
        size=7,
        fill="#d8dfef",
        weight="normal",
    )


MUSLIMSIM_MCDU32_BB36_AUTHORED_FACEPLATE_V1 = True
