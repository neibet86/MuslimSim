"""Render the FCU/EFIS faceplate and check typography separation offline."""

from __future__ import annotations

from pathlib import Path
import sys
import tkinter as tk
import tkinter.font as tkfont
import types


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.gui import studio as studio_module  # noqa: E402


Studio = studio_module.MuslimSimStudio
WIDTH = studio_module.FACEPLATE_DESIGN_WIDTH
HEIGHT = studio_module.FACEPLATE_DESIGN_HEIGHT


class FaceplateHarness:
    def __init__(self) -> None:
        self._selected_device = "fcu_32_efis"
        self._selected_visual = None
        self._flash_until = {}
        self._detected = {"fcu_32_efis": {"connected": True}}
        self._device_states = {"fcu_32_efis": {"mirror": {"values": {}}}}
        self._preview_snapshot = {}
        self.practice_mode = tk.BooleanVar(value=False)
        self._fcu_values = {"speed": 250, "heading": 90, "altitude": 10000, "vs": 0}
        self._fcu_efis_visual = {
            side: {
                "unit": "inhg", "std": False, "mode": "nav", "range": 40,
                "nav1": "off", "nav2": "off",
                "buttons": {
                    "fd": False, "ls": False, "cstr": False, "wpt": False,
                    "vord": False, "ndb": False, "arpt": False,
                },
            }
            for side in ("left", "right")
        }
        self._learned_source = lambda key: key
        self._number = Studio._number
        self._fcu_controls = Studio._fcu_controls
        for name in (
            "_draw_fcu", "_device_mirror", "_efis_state", "_draw_efis_toggle",
            "_draw_efis_selector", "_draw_efis_unit_arc", "_draw_mini_button",
            "_draw_knob", "_control_color", "_control_fill", "_highlight_ring",
            "_tag",
        ):
            setattr(self, name, types.MethodType(getattr(Studio, name), self))


def bbox(canvas: tk.Canvas, tag: str) -> tuple[int, int, int, int]:
    value = canvas.bbox(tag)
    assert value is not None, f"missing layout tag {tag}"
    return value


def assert_above(canvas: tk.Canvas, upper: str, lower: str) -> None:
    upper_box = bbox(canvas, upper)
    lower_box = bbox(canvas, lower)
    assert upper_box[3] < lower_box[1], (upper, upper_box, lower, lower_box)


def minimum_font_size(canvas: tk.Canvas, tag: str) -> int:
    sizes = []
    for item in canvas.find_withtag(tag):
        if canvas.type(item) != "text":
            continue
        sizes.append(abs(int(tkfont.Font(font=canvas.itemcget(item, "font")).cget("size"))))
    assert sizes, f"no text found for {tag}"
    return min(sizes)


def main() -> int:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"FCU faceplate layout check skipped: no display ({exc}).")
        return 0
    root.withdraw()
    try:
        canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, highlightthickness=0)
        canvas.pack()
        harness = FaceplateHarness()
        harness._draw_fcu(canvas, WIDTH, HEIGHT)
        root.update_idletasks()

        # The centre keeps its original four-display design, but the knob
        # captions, pull row, and two action rows now occupy separate bands.
        assert_above(canvas, "fcu-knob-labels", "fcu-pull-row")
        assert_above(canvas, "fcu-pull-row", "fcu-button-row-1")
        assert_above(canvas, "fcu-button-row-1", "fcu-button-row-2")
        assert minimum_font_size(canvas, "fcu-pull-row") >= 8
        assert minimum_font_size(canvas, "fcu-button-row-1") >= 8

        # Both EFIS wings must keep headings, selector lines, and their labels
        # in distinct vertical bands. These were the collisions visible in
        # the owner's screenshot around MAP MODE, RANGE, and NAV 1/2.
        for side in ("left", "right"):
            assert_above(canvas, f"fcu-{side}-std:labels", f"fcu-{side}-baro-arc")
            assert_above(canvas, "fcu-baro-unit-labels", f"fcu-{side}-map-heading")
            assert_above(canvas, f"fcu-{side}-map-heading", f"fcu-{side}-map:line")
            assert_above(canvas, f"fcu-{side}-map:labels", f"fcu-{side}-range-heading")
            assert_above(canvas, f"fcu-{side}-range-heading", f"fcu-{side}-range:line")
            assert_above(canvas, f"fcu-{side}-range:labels", f"fcu-{side}-nav1:line")
            assert_above(canvas, f"fcu-{side}-nav1:labels", f"fcu-{side}-nav2:line")
            assert bbox(canvas, f"fcu-{side}-nav2:labels")[3] < 570
            for group in ("std", "map", "range", "nav1", "nav2"):
                assert minimum_font_size(canvas, f"fcu-{side}-{group}:labels") >= 8

        # Typography changes must not cost a control its existing click tag.
        for key in harness._fcu_controls():
            assert canvas.find_withtag(f"control:{key}"), key

        print("FCU/EFIS faceplate layout check passed: larger text, separated labels/lines, and all controls clickable.")
        return 0
    finally:
        root.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
