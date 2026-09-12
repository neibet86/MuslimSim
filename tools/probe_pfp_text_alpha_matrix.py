"""Probe native text-cell alpha/order modes on BB35 or BB36.

This is an isolated display-only experiment.  It uploads one temporary
96x96 diagonal glyph to font slot 8, resets the selected display, paints six
four-colour witness cards, and draws the same glyph with six background-byte
combinations.  A genuinely transparent text background leaves every witness
quadrant visible around the white line.

Production font slots 3-7 and production source files are untouched.  Studio
must be stopped so two processes never write to the panel together.
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


FONT_ID = 8
CODEPOINT = ord("!")
WIDTH = 96
HEIGHT = 96
BYTES_PER_ROW = (WIDTH + 7) // 8
GLYPH_SIZE = 4 + BYTES_PER_ROW * HEIGHT

# Positions leave room above each card for a count marker (one through six).
CARDS = (
    (44, 86),
    (272, 86),
    (500, 86),
    (44, 316),
    (272, 316),
    (500, 316),
)

# Raw payloads for command 0x113.  The first five exercise the documented
# A,R,G,B order; the last checks the alternate B,G,R,A interpretation exposed
# by a second conversion helper in SimAppPro's bundled JavaScript.
BACKGROUND_CASES = (
    bytes((0x00, 0x06, 0x07, 0x0D)),  # 1: A=0, dark RGB (previous test)
    bytes((0x00, 0xFF, 0xFF, 0xFF)),  # 2: A=0, white RGB
    bytes((0x00, 0xFF, 0x00, 0x00)),  # 3: A=0, red RGB
    bytes((0x01, 0xFF, 0xFF, 0xFF)),  # 4: almost transparent white
    bytes((0x7F, 0xFF, 0xFF, 0xFF)),  # 5: half-alpha white
    bytes((0xFF, 0xFF, 0xFF, 0x00)),  # 6: alternate-order alpha=0
)

QUADRANTS = (
    (34, 110, 216),
    (139, 75, 24),
    (14, 126, 94),
    (110, 52, 150),
)


def _glyph_memory() -> bytes:
    image = Image.new("1", (WIDTH, HEIGHT), 0)
    ImageDraw.Draw(image).line((7, 89, 89, 7), fill=1, width=3)
    pixels = image.load()
    visible = bytearray(struct.pack("<I", CODEPOINT))
    for y in range(HEIGHT):
        for byte_index in range(BYTES_PER_ROW):
            value = 0
            for bit in range(8):
                x = byte_index * 8 + bit
                if x < WIDTH and pixels[x, y]:
                    value |= 1 << (7 - bit)
            visible.append(value)
    if len(visible) != GLYPH_SIZE:
        raise RuntimeError("alpha-probe glyph encoding has an invalid size")
    blank = struct.pack("<I", ord(" ")) + bytes(GLYPH_SIZE - 4)
    return blank + bytes(visible)


def _font_records():
    memory = _glyph_memory()
    header = struct.pack(
        "<IHHIIII",
        FONT_ID,
        WIDTH,
        HEIGHT,
        GLYPH_SIZE,
        2,
        0,
        25 + len(memory),
    ) + b"\x00"
    if len(header) != 25:
        raise RuntimeError("alpha-probe font header has an invalid size")
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


def _set_foreground(canvas, colour: tuple[int, int, int]) -> None:
    """Set only 0x112 so witness fills do not disturb 0x113 state."""
    canvas.command(0x112, bytes((0xFF, *colour)))


def _paint_witness(canvas, x: int, y: int, index: int) -> None:
    half_w = WIDTH // 2
    half_h = HEIGHT // 2
    for colour, (qx, qy) in zip(
        QUADRANTS,
        ((x, y), (x + half_w, y), (x, y + half_h),
         (x + half_w, y + half_h)),
    ):
        _set_foreground(canvas, colour)
        canvas.fill(qx, qy, half_w, half_h)

    # External cyan frame and count markers identify cards without placing any
    # second text cell over the alpha witness.
    _set_foreground(canvas, (0, 205, 255))
    canvas.fill(x - 3, y - 3, WIDTH + 6, 2)
    canvas.fill(x - 3, y + HEIGHT + 1, WIDTH + 6, 2)
    canvas.fill(x - 3, y - 1, 2, HEIGHT + 2)
    canvas.fill(x + WIDTH + 1, y - 1, 2, HEIGHT + 2)
    marker_width = 8
    gap = 4
    total = index * marker_width + (index - 1) * gap
    marker_x = x + (WIDTH - total) // 2
    for marker in range(index):
        canvas.fill(marker_x + marker * (marker_width + gap), y - 18, 8, 8)


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
        _set_foreground(canvas, (6, 7, 13))
        canvas.fill(0, 0, 640, 480)
        for index, (x, y) in enumerate(CARDS, start=1):
            _paint_witness(canvas, x, y, index)

        canvas.set_font(FONT_ID)
        canvas.command(0x112, bytes((0xFF, 0xFF, 0xFF, 0xFF)))
        for (x, y), background in zip(CARDS, BACKGROUND_CASES):
            canvas.command(0x113, background)
            canvas.command(
                0x114,
                struct.pack("<HH", x, y) + b"!\x00",
            )
        canvas.command(0x103)
        draw_acks = line_probe._collect_acks(device, 0.8)

        print(f"{label}: six-card native text alpha matrix")
        print(
            f"Glyph: {WIDTH}x{HEIGHT}, {GLYPH_SIZE} bytes; "
            f"upload records: {len(records)}"
        )
        print(f"Upload acknowledgements: {upload_acks}")
        print(f"Draw acknowledgements: {len(draw_acks)}")
        print("A working card keeps all four coloured quadrants around its line.")
        print("Cards are identified by one through six cyan blocks above them.")
    finally:
        try:
            device.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
