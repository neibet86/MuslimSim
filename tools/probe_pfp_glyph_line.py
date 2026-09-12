"""Draw one long angled line through a temporary native bitmap-font slot.

This is an isolated display-only experiment for BB35/BB36.  It clones the
proven 17x29 slot-5 upload into temporary slot 7 in memory, replaces a small
set of printable glyphs with tiles cut from one clean diagonal, uploads only
that temporary slot, and stamps the tiles with ordinary 0x114 text commands.

Production font slots 3, 4, 5 and 6 are never modified.  The script never
contacts X-Plane or another WinCtrl device and refuses to run while MuslimSim
Studio/launch.py owns display output.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import struct
import sys
import time

from PIL import Image, ImageDraw


PROJECT = Path(__file__).resolve().parents[1]
TOOLS = PROJECT / "tools"
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_pfp_dual_font as font_base
import build_pfp_shape_tiles as shape_tiles
import probe_pfp_native_line as line_probe


BACKGROUND = (6, 7, 13)
TEST_FONT_ID = 7
SOURCE_FONT_ID = 5
SOURCE_FONT = (
    PROJECT / "bridge" / "winctrl-pfp-b737-cockpit-font3-4-5-6.xpwwf"
)

TEST_WIDTH = 7 * font_base.CELL_WIDTH
TEST_HEIGHT = 4 * font_base.CELL_HEIGHT
TEST_ORIGIN = (260, 175)
FREE_CODES = [chr(code) for code in range(0x21, 0x7F)]


def _diagonal_mask() -> set[tuple[int, int]]:
    """Return one connected, three-pixel, exact 45-degree test stroke."""
    image = Image.new("1", (TEST_WIDTH, TEST_HEIGHT), 0)
    draw = ImageDraw.Draw(image)
    draw.line((8, TEST_HEIGHT - 10, 108, TEST_HEIGHT - 110), fill=1, width=3)
    pixels = image.load()
    return {
        (x, y)
        for y in range(TEST_HEIGHT)
        for x in range(TEST_WIDTH)
        if pixels[x, y]
    }


def _tile_plan() -> tuple[dict[int, bytes], tuple[tuple[int, int, str], ...]]:
    """Assign printable test glyphs to the non-empty 17x29 line tiles."""
    pixels = _diagonal_mask()
    keys: dict[bytes, str] = {}
    runs: list[tuple[int, int, str]] = []

    for row_y in range(0, TEST_HEIGHT, font_base.CELL_HEIGHT):
        row_tiles: list[tuple[int, bytes]] = []
        for column_x in range(0, TEST_WIDTH, font_base.CELL_WIDTH):
            bits = bytes(
                1 if (column_x + x, row_y + y) in pixels else 0
                for y in range(font_base.CELL_HEIGHT)
                for x in range(font_base.CELL_WIDTH)
            )
            if any(bits):
                row_tiles.append((column_x, bits))
        if not row_tiles:
            continue

        # A straight line crosses only adjacent cells in each tile row.  Keep
        # separate runs anyway so the test stays correct if an edge lands on a
        # third cell due to raster rounding.
        run_x: int | None = None
        previous_x: int | None = None
        text = ""
        for column_x, bits in row_tiles:
            if previous_x is not None and column_x != previous_x + font_base.CELL_WIDTH:
                runs.append((run_x or 0, row_y, text))
                run_x, text = None, ""
            if bits not in keys:
                if len(keys) >= len(FREE_CODES):
                    raise RuntimeError("temporary font ran out of printable tile codes")
                keys[bits] = FREE_CODES[len(keys)]
            if run_x is None:
                run_x = column_x
            text += keys[bits]
            previous_x = column_x
        if text:
            runs.append((run_x or 0, row_y, text))

    wanted = {ord(character): bits for bits, character in keys.items()}
    return wanted, tuple(runs)


def _temporary_font_memory(source: bytes) -> tuple[bytes, tuple[tuple[int, int, str], ...]]:
    """Clone slot 5 in memory and patch only glyphs used by the test line."""
    wanted, runs = _tile_plan()
    memory = bytearray(font_base._font_memory(source, SOURCE_FONT_ID))
    patched = 0
    for glyph_start in range(0, len(memory), font_base.GLYPH_SIZE):
        if glyph_start + font_base.GLYPH_SIZE > len(memory):
            continue
        codepoint = int.from_bytes(memory[glyph_start:glyph_start + 4], "little")
        bits = wanted.get(codepoint)
        if bits is None:
            continue
        encoded = shape_tiles.encode_tile(bits, font_base)
        memory[glyph_start + 4:glyph_start + font_base.GLYPH_SIZE] = encoded
        patched += 1
    if patched != len(wanted):
        raise RuntimeError(
            f"expected {len(wanted)} temporary line glyphs; patched {patched}"
        )
    return bytes(memory), runs


def _slot7_records(source: bytes, memory: bytes):
    """Clone the measured slot-5 header/chunks/commit records into slot 7."""
    records = font_base._command_records(source)
    selected = []
    active = False
    chunk_count = 0
    for _identifier, function_id, _transaction, flag, data in records:
        if function_id == 0x106 and len(data) >= 8:
            found_id = int.from_bytes(data[:4], "little")
            if active or found_id != SOURCE_FONT_ID:
                if active:
                    break
                continue
            active = True
            replacement = bytearray(data)
            replacement[:4] = TEST_FONT_ID.to_bytes(4, "little")
            selected.append((function_id, flag, bytes(replacement)))
            continue
        if not active:
            continue
        if function_id == 0x107 and len(data) >= 12:
            found_id, chunk_offset, chunk_size = struct.unpack_from("<III", data, 0)
            if found_id != SOURCE_FONT_ID:
                break
            replacement = bytearray(struct.pack(
                "<III", TEST_FONT_ID, chunk_offset, chunk_size
            ))
            replacement.extend(memory[chunk_offset:chunk_offset + chunk_size])
            if len(replacement) != 12 + chunk_size:
                raise RuntimeError("temporary font chunk exceeds cloned memory")
            selected.append((function_id, flag, bytes(replacement)))
            chunk_count += 1
            continue
        if function_id == 0x105:
            selected.append((function_id, flag, data))
            if chunk_count == 21:
                break
            continue
        break
    if chunk_count != 21 or len(selected) != 43:
        raise RuntimeError(
            f"expected header + 21 chunks/commits; got {len(selected)} records, "
            f"{chunk_count} chunks"
        )
    return tuple(selected)


def _send_records(device, identifier: int, records) -> tuple[int, int]:
    """Send the cloned upload with measured response points and safe pacing."""
    sequence = 1
    transaction = int(time.monotonic() * 1000) & 0xFFFFFFFF
    acknowledgements = 0
    for function_id, flag, data in records:
        body = bytearray()
        body.extend(struct.pack("<I", int(identifier) | (0xBB << 8)))
        body.extend(struct.pack("<I", int(function_id)))
        body.extend(struct.pack("<I", transaction))
        body.append(int(flag) & 0xFF)
        body.extend(struct.pack("<I", len(data)))
        body.extend(data)
        transaction = (transaction + 1) & 0xFFFFFFFF

        for offset in range(0, len(body), 56):
            payload = body[offset:offset + 56]
            report = bytearray(64)
            report[0] = 0xF0
            report[1] = 0
            report[2] = sequence & 0xFF
            report[3] = len(payload)
            report[4:4 + len(payload)] = payload
            written = device.write(list(report))
            if isinstance(written, int) and written < 0:
                raise OSError(f"temporary font report failed ({written})")
            sequence = (sequence + 1) & 0xFF
            if sequence % 8 == 0:
                time.sleep(0.001)
        if flag:
            acknowledgements += len(line_probe._collect_acks(device, 0.05))
    return sequence, acknowledgements


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", choices=("bb35", "bb36"), default="bb35")
    parser.add_argument("--confirm-studio-stopped", action="store_true")
    args = parser.parse_args()

    if not args.confirm_studio_stopped:
        parser.error("--confirm-studio-stopped is required")
    active = line_probe._active_studio_processes()
    if active:
        print("REFUSED: MuslimSim Studio/launch.py still owns display output:")
        for row in active:
            print(f"  {row}")
        return 3
    if not SOURCE_FONT.is_file():
        print(f"Temporary font source is missing: {SOURCE_FONT}")
        return 2

    bridge = line_probe._load_bridge()
    if bridge.hid is None:
        print("hidapi unavailable")
        return 2

    if args.panel == "bb35":
        pid = bridge.PFP_PFD_PID
        identifier = bridge.PFP_PFD_IDENTIFIER
        label = "BB35 PFP"
        config_packets = (
            bridge._pfp_black_background_packet(),
            bridge._pfp_text_grid_packet(),
        )
    else:
        pid = bridge.MCDU_PFD_PID
        identifier = bridge.MCDU_PFD_IDENTIFIER
        label = "BB36 MCDU"
        config_packets = ()

    devices = list(bridge.hid.enumerate(bridge.PFP_PFD_VID, pid))
    if not devices:
        print(f"{label} not found")
        return 2
    info = devices[0]
    if not bridge._force_refresh_one_winctrl_display(
        info, identifier, label, config_packets
    ):
        print(f"{label}: display reinitialization failed")
        return 2
    time.sleep(0.20)

    devices = list(bridge.hid.enumerate(bridge.PFP_PFD_VID, pid))
    path = devices[0].get("path") if devices else None
    if not path:
        print(f"{label} did not return after reinitialization")
        return 2

    source = SOURCE_FONT.read_bytes()
    memory, runs = _temporary_font_memory(source)
    records = _slot7_records(source, memory)

    device = bridge.hid.device()
    device.open_path(path)
    try:
        device.set_nonblocking(1)
        line_probe._collect_acks(device, 0.15)
        bridge._winctrl_display_set_brightness(device, identifier, 0, 128)
        bridge._winctrl_display_set_brightness(device, identifier, 1, 220)

        sequence, upload_acks = _send_records(
            device, identifier, records
        )

        # Flash-backed font uploads acknowledge their report stream before the
        # new slot is always selectable.  Give the controller a quiet commit
        # window, then drain late acknowledgements before starting a fresh
        # drawing transaction on the continued F0 sequence.
        time.sleep(0.75)
        upload_acks += len(line_probe._collect_acks(device, 0.40))

        canvas = bridge._PfpNativeCanvas(device, identifier=identifier)
        canvas.sequence = sequence
        canvas.colour(*BACKGROUND)
        canvas.fill(0, 0, 640, 480)
        canvas.colour(0, 180, 255)
        for x, y in ((70, 55), (550, 55), (70, 405), (550, 405)):
            canvas.fill(x, y, 20, 20)

        origin_x, origin_y = TEST_ORIGIN
        for x, y, text in runs:
            canvas.text(
                origin_x + x,
                origin_y + y,
                text,
                (255, 255, 255),
                BACKGROUND,
                TEST_FONT_ID,
            )
        canvas.command(0x103)
        draw_acks = line_probe._collect_acks(device, 0.8)

        print(f"{label}: temporary slot-{TEST_FONT_ID} diagonal glyph test")
        print(f"Temporary glyphs: {len(_tile_plan()[0])}; text runs: {len(runs)}")
        print(f"Upload acknowledgements: {upload_acks}")
        print(f"Draw acknowledgements: {len(draw_acks)}")
        print("Four cyan blocks + one long white diagonal -> glyph-line method works.")
        print("Four cyan blocks only -> slot 7 was ignored or upload did not commit.")
    finally:
        try:
            device.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
