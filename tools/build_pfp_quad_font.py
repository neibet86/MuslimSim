"""Append an even-smaller PFD value font to the proven WinCtrl resource.

The input is the established slot-4/5/6 file already used by BB35.  This
offline builder preserves every input byte as an exact prefix, clones the
measured slot-5 font upload transaction into slot 3, and replaces only the
printable glyph pixels with smaller centred Bahnschrift artwork.

It never opens HID hardware, Studio, or X-Plane.
"""

from __future__ import annotations

from pathlib import Path
import struct

from PIL import Image, ImageDraw, ImageFont

import build_pfp_dual_font as base
import build_pfp_shape_tiles as shape_tiles
from muslimsim.devices import pfp_renderer as renderer

# Re-export the established decoder geometry so the offline screen emulator
# can read this generated four-slot resource without duplicating the parser.
font_byte_positions = base.font_byte_positions
GLYPH_SIZE = base.GLYPH_SIZE
BYTES_PER_ROW = base.BYTES_PER_ROW


PROJECT = Path(__file__).resolve().parents[1]
BRIDGE = PROJECT / "bridge"
SOURCE = BRIDGE / "winctrl-pfp-b737-cockpit-bb35-font4-5-6.xpwwf"
OUTPUT = BRIDGE / "winctrl-pfp-b737-cockpit-font3-4-5-6.xpwwf"
PREVIEW = PROJECT / "assets" / "pfp-cockpit-micro17-font3-preview.png"
RIGHT_STRIP_MODULE = PROJECT / "muslimsim" / "devices" / "pfp_right_strip_tiles.py"
TYPEFACE = Path(r"C:\Windows\Fonts\bahnschrift.ttf")

SOURCE_FONT_ID = 5
MICRO_FONT_ID = 3
MICRO_FONT_SIZE = 14

# Slot 3 is used only by the PFD's compact values.  These otherwise-unused
# lower-case code points carry boundary glyphs whose *ink* is shifted toward
# the preceding identifier/value while the proven 17x29 native cell remains
# unchanged.  That gives LS113.3, 1013HPA, 29.92IN and 335H aircraft-like
# joins without overlapping opaque cells, changing the font header, or adding
# another USB drawing command per frame.
BOUNDARY_ALIASES = {
    **{ord(chr(ord("a") + digit)): (str(digit), -4) for digit in range(10)},
    ord("k"): ("H", -4),
    ord("l"): ("I", -4),
    ord("x"): ("-", -4),
}

# Slot 3 is appended after the immutable slot-4/5/6 resource, so its unused
# lower-case characters are also the safe home for the redesigned V/S shape.
# a-l belong to the original boundary aliases, x is the compact altitude
# minus, m-w are the eleven codes deliberately reserved for this exact
# silhouette.  The remaining codes below are code-native ToLiss moving
# markers; their cells are painted only over known uniform PFD backgrounds.
# A changed shape must fail for review instead of consuming an unrelated
# character silently.
RIGHT_STRIP_CODES = list("mnopqrstuvw")
DEVIATION_DIAMOND_CHARACTER = "y"
SPEED_RING_CHARACTER = "z"
SPEED_TRIANGLE_CHARACTER = "~"


def _micro_glyph(codepoint: int, font: ImageFont.FreeTypeFont) -> bytes:
    visible, _legacy_shift = BOUNDARY_ALIASES.get(
        codepoint, (chr(codepoint), 0)
    )
    glyph, image = base.raster_glyph(visible, font)
    bounds = image.getbbox()
    if bounds is None:
        return glyph
    # The controller keeps a fixed 17-pixel cell advance.  Put all visible
    # micro glyph ink against x=1 so the renderer can safely overlap the next
    # opaque cell only after this ink ends.  This is deterministic kerning,
    # not the old blind overlap that chopped centred characters.
    shift_x = 1 - bounds[0]
    if bounds[2] + shift_x > base.CELL_WIDTH:
        raise SystemExit(
            f"Left-aligned glyph {chr(codepoint)!r} would clip {visible!r}"
        )
    shifted = Image.new("L", (base.CELL_WIDTH, base.CELL_HEIGHT), 0)
    shifted.paste(image, (shift_x, 0))
    return base._encode_cell(shifted)


