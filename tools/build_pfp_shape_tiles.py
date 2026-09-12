"""Bake the PFD's static shapes into spare glyph codes of native font 6.

The PFP can only fill rectangles or stamp runs of opaque font cells.  A
rectangle costs twenty-five bytes of USB traffic; one 17x29 font cell inside a
text run costs about one byte.  Shapes that never change - the grey heading
rose and the vertical-speed wedge - are therefore far cheaper to stamp than to
rasterise every frame, and they come out pixel-exact either way.

The PFD only uses digits, capitals and a little punctuation, so the lower-case
codes in the font are free.  This tool cuts each static shape into 17x29
tiles, stores the distinct ones in those free codes, and writes
`muslimsim/devices/pfp_shape_tiles.py` with the runs the renderer stamps.

It never opens the PFP, COM5, the WinCtrl hardware, or X-Plane.  Run it after
`build_pfp_compact17_font.py`, which rewrites every printable glyph and would
otherwise overwrite the tiles.

Usage:
    python tools/build_pfp_compact17_font.py
    python tools/build_pfp_shape_tiles.py
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.devices import pfp_renderer as renderer

FONT_BUILDER = PROJECT / "tools" / "build_pfp_compact17_font.py"
GENERATED = PROJECT / "muslimsim" / "devices" / "pfp_shape_tiles.py"

# Codes the PFD never draws.  Lower case first, then punctuation it does not
# use; the tape, FMA and readouts only ever need digits, capitals, space,
# full stop, solidus and hyphen.
FREE_CODES = [chr(code) for code in range(ord("a"), ord("z") + 1)]
FREE_CODES += list("!\"#$%&'()*+,;:<=>?@[]^_{|}~")


def _load_font_builder():
    spec = importlib.util.spec_from_file_location("_pfp_font_builder", FONT_BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def shape_mask(rows) -> set[tuple[int, int]]:
    """Turn a shape's row list into the set of pixels it covers."""
    pixels: set[tuple[int, int]] = set()
    for x, y, width in rows:
        for offset in range(width):
            pixels.add((x + offset, y))
    return pixels


def cut_tiles(pixels: set[tuple[int, int]], cell_width: int, cell_height: int, height_limit: int):
    """Cut a pixel set into aligned tiles, skipping the empty ones.

    Returns the tile grid origin, the runs of tile keys, and any rows the tile
    grid cannot reach because a full cell would fall off the display.
    """
    left = min(x for x, _y in pixels)
    top = min(y for _x, y in pixels)
    right = max(x for x, _y in pixels) + 1
    bottom = max(y for _x, y in pixels) + 1

    usable_bottom = top
    while usable_bottom + cell_height <= min(bottom, height_limit):
        usable_bottom += cell_height

    runs: list[tuple[int, int, list[bytes]]] = []
    for row_y in range(top, usable_bottom, cell_height):
        run_x: int | None = None
        run: list[bytes] = []
        for column_x in range(left, right, cell_width):
            bits = bytearray()
            for y in range(row_y, row_y + cell_height):
                for x in range(column_x, column_x + cell_width):
                    bits.append(1 if (x, y) in pixels else 0)
            key = bytes(bits)
            if not any(key):
                if run:
                    runs.append((run_x, row_y, run))
                    run_x, run = None, []
                continue
            if run_x is None:
                run_x = column_x
            run.append(key)
        if run:
            runs.append((run_x, row_y, run))

    remainder: list[tuple[int, int, int, int]] = []
    for y in range(usable_bottom, bottom):
        row = sorted(x for x, pixel_y in pixels if pixel_y == y)
        if row:
            remainder.append((row[0], y, row[-1] - row[0] + 1, 1))
    return runs, remainder


def merge_remainder(remainder):
    """Collapse identical remainder rows into taller rectangles."""
    merged: list[list[int]] = []
    for x, y, width, height in remainder:
        if merged and merged[-1][0] == x and merged[-1][2] == width and merged[-1][1] + merged[-1][3] == y:
            merged[-1][3] += height
            continue
        merged.append([x, y, width, height])
    return [tuple(entry) for entry in merged]


