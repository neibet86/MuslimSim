"""Build the native cockpit font resource used by BB35 and BB36.

The immutable Point A resource already contains the proven compact PFD font in
slot 5 and the larger ND/ENG/HYD font in slot 6.  A third, still smaller 17x29
font is appended in slot 4 for BB35's Boeing ND only.  The complete Point A
resource stays an exact byte-for-byte prefix, so PFD and BB36 upload packets
are not rebuilt or rewritten.

The script is offline.  It never opens HID hardware, X-Plane, or Studio.
"""

from __future__ import annotations

from pathlib import Path
import struct

from PIL import Image, ImageDraw, ImageFont


PROJECT = Path(__file__).resolve().parents[1]
BRIDGE = PROJECT / "bridge"
SOURCE = BRIDGE / "winctrl-pfp-b737-cockpit-point-a-font5-6.xpwwf"
OUTPUT = BRIDGE / "winctrl-pfp-b737-cockpit-bb35-font4-5-6.xpwwf"
PREVIEW = PROJECT / "assets" / "pfp-cockpit-small17-font5-preview.png"
TINY_PREVIEW = PROJECT / "assets" / "pfp-cockpit-tiny17-font4-preview.png"
TYPEFACE = Path(r"C:\Windows\Fonts\bahnschrift.ttf")

FONT_ID = 5
TINY_FONT_ID = 4
CELL_WIDTH = 17
CELL_HEIGHT = 29
BYTES_PER_ROW = 3
GLYPH_SIZE = 4 + CELL_HEIGHT * BYTES_PER_ROW
FONT_SIZE = 22
INK_WIDTH = 13
INK_HEIGHT = 19
TINY_FONT_SIZE = 18
TINY_INK_WIDTH = 10
TINY_INK_HEIGHT = 15
REPORT_SIZE = 64
REPORT_PAYLOAD_BYTES = 56
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


def font_byte_positions(
    raw: bytes,
    font_id: int = FONT_ID,
) -> tuple[dict[int, int], bytes, list[int]]:
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
            found_id, chunk_offset, chunk_size = struct.unpack_from(
                "<III", stream, data_start
            )
            chunk_start = data_start + 12
            if found_id == int(font_id) and chunk_start + chunk_size <= end:
                for local_offset in range(chunk_size):
                    result[chunk_offset + local_offset] = positions[
                        chunk_start + local_offset
                    ]
        offset = end
    return result, stream, positions


def _encode_cell(image: Image.Image) -> bytes:
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


def raster_glyph(
    character: str,
    font: ImageFont.FreeTypeFont,
    ink_width: int = INK_WIDTH,
    ink_height: int = INK_HEIGHT,
) -> tuple[bytes, Image.Image]:
    image = Image.new("L", (CELL_WIDTH, CELL_HEIGHT), 0)
    scratch_draw = ImageDraw.Draw(image)
    left, top, right, bottom = scratch_draw.textbbox((0, 0), character, font=font)
    ink_width = right - left
    ink_height = bottom - top
    if ink_width <= 0 or ink_height <= 0:
        return _encode_cell(image), image

    scratch = Image.new("L", (ink_width + 8, ink_height + 8), 0)
    ImageDraw.Draw(scratch).text(
        (4 - left, 4 - top), character, font=font, fill=255
    )
    box = scratch.getbbox()
    if box is not None:
        scratch = scratch.crop(box)
        if scratch.width > ink_width or scratch.height > ink_height:
            scale = min(
                ink_width / max(1, scratch.width),
                ink_height / max(1, scratch.height),
            )
            scratch = scratch.resize(
                (
                    max(1, int(round(scratch.width * scale))),
                    max(1, int(round(scratch.height * scale))),
                ),
                Image.Resampling.LANCZOS,
            )
        image.paste(
            scratch,
            (
                (CELL_WIDTH - scratch.width) // 2,
                (CELL_HEIGHT - scratch.height) // 2,
            ),
        )
    return _encode_cell(image), image


