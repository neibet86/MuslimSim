"""Test one clean 128x128 diagonal stored as a single temporary glyph.

The proven native font header exposes width, height, glyph byte size, glyph
count and total upload bytes.  This display-only probe uses those fields to
create temporary slot 8 with one printable glyph, uploads five bounded chunks,
and stamps the complete line with one ordinary 0x114 text command.

Production slots 3-7 are untouched.  Studio must be stopped.
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

import probe_pfp_glyph_line as glyph_probe
import probe_pfp_native_line as line_probe


BACKGROUND = (6, 7, 13)
FONT_ID = 8
CODEPOINT = ord("!")
WIDTH = 128
HEIGHT = 128
BYTES_PER_ROW = (WIDTH + 7) // 8
GLYPH_SIZE = 4 + BYTES_PER_ROW * HEIGHT


def _glyph_memory() -> bytes:
    image = Image.new("1", (WIDTH, HEIGHT), 0)
    ImageDraw.Draw(image).line((10, 118, 118, 10), fill=1, width=3)
    pixels = image.load()
    glyph = bytearray(struct.pack("<I", CODEPOINT))
    for y in range(HEIGHT):
        for byte_index in range(BYTES_PER_ROW):
            value = 0
            for bit in range(8):
                x = byte_index * 8 + bit
                if x < WIDTH and pixels[x, y]:
                    value |= 1 << (7 - bit)
            glyph.append(value)
    if len(glyph) != GLYPH_SIZE:
        raise RuntimeError("large glyph encoding has an invalid size")

    # The firmware addresses the table from printable ASCII space rather than
    # performing an arbitrary one-record codepoint search.  Supply the blank
    # space record at index zero and the visible exclamation record at index
    # one; this remains only two large cells instead of an A-sized 34-cell
    # table.
    blank = struct.pack("<I", ord(" ")) + bytes(GLYPH_SIZE - 4)
    return blank + bytes(glyph)


def _font_records():
    memory = _glyph_memory()
    total_bytes = 25 + len(memory)
    header = struct.pack(
        "<IHHIIII",
        FONT_ID,
        WIDTH,
        HEIGHT,
        GLYPH_SIZE,
        2,
        0,
        total_bytes,
    ) + b"\x00"
    if len(header) != 25:
        raise RuntimeError("large font header has an invalid size")

    records = [(0x106, 0, header)]
    for offset in range(0, len(memory), 512):
        chunk = memory[offset:offset + 512]
        records.append((
            0x107,
            0,
            struct.pack("<III", FONT_ID, offset, len(chunk)) + chunk,
        ))
        records.append((0x105, 1, b""))
    return tuple(records)


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
    if not bridge._force_refresh_one_winctrl_display(
        devices[0], identifier, label, config_packets
    ):
        print(f"{label}: display reinitialization failed")
        return 2
    time.sleep(0.20)

    devices = list(bridge.hid.enumerate(bridge.PFP_PFD_VID, pid))
    path = devices[0].get("path") if devices else None
    if not path:
        print(f"{label} did not return after reinitialization")
        return 2

    records = _font_records()
    device = bridge.hid.device()
    device.open_path(path)
    try:
        device.set_nonblocking(1)
        line_probe._collect_acks(device, 0.15)
        bridge._winctrl_display_set_brightness(device, identifier, 0, 128)
        bridge._winctrl_display_set_brightness(device, identifier, 1, 220)

        sequence, upload_acks = glyph_probe._send_records(
            device, identifier, records
        )
        time.sleep(0.75)
        upload_acks += len(line_probe._collect_acks(device, 0.40))

        canvas = bridge._PfpNativeCanvas(device, identifier=identifier)
        canvas.sequence = sequence
        # A blue/brown split makes an opaque 128x128 glyph background obvious.
        # The line crosses both colours, so a successful alpha-zero background
        # leaves those fields untouched while retaining the white foreground.
        canvas.colour(34, 110, 216)
        canvas.fill(0, 0, 640, 240)
        canvas.colour(139, 75, 24)
        canvas.fill(0, 240, 640, 240)
        canvas.colour(0, 180, 255)
        for x, y in ((70, 55), (550, 55), (70, 405), (550, 405)):
            canvas.fill(x, y, 20, 20)
        canvas.set_font(FONT_ID)
        canvas.command(0x112, bytes((0xFF, 255, 255, 255)))
        canvas.command(0x113, bytes((0x00, *BACKGROUND)))
        canvas.command(
            0x114,
            struct.pack("<HH", 256, 176) + b"!\x00",
        )
        canvas.command(0x103)
        draw_acks = line_probe._collect_acks(device, 0.8)

        print(f"{label}: temporary slot-{FONT_ID} single large-glyph test")
        print(
            f"Glyph: {WIDTH}x{HEIGHT}, {GLYPH_SIZE} bytes; "
            f"upload records: {len(records)}"
        )
        print(f"Upload acknowledgements: {upload_acks}")
        print(f"Draw acknowledgements: {len(draw_acks)}")
        print("White diagonal with uninterrupted blue/brown -> transparency works.")
        print("Dark 128x128 square behind line -> alpha-zero background is ignored.")
    finally:
        try:
            device.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
