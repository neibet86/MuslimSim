"""Shared contract for background-matched continuous PFD pitch-rung glyphs.

The WinCtrl text engine always paints a rectangular background cell.  The
reviewed production workaround cuts each complete 10/20-degree rung from one
continuous raster into 40x40 native cells, then paints every cell with the
local sky or ground colour.  The rectangle is therefore visually invisible
while the white line retains the clean joins proven on BB35 and BB36.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple


BANK_LINE_FONT_IDS = (7, 8)
BANK_LINE_CELL_WIDTH = 40
BANK_LINE_CELL_HEIGHT = 40
BANK_LINE_BYTES_PER_ROW = (BANK_LINE_CELL_WIDTH + 7) // 8
BANK_LINE_GLYPH_SIZE = 4 + BANK_LINE_BYTES_PER_ROW * BANK_LINE_CELL_HEIGHT
# Keep an exact horizontal rung, two-degree steps through the useful range,
# and exact 45-degree endpoints for the limit-bank test.
BANK_LINE_ANGLES = (-45,) + tuple(range(-44, 45, 2)) + (45,)
BANK_LINE_OUTER = 42.0
BANK_LINE_INNER_GAP = 10.0
BANK_LINE_THICKNESS = 3
BANK_LINE_CANVAS_WIDTH = 120
BANK_LINE_CANVAS_HEIGHT = 120
BANK_LINE_VISIBLE_GLYPHS_PER_FONT = 94
BANK_LINE_FIRST_CODEPOINT = 0x21

_PLAN_PATH = Path(__file__).with_name("pfp_bank_line_plan.json")


def nearest_bank_line_angle(angle: float) -> int:
    """Return the closest reviewed two-degree continuous-rung angle."""
    value = max(-45.0, min(45.0, float(angle)))
    return min(BANK_LINE_ANGLES, key=lambda candidate: abs(candidate - value))


def _load_plan() -> tuple[
    dict[int, Tuple[Tuple[int, int, int, str], ...]],
    dict[int, int],
    dict[tuple[int, str], Tuple[Tuple[int, int, int, int], ...]],
    dict[str, Tuple[Tuple[int, int, int, int], ...]],
]:
    if not _PLAN_PATH.is_file():
        raise RuntimeError(
            "PFD continuous-rung plan is missing; run "
            "tools/build_pfp_bank_line_font.py"
        )
    document = json.loads(_PLAN_PATH.read_text(encoding="utf-8"))
    if int(document.get("version", -1)) < 3:
        raise RuntimeError("PFD continuous-rung plan has no software-alpha masks")
    expected = {
        "cell_width": BANK_LINE_CELL_WIDTH,
        "cell_height": BANK_LINE_CELL_HEIGHT,
        "glyph_size": BANK_LINE_GLYPH_SIZE,
        "outer": int(BANK_LINE_OUTER),
        "inner_gap": int(BANK_LINE_INNER_GAP),
        "thickness": BANK_LINE_THICKNESS,
        "canvas_width": BANK_LINE_CANVAS_WIDTH,
        "canvas_height": BANK_LINE_CANVAS_HEIGHT,
    }
    for key, value in expected.items():
        if int(document.get(key, -1)) != value:
            raise RuntimeError(f"PFD continuous-rung plan has wrong {key}")

    raw_counts = document.get("font_glyph_counts", {})
    counts = {int(font_id): int(count) for font_id, count in raw_counts.items()}
    if tuple(sorted(counts)) != BANK_LINE_FONT_IDS:
        raise RuntimeError("PFD continuous-rung plan has wrong font slots")
    if any(count < 2 or count > 95 for count in counts.values()):
        raise RuntimeError("PFD continuous-rung plan exceeds printable glyph capacity")

    plans: dict[int, Tuple[Tuple[int, int, int, str], ...]] = {}
    for angle in BANK_LINE_ANGLES:
        raw_runs = document.get("angles", {}).get(str(angle))
        if not raw_runs:
            raise RuntimeError(f"PFD continuous-rung plan is missing angle {angle}")
        runs = tuple(
            (int(font_id), int(x), int(y), str(text))
            for font_id, x, y, text in raw_runs
        )
        if any(
            font_id not in BANK_LINE_FONT_IDS or not text
            for font_id, _x, _y, text in runs
        ):
            raise RuntimeError(f"PFD continuous-rung plan angle {angle} is invalid")
        plans[angle] = runs

    line_rectangles: dict[
        tuple[int, str], Tuple[Tuple[int, int, int, int], ...]
    ] = {}
    for raw_key, raw_rectangles in document.get(
        "line_glyph_rectangles", {}
    ).items():
        font_text, code_text = str(raw_key).split(":", 1)
        font_id, character = int(font_text), chr(int(code_text))
        rectangles = tuple(
            tuple(int(value) for value in rectangle)
            for rectangle in raw_rectangles
        )
        if font_id not in BANK_LINE_FONT_IDS or any(
            len(rectangle) != 4
            or rectangle[2] <= 0
            or rectangle[3] <= 0
            or rectangle[0] < 0
            or rectangle[1] < 0
            or rectangle[0] + rectangle[2] > BANK_LINE_CELL_WIDTH
            or rectangle[1] + rectangle[3] > BANK_LINE_CELL_HEIGHT
            for rectangle in rectangles
        ):
            raise RuntimeError("PFD continuous-rung foreground mask is invalid")
        line_rectangles[(font_id, character)] = rectangles
    required_line_glyphs = {
        (font_id, character)
        for runs in plans.values()
        for font_id, _x, _y, text in runs
        for character in text
    }
    if not required_line_glyphs.issubset(line_rectangles):
        raise RuntimeError("PFD continuous-rung foreground masks are incomplete")

    number_width = int(document.get("number_font_width", -1))
    number_height = int(document.get("number_font_height", -1))
    if number_width != 17 or number_height != 29:
        raise RuntimeError("PFD software-alpha number font has wrong geometry")
    number_rectangles = {
        chr(int(codepoint)): tuple(
            tuple(int(value) for value in rectangle)
            for rectangle in raw_rectangles
        )
        for codepoint, raw_rectangles in document.get(
            "number_glyph_rectangles", {}
        ).items()
    }
    if any(
        len(rectangle) != 4
        or rectangle[2] <= 0
        or rectangle[3] <= 0
        or rectangle[0] < 0
        or rectangle[1] < 0
        or rectangle[0] + rectangle[2] > number_width
        or rectangle[1] + rectangle[3] > number_height
        for rectangles in number_rectangles.values()
        for rectangle in rectangles
    ):
        raise RuntimeError("PFD software-alpha number mask is invalid")
    if not set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ.-/+").issubset(
        number_rectangles
    ):
        raise RuntimeError("PFD software-alpha number masks are incomplete")
    return plans, counts, line_rectangles, number_rectangles


# Load lazily.  This also lets the offline builder replace an older generated
# plan after shared geometry changes, without importing stale data first.
_BANK_LINE_PLANS: dict[int, Tuple[Tuple[int, int, int, str], ...]] = {}
BANK_LINE_FONT_GLYPH_COUNTS: dict[int, int] = {}
_BANK_LINE_GLYPH_RECTANGLES: dict[
    tuple[int, str], Tuple[Tuple[int, int, int, int], ...]
] = {}
_PFD_NUMBER_GLYPH_RECTANGLES: dict[
    str, Tuple[Tuple[int, int, int, int], ...]
] = {}


def _ensure_loaded() -> None:
    global _BANK_LINE_PLANS, BANK_LINE_FONT_GLYPH_COUNTS
    global _BANK_LINE_GLYPH_RECTANGLES, _PFD_NUMBER_GLYPH_RECTANGLES
    if _BANK_LINE_PLANS:
        return
    (
        _BANK_LINE_PLANS,
        BANK_LINE_FONT_GLYPH_COUNTS,
        _BANK_LINE_GLYPH_RECTANGLES,
        _PFD_NUMBER_GLYPH_RECTANGLES,
    ) = _load_plan()


def bank_rung_runs(angle: float) -> Tuple[Tuple[int, int, int, str], ...]:
    """Return `(font, dx, dy, text)` runs for one complete paired rung."""
    _ensure_loaded()
    return _BANK_LINE_PLANS[nearest_bank_line_angle(angle)]


def bank_line_glyph_rectangles(
    font_id: int,
    character: str,
) -> Tuple[Tuple[int, int, int, int], ...]:
    """Return the exact foreground pixels for one clean line glyph."""
    _ensure_loaded()
    return _BANK_LINE_GLYPH_RECTANGLES.get((int(font_id), str(character)), ())


def pfd_number_glyph_rectangles(
    character: str,
) -> Tuple[Tuple[int, int, int, int], ...]:
    """Return foreground-only rectangles for one exact slot-3 character."""
    _ensure_loaded()
    return _PFD_NUMBER_GLYPH_RECTANGLES.get(str(character), ())


def bank_line_font_glyph_counts() -> dict[int, int]:
    """Return generated glyph counts, loading the reviewed plan if needed."""
    _ensure_loaded()
    return dict(BANK_LINE_FONT_GLYPH_COUNTS)
