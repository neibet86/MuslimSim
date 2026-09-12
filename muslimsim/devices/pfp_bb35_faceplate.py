"""Photo-authored 2-D Studio faceplate for WINCTRL 3N PFP CAPTAIN (BB35).

Reference: owner-supplied 20260902_220800.jpg.

This is a Studio renderer only. The existing BB35 display/keypad owner and its
captured ``key_N`` identities remain untouched.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

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

PFP_REFERENCE_SIZE: Tuple[int, int] = (620, 990)

PANEL = "#a3a8ab"
PANEL_INNER = "#92989b"
PANEL_EDGE = "#4e5559"
BEZEL = "#899095"
BEZEL_EDGE = "#555b5e"
KEY_FACE = "#4a4848"
KEY_EDGE = "#292828"
KEY_TEXT = "#f5f2eb"

PFP_PHYSICAL_LABELS: Dict[int, str] = {
    12: "INIT\nREF",
    13: "RTE",
    14: "CLB",
    15: "CRZ",
    16: "DES",
    17: "−",
    18: "+",
    19: "MENU",
    20: "LEGS",
    21: "DEP\nARR",
    22: "HOLD",
    23: "PROG",
    24: "EXEC",
    25: "N1\nLIMIT",
    26: "FIX",
    27: "PREV\nPAGE",
    28: "NEXT\nPAGE",
    29: "1", 30: "2", 31: "3",
    32: "4", 33: "5", 34: "6",
    35: "7", 36: "8", 37: "9",
    38: ".", 39: "0", 40: "+/-",
    41: "A", 42: "B", 43: "C", 44: "D", 45: "E",
    46: "F", 47: "G", 48: "H", 49: "I", 50: "J",
    51: "K", 52: "L", 53: "M", 54: "N", 55: "O",
    56: "P", 57: "Q", 58: "R", 59: "S", 60: "T",
    61: "U", 62: "V", 63: "W", 64: "X", 65: "Y",
    66: "Z", 67: "SP", 68: "DEL", 69: "/", 70: "CLR",
}

PFP_COMPASS_OUTLINE_KEYS = frozenset({45, 54, 59, 63})
PFP_SCREEN_RECT = Rect("screen", 88, 72, 532, 424)
PFP_LSK_REGIONS = tuple(
    Rect(f"lsk_l_{i+1}", 15, 106 + i * 53, 62, 140 + i * 53)
    for i in range(6)
) + tuple(
    Rect(f"lsk_r_{i+1}", 558, 106 + i * 53, 605, 140 + i * 53)
    for i in range(6)
)


def _shell(canvas: Any, ox: float, oy: float, s: float) -> None:
    x1, y1 = xy(ox, oy, s, 9, 7)
    x2, y2 = xy(ox, oy, s, 611, 982)
    canvas.create_round_rect(
        x1,
        y1,
        x2,
        y2,
        radius=max(10, int(20 * s)),
        fill=PANEL,
        outline=PANEL_EDGE,
        width=max(1, int(3 * s)),
    )

    # Slightly darker recessed keypad sections from the physical photo.
    for rect in (
        (58, 454, 486, 600),
        (50, 592, 220, 733),
    ):
        ax1, ay1 = xy(ox, oy, s, rect[0], rect[1])
        ax2, ay2 = xy(ox, oy, s, rect[2], rect[3])
        canvas.create_round_rect(
            ax1,
            ay1,
            ax2,
            ay2,
            radius=max(4, int(9 * s)),
            fill=PANEL_INNER,
            outline="#707679",
            width=max(1, int(2 * s)),
        )

    # Screws/large quarter-turn fasteners.
    for x, y, large in (
        (25, 22, False), (595, 22, False),
        (24, 60, True), (596, 60, True),
        (25, 447, False), (595, 447, False),
        (25, 620, False), (595, 620, False),
        (25, 875, False), (595, 875, False),
    ):
        cx, cy = xy(ox, oy, s, x, y)
        screw(canvas, cx, cy, s, large=large)


def _key(
    studio: Any,
    canvas: Any,
    ox: float,
    oy: float,
    s: float,
    index: int,
    x: float,
    y: float,
    *,
    width: float = 68,
    height: float = 43,
    font: int = 12,
    white_outline: bool = False,
) -> None:
    rectangular_key(
        studio,
        canvas,
        ox,
        oy,
        s,
        key_index=index,
        center=(x, y),
        size=(width, height),
        label=PFP_PHYSICAL_LABELS[index],
        face=KEY_FACE,
        outline=KEY_EDGE,
        font_size=font,
        white_outline=white_outline,
    )


def _brightness_rocker(
    studio: Any,
    canvas: Any,
    ox: float,
    oy: float,
    s: float,
) -> None:
    """Draw one physical BRT rocker with two existing key identities."""

    cx, cy = xy(ox, oy, s, 536, 484)
    w, h = 88 * s, 44 * s
    canvas.create_round_rect(
        cx - w / 2,
        cy - h / 2,
        cx + w / 2,
        cy + h / 2,
        radius=max(3, int(5 * s)),
        fill="#555454",
        outline="#2b2b2b",
        width=max(1, int(2 * s)),
    )
    canvas.create_text(
        cx,
        cy,
        text="BRT",
        fill=KEY_TEXT,
        font=("Segoe UI Semibold", max(7, int(12 * s))),
    )

    # Left and right transparent-ish hit halves with visible minus/plus.
    for index, x, glyph in ((17, 510, "−"), (18, 562, "+")):
        key = f"key_{index}"
        kx, ky = xy(ox, oy, s, x, 484)
        item = canvas.create_rectangle(
            kx - 20 * s,
            ky - 17 * s,
            kx + 20 * s,
            ky + 17 * s,
            fill="",
            outline=control_color(studio, key),
            width=max(1, int(1.5 * s)),
        )
        tag(studio, canvas, item, key)
        t = canvas.create_text(
            kx,
            ky,
            text=glyph,
            fill="#f7f4ed",
            font=("Segoe UI Semibold", max(7, int(13 * s))),
        )
        tag(studio, canvas, t, key)


def draw_pfp3n_faceplate(
    studio: Any,
    canvas: Any,
    width: int,
    height: int,
) -> None:
    ox, oy, s = fit(width, height, PFP_REFERENCE_SIZE, margin=14)
    _shell(canvas, ox, oy, s)

    lines = display_lines(studio, "pfp3n_bb35", label="PFP3N")
    screen(
        canvas,
        ox,
        oy,
        s,
        (78, 65, 542, 430),
        lines,
        bezel=BEZEL,
        edge=BEZEL_EDGE,
        line_color="#b9f7df",
    )

    for row in range(6):
        y = 122 + row * 53
        lsk(studio, canvas, ox, oy, s, key_index=row, center=(39, y))
        lsk(studio, canvas, ox, oy, s, key_index=row + 6, center=(581, y))

    # Top function keypad.
    top_x = (104, 190, 276, 362, 448)
    for index, x in zip(range(12, 17), top_x):
        _key(studio, canvas, ox, oy, s, index, x, 486)
    _brightness_rocker(studio, canvas, ox, oy, s)

    second_indices = (19, 20, 21, 22, 23)
    for index, x in zip(second_indices, top_x):
        _key(studio, canvas, ox, oy, s, index, x, 542)
    _key(studio, canvas, ox, oy, s, 24, 536, 542, width=76, height=43, font=12)

    # Small EXEC annunciator bar immediately above EXEC in the photo.
    ax1, ay1 = xy(ox, oy, s, 508, 512)
    ax2, ay2 = xy(ox, oy, s, 564, 520)
    canvas.create_round_rect(
        ax1,
        ay1,
        ax2,
        ay2,
        radius=max(2, int(3 * s)),
        fill="#f2f3e8",
        outline="#c9cbc1",
        width=1,
    )

    # Left-side N1/FIX and PREV/NEXT block.
    _key(studio, canvas, ox, oy, s, 25, 104, 602, width=74, height=48, font=12)
    _key(studio, canvas, ox, oy, s, 26, 190, 602, width=74, height=48, font=12)
    _key(studio, canvas, ox, oy, s, 27, 104, 660, width=74, height=48, font=10)
    _key(studio, canvas, ox, oy, s, 28, 190, 660, width=74, height=48, font=10)

    # Round numeric keypad.
    num_positions = (
        (29, 80, 724), (30, 145, 724), (31, 210, 724),
        (32, 80, 786), (33, 145, 786), (34, 210, 786),
        (35, 80, 848), (36, 145, 848), (37, 210, 848),
        (38, 80, 910), (39, 145, 910), (40, 210, 910),
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
            label=PFP_PHYSICAL_LABELS[index],
            face="#4e4b4b",
            font_size=16,
        )

    # Alphabetic 6x5 matrix.
    alpha_x = (300, 365, 430, 495, 560)
    alpha_y = (606, 670, 734, 798, 862, 926)
    index = 41
    for y in alpha_y:
        for x in alpha_x:
            _key(
                studio,
                canvas,
                ox,
                oy,
                s,
                index,
                x,
                y,
                width=52,
                height=48,
                font=15 if len(PFP_PHYSICAL_LABELS[index]) <= 2 else 10,
                white_outline=index in PFP_COMPASS_OUTLINE_KEYS,
            )
            index += 1

    speaker_grille(canvas, ox, oy, s, 32, 706, 858)
    speaker_grille(canvas, ox, oy, s, 603, 706, 858)

    cx, cy = xy(ox, oy, s, 310, 968)
    text(
        canvas,
        cx,
        cy,
        "WINCTRL 3N PFP CAPTAIN",
        s,
        size=7,
        fill="#e4e7e9",
        weight="normal",
    )


MUSLIMSIM_PFP3N_BB35_AUTHORED_FACEPLATE_V1 = True