def encode_tile(key: bytes, builder) -> bytes:
    """Pack one tile into the font's one-bit glyph rows."""
    encoded = bytearray()
    for row in range(builder.CELL_HEIGHT):
        for byte_index in range(builder.BYTES_PER_ROW):
            value = 0
            for bit in range(8):
                x = byte_index * 8 + bit
                if x < builder.CELL_WIDTH and key[row * builder.CELL_WIDTH + x]:
                    value |= 1 << (7 - bit)
            encoded.append(value)
    return bytes(encoded)


def main() -> int:
    builder = _load_font_builder()
    font_path = builder.OUTPUT
    if not font_path.is_file():
        raise SystemExit(f"Build the cockpit font first: {font_path.name}")

    shapes = {
        "COMPASS_ROSE": renderer.compass_rose_rows(),
        "VERTICAL_SPEED_WEDGE": renderer.vertical_speed_wedge_rows(),
    }

    tile_codes: dict[bytes, str] = {}
    generated: dict[str, tuple] = {}
    for name, rows in shapes.items():
        runs, remainder = cut_tiles(
            shape_mask(rows), builder.CELL_WIDTH, builder.CELL_HEIGHT, renderer.HEIGHT
        )
        text_runs = []
        for run_x, run_y, keys in runs:
            characters = ""
            for key in keys:
                if key not in tile_codes:
                    if not FREE_CODES:
                        raise SystemExit("Ran out of spare glyph codes for shape tiles")
                    tile_codes[key] = FREE_CODES.pop(0)
                characters += tile_codes[key]
            text_runs.append((run_x, run_y, characters))
        generated[name] = (tuple(text_runs), tuple(merge_remainder(remainder)))
        print(f"  {name:<22} {len(text_runs)} runs, {len(remainder)} remainder rows")

    raw = bytearray(font_path.read_bytes())
    positions, stream, byte_positions = builder.font_byte_positions(bytes(raw))
    if not positions:
        raise SystemExit("Font ID 6 was not found in the cockpit font")

    wanted = {ord(character): key for key, character in tile_codes.items()}
    patched = 0
    for glyph_start in range(0, max(positions) + 1, builder.GLYPH_SIZE):
        indexes = range(glyph_start, glyph_start + builder.GLYPH_SIZE)
        if any(index not in positions for index in indexes):
            continue
        codepoint = int.from_bytes(
            bytes(raw[positions[glyph_start + offset]] for offset in range(4)), "little"
        )
        if codepoint not in wanted:
            continue
        for pixel_offset, value in enumerate(encode_tile(wanted[codepoint], builder)):
            raw[positions[glyph_start + 4 + pixel_offset]] = value
        patched += 1

    if patched != len(wanted):
        raise SystemExit(f"Expected {len(wanted)} tile glyphs; patched {patched}")
    font_path.write_bytes(raw)

    lines = [
        '"""Static PFD shapes stamped from spare glyph codes of native font 6.',
        "",
        "Generated by tools/build_pfp_shape_tiles.py.  Do not edit by hand: run",
        "the cockpit font builder and then the tile builder again.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass",
        "",
        "",
        "@dataclass(frozen=True)",
        "class ShapeTiles:",
        '    """Text runs that stamp one static shape, plus any rectangle rows."""',
        "",
        "    runs: tuple",
        "    remainder: tuple",
        "",
        "",
        f"TILE_COUNT = {len(tile_codes)}",
        "",
    ]
    for name, (runs, remainder) in generated.items():
        lines.append(f"{name} = ShapeTiles(")
        lines.append("    runs=(")
        for run_x, run_y, characters in runs:
            lines.append(f"        ({run_x}, {run_y}, {characters!r}),")
        lines.append("    ),")
        lines.append(f"    remainder={remainder!r},")
        lines.append(")")
        lines.append("")
    GENERATED.write_text("\n".join(lines), encoding="utf-8")

    print(f"Patched {patched} tile glyphs into {font_path.name}")
    print(f"Wrote {GENERATED.relative_to(PROJECT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
