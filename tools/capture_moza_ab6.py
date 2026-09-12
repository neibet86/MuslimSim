"""Guided capture for the MOZA AB6 FFB Base (VID 346E / PID 1002).

The AB6 entered the catalogue from an owner-supplied A320/MSFS2024 `.preset`
file.  A preset carries calibration numbers, not a USB identity and not a
report layout, so the AB6 has been sitting at ``status: unimplemented`` with
no VID/PID and three guessed axis names.  This tool replaces all of that with
evidence read from the device itself.

**Read-only, and deliberately so.**  The AB6 is a force-feedback base.  This
tool opens its HID handle, reads the report descriptor, and reads input
reports.  It never calls ``write``, ``send_feature_report``, or any Moza SDK
entry point.  No torque, effect, or motor motion is possible from it.

Three phases, each usable on its own:

``--report`` (default)
    Identity, report descriptor, and its SHA-256 next to the A210's.  Proves
    what the input protocol *is* rather than assuming the sibling's.

``--watch``
    Live decode, so the owner can see axes, hat and contacts move.  Also
    reports which of the eight declared axes actually carry motion.

``--capture``
    One physical control at a time: the owner names it, moves it, and the
    observed axis/contact is recorded.  This is the only part that cannot be
    derived from the descriptor, because a generic HID button number does not
    say which legend is printed above it.  Writes a JSON capture record; it
    installs nothing on its own.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.devices.moza_a210 import (  # noqa: E402
    MOZA_A210_AXIS_KEYS,
    MOZA_A210_BUTTON_COUNT,
    MOZA_A210_PID,
    MOZA_A210_REPORT_LENGTH,
    MOZA_A210_VID,
    decode_moza_a210_report,
)

try:
    import hid
except ImportError:  # pragma: no cover
    hid = None


MOZA_AB6_VID = 0x346E
MOZA_AB6_PID = 0x1002
DEVICE_KEY = "moza_ab6"

# An axis has to move by more than this fraction of full scale to count as
# real.  Well above the resting jitter of a loaded force-feedback base.
AXIS_MOTION_THRESHOLD = 1500
CAPTURE_TIMEOUT_SECONDS = 30.0
SETTLE_SECONDS = 0.40


def _fail(message: str) -> int:
    print(f"ERROR: {message}")
    return 2


def _find(vid: int, pid: int) -> Optional[Dict[str, Any]]:
    if hid is None:
        return None
    try:
        entries = hid.enumerate(vid, pid)
    except Exception:
        return None
    return entries[0] if entries else None


def _open(info: Dict[str, Any]):
    device = hid.device()
    device.open_path(info["path"])
    try:
        device.set_nonblocking(1)
    except Exception:
        pass
    return device


def _descriptor(info: Dict[str, Any]) -> Optional[bytes]:
    device = _open(info)
    try:
        return bytes(device.get_report_descriptor())
    except Exception:
        return None
    finally:
        device.close()


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return str(value or "")


def phase_report() -> int:
    """Identity and protocol, proven from the device rather than the sibling."""

    if hid is None:
        return _fail("hidapi is unavailable; install the hid package")

    ab6 = _find(MOZA_AB6_VID, MOZA_AB6_PID)
    if ab6 is None:
        return _fail(
            "MOZA AB6 FFB Base (346E:1002) is not connected. "
            "Power it on and plug it in, then run this again."
        )

    print("MOZA AB6 identity, read from the connected device")
    print("-" * 62)
    print(f"  vendor id      : {ab6['vendor_id']:#06x}")
    print(f"  product id     : {ab6['product_id']:#06x}")
    print(f"  manufacturer   : {_text(ab6.get('manufacturer_string'))!r}")
    print(f"  product string : {_text(ab6.get('product_string'))!r}")
    print(f"  serial number  : {_text(ab6.get('serial_number'))!r}  (diagnostic only)")
    print(f"  interface      : {ab6.get('interface_number')}")
    print(
        f"  usage          : page {ab6.get('usage_page'):#06x} "
        f"usage {ab6.get('usage'):#04x}  (Generic Desktop / Joystick)"
    )

    ab6_desc = _descriptor(ab6)
    if ab6_desc is None:
        return _fail("the AB6 refused to return its HID report descriptor")

    print()
    print("Report descriptor")
    print("-" * 62)
    print(f"  length         : {len(ab6_desc)} bytes")
    print(f"  sha256         : {hashlib.sha256(ab6_desc).hexdigest()}")

    a210 = _find(MOZA_A210_VID, MOZA_A210_PID)
    if a210 is None:
        print("  A210 comparison: skipped, the A210/AY210 is not connected")
    else:
        a210_desc = _descriptor(a210)
        if a210_desc is None:
            print("  A210 comparison: skipped, the A210 refused its descriptor")
        elif a210_desc == ab6_desc:
            print(
                "  A210 comparison: IDENTICAL, byte for byte.\n"
                "                   The AB6 presents the same HID input\n"
                "                   collection as the already capture-proven\n"
                "                   A210, so its decoder applies unchanged."
            )
        else:
            print(
                f"  A210 comparison: DIFFERENT "
                f"(A210 {len(a210_desc)} bytes, "
                f"sha256 {hashlib.sha256(a210_desc).hexdigest()[:16]}).\n"
                "                   The AB6 needs its own decode; do not\n"
                "                   reuse the A210 reader."
            )

    print()
    print("Live input report")
    print("-" * 62)
    device = _open(ab6)
    frames = 0
    lengths: Dict[int, int] = {}
    first: Optional[bytes] = None
    try:
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            raw = device.read(64)
            if raw:
                frames += 1
                lengths[len(raw)] = lengths.get(len(raw), 0) + 1
                if first is None:
                    first = bytes(raw)
    finally:
        device.close()

    if not frames:
        return _fail(
            "the AB6 produced no input reports in two seconds. "
            "Close Studio and Moza Cockpit, then run this again."
        )

    print(f"  frames in 2 s  : {frames}")
    print(f"  frame lengths  : {lengths}")
    print(f"  first frame    : {first.hex() if first else '-'}")

    decoded = decode_moza_a210_report(first)
    if decoded is None:
        print(
            "  decode         : REFUSED. The frame does not match the proven "
            "34-byte report-01 layout."
        )
        return 1

    print(
        f"  decode         : accepted, report id 01, "
        f"{MOZA_A210_REPORT_LENGTH} bytes"
    )
    print()
    print("  resting values")
    for key in MOZA_A210_AXIS_KEYS:
        print(f"    {key:12s} {decoded['axes'][key]:5d}")
    print(f"    {'hat':12s} {decoded['hat']}")
    held = [i + 1 for i, state in enumerate(decoded["buttons"]) if state]
    print(f"    contacts held at rest: {held if held else 'none'}")
    if held:
        print(
            "    NOTE: a contact held at rest is normal for a detented switch\n"
            "          or a selector, but run --capture to establish which\n"
            "          physical control each number is."
        )
    return 0


def _read_decoded(device) -> Optional[Dict[str, Any]]:
    raw = device.read(64)
    if not raw:
        return None
    return decode_moza_a210_report(raw)


def _sample(device, seconds: float) -> List[Dict[str, Any]]:
    samples = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        decoded = _read_decoded(device)
        if decoded is not None:
            samples.append(decoded)
    return samples


def phase_watch(seconds: float) -> int:
    """Live decode, and report which declared axes actually carry motion."""

    if hid is None:
        return _fail("hidapi is unavailable; install the hid package")
    ab6 = _find(MOZA_AB6_VID, MOZA_AB6_PID)
    if ab6 is None:
        return _fail("MOZA AB6 FFB Base (346E:1002) is not connected")

    print(
        f"Watching the AB6 for {seconds:.0f} s. Move every axis through its "
        "full travel\nand press every button, then wait for the summary."
    )
    print("-" * 62)

    device = _open(ab6)
    seen_low: Dict[str, int] = {}
    seen_high: Dict[str, int] = {}
    contacts: set = set()
    hats: set = set()
    frames = 0
    next_line = time.monotonic()
    try:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            decoded = _read_decoded(device)
            if decoded is None:
                continue
            frames += 1
            for key, value in decoded["axes"].items():
                seen_low[key] = min(seen_low.get(key, value), value)
                seen_high[key] = max(seen_high.get(key, value), value)
            for index, state in enumerate(decoded["buttons"]):
                if state:
                    contacts.add(index + 1)
            hats.add(decoded["hat"])

            now = time.monotonic()
            if now >= next_line:
                next_line = now + 0.25
                axes = "  ".join(
                    f"{key.removeprefix('axis_')}={decoded['axes'][key]:5d}"
                    for key in MOZA_A210_AXIS_KEYS[:4]
                )
                print(
                    f"\r  {axes}  hat={decoded['hat']}  "
                    f"contacts={sorted(contacts)[:8]}      ",
                    end="",
                    flush=True,
                )
    finally:
        device.close()

    print()
    print("-" * 62)
    print(f"  frames observed: {frames}")
    print()
    print("  axis travel (declared 0..65535)")
    moving = []
    for key in MOZA_A210_AXIS_KEYS:
        low = seen_low.get(key, 0)
        high = seen_high.get(key, 0)
        span = high - low
        real = span >= AXIS_MOTION_THRESHOLD
        if real:
            moving.append(key)
        print(
            f"    {key:12s} {low:5d} .. {high:5d}  span {span:5d}  "
            f"{'MOVES' if real else 'flat'}"
        )
    print()
    print(f"  axes that actually moved : {moving or 'none'}")
    print(f"  hat positions seen       : {sorted(hats)}")
    print(f"  contacts seen closed     : {sorted(contacts) or 'none'}")
    print()
    print(
        "  An axis reported 'flat' was declared by the descriptor but did not\n"
        "  move here. Re-run and exercise it before concluding it is unused."
    )
    return 0


def _quiet_baseline(device) -> Optional[Dict[str, Any]]:
    samples = _sample(device, SETTLE_SECONDS)
    return samples[-1] if samples else None


def phase_capture(output: Optional[Path]) -> int:
    """Ask the owner to name and exercise one control at a time."""

    if hid is None:
        return _fail("hidapi is unavailable; install the hid package")
    ab6 = _find(MOZA_AB6_VID, MOZA_AB6_PID)
    if ab6 is None:
        return _fail("MOZA AB6 FFB Base (346E:1002) is not connected")

    print("MOZA AB6 guided control capture")
    print("-" * 62)
    print(
        "Close Studio and Moza Cockpit first, so nothing else is reading the\n"
        "base. Nothing is written to the AB6 at any point.\n\n"
        "For each control: type the name printed on it, press ENTER, then\n"
        "move or press only that one control. Leave the name blank to stop."
    )
    print()

    records: List[Dict[str, Any]] = []
    device = _open(ab6)
    try:
        while True:
            label = input("Control name (blank to finish): ").strip()
            if not label:
                break

            print("  Release everything...", end="", flush=True)
            baseline = _quiet_baseline(device)
            if baseline is None:
                print(" no frames; is the base still connected?")
                continue
            print(" now move/press it.")

            found: Optional[Tuple[str, Any]] = None
            deadline = time.monotonic() + CAPTURE_TIMEOUT_SECONDS
            while time.monotonic() < deadline and found is None:
                decoded = _read_decoded(device)
                if decoded is None:
                    continue
                for index, state in enumerate(decoded["buttons"]):
                    if state != baseline["buttons"][index]:
                        found = ("contact", index + 1)
                        break
                if found is None and decoded["hat"] != baseline["hat"]:
                    found = ("hat", decoded["hat"])
                if found is None:
                    for key in MOZA_A210_AXIS_KEYS:
                        delta = abs(
                            decoded["axes"][key] - baseline["axes"][key]
                        )
                        if delta >= AXIS_MOTION_THRESHOLD:
                            found = ("axis", key)
                            break

            if found is None:
                print(f"  '{label}': nothing changed within "
                      f"{CAPTURE_TIMEOUT_SECONDS:.0f} s; skipped.\n")
                continue

            kind, value = found
            print(f"  '{label}' -> {kind} {value}\n")
            records.append({
                "label": label,
                "kind": kind,
                "value": value,
            })
            # Let the control settle before the next baseline.
            _sample(device, SETTLE_SECONDS)
    except (KeyboardInterrupt, EOFError):
        print("\n  interrupted")
    finally:
        device.close()

    if not records:
        print("Nothing captured; no file written.")
        return 1

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    target = output or (
        PROJECT / "logs" / f"moza_ab6_capture_{stamp}.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "device": DEVICE_KEY,
        "vendor_id": MOZA_AB6_VID,
        "product_id": MOZA_AB6_PID,
        "product_string": _text(ab6.get("product_string")),
        "captured": stamp,
        "report_length": MOZA_A210_REPORT_LENGTH,
        "controls": records,
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print()
    print(f"Captured {len(records)} control(s) -> {target}")
    print(
        "Nothing was installed. Review the file, then it can be turned into\n"
        "catalogue entries with real legends instead of generic numbers."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only identity, protocol and control capture for the MOZA AB6.",
    )
    parser.add_argument(
        "--watch", action="store_true",
        help="live decode; shows which declared axes actually move",
    )
    parser.add_argument(
        "--capture", action="store_true",
        help="guided one-control-at-a-time capture to a JSON record",
    )
    parser.add_argument(
        "--seconds", type=float, default=30.0,
        help="how long --watch runs (default 30)",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="where --capture writes its JSON record",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.capture:
        return phase_capture(args.output)
    if args.watch:
        return phase_watch(args.seconds)
    return phase_report()


if __name__ == "__main__":
    raise SystemExit(main())
