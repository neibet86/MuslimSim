"""Prove background-matched clean glyph lines on PFD sky and ground.

This isolated display test reuses the physically proven 100-pixel continuous
diagonal, cut into adjacent native 17x29 glyph cells.  It places one copy over
blue sky and one over brown ground while matching every opaque cell to its
local field colour.  Correct output has two clean white diagonals, no black
boxes and no visible joins.

Studio must be stopped.  Temporary slot 7 only; production files are untouched.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time


PROJECT = Path(__file__).resolve().parents[1]
TOOLS = PROJECT / "tools"
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import probe_pfp_glyph_line as glyph_probe
import probe_pfp_native_line as line_probe


SKY = (34, 110, 216)
EARTH = (139, 75, 24)
SKY_ORIGIN = (105, 78)
EARTH_ORIGIN = (416, 286)


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
    if not glyph_probe.SOURCE_FONT.is_file():
        print(f"Temporary font source is missing: {glyph_probe.SOURCE_FONT}")
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

    source = glyph_probe.SOURCE_FONT.read_bytes()
    memory, runs = glyph_probe._temporary_font_memory(source)
    records = glyph_probe._slot7_records(source, memory)

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
        canvas.colour(*SKY)
        canvas.fill(0, 0, 640, 240)
        canvas.colour(*EARTH)
        canvas.fill(0, 240, 640, 240)

        for origin, background in (
            (SKY_ORIGIN, SKY),
            (EARTH_ORIGIN, EARTH),
        ):
            origin_x, origin_y = origin
            for x, y, text in runs:
                canvas.text(
                    origin_x + x,
                    origin_y + y,
                    text,
                    (255, 255, 255),
                    background,
                    glyph_probe.TEST_FONT_ID,
                )

        # Small cyan corner witnesses ensure the complete frame reached glass.
        canvas.colour(0, 205, 255)
        for x, y in ((24, 24), (596, 24), (24, 436), (596, 436)):
            canvas.fill(x, y, 20, 20)
        canvas.command(0x103)
        draw_acks = line_probe._collect_acks(device, 0.8)

        print(f"{label}: background-matched continuous-glyph line test")
        print(f"Temporary glyphs: {len(glyph_probe._tile_plan()[0])}")
        print(f"Text runs per line: {len(runs)}")
        print(f"Upload acknowledgements: {upload_acks}")
        print(f"Draw acknowledgements: {len(draw_acks)}")
        print("Expected: one clean sky line and one clean ground line, no boxes.")
    finally:
        try:
            device.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
