"""Verify the PFD's hybrid text transparency without opening hardware.

The WinCtrl controller ignores native text-cell alpha.  Production therefore
uses a hybrid renderer: a fast opaque glyph is allowed only over one uniform
background colour, while a cell crossing the horizon or rounded shell is
replaced by foreground-only rectangles from the exact same glyph bitmap.

This check proves that the generated masks are pixel-identical to the uploaded
font and that no native line/number cell spans a moving sky/earth boundary.
It never opens X-Plane, Studio, HID, COM, or a physical display.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.devices import pfp_renderer as renderer
from muslimsim.devices.pfp_bank_line_font import (
    BANK_LINE_ANGLES,
    BANK_LINE_CELL_HEIGHT,
    BANK_LINE_CELL_WIDTH,
    bank_line_glyph_rectangles,
    bank_rung_runs,
    pfd_number_glyph_rectangles,
)


def _emulator():
    path = PROJECT / "tools" / "render_pfp_frame_png.py"
    spec = importlib.util.spec_from_file_location("_pfp_mask_emulator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load PFD font emulator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pixels_from_rectangles(width: int, height: int, rectangles) -> bytes:
    pixels = bytearray(width * height)
    for x, y, run_width, run_height in rectangles:
        for row in range(y, y + run_height):
            for column in range(x, x + run_width):
                pixels[row * width + column] = 255
    return bytes(pixels)


def check_generated_masks() -> None:
    emulator = _emulator()
    loaded = {
        font_id: emulator._load_font_glyphs(font_id)[0]
        for font_id in (3, 7, 8)
    }
    line_characters = {
        (font_id, character)
        for angle in BANK_LINE_ANGLES
        for font_id, _x, _y, text in bank_rung_runs(angle)
        for character in text
    }
    for font_id, character in line_characters:
        expected = bytes(loaded[font_id][character].get_flattened_data())
        actual = _pixels_from_rectangles(
            BANK_LINE_CELL_WIDTH,
            BANK_LINE_CELL_HEIGHT,
            bank_line_glyph_rectangles(font_id, character),
        )
        if actual != expected:
            raise AssertionError(
                f"line foreground mask differs: slot {font_id} {character!r}"
            )
    for codepoint in range(0x20, 0x7F):
        character = chr(codepoint)
        expected = bytes(loaded[3][character].get_flattened_data())
        actual = _pixels_from_rectangles(
            renderer.FONT_CELL_WIDTH,
            renderer.FONT_CELL_HEIGHT,
            pfd_number_glyph_rectangles(character),
        )
        if actual != expected:
            raise AssertionError(
                f"number foreground mask differs: {character!r}"
            )
    print(
        f"masks: {len(line_characters)} clean-line glyphs and 95 slot-3 "
        "characters are pixel-identical"
    )


class ProbeCanvas:
    def __init__(self) -> None:
        self._muslimsim_bank_line_font = True
        self._colour = renderer.WHITE
        self.texts: list[tuple] = []

    def colour(self, red: int, green: int, blue: int) -> None:
        self._colour = (red, green, blue)

    def fill(self, _x: int, _y: int, _width: int, _height: int) -> None:
        return

    def text(self, x, y, value, foreground, background, font_id) -> None:
        self.texts.append(
            (int(x), int(y), str(value), tuple(foreground),
             tuple(background), int(font_id))
        )


def check_native_cells() -> None:
    old_phase = renderer._packed_value_phase
    old_recovery = renderer._recovery_frame
    renderer._packed_value_phase = 3
    renderer._recovery_frame = False
    checked = 0
    masked_cells = 0
    max_mask_rectangles = 0
    try:
        for pitch in range(-20, 21, 5):
            horizon_y = 226.0 + pitch * 5.0
            for roll in range(-45, 46, 5):
                slope = math.tan(math.radians(float(roll)))
                canvas = ProbeCanvas()
                renderer._draw_bank_and_pitch(canvas, horizon_y, slope)
                for x, y, text, _foreground, background, font_id in canvas.texts:
                    if font_id not in (3, 7, 8):
                        continue
                    width = (
                        BANK_LINE_CELL_WIDTH if font_id in (7, 8)
                        else renderer.FONT_CELL_WIDTH
                    ) * len(text)
                    height = (
                        BANK_LINE_CELL_HEIGHT if font_id in (7, 8)
                        else renderer.FONT_CELL_HEIGHT
                    )
                    expected = renderer._uniform_attitude_background(
                        x, y, width, height, horizon_y, slope
                    )
                    if expected is None or expected != background:
                        raise AssertionError(
                            f"opaque slot {font_id} cell crosses live background "
                            f"at pitch={pitch} roll={roll}: {(x, y, text)}"
                        )
                    checked += 1

                ladder_slope = -slope
                line_angle = math.degrees(math.atan(ladder_slope))
                for pitch_mark in (-20.0, -10.0, 10.0, 20.0):
                    center_x, center_y = renderer._pitch_ladder_center(
                        horizon_y, ladder_slope, pitch_mark
                    )
                    parts = renderer._bank_rung_parts(
                        center_x,
                        center_y,
                        line_angle,
                        horizon_y,
                        slope,
                    )
                    if parts is None:
                        # At the grid extremes the complete mark can be beyond
                        # the rounded attitude shell, so there is no ink to
                        # render and therefore no hybrid part to validate.
                        continue
                    _glyphs, foreground = parts
                    if foreground:
                        masked_cells += 1
                        max_mask_rectangles = max(
                            max_mask_rectangles, len(foreground)
                        )
    finally:
        renderer._packed_value_phase = old_phase
        renderer._recovery_frame = old_recovery
    if masked_cells == 0:
        raise AssertionError("test grid never exercised software transparency")
    print(
        f"geometry: {checked} native cells are background-safe; "
        f"{masked_cells} rung cases used foreground-only masks "
        f"(maximum {max_mask_rectangles} rectangles)"
    )


def main() -> int:
    check_generated_masks()
    check_native_cells()
    print("PASS: hybrid line/text transparency preserves every live background pixel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
