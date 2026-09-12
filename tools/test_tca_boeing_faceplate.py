"""Render the TCA Boeing faceplate offline and check it is actually usable.

The previous faceplate looked finished and was inert: it drew every lever at
mid-lane from no live data, and it never called ``_tag`` once, so nothing on it
could be clicked.  ``_faceplate_click`` only reacts to a ``control:<key>`` tag,
so with no tags "Choose simulator function" could never enable and the panel
could not map anything -- which is exactly how it behaved.

Neither a syntax check nor an import would have caught that, and nor would they
catch a bad colour literal or a wrong geometry call, which only fail inside Tcl
at draw time.  So this actually draws the panel onto a real off-screen canvas
and then interrogates what came out.

It opens no hardware and talks to no simulator.  It does need a display: on a
headless machine it reports that and exits 0 rather than failing.

Usage:
    python tools/test_tca_boeing_faceplate.py
"""

from __future__ import annotations

from pathlib import Path
import sys
import types

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

import tkinter as tk  # noqa: E402

from muslimsim.gui import studio as studio_module  # noqa: E402
from muslimsim.hardware.catalog import catalogue_snapshot  # noqa: E402

Studio = studio_module.MuslimSimStudio

# Every captured source must be clickable under either selector identity.
EXPECTED_TAGS = {}
for bank in ("12", "34"):
    EXPECTED_TAGS.update({
        f"bank{bank}_axis_3": "left slide",
        f"bank{bank}_axis_4": "middle slide",
        f"bank{bank}_axis_5": "right slide",
        f"bank{bank}_button_4": "middle reverse lever",
        f"bank{bank}_button_5": "right reverse lever",
        f"bank{bank}_button_1": "middle slide button",
        f"bank{bank}_button_2": "right slide button",
        f"bank{bank}_button_6": "side button",
        f"bank{bank}_button_7": "side button",
        f"bank{bank}_button_8": "side button",
        f"bank{bank}_button_9": "side button",
        f"bank{bank}_button_10": "side button",
        f"bank{bank}_button_11": "select IAS/MACH",
        f"bank{bank}_button_12": "select HDG/TRK",
        f"bank{bank}_button_13": "select ALTITUDE",
        f"bank{bank}_button_14": "encoder CCW",
        f"bank{bank}_button_15": "encoder CW",
        f"bank{bank}_button_16": "knob pushbutton",
    })


class FaceplateHarness:
    """Just enough Studio to draw, using the real drawing helpers."""

    def __init__(self, mirror, selected=None, practice=True):
        self._catalog = {item["key"]: item for item in catalogue_snapshot()["devices"]}
        self._selected_device = "tca_boeing"
        self._selected_visual = selected
        self._flash_until = {}
        self._learned_cache = {}
        self._detected = {
            "tca_boeing": {
                "product": "TCA Quadrant Boeing 1&2",
                "connected": True,
            }
        }
        self._device_states = {"tca_boeing": {"mirror": dict(mirror)}}
        self._preview_snapshot = {}
        self.practice_mode = tk.BooleanVar(value=practice)
        self._tca_axis_tracks = {}
        self._tca_practice_axes = {
            f"bank{bank}_axis_{axis}": float(mirror.get(f"bank{bank}_axis_{axis}", 1.0))
            for bank in ("12", "34") for axis in (3, 4, 5)
        }
        self._tca_drag_axis = None

        for name in (
            "_draw_tca_boeing_set",
            "_draw_tca_unit",
            "_tca_axis_value",
            "_device_mirror",
            "_visual_controls",
            "_control_color",
            "_control_fill",
            "_highlight_ring",
            "_tag",
            "_axis_ease",
            "_axis_ease_request_frame",
            "_pdc_flat_animate",
            "_pdc_flat_request_frame",
        ):
            setattr(self, name, types.MethodType(getattr(Studio, name), self))
        for name in (
            "_TCA_UNITS", "_TCA_FULL_SET_ROLES", "_TCA_SINGLE_ROLES",
            "_TCA_SIDE_BUTTONS", "_TCA_SELECT_DETENTS", "_TCA_HANDLE_CONTACTS",
        ):
            setattr(self, name, getattr(Studio, name))

    def _learned_source(self, key):
        return ""

    def after(self, _ms, _fn):
        # Each check draws with a fresh harness, so the first _axis_ease
        # call for any key always lands exactly on target - nothing here
        # ever needs to actually fire.
        return "after-noop"

    def _draw_faceplate(self):
        pass

    def _learned(self):
        return {}


def draw(canvas, mirror, selected=None):
    canvas.delete("all")
    FaceplateHarness(mirror, selected)._draw_tca_boeing_set(canvas, 1180, 620)
    canvas.update_idletasks()


