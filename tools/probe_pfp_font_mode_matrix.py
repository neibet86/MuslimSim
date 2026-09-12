"""Probe unused native-font header fields for foreground-only rendering.

The 25-byte WinCtrl font header contains a reserved 32-bit field and a final
byte that every captured production font leaves at zero.  This isolated test
uploads the same clean 96x96 diagonal six times with controlled combinations
of those fields, draws each over a four-colour witness card, and refreshes only
after all six cards are complete.

Studio must be stopped.  Slot 8 is temporary; production files are untouched.
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

import probe_pfp_native_line as line_probe
import probe_pfp_text_alpha_matrix as alpha_probe


MODES = (
    (0, 0),
    (1, 0),
    (2, 0),
    (0, 1),
    (0, 2),
    (1, 1),
)


def _font_records(reserved: int, trailer: int):
    memory = alpha_probe._glyph_memory()
    header = struct.pack(
        "<IHHIIII",
        alpha_probe.FONT_ID,
        alpha_probe.WIDTH,
        alpha_probe.HEIGHT,
        alpha_probe.GLYPH_SIZE,
        2,
        int(reserved) & 0xFFFFFFFF,
        25 + len(memory),
    ) + bytes((int(trailer) & 0xFF,))
    records = [(0x106, 0, header)]
    for offset in range(0, len(memory), 512):
        chunk = memory[offset:offset + 512]
        records.append((
            0x107,
            0,
            struct.pack("<III", alpha_probe.FONT_ID, offset, len(chunk))
            + chunk,
        ))
        records.append((0x105, 1, b""))
    return tuple(records)


def _send_records(device, identifier: int, sequence: int, records):
    transaction = int(time.monotonic() * 1000) & 0xFFFFFFFF
    acknowledgements = 0
    for function_id, response, data in records:
        body = bytearray()
        body.extend(struct.pack("<I", int(identifier) | (0xBB << 8)))
        body.extend(struct.pack("<I", int(function_id)))
        body.extend(struct.pack("<I", transaction))
        body.append(int(response) & 0xFF)
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
                raise OSError(f"temporary font-mode report failed ({written})")
            sequence = (sequence + 1) & 0xFF
            if sequence % 8 == 0:
                time.sleep(0.001)
        if response:
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

    device = bridge.hid.device()
    device.open_path(path)
    try:
        device.set_nonblocking(1)
        line_probe._collect_acks(device, 0.15)
        bridge._winctrl_display_set_brightness(device, identifier, 0, 128)
        bridge._winctrl_display_set_brightness(device, identifier, 1, 220)

        sequence = 1
        canvas = bridge._PfpNativeCanvas(device, identifier=identifier)
        canvas.sequence = sequence
        alpha_probe._set_foreground(canvas, (6, 7, 13))
        canvas.fill(0, 0, 640, 480)
        for index, (x, y) in enumerate(alpha_probe.CARDS, start=1):
            alpha_probe._paint_witness(canvas, x, y, index)
        canvas.flush()
        sequence = canvas.sequence

        upload_acks = 0
        for (x, y), (reserved, trailer) in zip(alpha_probe.CARDS, MODES):
            sequence, acks = _send_records(
                device,
                identifier,
                sequence,
                _font_records(reserved, trailer),
            )
            upload_acks += acks
            canvas = bridge._PfpNativeCanvas(device, identifier=identifier)
            canvas.sequence = sequence
            canvas.set_font(alpha_probe.FONT_ID)
            canvas.command(0x112, bytes((0xFF, 0xFF, 0xFF, 0xFF)))
            canvas.command(0x113, bytes((0x00, 0x06, 0x07, 0x0D)))
            canvas.command(
                0x114,
                struct.pack("<HH", x, y) + b"!\x00",
            )
            canvas.flush()
            sequence = canvas.sequence

        canvas = bridge._PfpNativeCanvas(device, identifier=identifier)
        canvas.sequence = sequence
        canvas.command(0x103)
        draw_acks = line_probe._collect_acks(device, 0.9)

        print(f"{label}: six-card font-header mode matrix")
        print(f"Modes: {MODES}")
        print(f"Upload acknowledgements: {upload_acks}")
        print(f"Refresh acknowledgements: {len(draw_acks)}")
        print("Success: one card retains four quadrants behind its white line.")
        print("No line: that font-header combination was rejected by firmware.")
    finally:
        try:
            device.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
