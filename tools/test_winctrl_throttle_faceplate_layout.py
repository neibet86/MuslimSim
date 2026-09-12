#!/usr/bin/env python3
"""Offline readability guard for the WinCtrl ToLiss throttle faceplate."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time
import tkinter as tk
import tkinter.font as tkfont


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from muslimsim.gui import studio  # noqa: E402


WIDTH = studio.FACEPLATE_DESIGN_WIDTH
HEIGHT = studio.FACEPLATE_DESIGN_HEIGHT


class Harness:
    _draw_winctrl_throttle = studio.MuslimSimStudio._draw_winctrl_throttle
    _draw_winctrl_linear_axis = (
        studio.MuslimSimStudio._draw_winctrl_linear_axis
    )
    _draw_winctrl_output_tile = (
        studio.MuslimSimStudio._draw_winctrl_output_tile
    )
    _draw_winctrl_engine_toggle = (
        studio.MuslimSimStudio._draw_winctrl_engine_toggle
    )
    _draw_mini_button = studio.MuslimSimStudio._draw_mini_button
    _draw_button = studio.MuslimSimStudio._draw_button
    _draw_efis_selector = studio.MuslimSimStudio._draw_efis_selector
    _toliss_throttle_probe_note = (
        studio.MuslimSimStudio._toliss_throttle_probe_note
    )

    def __init__(self) -> None:
        self._selected_visual = ""
        self._flash_until: dict[str, float] = {}
        self._throttle_trim_mode = "RUDDER"
        self._throttle_trim_values = {
            "STAB": 4.2, "RUDDER": 0.0, "AILERON": 0.0,
        }
        self._throttle_trim_label_until = time.monotonic() - 1.0
        self._throttle_trim_selector = "trim_mode_norm"
        self._device_states = {
            "winctrl_throttle": {
                "calibration_source": "saved ToLiss profile",
                "calibration_probe": {},
            },
        }
        self._axis_values = {
            "left_thrust": 45370 / 65535,
            "right_thrust": 55453 / 65535,
            "speedbrake": 0.0,
            "flap_axis": 0.5,
        }

    @staticmethod
    def _is_toliss_throttle_workspace() -> bool:
        return True

    @staticmethod
    def _toliss_throttle_calibration() -> dict:
        return {
            "aircraft_family": "toliss-a320-a321",
            "version": 2,
            "left": {
                "full_reverse": 3,
                "reverse_idle": 14115,
                "idle": 20165,
                "climb": 45370,
                "flex_mct": 55452,
                "toga": 65534,
            },
            "right": {
                "full_reverse": 4,
                "reverse_idle": 14116,
                "idle": 20166,
                "climb": 45371,
                "flex_mct": 55453,
                "toga": 65535,
            },
        }

    def _throttle_axis_fraction(self, key: str) -> float:
        return float(self._axis_values.get(key, 0.0))

    @staticmethod
    def _axis_ease(_device: str, _key: str, target: float) -> float:
        return float(target)

    @staticmethod
    def _throttle_output_value(_key: str, fallback: int = 0) -> int:
        return int(fallback)

    def _throttle_trim_display_value(
        self, mode: str | None, fallback: float,
    ) -> float:
        return float(self._throttle_trim_values.get(mode or "", fallback))

    @staticmethod
    def _control_color(_key: str) -> str:
        return studio.BLUE

    @staticmethod
    def _control_fill(_key: str, default: str = "#202e49") -> str:
        return default

    @staticmethod
    def _highlight_ring(
        _canvas: tk.Canvas, _x1: float, _y1: float,
        _x2: float, _y2: float, _key: str, *, radius: float = 7,
    ) -> None:
        del radius

    @staticmethod
    def _tag(canvas: tk.Canvas, item: int, key: str) -> None:
        canvas.addtag_withtag(f"control:{key}", item)


def _text_items(canvas: tk.Canvas) -> list[int]:
    return [item for item in canvas.find_all() if canvas.type(item) == "text"]


def _overlap(a: tuple[int, ...], b: tuple[int, ...]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--preview")
    args, _unknown = parser.parse_known_args()
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"WinCtrl throttle layout check skipped: no display ({exc}).")
        return 0
    if args.preview:
        root.title("MuslimSim WinCtrl throttle preview")
        root.geometry(f"{WIDTH}x{HEIGHT}+40+40")
    else:
        root.withdraw()
    failures: list[str] = []
    checks = 0

    def check(condition: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(message)

    try:
        canvas = tk.Canvas(
            root, width=WIDTH, height=HEIGHT, highlightthickness=0,
            bg=studio.BG,
        )
        canvas.pack()
        Harness()._draw_winctrl_throttle(canvas, WIDTH, HEIGHT)
        root.update_idletasks()

        items = _text_items(canvas)
        labels = {str(canvas.itemcget(item, "text")) for item in items}
        check(
            "READY — Set both levers to FULL REV, then select CALIBRATE DETENTS"
            in labels,
            "the calibration instruction is not visible in its status row",
        )
        check(
            "SAVED TOLISS PROFILE" in labels,
            "the active calibration source is not visible",
        )
        check(
            "FULL REV\n00003" in labels and "TOGA\n65535" in labels,
            "the readable two-line raw gate labels are incomplete",
        )
        check(
            "CAPTURED OUTPUT TESTS" not in labels
            and "NEW CAPTURED AUXILIARY BUTTONS — USER-REMAPPABLE" not in labels,
            "removed microcopy returned to the faceplate",
        )
        check(
            all("\\n" not in label for label in labels),
            "a selector is showing a literal \\n instead of a line break",
        )

        for item in items:
            description = str(canvas.itemcget(item, "text"))
            font = tkfont.Font(root=root, font=canvas.itemcget(item, "font"))
            check(
                abs(int(font.actual("size"))) >= 8,
                f"text is smaller than 8 pt: {description!r}",
            )
            bbox = canvas.bbox(item)
            check(
                bbox is not None
                and 30 <= bbox[0] <= bbox[2] <= WIDTH - 30
                and 28 <= bbox[1] <= bbox[3] <= HEIGHT - 26,
                f"text leaves the authored panel: {description!r} at {bbox}",
            )

        status_item = next(
            item for item in items
            if str(canvas.itemcget(item, "text")).startswith("READY —")
        )
        status_bbox = canvas.bbox(status_item)
        check(
            status_bbox is not None and status_bbox[3] < 108,
            "the status instruction still sits behind the throttle ruler",
        )

        gate_names = {"FULL REV", "REV IDLE", "IDLE", "CL", "FLEX/MCT", "TOGA"}
        gate_items = [
            item for item in items
            if "\n" in str(canvas.itemcget(item, "text"))
            and str(canvas.itemcget(item, "text")).partition("\n")[0]
            in gate_names
        ]
        rows: dict[int, list[int]] = {}
        for item in gate_items:
            bbox = canvas.bbox(item)
            if bbox is not None:
                row = int(round(((bbox[1] + bbox[3]) / 2) / 10.0) * 10)
                rows.setdefault(row, []).append(item)
        check(
            len(rows) == 2 and all(len(row) == 6 for row in rows.values()),
            "expected six readable detent labels on each engine ruler",
        )
        for row_items in rows.values():
            ordered = sorted(row_items, key=lambda item: canvas.bbox(item)[0])
            for previous, current in zip(ordered, ordered[1:]):
                previous_bbox = canvas.bbox(previous)
                current_bbox = canvas.bbox(current)
                check(
                    previous_bbox is not None
                    and current_bbox is not None
                    and not _overlap(previous_bbox, current_bbox),
                    "adjacent detent labels overlap",
                )

        if args.preview:
            from PIL import ImageGrab

            root.deiconify()
            root.update()
            preview_path = Path(args.preview).resolve()
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            x1, y1 = canvas.winfo_rootx(), canvas.winfo_rooty()
            ImageGrab.grab(
                bbox=(x1, y1, x1 + WIDTH, y1 + HEIGHT), all_screens=True,
            ).save(preview_path)
            print(f"Preview saved: {preview_path}")
    finally:
        root.destroy()

    if failures:
        print("WinCtrl throttle readability check FAILED:", file=sys.stderr)
        for failure in failures:
            print("  - " + failure, file=sys.stderr)
        return 1
    print(
        f"WinCtrl throttle readability check passed: {checks} checks; "
        "all text >= 8 pt, status clear of ruler, labels bounded and separated."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
