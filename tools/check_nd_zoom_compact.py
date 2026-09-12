"""Offline compact ND, MAP/PLAN zoom and native-report regression."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from bridge.final import _PfpNativeCanvas, _cockpit_nd_range_nm
from muslimsim.devices.nd_renderer import assert_layout_contract, draw_live_nd
from render_coded_display_pages import _nd_values


class _MockPfp:
    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def write(self, report) -> int:
        data = bytes(report)
        self.writes.append(data)
        return len(data)


def _draw_until_visible(canvas, device: _MockPfp, values: dict) -> list[int]:
    bursts = []
    for _attempt in range(4):
        before = len(device.writes)
        changed = draw_live_nd(canvas, values)
        if changed:
            canvas.command(0x103)
        bursts.append(len(device.writes) - before)
        if changed:
            return bursts
    raise AssertionError("ND staged frame did not complete within four passes")


def _reports(identifier: int, mode: int, span: float) -> tuple[int, int, int]:
    device = _MockPfp()
    canvas = _PfpNativeCanvas(device, identifier=identifier)
    values = {
        **_nd_values(),
        "map_mode": float(mode),
        "map_range_nm": float(span),
    }
    bursts = _draw_until_visible(canvas, device, values)
    first = sum(bursts)
    largest = max(bursts)
    before = len(device.writes)
    changed = draw_live_nd(canvas, values)
    if changed:
        canvas.command(0x103)
    return first, largest, len(device.writes) - before


def _transition_reports(
    identifier: int, mode: int, first_span: float, second_span: float
) -> tuple[int, int]:
    device = _MockPfp()
    canvas = _PfpNativeCanvas(device, identifier=identifier)
    values = {**_nd_values(), "map_mode": float(mode), "map_range_nm": first_span}
    _draw_until_visible(canvas, device, values)
    before = len(device.writes)
    values["map_range_nm"] = second_span
    bursts = _draw_until_visible(canvas, device, values)
    return len(device.writes) - before, max(bursts)


def _mode_transition_reports(identifier: int) -> tuple[int, int]:
    device = _MockPfp()
    canvas = _PfpNativeCanvas(device, identifier=identifier)
    values = {**_nd_values(), "map_mode": 2.0, "map_range_nm": 20.0}
    _draw_until_visible(canvas, device, values)
    before = len(device.writes)
    values["map_mode"] = 3.0
    bursts = _draw_until_visible(canvas, device, values)
    return len(device.writes) - before, max(bursts)


def _recovery_reports(identifier: int) -> tuple[int, int]:
    device = _MockPfp()
    canvas = _PfpNativeCanvas(device, identifier=identifier)
    values = {**_nd_values(), "map_mode": 3.0, "map_range_nm": 40.0}
    _draw_until_visible(canvas, device, values)
    operations, _timestamp, sequence, mode = canvas._muslimsim_nd_state
    canvas._muslimsim_nd_state = (operations, 0.0, sequence, mode)
    before = len(device.writes)
    bursts = _draw_until_visible(canvas, device, values)
    return len(device.writes) - before, max(bursts)


def main() -> int:
    assert_layout_contract()
    if _cockpit_nd_range_nm({"map_range_index": 3.0, "map_range_nm": 20.0}) != 40.0:
        raise AssertionError("Zibo captain range detent did not override stale generic range")
    if _cockpit_nd_range_nm({"map_range_index": float("nan"), "map_range_nm": 80.0}) != 80.0:
        raise AssertionError("Generic X-Plane ND range fallback is broken")
    for identifier, label in ((0x31, "BB35"), (0x32, "BB36")):
        for mode, span in ((2, 20.0), (3, 10.0), (3, 40.0)):
            first, largest, steady = _reports(identifier, mode, span)
            page = "MAP" if mode == 2 else "PLAN"
            if steady != 0:
                raise AssertionError(
                    f"{label} {page} {span:g} NM repeated {steady} reports at steady state"
                )
            if largest > 290:
                raise AssertionError(
                    f"{label} {page} {span:g} NM burst {largest} exceeds 290 reports"
                )
            print(
                f"{label} {page} {span:g} NM: {first} total, "
                f"{largest} largest burst, {steady} steady reports"
            )
        map_zoom = _transition_reports(identifier, 2, 20.0, 40.0)
        plan_zoom = _transition_reports(identifier, 3, 10.0, 40.0)
        mode_change = _mode_transition_reports(identifier)
        recovery = _recovery_reports(identifier)
        if max(map_zoom[1], plan_zoom[1], mode_change[1], recovery[1]) > 290:
            raise AssertionError(f"{label} ND transition exceeded 290 reports")
        print(
            f"{label} zoom: MAP 20>40 "
            f"{map_zoom[0]} total/{map_zoom[1]} max, "
            f"PLAN 10>40 {plan_zoom[0]} total/{plan_zoom[1]} max, "
            f"MAP>PLAN {mode_change[0]} total/{mode_change[1]} max, "
            f"recovery {recovery[0]} total/{recovery[1]} max"
        )
    print("PASS: compact ND layout, waypoint labels and MAP/PLAN zoom are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
