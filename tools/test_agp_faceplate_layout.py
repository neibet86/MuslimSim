"""Offline authored-faceplate checks for AGP RADIO/NAV V2.

No cockpit hardware or simulator is opened.
"""
from __future__ import annotations

from pathlib import Path
import sys
import tkinter as tk

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.gui import studio as studio_module  # noqa: E402
from muslimsim.devices import agp_faceplate  # noqa: E402

WIDTH = studio_module.FACEPLATE_DESIGN_WIDTH
HEIGHT = studio_module.FACEPLATE_DESIGN_HEIGHT
failures: list[str] = []
checks = 0


def check(condition: bool, message: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(message)


class Harness:
    def __init__(self, controls: dict, mode: str) -> None:
        self._selected_device = "agp_bb80"
        self._mirror = {
            "page": mode,
            "values": (
                ("U1d1", "120900", "1200")
                if mode == "radio"
                else (" 250", " 10000", "  90")
            ),
            "vhf": 1,
            "controls": controls,
            "rotary_raw": {"rst": 3, "chr": 7, "date": 11},
        }

    def _device_mirror(self, key: str) -> dict:
        return dict(self._mirror) if key == "agp_bb80" else {}

    def _control_color(self, key: str) -> str:
        return "#5aa9ff"

    def _control_fill(self, key: str, default: str) -> str:
        return default

    def _tag(self, canvas: tk.Canvas, item: int, key: str) -> None:
        canvas.addtag_withtag(f"control:{key}", item)


STATES = (
    {
        "gear": "DOWN", "autobrake": "OFF", "brake_fan": False,
        "anti_skid": True, "elapsed_running": False, "vhf": 1,
    },
    {
        "gear": "UP", "autobrake": "MAX", "brake_fan": True,
        "anti_skid": False, "elapsed_running": True, "vhf": 3,
    },
)

EXPECTED = {
    "gear_up", "gear_down",
    "brake_fan_on", "brake_fan_off",
    "autobrake_low", "autobrake_med", "autobrake_max",
    "anti_skid_on", "anti_skid_off",
    "terr_on_nd",
    "rst_ccw", "rst", "rst_cw",
    "chr_left", "chr_press", "chr_right",
    "date_ccw", "date_press", "date_cw",
    "utc_gps", "utc_int", "utc_set",
    "timer_run", "timer_stop", "timer_reset",
}


def tagged(canvas: tk.Canvas) -> set[str]:
    found: set[str] = set()
    for item in canvas.find_all():
        for tag in canvas.gettags(item):
            if tag.startswith("control:"):
                found.add(tag.partition(":")[2])
    return found


def texts(canvas: tk.Canvas) -> set[str]:
    return {
        str(canvas.itemcget(item, "text"))
        for item in canvas.find_all()
        if canvas.type(item) == "text"
    }


def main() -> int:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"AGP faceplate check skipped: no display ({exc}).")
        return 0
    root.withdraw()
    try:
        seen: set[str] = set()
        for state in STATES:
            for mode in ("radio", "navigation"):
                canvas = tk.Canvas(
                    root, width=WIDTH, height=HEIGHT, highlightthickness=0
                )
                canvas.pack()
                agp_faceplate.draw_agp_faceplate(
                    Harness(state, mode), canvas, WIDTH, HEIGHT
                )
                root.update_idletasks()
                found = tagged(canvas)
                seen |= found
                labels = texts(canvas)

                check(
                    "agp_window_mode" not in found,
                    "the removed independent clock/radio mode control returned",
                )
                if mode == "radio":
                    check(
                        {"RADIO", "FREQ", "ATC"} <= labels,
                        "RADIO mode labels are incomplete",
                    )
                    check(
                        "MODE: RADIO  •  TERR ON ND" in labels,
                        "RADIO mode status is not visible",
                    )
                else:
                    check(
                        {"SPD", "ALT", "HDG"} <= labels,
                        "NAV mode labels are incomplete",
                    )
                    check(
                        "MODE: NAV  •  TERR ON ND" in labels,
                        "NAV mode status is not visible",
                    )

                check(
                    {"LDG GEAR", "BRK FAN", "AUTO BRK", "TERR ON ND"} <= labels,
                    f"printed panel legends missing in {mode}",
                )
                check(
                    len(canvas.find_all()) > 60,
                    f"{mode} faceplate drew suspiciously little",
                )
                canvas.destroy()

        missing = sorted(EXPECTED - seen)
        check(
            not missing,
            "these AGP controls are not clickable: " + ", ".join(missing),
        )

        rw, rh = agp_faceplate.AGP_REFERENCE_SIZE
        for rect in (
            agp_faceplate.AGP_LABEL_REGIONS
            + agp_faceplate.AGP_CONTROL_REGIONS
        ):
            check(
                0 <= rect.x1 < rect.x2 <= rw
                and 0 <= rect.y1 < rect.y2 <= rh,
                f"region {rect.name} is outside {rw}x{rh}",
            )
    finally:
        root.destroy()

    if failures:
        print("AGP faceplate V2 check FAILED:", file=sys.stderr)
        for line in failures:
            print("  - " + line, file=sys.stderr)
        return 1
    print(f"AGP faceplate V2 check passed: {checks} checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
