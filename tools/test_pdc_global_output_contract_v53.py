#!/usr/bin/env python3
"""Offline contract for fixed-PDC Rule 0.1 output authority.

No hardware, simulator, HID handle, serial port, or network connection is opened.
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GLOBAL = ROOT / "tools" / "test_global_output_authority.py"
PDC = ROOT / "muslimsim" / "devices" / "pdc_bb61_bb52.py"
CATALOG = ROOT / "muslimsim" / "hardware" / "catalog.py"
MARK = "MUSLIMSIM_PDC_FIXED_BLACKOUT_CONTRACT_V53"


def fail(message: str) -> None:
    raise AssertionError(message)


def main() -> int:
    for path in (GLOBAL, PDC, CATALOG):
        if not path.is_file():
            fail(f"required file missing: {path}")
        ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))

    global_text = GLOBAL.read_text(encoding="utf-8-sig")
    pdc_text = PDC.read_text(encoding="utf-8-sig")
    catalog_text = CATALOG.read_text(encoding="utf-8-sig")

    # The modern Rule 0.1 suite has a catalogue-vs-blackout coverage registry.
    # Once that registry exists, V5.3 must explicitly declare both new outputs.
    modern_coverage = (
        "no declared blackout" in global_text
        or "implemented outputs" in global_text
        or "declared blackout" in global_text
    )
    if modern_coverage:
        if MARK not in global_text:
            fail("modern global-output coverage exists but V5.3 PDC registry marker is absent")
        for key in ("pdc_bb61_left", "pdc_bb52_right"):
            if key not in global_text:
                fail(f"global output authority does not declare {key}")

    # Runtime owner must actually darken before releasing the HID handle.
    if "self._write_backlight(device, 0)" not in pdc_text:
        fail("fixed-PDC reader does not send capture-proven brightness 0 at final teardown")
    if pdc_text.find("self._write_backlight(device, 0)") > pdc_text.find("device.close()"):
        # There can be other device.close() calls earlier in the class; verify the
        # final reader-loop fragment more precisely below if this coarse order is
        # inconclusive rather than accepting a post-close blackout.
        reader_pos = pdc_text.find("def _reader_loop")
        off_pos = pdc_text.find("self._write_backlight(device, 0)", reader_pos)
        close_pos = pdc_text.find("device.close()", off_pos)
        if not (reader_pos >= 0 and off_pos > reader_pos and close_pos > off_pos):
            fail("fixed-PDC final blackout is not before HID close")

    # Model identity is now a PID-dependent property. The actual exact OFF
    # and full-brightness bytes below are the contract, not source spelling.
    if "PDC_INPUT_REPORT_LEN = 17" not in pdc_text or "PDC_INPUT_REPORT_ID = 0x01" not in pdc_text:
        fail("fixed-PDC physical-input framing is not pinned to report-ID 01 / 17 bytes")

    # Catalogue must expose the output that triggered the Rule 0.1 coverage check.
    if catalog_text.count('"panel_backlight"') < 2:
        fail("catalogue does not expose both fixed-PDC panel_backlight outputs")

    spec = importlib.util.spec_from_file_location("_v53_pdc", PDC)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    left = module.MuslimSimPDCBB61Left()
    right = module.MuslimSimPDCBB52Right()
    if left._backlight_packet(0).hex() != "0260bb0000034900000000000000":
        fail("BB61 capture-proven OFF packet changed")
    if right._backlight_packet(0).hex() != "0250bb0000034900000000000000":
        fail("BB52 capture-proven OFF packet changed")
    if left._backlight_packet(255).hex() != "0260bb0000034900ff0000000000":
        fail("BB61 capture-proven full-brightness packet changed")
    if right._backlight_packet(255).hex() != "0250bb0000034900ff0000000000":
        fail("BB52 capture-proven full-brightness packet changed")

    left._active_pid = module.BB51_PID
    if left._backlight_packet(0).hex() != "0250bb0000034900000000000000":
        fail("BB51 3M OFF packet changed")
    if left._backlight_packet(255).hex() != "0250bb0000034900ff0000000000":
        fail("BB51 3M full-brightness packet changed")

    if module._is_input_report(bytes.fromhex("0260bb0000034900000000000000")):
        fail("BB61 14-byte output acknowledgement can leak into physical input")
    if not module._is_input_report(bytes([1]) + bytes(16)):
        fail("normal 17-byte report-ID 01 physical input is rejected")

    print("V5.3 Rule 0.1 fixed-PDC contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