def write_preview(
    font: ImageFont.FreeTypeFont,
    path: Path = PREVIEW,
    ink_width: int = INK_WIDTH,
    ink_height: int = INK_HEIGHT,
) -> None:
    characters = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ+-./"
    columns = 10
    rows = (len(characters) + columns - 1) // columns
    preview = Image.new(
        "RGB", (columns * CELL_WIDTH, rows * CELL_HEIGHT), (6, 7, 13)
    )
    for index, character in enumerate(characters):
        _encoded, glyph = raster_glyph(character, font, ink_width, ink_height)
        coloured = Image.new("RGB", glyph.size, (245, 246, 249))
        preview.paste(
            coloured,
            ((index % columns) * CELL_WIDTH, (index // columns) * CELL_HEIGHT),
            glyph,
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    preview.resize(
        (preview.width * 4, preview.height * 4), Image.Resampling.NEAREST
    ).save(path)


def _font_memory(raw: bytes, font_id: int) -> bytes:
    """Return one uploaded font's contiguous firmware memory image."""
    positions, _stream, _byte_positions = font_byte_positions(raw, font_id)
    if not positions:
        raise SystemExit(f"Font ID {font_id} was not found in the resource")
    expected = set(range(max(positions) + 1))
    if set(positions) != expected:
        raise SystemExit(f"Font ID {font_id} has a sparse upload")
    return bytes(raw[positions[index]] for index in range(max(positions) + 1))


def _command_records(raw: bytes) -> list[tuple[int, int, int, int, bytes]]:
    """Decode the structured native commands carried by the F0 reports."""
    stream, _positions = frame_payload_positions(raw)
    result: list[tuple[int, int, int, int, bytes]] = []
    offset = 0
    while offset + 17 <= len(stream):
        data_size = int.from_bytes(stream[offset + 13:offset + 17], "little")
        end = offset + 17 + data_size
        if end > len(stream):
            raise SystemExit("Font resource ends inside a native command")
        result.append((
            int.from_bytes(stream[offset:offset + 4], "little"),
            int.from_bytes(stream[offset + 4:offset + 8], "little"),
            int.from_bytes(stream[offset + 8:offset + 12], "little"),
            int(stream[offset + 12]),
            bytes(stream[offset + 17:end]),
        ))
        offset = end
    if offset != len(stream):
        raise SystemExit("Font resource has a partial native command tail")
    return result


def _next_report_sequence(raw: bytes) -> int:
    """Continue the resource's existing F0 report sequence."""
    offset = 0
    last = 0
    while offset < len(raw):
        packet_size = raw[offset]
        packet = raw[offset + 1:offset + 1 + packet_size]
        if len(packet) >= 3 and packet[0] == 0xF0:
            last = int(packet[2])
        offset += 1 + packet_size
    return (last + 1) & 0xFF


def append_tiny_font(dual: bytes, font: ImageFont.FreeTypeFont) -> bytes:
    """Append a slot-4 clone with smaller printable ink to the proven resource.

    The command types, chunk sizes and commit records are copied from the
    measured slot-5 upload.  Only the declared font ID and printable glyph
    pixels differ.  This avoids inventing a new vendor transaction.
    """
    tiny_memory = bytearray(_font_memory(dual, FONT_ID))
    patched = 0
    for glyph_start in range(0, len(tiny_memory), GLYPH_SIZE):
        if glyph_start + GLYPH_SIZE > len(tiny_memory):
            continue
        codepoint = int.from_bytes(tiny_memory[glyph_start:glyph_start + 4], "little")
        if codepoint not in PRINTABLE_ASCII:
            continue
        glyph, _image = raster_glyph(
            chr(codepoint), font, TINY_INK_WIDTH, TINY_INK_HEIGHT
        )
        tiny_memory[glyph_start + 4:glyph_start + GLYPH_SIZE] = glyph
        patched += 1
    if patched != len(PRINTABLE_ASCII):
        raise SystemExit(
            f"Expected {len(PRINTABLE_ASCII)} slot-4 glyphs; patched {patched}"
        )

    records = _command_records(dual)
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
            if found_id != FONT_ID:
                continue
            active = True
            cloned_header = True
            replacement = bytearray(data)
            replacement[:4] = TINY_FONT_ID.to_bytes(4, "little")
            data = bytes(replacement)
        elif active and function_id == 0x107 and len(data) >= 12:
            found_id, chunk_offset, chunk_size = struct.unpack_from("<III", data, 0)
            if found_id != FONT_ID:
                break
            replacement = bytearray(data[:12])
            replacement[:4] = TINY_FONT_ID.to_bytes(4, "little")
            replacement.extend(tiny_memory[chunk_offset:chunk_offset + chunk_size])
            if len(replacement) != 12 + chunk_size:
                raise SystemExit("Slot-4 font chunk leaves the cloned memory")
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
            f"Expected one font header and 21 upload chunks; got "
            f"header={cloned_header}, chunks={cloned_chunks}"
        )

    packed = bytearray(dual)
    sequence = _next_report_sequence(dual)
    for offset in range(0, len(cloned), REPORT_PAYLOAD_BYTES):
        payload = cloned[offset:offset + REPORT_PAYLOAD_BYTES]
        report = bytearray(REPORT_SIZE)
        report[0] = 0xF0
        report[1] = 0
        report[2] = sequence
        report[3] = len(payload)
        report[4:4 + len(payload)] = payload
        packed.append(REPORT_SIZE)
        packed.extend(report)
        sequence = (sequence + 1) & 0xFF
    return bytes(packed)


def main() -> int:
    if not SOURCE.is_file():
        raise SystemExit(f"Missing immutable Point A font resource: {SOURCE}")
    if not TYPEFACE.is_file():
        raise SystemExit(f"Missing Windows typeface: {TYPEFACE}")

    dual = SOURCE.read_bytes()
    if not _font_memory(dual, FONT_ID) or not _font_memory(dual, 6):
        raise SystemExit("Point A resource does not contain both established fonts")
    font = ImageFont.truetype(str(TYPEFACE), FONT_SIZE)
    tiny_font = ImageFont.truetype(str(TYPEFACE), TINY_FONT_SIZE)
    output = append_tiny_font(dual, tiny_font)
    if output[:len(dual)] != dual:
        raise SystemExit("Appending slot 4 changed the established slot-5/6 prefix")
    if _font_memory(output, FONT_ID) != _font_memory(dual, FONT_ID):
        raise SystemExit("Slot 5 changed while appending the BB35 font")
    if _font_memory(output, 6) != _font_memory(dual, 6):
        raise SystemExit("Slot 6 changed while appending the BB35 font")
    if len(_font_memory(output, TINY_FONT_ID)) != len(_font_memory(dual, FONT_ID)):
        raise SystemExit("Slot 4 upload is incomplete")

    OUTPUT.write_bytes(output)
    write_preview(font)
    write_preview(
        tiny_font, TINY_PREVIEW, TINY_INK_WIDTH, TINY_INK_HEIGHT
    )
    print(
        f"Created {OUTPUT.name}: Point A slots 5/6 plus "
        f"{len(PRINTABLE_ASCII)} tiny glyphs in appended slot 4."
    )
    print("The complete slot-5/slot-6 resource remains a byte-for-byte prefix.")
    print(f"Preview written: {PREVIEW}")
    print(f"Tiny preview written: {TINY_PREVIEW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
