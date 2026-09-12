"""Build the tight 17x29 MuslimSim bitmap font for PFP native font slot 6.

The PFP supports 1-bit bitmap fonts with widths from 17 to 23 pixels.  The
factory 23-pixel cell creates an unavoidable visual gap between every pair of
letters.  This resource changes font slot 6 to a 17-pixel cell and rasterises
matching cockpit glyphs, giving normal number spacing without unsafe native
cell overlap or expensive per-pixel USB drawing.
"""

from __future__ import annotations

from pathlib import Path
import struct

from PIL import Image, ImageDraw, ImageFont


PROJECT = Path(__file__).resolve().parents[1]
BRIDGE = PROJECT / "bridge"
SOURCE = BRIDGE / "winctrl-pfp-b737-clean-font6.xpwwf"
OUTPUT = BRIDGE / "winctrl-pfp-b737-cockpit-compact17-font6.xpwwf"
PREVIEW = PROJECT / "assets" / "pfp-cockpit-compact17-font-preview.png"
TAPE_PREVIEW = PROJECT / "assets" / "pfp-compact17-tape-preview.png"
TYPEFACE = Path(r"C:\Windows\Fonts\bahnschrift.ttf")

FONT_ID = 6
CELL_WIDTH = 17
CELL_HEIGHT = 29
BYTES_PER_ROW = 3
GLYPH_SIZE = 4 + CELL_HEIGHT * BYTES_PER_ROW
# The cell stays 17 x 29.  Only the artwork inside it grew: the reference 737
# readouts carry digits about two thirds of their cell, where the first
# cockpit font drew barely half, which is what made the live speed and
# altitude look undersized on the panel.
FONT_SIZE = 28
INK_WIDTH = 15
INK_HEIGHT = 23
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


def font_byte_positions(raw: bytes) -> tuple[dict[int, int], bytes, list[int]]:
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
    return result, stream, positions


def patch_font_width(raw: bytearray, stream: bytes, positions: list[int]) -> None:
    """Set font ID 6's native matrix width to 17 pixels inside its 0x106 head."""
    offset = 0
    matches = 0
    while offset + 17 <= len(stream):
        data_size = int.from_bytes(stream[offset + 13:offset + 17], "little")
        end = offset + 17 + data_size
        if end > len(stream):
            break
        function_id = int.from_bytes(stream[offset + 4:offset + 8], "little")
        data_start = offset + 17
        if function_id == 0x106 and data_size >= 8:
            font_id = int.from_bytes(stream[data_start:data_start + 4], "little")
            if font_id == FONT_ID:
                original_width = int.from_bytes(stream[data_start + 4:data_start + 6], "little")
                original_height = int.from_bytes(stream[data_start + 6:data_start + 8], "little")
                if original_width != 23 or original_height != CELL_HEIGHT:
                    raise SystemExit(
                        f"Unexpected font-6 matrix: {original_width}x{original_height}; expected 23x{CELL_HEIGHT}"
                    )
                replacement = CELL_WIDTH.to_bytes(2, "little")
                raw[positions[data_start + 4]] = replacement[0]
                raw[positions[data_start + 5]] = replacement[1]
                matches += 1
        offset = end
    if matches != 1:
        raise SystemExit(f"Expected one font-6 matrix header, found {matches}")


