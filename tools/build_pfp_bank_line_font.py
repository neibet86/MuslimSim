"""Append background-matched continuous pitch-rung fonts to the live PFD.

The established slot-3/4/5/6 resource remains an exact byte-for-byte prefix.
Slots 7 and 8 store the unique 40x40 tiles cut from complete paired 10/20
degree rungs at every two-degree bank angle.  The runtime plan groups adjacent
tiles into native text runs and supplies the local sky/ground cell colour.

This builder is offline: it never opens hardware, X-Plane, or MuslimSim Studio.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import struct
import sys

from PIL import Image, ImageDraw


PROJECT = Path(__file__).resolve().parents[1]
BRIDGE = PROJECT / "bridge"
SOURCE = BRIDGE / "winctrl-pfp-b737-cockpit-font3-4-5-6.xpwwf"
OUTPUT = BRIDGE / "winctrl-pfp-b737-cockpit-font3-4-5-6-8.xpwwf"
PLAN_OUTPUT = PROJECT / "muslimsim" / "devices" / "pfp_bank_line_plan.json"
PREVIEW = PROJECT / "assets" / "pfp-bank-line-font8-preview.png"

if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.devices.pfp_bank_line_font import (
    BANK_LINE_ANGLES,
    BANK_LINE_BYTES_PER_ROW,
    BANK_LINE_CANVAS_HEIGHT,
    BANK_LINE_CANVAS_WIDTH,
    BANK_LINE_CELL_HEIGHT,
    BANK_LINE_CELL_WIDTH,
    BANK_LINE_FIRST_CODEPOINT,
    BANK_LINE_FONT_IDS,
    BANK_LINE_GLYPH_SIZE,
    BANK_LINE_INNER_GAP,
    BANK_LINE_OUTER,
    BANK_LINE_THICKNESS,
    BANK_LINE_VISIBLE_GLYPHS_PER_FONT,
)


def _load_resource_parser():
    path = PROJECT / "tools" / "build_pfp_dual_font.py"
    spec = importlib.util.spec_from_file_location("_pfp_resource_parser", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the established PFP resource parser")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load_resource_parser()


def _encode_mask(bits: bytes) -> bytes:
    result = bytearray()
    for y in range(BANK_LINE_CELL_HEIGHT):
        for byte_index in range(BANK_LINE_BYTES_PER_ROW):
            value = 0
            for bit in range(8):
                x = byte_index * 8 + bit
                index = y * BANK_LINE_CELL_WIDTH + x
                if x < BANK_LINE_CELL_WIDTH and bits[index]:
                    value |= 1 << (7 - bit)
            result.append(value)
    return bytes(result)


def _mask_rectangles(
    bits: bytes,
    width: int,
    height: int,
) -> list[list[int]]:
    """Return exact foreground-only rectangles for one 1-bit glyph mask.

    The LCD text command always repaints its complete background cell.  These
    rectangles are the software-alpha fallback: only foreground pixels are
    emitted when a cell overlaps the moving sky/earth boundary.  Adjacent
    identical scanline spans are merged vertically without changing a pixel.
    """
    active: dict[tuple[int, int], list[int]] = {}
    finished: list[list[int]] = []
    for y in range(height):
        spans: list[tuple[int, int]] = []
        x = 0
        while x < width:
            if not bits[y * width + x]:
                x += 1
                continue
            start = x
            while x < width and bits[y * width + x]:
                x += 1
            spans.append((start, x - start))
        current = set(spans)
        for key in tuple(active):
            if key not in current:
                finished.append(active.pop(key))
        for x, run_width in spans:
            key = (x, run_width)
            if key in active:
                active[key][3] += 1
            else:
                active[key] = [x, y, run_width, 1]
    finished.extend(active.values())
    return sorted(finished, key=lambda rect: (rect[1], rect[0]))


def _font_header(source: bytes, font_id: int) -> tuple[int, int, int]:
    for _identifier, function_id, _transaction, _flag, data in base._command_records(source):
        if function_id != 0x106 or len(data) < 12:
            continue
        if int.from_bytes(data[:4], "little") != int(font_id):
            continue
        return (
            int.from_bytes(data[4:6], "little"),
            int.from_bytes(data[6:8], "little"),
            int.from_bytes(data[8:12], "little"),
        )
    raise RuntimeError(f"font slot {font_id} header is missing")


def _font_foreground_rectangles(
    source: bytes,
    font_id: int,
) -> tuple[int, int, dict[str, list[list[int]]]]:
    """Decode printable glyph ink from the exact resource sent to the panel."""
    width, height, glyph_size = _font_header(source, font_id)
    bytes_per_row = (width + 7) // 8
    if glyph_size != 4 + bytes_per_row * height:
        raise RuntimeError(f"font slot {font_id} has inconsistent geometry")
    result: dict[str, list[list[int]]] = {}
    memory = base._font_memory(source, font_id)
    for offset in range(0, len(memory), glyph_size):
        glyph = memory[offset:offset + glyph_size]
        if len(glyph) != glyph_size:
            continue
        codepoint = int.from_bytes(glyph[:4], "little")
        if not 0x20 <= codepoint <= 0x7E:
            continue
        bits = bytearray(width * height)
        for y in range(height):
            for byte_index in range(bytes_per_row):
                value = glyph[4 + y * bytes_per_row + byte_index]
                for bit in range(8):
                    x = byte_index * 8 + bit
                    if x < width and value & (1 << (7 - bit)):
                        bits[y * width + x] = 1
        result[str(codepoint)] = _mask_rectangles(bytes(bits), width, height)
    return width, height, result


def _rung_tiles(angle: int) -> tuple[tuple[int, int, bytes], ...]:
    image = Image.new(
        "1", (BANK_LINE_CANVAS_WIDTH, BANK_LINE_CANVAS_HEIGHT), 0
    )
    draw = ImageDraw.Draw(image)
    center_x = BANK_LINE_CANVAS_WIDTH / 2.0
    center_y = BANK_LINE_CANVAS_HEIGHT / 2.0
    radians = math.radians(float(angle))
    tangent = (math.cos(radians), math.sin(radians))
    for start, end in (
        (-BANK_LINE_OUTER, -BANK_LINE_INNER_GAP),
        (BANK_LINE_INNER_GAP, BANK_LINE_OUTER),
    ):
        draw.line(
            (
                round(center_x + start * tangent[0]),
                round(center_y + start * tangent[1]),
                round(center_x + end * tangent[0]),
                round(center_y + end * tangent[1]),
            ),
            fill=1,
            width=BANK_LINE_THICKNESS,
        )
    pixels = image.load()
    tiles = []
    for y0 in range(0, BANK_LINE_CANVAS_HEIGHT, BANK_LINE_CELL_HEIGHT):
        for x0 in range(0, BANK_LINE_CANVAS_WIDTH, BANK_LINE_CELL_WIDTH):
            bits = bytes(
                1 if pixels[x0 + x, y0 + y] else 0
                for y in range(BANK_LINE_CELL_HEIGHT)
                for x in range(BANK_LINE_CELL_WIDTH)
            )
            if any(bits):
                tiles.append((x0, y0, bits))
    return tuple(tiles)


def _patterns_and_plans():
    patterns: dict[bytes, tuple[int, str]] = {}
    tiles_by_angle = {angle: _rung_tiles(angle) for angle in BANK_LINE_ANGLES}
    for angle in BANK_LINE_ANGLES:
        for _x, _y, bits in tiles_by_angle[angle]:
            if bits in patterns:
                continue
            index = len(patterns)
            font_index = index // BANK_LINE_VISIBLE_GLYPHS_PER_FONT
            if font_index >= len(BANK_LINE_FONT_IDS):
                raise RuntimeError("continuous pitch-rung patterns exceed slots 7/8")
            code_index = index % BANK_LINE_VISIBLE_GLYPHS_PER_FONT
            patterns[bits] = (
                BANK_LINE_FONT_IDS[font_index],
                chr(BANK_LINE_FIRST_CODEPOINT + code_index),
            )

    plans: dict[str, list[list[object]]] = {}
    origin_x = BANK_LINE_CANVAS_WIDTH // 2
    origin_y = BANK_LINE_CANVAS_HEIGHT // 2
    for angle in BANK_LINE_ANGLES:
        raw = [
            (x, y, *patterns[bits])
            for x, y, bits in tiles_by_angle[angle]
        ]
        runs: list[list[object]] = []
        for x, y, font_id, character in raw:
            if (
                runs
                and runs[-1][0] == font_id
                and runs[-1][2] == y - origin_y
                and runs[-1][1] + len(str(runs[-1][3])) * BANK_LINE_CELL_WIDTH
                == x - origin_x
            ):
                runs[-1][3] = str(runs[-1][3]) + character
            else:
                runs.append([font_id, x - origin_x, y - origin_y, character])
        plans[str(angle)] = runs
    return patterns, plans


def _font_memories(patterns: dict[bytes, tuple[int, str]]) -> dict[int, bytes]:
    grouped: dict[int, list[tuple[str, bytes]]] = {
        font_id: [] for font_id in BANK_LINE_FONT_IDS
    }
    for bits, (font_id, character) in patterns.items():
        grouped[font_id].append((character, bits))
    memories = {}
    for font_id, items in grouped.items():
        records = [
            struct.pack("<I", ord(" ")) + bytes(BANK_LINE_GLYPH_SIZE - 4)
        ]
        for expected, (character, bits) in enumerate(
            items, start=BANK_LINE_FIRST_CODEPOINT
        ):
            if ord(character) != expected:
                raise RuntimeError(f"slot {font_id} glyphs are not sequential")
            encoded = _encode_mask(bits)
            records.append(struct.pack("<I", ord(character)) + encoded)
        memories[font_id] = b"".join(records)
    return memories


def _record(identifier: int, function_id: int, transaction: int,
            flag: int, data: bytes) -> bytes:
    return (
        struct.pack("<III", identifier, function_id, transaction)
        + bytes((flag & 0xFF,))
        + struct.pack("<I", len(data))
        + data
    )


def append_bank_line_fonts(source: bytes, memories: dict[int, bytes]) -> bytes:
    existing = base._command_records(source)
    if not existing:
        raise RuntimeError("the live PFD resource contains no native commands")
    identifier = existing[0][0]
    transaction = (max(item[2] for item in existing) + 1) & 0xFFFFFFFF
    stream = bytearray()
    for font_id in BANK_LINE_FONT_IDS:
        memory = memories[font_id]
        glyph_count = len(memory) // BANK_LINE_GLYPH_SIZE
        header = struct.pack(
            "<IHHIIII",
            font_id,
            BANK_LINE_CELL_WIDTH,
            BANK_LINE_CELL_HEIGHT,
            BANK_LINE_GLYPH_SIZE,
            glyph_count,
            0,
            25 + len(memory),
        ) + b"\x00"
        stream.extend(_record(identifier, 0x106, transaction, 0, header))
        transaction = (transaction + 1) & 0xFFFFFFFF
        for offset in range(0, len(memory), 512):
            chunk = memory[offset:offset + 512]
            data = struct.pack("<III", font_id, offset, len(chunk)) + chunk
            stream.extend(_record(identifier, 0x107, transaction, 0, data))
            stream.extend(_record(identifier, 0x105, transaction, 1, b""))
            transaction = (transaction + 1) & 0xFFFFFFFF

    packed = bytearray(source)
    sequence = base._next_report_sequence(source)
    for offset in range(0, len(stream), base.REPORT_PAYLOAD_BYTES):
        payload = stream[offset:offset + base.REPORT_PAYLOAD_BYTES]
        report = bytearray(base.REPORT_SIZE)
        report[0] = 0xF0
        report[1] = 0
        report[2] = sequence
        report[3] = len(payload)
        report[4:4 + len(payload)] = payload
        packed.append(base.REPORT_SIZE)
        packed.extend(report)
        sequence = (sequence + 1) & 0xFF
    return bytes(packed)


def write_plan(
    plans: dict[str, list[list[object]]],
    memories: dict[int, bytes],
    patterns: dict[bytes, tuple[int, str]],
    source: bytes,
) -> None:
    number_width, number_height, number_rectangles = (
        _font_foreground_rectangles(source, 3)
    )
    line_rectangles = {
        f"{font_id}:{ord(character)}": _mask_rectangles(
            bits, BANK_LINE_CELL_WIDTH, BANK_LINE_CELL_HEIGHT
        )
        for bits, (font_id, character) in patterns.items()
    }
    document = {
        "version": 3,
        "cell_width": BANK_LINE_CELL_WIDTH,
        "cell_height": BANK_LINE_CELL_HEIGHT,
        "glyph_size": BANK_LINE_GLYPH_SIZE,
        "outer": int(BANK_LINE_OUTER),
        "inner_gap": int(BANK_LINE_INNER_GAP),
        "thickness": BANK_LINE_THICKNESS,
        "canvas_width": BANK_LINE_CANVAS_WIDTH,
        "canvas_height": BANK_LINE_CANVAS_HEIGHT,
        "font_glyph_counts": {
            str(font_id): len(memory) // BANK_LINE_GLYPH_SIZE
            for font_id, memory in memories.items()
        },
        "line_glyph_rectangles": line_rectangles,
        "number_font_width": number_width,
        "number_font_height": number_height,
        "number_glyph_rectangles": number_rectangles,
        "angles": plans,
    }
    PLAN_OUTPUT.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_preview(
    plans: dict[str, list[list[object]]],
    patterns: dict[bytes, tuple[int, str]],
) -> None:
    lookup = {
        (font_id, character): bits
        for bits, (font_id, character) in patterns.items()
    }
    samples = (-45, -30, -14, 0, 14, 30, 45)
    panel_w, panel_h = 150, 130
    preview = Image.new(
        "RGB", (panel_w * len(samples), panel_h * 2), (6, 7, 13)
    )
    for row, background in enumerate(((34, 110, 216), (139, 75, 24))):
        for column, angle in enumerate(samples):
            origin_x = column * panel_w + panel_w // 2
            origin_y = row * panel_h + panel_h // 2
            for font_id, dx, dy, text in plans[str(angle)]:
                for index, character in enumerate(str(text)):
                    bits = lookup[(int(font_id), character)]
                    cell = Image.new(
                        "RGB",
                        (BANK_LINE_CELL_WIDTH, BANK_LINE_CELL_HEIGHT),
                        background,
                    )
                    mask = Image.new("L", cell.size, 0)
                    pixels = mask.load()
                    for y in range(BANK_LINE_CELL_HEIGHT):
                        for x in range(BANK_LINE_CELL_WIDTH):
                            if bits[y * BANK_LINE_CELL_WIDTH + x]:
                                pixels[x, y] = 255
                    cell.paste(
                        Image.new("RGB", cell.size, (255, 255, 255)),
                        (0, 0),
                        mask,
                    )
                    preview.paste(
                        cell,
                        (
                            origin_x + int(dx) + index * BANK_LINE_CELL_WIDTH,
                            origin_y + int(dy),
                        ),
                    )
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    preview.save(PREVIEW)


def main() -> int:
    if not SOURCE.is_file():
        raise SystemExit(f"Missing established live PFD resource: {SOURCE}")
    patterns, plans = _patterns_and_plans()
    memories = _font_memories(patterns)
    source = SOURCE.read_bytes()
    output = append_bank_line_fonts(source, memories)
    if output[:len(source)] != source:
        raise SystemExit("continuous-rung fonts changed the established prefix")
    for font_id, memory in memories.items():
        if base._font_memory(output, font_id) != memory:
            raise SystemExit(f"slot {font_id} did not round-trip")
    OUTPUT.write_bytes(output)
    write_plan(plans, memories, patterns, source)
    write_preview(plans, patterns)
    print(
        f"Created {OUTPUT.name}: preserved {len(source)} source bytes and "
        f"appended slots {BANK_LINE_FONT_IDS}."
    )
    print(
        f"Unique continuous-rung tiles: {len(patterns)}; glyph counts: "
        + ", ".join(
            f"slot {font_id}={len(memory) // BANK_LINE_GLYPH_SIZE}"
            for font_id, memory in memories.items()
        )
    )
    print(f"Runtime plan written: {PLAN_OUTPUT}")
    print(f"Preview written: {PREVIEW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