def _bake_right_strip_tiles(memory: bytearray) -> tuple[tuple, tuple, int]:
    """Patch the notched V/S silhouette into unused slot-3 glyphs."""
    runs, remainder = shape_tiles.cut_tiles(
        shape_tiles.shape_mask(renderer.vertical_speed_wedge_rows()),
        base.CELL_WIDTH,
        base.CELL_HEIGHT,
        renderer.HEIGHT,
    )
    available = list(RIGHT_STRIP_CODES)
    tile_codes: dict[bytes, str] = {}
    text_runs: list[tuple[int, int, str]] = []
    for run_x, run_y, keys in runs:
        characters = ""
        for key in keys:
            if key not in tile_codes:
                if not available:
                    raise SystemExit("Ran out of safe slot-3 V/S tile codes")
                tile_codes[key] = available.pop(0)
            characters += tile_codes[key]
        text_runs.append((run_x, run_y, characters))

    wanted = {ord(character): key for key, character in tile_codes.items()}
    patched = 0
    for glyph_start in range(0, len(memory), base.GLYPH_SIZE):
        if glyph_start + base.GLYPH_SIZE > len(memory):
            continue
        codepoint = int.from_bytes(memory[glyph_start:glyph_start + 4], "little")
        key = wanted.get(codepoint)
        if key is None:
            continue
        encoded = shape_tiles.encode_tile(key, base)
        memory[glyph_start + 4:glyph_start + base.GLYPH_SIZE] = encoded
        patched += 1
    if patched != len(wanted):
        raise SystemExit(
            f"Expected {len(wanted)} slot-3 V/S tile glyphs; patched {patched}"
        )
    return (
        tuple(text_runs),
        tuple(shape_tiles.merge_remainder(remainder)),
        len(tile_codes),
    )


def _shape_bits(draw_shape) -> bytes:
    image = Image.new("1", (base.CELL_WIDTH, base.CELL_HEIGHT), 0)
    draw_shape(ImageDraw.Draw(image))
    return bytes(
        1 if image.getpixel((x, y)) else 0
        for y in range(base.CELL_HEIGHT)
        for x in range(base.CELL_WIDTH)
    )


def _bake_special_pfd_glyphs(memory: bytearray) -> None:
    """Patch crisp moving PFD symbols into three reserved slot-3 codes."""
    shapes = {
        DEVIATION_DIAMOND_CHARACTER: _shape_bits(
            lambda draw: draw.polygon(
                ((8, 7), (14, 14), (8, 21), (2, 14)), outline=1, width=2,
            )
        ),
        SPEED_RING_CHARACTER: _shape_bits(
            lambda draw: draw.ellipse((3, 9, 13, 19), outline=1, width=2)
        ),
        SPEED_TRIANGLE_CHARACTER: _shape_bits(
            lambda draw: draw.polygon(
                ((2, 14), (13, 8), (13, 20)), outline=1, width=2,
            )
        ),
    }
    wanted = {
        ord(character): shape_tiles.encode_tile(bits, base)
        for character, bits in shapes.items()
    }
    patched = 0
    for glyph_start in range(0, len(memory), base.GLYPH_SIZE):
        if glyph_start + base.GLYPH_SIZE > len(memory):
            continue
        codepoint = int.from_bytes(memory[glyph_start:glyph_start + 4], "little")
        encoded = wanted.get(codepoint)
        if encoded is None:
            continue
        memory[glyph_start + 4:glyph_start + base.GLYPH_SIZE] = encoded
        patched += 1
    if patched != len(wanted):
        raise SystemExit(
            f"Expected {len(wanted)} reserved slot-3 PFD glyphs; patched {patched}"
        )


def _write_right_strip_module(runs: tuple, remainder: tuple, tile_count: int) -> None:
    """Write the exact slot-3 text runs consumed by the live renderer."""
    lines = [
        '"""Notched PFD right-strip shape stamped from native font slot 3.',
        "",
        "Generated by tools/build_pfp_quad_font.py.  Do not edit by hand.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass",
        "",
        "",
        "@dataclass(frozen=True)",
        "class ShapeTiles:",
        '    """Text runs for one static shape and its final partial rows."""',
        "",
        "    runs: tuple",
        "    remainder: tuple",
        "    font_id: int",
        "",
        "",
        f"TILE_COUNT = {tile_count}",
        f"DEVIATION_DIAMOND_CHARACTER = {DEVIATION_DIAMOND_CHARACTER!r}",
        f"SPEED_RING_CHARACTER = {SPEED_RING_CHARACTER!r}",
        f"SPEED_TRIANGLE_CHARACTER = {SPEED_TRIANGLE_CHARACTER!r}",
        f"DEVIATION_DIAMOND_FONT_ID = {MICRO_FONT_ID}",
        "",
        "VERTICAL_SPEED_WEDGE = ShapeTiles(",
        "    runs=(",
    ]
    for run_x, run_y, characters in runs:
        lines.append(f"        ({run_x}, {run_y}, {characters!r}),")
    lines.extend([
        "    ),",
        f"    remainder={remainder!r},",
        f"    font_id={MICRO_FONT_ID},",
        ")",
        "",
    ])
    RIGHT_STRIP_MODULE.write_text("\n".join(lines), encoding="utf-8")


