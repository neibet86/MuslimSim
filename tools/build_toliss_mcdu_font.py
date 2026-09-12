"""Append the MCDU's native 23x29 glyphs as isolated font slot 2.

The established PFD/ND slots 3/4/5/6/7/8 remain a byte-for-byte prefix.
Only the ToLiss MCDU content painter selects slot 2; Boeing rendering is
therefore unchanged.  This offline builder never opens HID hardware.
"""

from __future__ import annotations

from pathlib import Path
import struct

import build_pfp_dual_font as base


PROJECT = Path(__file__).resolve().parents[1]
BRIDGE = PROJECT / "bridge"
MCDU_SOURCE = BRIDGE / "winctrl-pfp-b737-clean-font6.xpwwf"
DISPLAY_SOURCE = BRIDGE / "winctrl-pfp-b737-cockpit-font3-4-5-6-8.xpwwf"
OUTPUT = BRIDGE / "winctrl-pfp-b737-cockpit-font2-3-4-5-6-8.xpwwf"

SOURCE_FONT_ID = 6
TOLISS_MCDU_FONT_ID = 2


def append_mcdu_font(display_source: bytes, mcdu_source: bytes) -> bytes:
    source_records = base._command_records(mcdu_source)
    target_records = base._command_records(display_source)
    if not source_records or not target_records:
        raise RuntimeError("font resource contains no native commands")

    transaction = (max(record[2] for record in target_records) + 1) & 0xFFFFFFFF
    stream = bytearray()
    active = False
    headers = 0
    chunks = 0

    for identifier, function_id, _old_transaction, flag, data in source_records:
        if function_id == 0x106 and len(data) >= 8:
            found_id = int.from_bytes(data[:4], "little")
            if active:
                break
            if found_id != SOURCE_FONT_ID:
                continue
            active = True
            headers += 1
            replacement = bytearray(data)
            replacement[:4] = TOLISS_MCDU_FONT_ID.to_bytes(4, "little")
            data = bytes(replacement)
        elif active and function_id == 0x107 and len(data) >= 12:
            found_id = int.from_bytes(data[:4], "little")
            if found_id != SOURCE_FONT_ID:
                break
            replacement = bytearray(data)
            replacement[:4] = TOLISS_MCDU_FONT_ID.to_bytes(4, "little")
            data = bytes(replacement)
            chunks += 1
        elif active and function_id not in (0x105,):
            break

        if not active:
            continue
        stream.extend(struct.pack("<III", identifier, function_id, transaction))
        stream.append(flag)
        stream.extend(struct.pack("<I", len(data)))
        stream.extend(data)
        if function_id == 0x105:
            transaction = (transaction + 1) & 0xFFFFFFFF

    if headers != 1 or chunks < 1:
        raise RuntimeError(
            f"expected one slot-{SOURCE_FONT_ID} header and font chunks; "
            f"found headers={headers}, chunks={chunks}"
        )

    packed = bytearray(display_source)
    sequence = base._next_report_sequence(display_source)
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


def main() -> int:
    display_source = DISPLAY_SOURCE.read_bytes()
    mcdu_source = MCDU_SOURCE.read_bytes()
    output = append_mcdu_font(display_source, mcdu_source)
    if output[:len(display_source)] != display_source:
        raise RuntimeError("existing coded-display font bytes changed")
    for font_id in (3, 4, 5, 6, 7, 8):
        if base._font_memory(output, font_id) != base._font_memory(display_source, font_id):
            raise RuntimeError(f"existing font slot {font_id} changed")
    if base._font_memory(output, TOLISS_MCDU_FONT_ID) != base._font_memory(
        mcdu_source, SOURCE_FONT_ID,
    ):
        raise RuntimeError("ToLiss MCDU slot is not an exact source clone")
    OUTPUT.write_bytes(output)
    print(
        f"Created {OUTPUT.name}: preserved the full coded-display resource "
        "and appended native 23x29 ToLiss MCDU slot 2."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