def tagged_keys(canvas):
    keys = set()
    for item in canvas.find_all():
        for tag in canvas.gettags(item):
            if tag.startswith("control:"):
                keys.add(tag.partition(":")[2])
    return keys


def handle_y(canvas, key):
    """Vertical centre of the tagged items for one lever."""
    ys = []
    for item in canvas.find_all():
        if ("tca-handle:" + key) in canvas.gettags(item):
            coords = canvas.coords(item)
            ys.extend(coords[1::2])
    return sum(ys) / len(ys) if ys else None


def main() -> int:
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception as exc:
        print("No display available, skipping render test (%s)" % exc)
        return 0

    checks = 0
    failures = []

    def check(condition, message):
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(message)

    canvas = tk.Canvas(root, width=1180, height=620)

    rest = {
        "bank%s_axis_%d" % (bank, axis): 1.0
        for bank in ("12", "34") for axis in (3, 4, 5)
    }

    try:
        draw(canvas, rest)
    except Exception as exc:
        print("Faceplate raised while drawing: %r" % (exc,), file=sys.stderr)
        return 1
    check(True, "")  # drawing at all is the first check

    # 1. Every captured control must be clickable, or it cannot be mapped.
    keys = tagged_keys(canvas)
    for key, what in EXPECTED_TAGS.items():
        check(key in keys, f"{what} ({key}) is not clickable on the faceplate")

    # 2. Only real catalogue controls may be tagged: a tag that is not a
    #    control key selects something the mapper cannot bind.
    catalog_keys = {
        c["key"]
        for d in catalogue_snapshot()["devices"] if d["key"] == "tca_boeing"
        for c in d["controls"]
    }
    for key in keys:
        check(key in catalog_keys, f"faceplate tags {key!r}, which is not a catalogue control")

    # The complete Practice arrangement must read as six levers with the four
    # thrust slides together between airbrake and flaps.
    captions = []
    for item in canvas.find_all():
        try:
            value = canvas.itemcget(item, "text")
        except tk.TclError:
            continue
        if value:
            captions.append(value)
    for caption in ("AIRBRAKE", "THRUST 1", "THRUST 2", "THRUST 3", "THRUST 4", "FLAPS"):
        check(caption in captions, f"full-set role {caption!r} is not shown")

    # 3. The levers must move with live data, not sit at mid-lane.
    forward = dict(rest)
    forward["bank12_axis_4"] = -1.0
    draw(canvas, rest)
    rest_y = handle_y(canvas, "bank12_axis_4")
    draw(canvas, forward)
    forward_y = handle_y(canvas, "bank12_axis_4")
    check(
        rest_y is not None and forward_y is not None,
        "the middle lever produced no drawable geometry",
    )
    if rest_y is not None and forward_y is not None:
        check(
            abs(rest_y - forward_y) > 20,
            "the middle lever did not move between rest and full travel "
            f"(rest {rest_y:.1f}, full {forward_y:.1f}) -- the faceplate is static",
        )
        check(
            forward_y < rest_y,
            "full travel must draw above rest: rest is idle/retracted/up, which "
            "is the same direction the binding uses",
        )

    # 4. The other two levers must be independent of it.
    draw(canvas, rest)
    left_rest = handle_y(canvas, "bank12_axis_3")
    draw(canvas, forward)
    check(
        abs(handle_y(canvas, "bank12_axis_3") - left_rest) < 1.0,
        "moving the middle lever also moved the left one",
    )

    # 5. Selecting a control must change how it is drawn, or the click gives
    #    no feedback.
    draw(canvas, rest)
    plain = len(canvas.find_all())
    draw(canvas, rest, selected="bank12_axis_4")
    check(
        len(canvas.find_all()) > plain,
        "selecting a lever added no highlight, so a click looks like nothing",
    )

    # 6. A pressed contact must light.
    pressed = dict(rest)
    pressed["bank12_button_15"] = True
    draw(canvas, rest)
    before = [canvas.itemcget(i, "fill") for i in canvas.find_all()]
    draw(canvas, pressed)
    after = [canvas.itemcget(i, "fill") for i in canvas.find_all()]
    check(before != after, "pressing the encoder changed nothing on the panel")

    root.destroy()

    if failures:
        print("TCA Boeing faceplate self-test FAILED:", file=sys.stderr)
        for line in failures:
            print("  - " + line, file=sys.stderr)
        return 1

    print(
        "TCA Boeing faceplate self-test passed: %d checks. Every captured "
        "control is clickable, the levers track live axis values, and "
        "selection and presses are visible. No hardware or simulator touched."
        % checks
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
