"""Build the small MuslimSim cockpit font for PFP native font slot 6.

The PFP controller gives every native character a fixed 23x29 opaque cell.
The display cannot reduce that cell, but it can use small, sharp glyph artwork
inside it.  This font keeps PFD labels light and contained without relying on
overlapping cell backgrounds, which causes chopped letters on the hardware.
"""

from __future__ import annotations

from pathlib import Path
import struct

from PIL import Image, ImageDraw, ImageFont


PROJECT = Path(__file__).resolve().parents[1]
BRIDGE = PROJECT / "bridge"
SOURCE = BRIDGE / "winctrl-pfp-b737-clean-font6.xpwwf"
OUTPUT = BRIDGE / "winctrl-pfp-b737-cockpit-small-font6.xpwwf"
PREVIEW = PROJECT / "assets" / "pfp-cockpit-small-font-preview.png"
TYPEFACE = Path(r"C:\Windows\Fonts\bahnschrift.ttf")

FONT_ID = 6
CELL_WIDTH = 23
CELL_HEIGHT = 29
GLYPH_SIZE = 4 + CELL_HEIGHT * 3
# 17 px is intentionally compact on the physical 640x480 PFP while retaining
# clear, two-pixel cockpit strokes once the one-bit glyph is uploaded.
FONT_SIZE = 17
PRINTABLE_ASCII = range(0x20, 0x7F)


def frame_payload_positions(raw: bytes) -> tuple[bytes, list[int]]:
    stream = bytearray()
    positions: list[int] = []
    offset = 0
    while offset < len(raw):
        packet_size = raw[offset]
        start = offset + 1
        report = raw[start:start + packet_size]
        offset = start + packet_size
        if len(report) < 4 or report[0] != 0xF0 or report[1] != 0x00:
            continue
        payload_size = report[3]
        for index in range(payload_size):
            stream.append(report[4 + index])
            positions.append(start + 4 + index)
    return bytes(stream), positions


def font_byte_positions(raw: bytes) -> dict[int, int]:
    stream, positions = frame_payload_positions(raw)
    result: dict[int, int] = {}
    offset = 0
    while offset + 17 <= len(stream):
        data_size = int.from_bytes(stream[offset + 13:offset + 17], "little")
        end = offset + 17 + data_size
        if end > len(stream):
            break
        function_id = int.from_bytes(stream[offset + 4:offset + 8], "little")
        if function_id == 0x107 and data_size >= 12:
            data_start = offset + 17
            font_id, chunk_offset, chunk_size = struct.unpack_from("<III", stream, data_start)
            chunk_start = data_start + 12
            if font_id == FONT_ID and chunk_start + chunk_size <= end:
                for local_offset in range(chunk_size):
                    result[chunk_offset + local_offset] = positions[chunk_start + local_offset]
        offset = end
    return result


def raster_glyph(character: str, font: ImageFont.FreeTypeFont) -> tuple[bytes, Image.Image]:
    """Return one compact, centred 23x29 native one-bit glyph."""
    image = Image.new("L", (CELL_WIDTH, CELL_HEIGHT), 0)
    draw = ImageDraw.Draw(image)
    left, top, right, bottom = draw.textbbox((0, 0), character, font=font)
    ink_width = right - left
    ink_height = bottom - top
    draw_x = (CELL_WIDTH - ink_width) // 2 - left
    draw_y = (CELL_HEIGHT - ink_height) // 2 - top
    draw.text((draw_x, draw_y), character, font=font, fill=255)

    pixels = image.load()
    encoded = bytearray()
    for y in range(CELL_HEIGHT):
        for byte_index in range(3):
            value = 0
            for bit in range(8):
                x = byte_index * 8 + bit
                if x < CELL_WIDTH and pixels[x, y] >= 128:
                    value |= 1 << (7 - bit)
            encoded.append(value)
    return bytes(encoded), image


def write_preview(font: ImageFont.FreeTypeFont) -> None:
    characters = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ+-./"
    columns = 10
    rows = (len(characters) + columns - 1) // columns
    preview = Image.new("RGB", (columns * CELL_WIDTH, rows * CELL_HEIGHT), (6, 7, 13))
    for index, character in enumerate(characters):
        _encoded, glyph = raster_glyph(character, font)
        coloured = Image.new("RGB", glyph.size, (245, 246, 249))
        preview.paste(coloured, ((index % columns) * CELL_WIDTH, (index // columns) * CELL_HEIGHT), glyph)
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    preview.resize((preview.width * 4, preview.height * 4), Image.Resampling.NEAREST).save(PREVIEW)


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"Missing base font resource: {SOURCE}")
    if not TYPEFACE.is_file():
        raise SystemExit(f"Missing Windows typeface: {TYPEFACE}")

    font = ImageFont.truetype(str(TYPEFACE), FONT_SIZE)
    raw = bytearray(SOURCE.read_bytes())
    positions = font_byte_positions(bytes(raw))
    if not positions:
        raise SystemExit("Font ID 6 was not found in the base resource")

    patched = 0
    for glyph_start in range(0, max(positions) + 1, GLYPH_SIZE):
        indexes = range(glyph_start, glyph_start + GLYPH_SIZE)
        if any(index not in positions for index in indexes):
            continue
        codepoint = int.from_bytes(
            bytes(raw[positions[glyph_start + offset]] for offset in range(4)), "little"
        )
        if codepoint not in PRINTABLE_ASCII:
            continue
        glyph, _image = raster_glyph(chr(codepoint), font)
        for pixel_offset, value in enumerate(glyph):
            raw[positions[glyph_start + 4 + pixel_offset]] = value
        patched += 1

    if patched != len(PRINTABLE_ASCII):
        raise SystemExit(f"Expected {len(PRINTABLE_ASCII)} patched ASCII glyphs; found {patched}")
    OUTPUT.write_bytes(raw)
    write_preview(font)
    print(f"Created {OUTPUT.name}: compacted {patched} native glyphs safely inside their cells.")
    print(f"Preview written: {PREVIEW}")


if __name__ == "__main__":
    main()