def raster_glyph(character: str, font: ImageFont.FreeTypeFont) -> tuple[bytes, Image.Image]:
    """Return one centred 17x29 one-bit cockpit glyph.

    The glyph is drawn as large as the cell allows.  A glyph wider than the
    cell's ink budget, such as M or W, is condensed rather than clipped or
    allowed to touch its neighbour, which keeps the tall Boeing look without
    breaking the fixed cell pitch the whole layout depends on.
    """
    image = Image.new("L", (CELL_WIDTH, CELL_HEIGHT), 0)
    draw = ImageDraw.Draw(image)
    left, top, right, bottom = draw.textbbox((0, 0), character, font=font)
    ink_width = right - left
    ink_height = bottom - top
    if ink_width <= 0 or ink_height <= 0:
        return _encode_cell(image), image

    if ink_width > INK_WIDTH or ink_height > INK_HEIGHT:
        scratch = Image.new("L", (ink_width + 8, ink_height + 8), 0)
        ImageDraw.Draw(scratch).text((4 - left, 4 - top), character, font=font, fill=255)
        box = scratch.getbbox()
        if box is not None:
            scratch = scratch.crop(box)
            scratch = scratch.resize(
                (min(INK_WIDTH, scratch.width), min(INK_HEIGHT, scratch.height)),
                Image.LANCZOS,
            )
            image.paste(
                scratch,
                ((CELL_WIDTH - scratch.width) // 2, (CELL_HEIGHT - scratch.height) // 2),
            )
    else:
        draw.text(
            ((CELL_WIDTH - ink_width) // 2 - left, (CELL_HEIGHT - ink_height) // 2 - top),
            character,
            font=font,
            fill=255,
        )

    return _encode_cell(image), image


def _encode_cell(image: Image.Image) -> bytes:
    """Pack one grey cell into the panel's one-bit glyph rows."""
    pixels = image.load()
    encoded = bytearray()
    for y in range(CELL_HEIGHT):
        for byte_index in range(BYTES_PER_ROW):
            value = 0
            for bit in range(8):
                x = byte_index * 8 + bit
                if x < CELL_WIDTH and pixels[x, y] >= 96:
                    value |= 1 << (7 - bit)
            encoded.append(value)
    return bytes(encoded)


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


def write_tape_preview(font: ImageFont.FreeTypeFont) -> None:
    """Visual proof of the tight number spacing used on the physical PFD."""
    image = Image.new("RGB", (640, 170), (6, 7, 13))
    draw = ImageDraw.Draw(image)
    draw.rectangle((35, 8, 104, 162), fill=(64, 66, 71))
    draw.rectangle((478, 8, 549, 162), fill=(64, 66, 71))
    draw.rectangle((8, 68, 122, 106), outline=(245, 246, 249), width=2)
    draw.rectangle((440, 68, 556, 106), outline=(245, 246, 249), width=2)

    def paste_text(value: str, x: int, y: int, colour: tuple[int, int, int]) -> None:
        for offset, character in enumerate(value):
            _encoded, glyph = raster_glyph(character, font)
            coloured = Image.new("RGB", glyph.size, colour)
            image.paste(coloured, (x + offset * CELL_WIDTH, y), glyph)

    for text, y in (("240", 16), ("220", 46), ("200", 116)):
        paste_text(text, 43, y, (245, 246, 249))
    for text, y in (("3000", 16), ("2800", 46), ("2400", 116)):
        paste_text(text, 480, y, (245, 246, 249))
    paste_text("175", 32, 74, (245, 246, 249))
    paste_text("2400", 456, 74, (245, 246, 249))
    image.resize((image.width * 2, image.height * 2), Image.Resampling.NEAREST).save(TAPE_PREVIEW)


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"Missing base font resource: {SOURCE}")
    if not TYPEFACE.is_file():
        raise SystemExit(f"Missing Windows typeface: {TYPEFACE}")

    font = ImageFont.truetype(str(TYPEFACE), FONT_SIZE)
    raw = bytearray(SOURCE.read_bytes())
    positions, stream, byte_positions = font_byte_positions(bytes(raw))
    if not positions:
        raise SystemExit("Font ID 6 was not found in the base resource")
    patch_font_width(raw, stream, byte_positions)

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
    write_tape_preview(font)
    print(f"Created {OUTPUT.name}: {patched} tight 17x29 native glyphs.")
    print(f"Preview written: {PREVIEW}")
    print(f"Tape example written: {TAPE_PREVIEW}")


if __name__ == "__main__":
    main()