def append_micro_font(
    source: bytes,
    font: ImageFont.FreeTypeFont,
) -> tuple[bytes, tuple, tuple, int]:
    """Clone the measured slot-5 transaction as a smaller slot-3 font."""
    memory = bytearray(base._font_memory(source, SOURCE_FONT_ID))
    patched = 0
    for glyph_start in range(0, len(memory), base.GLYPH_SIZE):
        if glyph_start + base.GLYPH_SIZE > len(memory):
            continue
        codepoint = int.from_bytes(memory[glyph_start:glyph_start + 4], "little")
        if codepoint not in base.PRINTABLE_ASCII:
            continue
        glyph = _micro_glyph(codepoint, font)
        memory[glyph_start + 4:glyph_start + base.GLYPH_SIZE] = glyph
        patched += 1
    if patched != len(base.PRINTABLE_ASCII):
        raise SystemExit(
            f"Expected {len(base.PRINTABLE_ASCII)} slot-3 glyphs; patched {patched}"
        )
    right_runs, right_remainder, right_tile_count = _bake_right_strip_tiles(memory)
    _bake_special_pfd_glyphs(memory)

    records = base._command_records(source)
    transaction = (max(record[2] for record in records) + 1) & 0xFFFFFFFF
    cloned = bytearray()
    active = False
    cloned_header = False
    cloned_chunks = 0
    for identifier, function_id, _old_transaction, flag, data in records:
        if function_id == 0x106 and len(data) >= 8:
            found_id = int.from_bytes(data[:4], "little")
            if active:
                break
            if found_id != SOURCE_FONT_ID:
                continue
            active = True
            cloned_header = True
            replacement = bytearray(data)
            replacement[:4] = MICRO_FONT_ID.to_bytes(4, "little")
            data = bytes(replacement)
        elif active and function_id == 0x107 and len(data) >= 12:
            found_id, chunk_offset, chunk_size = struct.unpack_from("<III", data, 0)
            if found_id != SOURCE_FONT_ID:
                break
            replacement = bytearray(data[:12])
            replacement[:4] = MICRO_FONT_ID.to_bytes(4, "little")
            replacement.extend(memory[chunk_offset:chunk_offset + chunk_size])
            if len(replacement) != 12 + chunk_size:
                raise SystemExit("Slot-3 font chunk leaves the cloned memory")
            data = bytes(replacement)
            cloned_chunks += 1
        elif active and function_id != 0x105:
            break

        if not active:
            continue
        cloned.extend(struct.pack("<III", identifier, function_id, transaction))
        cloned.append(flag)
        cloned.extend(struct.pack("<I", len(data)))
        cloned.extend(data)
        if function_id == 0x105:
            transaction = (transaction + 1) & 0xFFFFFFFF

    if not cloned_header or cloned_chunks != 21:
        raise SystemExit(
            "Expected one font header and 21 upload chunks; got "
            f"header={cloned_header}, chunks={cloned_chunks}"
        )

    packed = bytearray(source)
    sequence = base._next_report_sequence(source)
    for offset in range(0, len(cloned), base.REPORT_PAYLOAD_BYTES):
        payload = cloned[offset:offset + base.REPORT_PAYLOAD_BYTES]
        report = bytearray(base.REPORT_SIZE)
        report[0] = 0xF0
        report[1] = 0
        report[2] = sequence
        report[3] = len(payload)
        report[4:4 + len(payload)] = payload
        packed.append(base.REPORT_SIZE)
        packed.extend(report)
        sequence = (sequence + 1) & 0xFF
    return bytes(packed), right_runs, right_remainder, right_tile_count


def main() -> int:
    if not SOURCE.is_file():
        raise SystemExit(f"Missing established slot-4/5/6 resource: {SOURCE}")
    if not TYPEFACE.is_file():
        raise SystemExit(f"Missing Windows typeface: {TYPEFACE}")

    source = SOURCE.read_bytes()
    font = ImageFont.truetype(str(TYPEFACE), MICRO_FONT_SIZE)
    output, right_runs, right_remainder, right_tile_count = append_micro_font(
        source, font
    )
    if output[:len(source)] != source:
        raise SystemExit("Appending slot 3 changed the established resource prefix")
    for font_id in (4, 5, 6):
        if base._font_memory(output, font_id) != base._font_memory(source, font_id):
            raise SystemExit(f"Established slot {font_id} changed while appending slot 3")
    if len(base._font_memory(output, MICRO_FONT_ID)) != len(
        base._font_memory(source, SOURCE_FONT_ID)
    ):
        raise SystemExit("Slot-3 upload is incomplete")

    OUTPUT.write_bytes(output)
    _write_right_strip_module(
        right_runs, right_remainder, right_tile_count
    )
    base.write_preview(font, PREVIEW)
    print(
        f"Created {OUTPUT.name}: preserved slots 4/5/6 and appended "
        f"{len(base.PRINTABLE_ASCII)} smaller glyphs in slot 3."
    )
    print(f"Slot 3 includes {len(BOUNDARY_ALIASES)} safe tight-boundary aliases.")
    print(
        f"Slot 3 also carries {right_tile_count} notched V/S shape tiles; "
        f"metadata written to {RIGHT_STRIP_MODULE.relative_to(PROJECT)}."
    )
    print(
        "Slot 3 reserves code-native ToLiss moving markers: "
        f"diamond={DEVIATION_DIAMOND_CHARACTER!r}, "
        f"ring={SPEED_RING_CHARACTER!r}, "
        f"triangle={SPEED_TRIANGLE_CHARACTER!r}."
    )
    print("The complete established slot-4/5/6 resource remains a byte-for-byte prefix.")
    print(f"Preview written: {PREVIEW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
