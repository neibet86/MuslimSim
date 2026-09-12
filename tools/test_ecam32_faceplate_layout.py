"""Render the ECAM faceplate and protect the measured-name box placement."""

from __future__ import annotations

from pathlib import Path
import sys
import types


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

import tkinter as tk  # noqa: E402

from muslimsim.devices.ecam32 import ECAM32_A320_CONTROLS  # noqa: E402
from muslimsim.gui import studio as studio_module  # noqa: E402


Studio = studio_module.MuslimSimStudio
WIDTH = studio_module.FACEPLATE_DESIGN_WIDTH
HEIGHT = studio_module.FACEPLATE_DESIGN_HEIGHT


class FaceplateHarness:
    def __init__(self) -> None:
        self._selected_device = "ecam32"
        self._selected_visual = None
        self._flash_until = {}
        self._ecam_awake = False
        self._ecam_active_page = ""
        self._device_states = {
            "ecam32": {
                "state": "running",
                "mirror": {
                    "status": "running",
                    "contacts_seen": (),
                    "wake_enabled": False,
                    "lamps": {},
                },
            }
        }
        self._preview_snapshot = {}
        # Studio's ECAM buttons read bridge-held physical state through
        # _live_control_active.  Giving the harness the two attributes that
        # method needs lets it borrow the real implementation instead of a
        # stub, so this layout check exercises the same live-feedback path
        # Studio uses.  An empty lab simply reports nothing as live.
        self._lab = {}
        self._control_kinds = {}
        self.practice_mode = tk.BooleanVar(value=False)
        learned = {
            key: f"raw_r01_b{index // 8 + 1:02d}_bit{index % 8}"
            for index, (key, _label, _role) in enumerate(ECAM32_A320_CONTROLS)
        }
        self._profile = {
            "active_profile": "Default",
            "profiles": {
                "Default": {
                    "learned": {"ecam32": learned},
                    "bindings": {},
                }
            },
        }
        for name in (
            "_draw_ecam32",
            "_device_mirror",
            "_ecam_face_label",
            "_learned",
            "_learned_source",
            "_live_control_active",
            "_tag",
            "_tag_capture",
        ):
            setattr(self, name, types.MethodType(getattr(Studio, name), self))


def main() -> int:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"ECAM faceplate layout check skipped: no display ({exc}).")
        return 0
    root.withdraw()
    try:
        canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, highlightthickness=0)
        canvas.pack()
        harness = FaceplateHarness()
        harness._draw_ecam32(canvas, WIDTH, HEIGHT)
        root.update_idletasks()

        status_items = canvas.find_withtag("ecam-measured-status")
        assert len(status_items) == 3, "measured-name box must include one frame and two text lines"
        status_box = canvas.bbox("ecam-measured-status")
        assert status_box is not None

        # For the fixed 980 x 680 design, the ECAM outer panel finishes at
        # y=622.  The complete guidance box must be below it in the blue area,
        # remain visible, and never overlap a physical control hit target.
        panel_bottom = 622
        assert status_box[1] > panel_bottom, status_box
        assert status_box[3] <= HEIGHT, status_box
        off_panel = studio_module._ECAM32_OFF_PANEL_CONTROLS
        assert off_panel == frozenset({"ecam_blank_3", "ecam_blank_4"})
        for key in off_panel:
            assert canvas.bbox(f"control:{key}") is None, key
        drawn_boxes = {
            key: canvas.bbox(f"control:{key}")
            for key, _label, _role in ECAM32_A320_CONTROLS
            if key not in off_panel
        }
        assert all(box is not None for box in drawn_boxes.values()), drawn_boxes
        control_bottom = max(
            box[3]
            for box in drawn_boxes.values()
            if box is not None
        )
        assert control_bottom < status_box[1], (control_bottom, status_box)

        legend_box = canvas.bbox("ecam-state-legend")
        assert legend_box is not None
        assert legend_box[3] < status_box[1], (legend_box, status_box)
        print("ECAM32 faceplate layout check passed: guidance is below the panel and every button remains clear.")
        return 0
    finally:
        root.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
