#!/usr/bin/env python3
"""Read-only WinCtrl PAP3 input probe.

This tool never writes to the panel and never touches X-Plane.  Close the
MuslimSim bridge before running it so only one process owns the PAP3 HID path.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import hid
except ImportError:
    hid = None

from muslimsim.devices.pap3_mcp import (
    PAP3_BUTTONS,
    PAP3_SPEED_BUTTONS,
    PAP3_VID,
    PAP3_PID,
    PAP3_FD_CAPT_INDEX,
    PAP3_FD_FO_INDEX,
    PAP3_AP_DISC_DOWN_INDEX,
    PAP3_AP_DISC_UP_INDEX,
    PAP3_BANK_ANGLE_TARGETS,
    PAP3_AT_ARMED_INDEX,
    PAP3_AT_DISARMED_INDEX,
    pap3_decode_button_bits,
)


SPECIAL_LABELS = {
    PAP3_FD_CAPT_INDEX: "FD CAPT",
    PAP3_FD_FO_INDEX: "FD FO",
    PAP3_AP_DISC_DOWN_INDEX: "AP DISC DOWN",
    PAP3_AP_DISC_UP_INDEX: "AP DISC UP",
    PAP3_AT_ARMED_INDEX: "A/T ARMED",
    PAP3_AT_DISARMED_INDEX: "A/T DISARMED",
}
for index, target in PAP3_BANK_ANGLE_TARGETS.items():
    SPECIAL_LABELS[index] = f"BANK ANGLE {(10, 15, 20, 25, 30)[target]}"


def label_for(index: int) -> str:
    if index in PAP3_BUTTONS:
        return PAP3_BUTTONS[index][0]
    if index in PAP3_SPEED_BUTTONS:
        return PAP3_SPEED_BUTTONS[index][0]
    return SPECIAL_LABELS.get(index, "UNASSIGNED")


def open_device():
    devices = hid.enumerate(PAP3_VID, PAP3_PID)
    if not devices:
        raise FileNotFoundError(
            f"WINCTRL PAP3 {PAP3_VID:04X}:{PAP3_PID:04X} not found"
        )

    print(f"Found {len(devices)} PAP3 HID interface(s):")
    for number, info in enumerate(devices):
        print(
            f"  [{number}] product={info.get('product_string')!r} "
            f"interface={info.get('interface_number')!r} "
            f"usage_page={info.get('usage_page')!r} "
            f"usage={info.get('usage')!r}"
        )

    info = devices[0]
    path = info.get("path")
    if not path:
        raise RuntimeError("PAP3 HID path unavailable")

    device = hid.device()
    device.open_path(path)
    try:
        device.set_nonblocking(1)
    except Exception:
        pass
    return device


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only WinCtrl PAP3 input decoder"
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=0.0,
        help="Stop after this many seconds; 0 means run until Ctrl+C",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print every changed raw report in hexadecimal",
    )
    args = parser.parse_args()

    if hid is None:
        print("ERROR: hidapi is not installed.")
        print("Run: py -m pip install hidapi")
        return 2

    device = None
    previous = None
    started = time.monotonic()

    print()
    print("=" * 76)
    print("MUSLIMSIM WINCTRL PAP3 READ-ONLY PROBE")
    print("=" * 76)
    print("No output reports and no X-Plane commands will be sent.")
    print("Move one PAP3 control at a time. Ctrl+C stops.")
    print()

    try:
        device = open_device()

        while True:
            if args.seconds > 0 and time.monotonic() - started >= args.seconds:
                break

            report = device.read(64)
            if not report:
                time.sleep(0.001)
                continue

            raw = bytes(report)
            bits = pap3_decode_button_bits(raw)
            if bits is None:
                if args.raw:
                    print(
                        f"IGNORED len={len(raw)} "
                        f"id=0x{raw[0] if raw else 0:02X} {raw.hex()}"
                    )
                continue

            if previous is None:
                previous = bits
                print(
                    f"BASELINE len={len(raw)} buttons=0x{bits:012X}"
                )
                if args.raw:
                    print(f"  {raw.hex()}")
                continue

            changed = bits ^ previous
            if not changed:
                continue

            if args.raw:
                print(f"RAW {raw.hex()}")

            for index in range(48):
                mask = 1 << index
                if not (changed & mask):
                    continue
                pressed = bool(bits & mask)
                print(
                    f"index={index:02d} "
                    f"{label_for(index):<20} "
                    f"{'PRESS' if pressed else 'RELEASE'}"
                )

            previous = bits

    except KeyboardInterrupt:
        print("\nProbe stopped.")
    except Exception as exc:
        print(f"\nPAP3 probe error: {exc}")
        return 1
    finally:
        if device is not None:
            try:
                device.close()
            except Exception:
                pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
