"""Probe omitted and nonstandard native text-background command forms.

This second isolated BB35/BB36 experiment resets the selected display and
reuses the proven 96x96 clean diagonal glyph.  Six four-colour witness cards
exercise no 0x113 command plus empty, short and extended 0x113 payloads.  A
working foreground-only mode leaves all four witness quadrants untouched.

Studio must be stopped.  Production source/font slots remain untouched.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import struct
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
import probe_pfp_text_alpha_matrix as alpha_probe


# Cards 2-6 first receive a distinctive opaque guard background.  If the
# candidate command is ignored, that guard colour remains and makes rejection
# obvious.  None means card 1 deliberately omits command 0x113 entirely.
CASES = (
    (None, None),
    (bytes((0xFF, 0xD0, 0x20, 0xD0)), b""),
    (bytes((0xFF, 0xFF, 0x80, 0x00)), bytes((0x00,))),
    (bytes((0xFF, 0xE0, 0xD0, 0x00)), bytes((0x00, 0x00, 0x00))),
    (bytes((0xFF, 0x00, 0xC0, 0xD0)), bytes((0x00, 0xFF, 0xFF, 0xFF, 0x00))),
    (bytes((0xFF, 0x20, 0xD0, 0x50)), bytes((0x00, 0xFF, 0xFF, 0xFF, 0x01))),
)


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

    records = alpha_probe._font_records()
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
        alpha_probe._set_foreground(canvas, (6, 7, 13))
        canvas.fill(0, 0, 640, 480)
        for index, (x, y) in enumerate(alpha_probe.CARDS, start=1):
            alpha_probe._paint_witness(canvas, x, y, index)

        canvas.set_font(alpha_probe.FONT_ID)
        canvas.command(0x112, bytes((0xFF, 0xFF, 0xFF, 0xFF)))
        for (x, y), (guard, candidate) in zip(alpha_probe.CARDS, CASES):
            if guard is not None:
                canvas.command(0x113, guard)
            if candidate is not None:
                canvas.command(0x113, candidate)
            canvas.command(
                0x114,
                struct.pack("<HH", x, y) + b"!\x00",
            )
        canvas.command(0x103)
        draw_acks = line_probe._collect_acks(device, 0.8)

        print(f"{label}: six-card background-command bypass matrix")
        print(f"Upload acknowledgements: {upload_acks}")
        print(f"Draw acknowledgements: {len(draw_acks)}")
        print("Card 1 omits 0x113; cards 2-6 use empty/short/extended forms.")
        print("Success means all four coloured quadrants survive around a line.")
    finally:
        try:
            device.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
