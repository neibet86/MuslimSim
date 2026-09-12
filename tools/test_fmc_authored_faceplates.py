#!/usr/bin/env python3
"""Offline checks for the authored BB35 PFP3N and BB36 MCDU32 faceplates.

No HID device and no simulator is opened.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muslimsim.devices import mcdu_bb36_faceplate, pfp_bb35_faceplate
from muslimsim.devices.mcdu_bb36 import MCDU_KEY_MAP
from muslimsim.devices.pfp_bb35_separate_paths import PFP3_KEYS


class FakeCanvas:
    def __init__(self) -> None:
        self._next = 1
        self.items = {}

    def _add(self, kind: str, coords, **kwargs):
        item = self._next
        self._next += 1
        self.items[item] = {
            "kind": kind,
            "coords": tuple(float(v) for v in coords),
            "tags": set(),
            **kwargs,
        }
        return item

    def create_round_rect(self, *coords, **kwargs):
        return self._add("round_rect", coords, **kwargs)

    def create_rectangle(self, *coords, **kwargs):
        return self._add("rectangle", coords, **kwargs)

    def create_oval(self, *coords, **kwargs):
        return self._add("oval", coords, **kwargs)

    def create_line(self, *coords, **kwargs):
        return self._add("line", coords, **kwargs)

    def create_text(self, x, y, **kwargs):
        return self._add("text", (x, y), **kwargs)

    def addtag_withtag(self, tag, item):
        self.items[item]["tags"].add(str(tag))

    def gettags(self, item):
        return tuple(self.items[item]["tags"])

    def find_all(self):
        return tuple(sorted(self.items))

    def type(self, item):
        return self.items[item]["kind"]

    def itemcget(self, item, option):
        return self.items[item].get(option, "")


class Harness:
    def __init__(self, device: str, lines) -> None:
        self.device = device
        self._selected_visual = None
        self._flash_until = {}
        self._detected = {
            device: {
                "source": "os",
                "title": device,
            }
        }
        self._device_states = {device: {"state": "live"}}
        self._mirror = {
            "state": "live",
            "lines": tuple(lines),
        }

    def _tag(self, canvas, item, key):
        canvas.addtag_withtag(f"control:{key}", item)

    def _control_color(self, key):
        return "#5aa9ff"

    def _control_fill(self, key, default="#202e49"):
        return default

    def _device_mirror(self, key):
        return dict(self._mirror) if key == self.device else {}


def controls(canvas: FakeCanvas):
    result = set()
    for item in canvas.find_all():
        for tag in canvas.gettags(item):
            if tag.startswith("control:"):
                result.add(tag.split(":", 1)[1])
    return result


def texts(canvas: FakeCanvas):
    return [
        str(canvas.itemcget(item, "text"))
        for item in canvas.find_all()
        if canvas.type(item) == "text"
    ]


def assert_inside(canvas: FakeCanvas, width: float, height: float) -> None:
    for item in canvas.find_all():
        data = canvas.items[item]
        coords = data["coords"]
        if data["kind"] == "text":
            x, y = coords
            assert -1 <= x <= width + 1, (item, data)
            assert -1 <= y <= height + 1, (item, data)
        elif coords:
            xs = coords[0::2]
            ys = coords[1::2]
            assert min(xs) >= -1 and max(xs) <= width + 1, (item, data)
            assert min(ys) >= -1 and max(ys) <= height + 1, (item, data)


def main() -> int:
    checks = 0
    sample = (
        "                    1/2",
        "   TEST FMC PAGE",
        "",
        " LEFT DATA      RIGHT DATA",
        "",
        "SCRATCHPAD",
    )

    # BB36 MCDU32.
    mcdu_canvas = FakeCanvas()
    mcdu_bb36_faceplate.draw_mcdu32_faceplate(
        Harness("mcdu32_bb36", sample),
        mcdu_canvas,
        980,
        680,
    )
    mcdu_controls = controls(mcdu_canvas)
    expected_mcdu = {f"key_{index}" for index in MCDU_KEY_MAP}
    assert mcdu_controls == expected_mcdu, (
        sorted(expected_mcdu - mcdu_controls),
        sorted(mcdu_controls - expected_mcdu),
    )
    checks += 1
    assert len(mcdu_controls) == 74
    checks += 1
    assert mcdu_bb36_faceplate.MCDU_PHYSICAL_LABELS[72] == "OVEY\n△"
    checks += 1
    assert mcdu_bb36_faceplate.MCDU_PHYSICAL_LABELS[24] == "MCDU\nMENU"
    checks += 1
    assert mcdu_bb36_faceplate.MCDU_PHYSICAL_LABELS[18] == "BRT"
    assert mcdu_bb36_faceplate.MCDU_PHYSICAL_LABELS[25] == "DIM"
    checks += 1
    assert mcdu_bb36_faceplate.MCDU_COMPASS_OUTLINE_KEYS == {
        48, 57, 62, 66
    }
    checks += 1
    mcdu_text = "\n".join(texts(mcdu_canvas))
    for token in (
        "DIR",
        "PROG",
        "PERF",
        "F-PLN",
        "RAD\nNAV",
        "ATC\nCOMM",
        "MCDU\nMENU",
        "AIR\nPORT",
        "OVEY\n△",
        "CLR",
        "TEST FMC PAGE",
    ):
        assert token in mcdu_text, token
        checks += 1
    assert_inside(mcdu_canvas, 980, 680)
    checks += 1

    # BB35 PFP3N.
    pfp_canvas = FakeCanvas()
    pfp_bb35_faceplate.draw_pfp3n_faceplate(
        Harness("pfp3n_bb35", sample),
        pfp_canvas,
        980,
        680,
    )
    pfp_controls = controls(pfp_canvas)
    expected_pfp = {f"key_{index}" for index in PFP3_KEYS}
    assert pfp_controls == expected_pfp, (
        sorted(expected_pfp - pfp_controls),
        sorted(pfp_controls - expected_pfp),
    )
    checks += 1
    assert len(pfp_controls) == 71
    checks += 1
    assert pfp_bb35_faceplate.PFP_COMPASS_OUTLINE_KEYS == {
        45, 54, 59, 63
    }
    checks += 1
    pfp_text = "\n".join(texts(pfp_canvas))
    for token in (
        "INIT\nREF",
        "RTE",
        "CLB",
        "CRZ",
        "DES",
        "BRT",
        "EXEC",
        "MENU",
        "LEGS",
        "DEP\nARR",
        "HOLD",
        "PROG",
        "N1\nLIMIT",
        "FIX",
        "PREV\nPAGE",
        "NEXT\nPAGE",
        "DEL",
        "CLR",
        "TEST FMC PAGE",
    ):
        assert token in pfp_text, token
        checks += 1
    assert_inside(pfp_canvas, 980, 680)
    checks += 1

    # Geometry reservations derived from the photos stay inside their native
    # references. This catches accidental faceplate drift.
    mw, mh = mcdu_bb36_faceplate.MCDU_REFERENCE_SIZE
    assert mcdu_bb36_faceplate.MCDU_SCREEN_RECT.inside(mw, mh)
    assert all(rect.inside(mw, mh) for rect in mcdu_bb36_faceplate.MCDU_LSK_REGIONS)
    checks += 1

    pw, ph = pfp_bb35_faceplate.PFP_REFERENCE_SIZE
    assert pfp_bb35_faceplate.PFP_SCREEN_RECT.inside(pw, ph)
    assert all(rect.inside(pw, ph) for rect in pfp_bb35_faceplate.PFP_LSK_REGIONS)
    checks += 1

    # Studio integration must use authored modules but keep the generic
    # _draw_fmc_keypad fallback intact.
    studio_source = (ROOT / "muslimsim" / "gui" / "studio.py").read_text(
        encoding="utf-8"
    )
    assert "draw_pfp3n_faceplate" in studio_source
    assert "draw_mcdu32_faceplate" in studio_source
    assert studio_source.count("self._draw_fmc_keypad(canvas, width, height)") >= 2
    checks += 1

    # No hardware owner or simulator mapping changed for this presentation task.
    assert len(MCDU_KEY_MAP) == 74
    assert len(PFP3_KEYS) == 71
    checks += 1

    print(f"FMC authored faceplates: {checks} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
