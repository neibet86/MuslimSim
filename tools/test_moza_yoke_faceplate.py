#!/usr/bin/env python3
"""The MOZA A210 yoke must look like a yoke, turn like one, and light up the
contacts the hardware actually has - not the ones a first guess assumed.

Three rounds of owner feedback shaped this, in order:

1. "the yoke faceplate its not clear the design i so bad... rebuild it in a
   way it looks like the original Moza yoke and also it move freely like a
   yoke." The old drawing was a flat bar sliding a few pixels sideways.

2. Having watched the first rebuild move: it was upside down, roll needed to
   reach 90 degrees each way on a fixed axle instead of sliding, and every
   contact needed to stop printing its raw HID number.

3. Having watched V2 and pressed the real hardware while a fresh capture
   ran (``yoke.pcapng``): "the right upper and the left upper its just one
   button not five buttons... you can tap it from multiple angle. the right
   and left grip text should be on the side. the select buttons missing too
   many... there is four buttons on each corner... they don't work at all."

Decoding that capture (the same 34-byte report ``muslimsim/devices/
moza_a210.py`` already parses) replaced every guessed number with a proven
one:

* Contacts 31, 32, 53, 59, 62, 64, 66, 68, 70, 72, 74 read as permanently
  pressed for the entire 91.5 s capture - a firmware idle pattern, not a
  button - and are excluded, which is why the old "LEFT UPPER" and "RIGHT
  UPPER" guesses (which leaned on 31/32) are gone.
* Contacts 24 and 25 asserted together for the whole ~0.9 s of one press,
  across several hundred consecutive reports, and released together - one
  physical switch reported on two bits. That is "one button you can tap
  from multiple angles", proven, and it is RIGHT UPPER now.
* The left-hand equivalent was never pressed in this capture, so it is
  drawn with no numbers bound to it - not guessed.
* 19, 20, 21, 22 and 14, 15, 16, 17 each produced one clean edge on its own
  with nothing else moving at the same instant - the grips, replacing the
  old five-a-side guess that included two numbers (13, 18) that never moved
  at all.
* 5 through 12 - eight contacts, not five - each produced one clean edge on
  its own in one continuous test run. Select.
* 1, 2, 3, 4 matched the old guess exactly and are unchanged.

Every check here renders the real drawing function on a real (hidden) Tk
canvas and reads back where things actually ended up - not what the code
claims it did.

Offline: a real Tk canvas, never shown, no hardware, no simulator.
"""

from __future__ import annotations

from pathlib import Path
import math
import sys
import tkinter as tk
import types


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.gui import studio as studio_module  # noqa: E402


Studio = studio_module.MuslimSimStudio
WIDTH = studio_module.FACEPLATE_DESIGN_WIDTH
HEIGHT = studio_module.FACEPLATE_DESIGN_HEIGHT

# Every contact yoke.pcapng actually proved real, grouped by the cluster it
# belongs to - each number here produced a clean edge with nothing else
# moving at the same instant, in its own dedicated test pass.
LEFT_GRIP_NUMBERS = (19, 20, 21, 22)
RIGHT_GRIP_NUMBERS = (14, 15, 16, 17)
SELECT_NUMBERS = (5, 6, 7, 8, 9, 10, 11, 12)
CORNER_NUMBERS = (1, 2, 3, 4)
RIGHT_UPPER_NUMBERS = (24, 25)          # proven together, one switch, two bits
ALL_PROVEN_NUMBERS = (
    LEFT_GRIP_NUMBERS + RIGHT_GRIP_NUMBERS + SELECT_NUMBERS
    + CORNER_NUMBERS + RIGHT_UPPER_NUMBERS
)

# Read off the capture as never moving at all - a firmware idle pattern, not
# a real control - and therefore must not appear as a live contact anywhere
# on the redrawn yoke.
NEVER_A_BUTTON = (31, 32, 53, 59, 62, 64, 66, 68, 70, 72, 74, 13, 18)


class YokeHarness:
    """Just enough Studio to draw the yoke, using the real drawing helpers."""

    MOZA_YOKE_MAX_ROLL_DEGREES = Studio.MOZA_YOKE_MAX_ROLL_DEGREES
    MOZA_YOKE_PITCH_SCALE_RANGE = Studio.MOZA_YOKE_PITCH_SCALE_RANGE
    MOZA_YOKE_VERTICAL_SHIFT = Studio.MOZA_YOKE_VERTICAL_SHIFT

    def __init__(self) -> None:
        self._selected_device = "moza_a210"
        self._selected_visual = None
        self._flash_until: dict = {}
        self._lab: dict = {"inputs": {"moza_a210": {}}}
        self._learned_source = lambda key: False
        self._number = Studio._number
        self._moza_layout_page = {"moza_a210": "yoke"}
        # Genuine staticmethods (no ``self``) must be copied as-is - wrapping
        # one in types.MethodType re-adds the ``self`` argument it was
        # deliberately declared without.
        self._moza_yoke_point = Studio._moza_yoke_point
        self._moza_button_key = Studio._moza_button_key
        for name in (
            "_draw_moza_a210_yoke_layout", "_moza_yoke_capsule",
            "_moza_yoke_request_frame", "_moza_yoke_ease", "_pdc_flat_animate",
            "_pdc_flat_request_frame",
            "_draw_moza_yoke_dot", "_draw_moza_yoke_ring", "_draw_moza_yoke_rocker",
            "_draw_moza_yoke_button",
            "_moza_pressed", "_device_input_value",
            "_control_color", "_control_fill", "_tag", "_axis_fraction",
        ):
            setattr(self, name, types.MethodType(getattr(Studio, name), self))

    def press(self, number: int, value: float = 1.0) -> None:
        key = f"button_{number:03d}"
        self._lab["inputs"]["moza_a210"][key] = {"value": value}


def draw(canvas: tk.Canvas, harness: YokeHarness, axis_x: float = 0.5, axis_y: float = 0.5) -> None:
    canvas.delete("all")
    axes = {"axis_x": axis_x, "axis_y": axis_y, "axis_z": .5, "axis_dial": .5}
    harness._draw_moza_a210_yoke_layout(canvas, 20, 20, WIDTH - 20, HEIGHT - 20, axes, True)
    canvas.update_idletasks()


def fresh_draw(canvas: tk.Canvas, axis_x: float = 0.5, axis_y: float = 0.5, *, press: tuple[int, ...] = ()) -> YokeHarness:
    """A brand new harness per call, so the eased animation starts exactly on
    target - correctness of a single frame is not what the animation test is
    for."""

    harness = YokeHarness()
    for number in press:
        harness.press(number)
    draw(canvas, harness, axis_x, axis_y)
    return harness


def centre(canvas: tk.Canvas, tag: str) -> tuple[float, float]:
    box = canvas.bbox(tag)
    assert box is not None, f"nothing drawn for tag {tag}"
    return (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0


def button_tag(number: int) -> str:
    return f"control:button_{number:03d}"


def main() -> int:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"MOZA yoke faceplate check skipped: no display ({exc}).")
        return 0
    root.withdraw()
    try:
        canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, highlightthickness=0)
        canvas.pack()

        print("MOZA A210 yoke faceplate:")

        # -- every capture-proven contact is present, nothing invented is ----
        fresh_draw(canvas, 0.5, 0.5)
        for number in ALL_PROVEN_NUMBERS:
            box = canvas.bbox(button_tag(number))
            assert box is not None, (
                f"contact {number} was proven real by yoke.pcapng but is "
                "missing from the drawing"
            )
        for number in NEVER_A_BUTTON:
            box = canvas.bbox(button_tag(number))
            assert box is None, (
                f"contact {number} is drawn as live, but the capture shows it "
                "either never moved in 91.5 s of real use, or read as "
                "permanently pressed the whole time - neither is a button"
            )
        print(f"  [ok] all {len(ALL_PROVEN_NUMBERS)} capture-proven contacts "
              "are present, and none of the disproven ones are drawn")

        # -- the right rocker is one switch, lit by either of its two bits ---
        # yoke.pcapng only ever caught both bits together, but the code must
        # not depend on that - a switch reported on two bits can plausibly
        # assert just one of them from a particular angle, and it is still
        # the same one button being touched.
        rest = fresh_draw(canvas, 0.5, 0.5)
        assert not rest._moza_pressed("button_024") and not rest._moza_pressed("button_025")
        only_24 = fresh_draw(canvas, 0.5, 0.5, press=(24,))
        item_24 = canvas.find_withtag(button_tag(24))
        assert canvas.itemcget(item_24[0], "fill") == "#10615b", (
            "the right rocker did not light up with only contact 24 active - "
            "it must light on either bit, not require both at once"
        )
        only_25 = fresh_draw(canvas, 0.5, 0.5, press=(25,))
        item_25 = canvas.find_withtag(button_tag(25))
        assert canvas.itemcget(item_25[0], "fill") == "#10615b", (
            "the right rocker did not light up with only contact 25 active"
        )
        print("  [ok] the right rocker is one switch that lights on either "
              "of its two proven bits")

        # -- the left rocker is honestly unmapped, not guessed ---------------
        # It was never pressed in the capture. Drawn dashed and inert rather
        # than bound to an invented number that would light up on an
        # unrelated press.
        fresh_draw(canvas, 0.5, 0.5)
        left_ovals = [
            item for item in canvas.find_all()
            if canvas.type(item) == "oval" and "dash" in canvas.itemconfigure(item)
            and canvas.itemcget(item, "dash")
        ]
        assert left_ovals, (
            "no dashed, untagged oval was found - the left rocker should be "
            "drawn as visibly pending rather than silently omitted or "
            "silently bound to a guessed number"
        )
        for item in left_ovals:
            tags = canvas.gettags(item)
            control_tags = [t for t in tags if t.startswith("control:")]
            assert not control_tags, (
                "the pending left rocker carries a control tag (%s) - it must "
                "not be bound to any button number until one is proven"
                % control_tags
            )
        print("  [ok] the left rocker is drawn pending, bound to nothing, "
              "rather than guessing a number for it")

        # -- select has eight contacts, not five - "missing too many" fixed --
        for number in SELECT_NUMBERS:
            assert canvas.bbox(button_tag(number)) is not None, (
                f"select contact {number} is missing - select was expanded to "
                "all eight capture-proven positions, not left at five"
            )
        print("  [ok] select has all %d capture-proven contacts" % len(SELECT_NUMBERS))

        # -- select sits on the two sides, not the centre crossbar -----------
        # "the select button they should be located on the side in the place
        # of those two slides in the corner" - split across left and right,
        # each half clearly further from the hub's own x than the grips are,
        # matching where the two removed axis sliders used to sit.
        hub_x_for_check = WIDTH / 2.0
        left_select_x, _ = centre(canvas, button_tag(5))
        right_select_x, _ = centre(canvas, button_tag(9))
        left_grip_x, _ = centre(canvas, button_tag(19))
        right_grip_x, _ = centre(canvas, button_tag(14))
        assert left_select_x < left_grip_x < hub_x_for_check, (
            "the left half of select (x=%.1f) is not further out (more to "
            "the side) than the left grip (x=%.1f)" % (left_select_x, left_grip_x)
        )
        assert right_select_x > right_grip_x > hub_x_for_check, (
            "the right half of select (x=%.1f) is not further out (more to "
            "the side) than the right grip (x=%.1f)" % (right_select_x, right_grip_x)
        )
        print("  [ok] select sits split across both sides, further out than the grips")

        # -- the removed sliders leave no trace -------------------------------
        leftover = [item for item in canvas.find_all() if "moza_axis:axis_z" in canvas.gettags(item) or "moza_axis:axis_dial" in canvas.gettags(item)]
        assert not leftover, (
            "found %d leftover item(s) tagged with the removed axis sliders' "
            "own tags" % len(leftover)
        )
        print("  [ok] the removed axis sliders leave no drawn trace behind")

        # -- the grip pads are rounded rectangles, positioned above the rocker
        # "move left pad button and right pad button and change their shape
        # to rounded rectangular and move each above the yoke." A fresh,
        # known rest draw first - every check up to here left the canvas in
        # whatever state its own last axis values produced, and comparing
        # positions across two different leftover states (or a rotated one)
        # would prove nothing.
        fresh_draw(canvas, 0.5, 0.5)
        # button_tag(19) alone is one dot at the "up" position, offset from
        # the pad's own centre by its own radial spread - the combined bbox
        # of all four dots is needed to find the true centre they surround.
        left_dot_box = canvas.bbox(*[button_tag(n) for n in LEFT_GRIP_NUMBERS])
        pad_centre = ((left_dot_box[0] + left_dot_box[2]) / 2.0, (left_dot_box[1] + left_dot_box[3]) / 2.0)
        # The pad's own housing carries no control tag (matching how select's
        # ring housing is untagged too), so it is found by proximity to its
        # own dots rather than by tag - and confirmed a polygon (the rounded
        # rectangle), not an oval (what an unreshaped ring housing would be),
        # ruling out the hub and grip-capsule polygons elsewhere on the
        # canvas by distance alone.
        housing = None
        for item in canvas.find_all():
            if canvas.gettags(item):
                continue
            box = canvas.bbox(item)
            if box is None:
                continue
            item_centre = ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
            if math.hypot(item_centre[0] - pad_centre[0], item_centre[1] - pad_centre[1]) < 5.0:
                housing = item
                break
        assert housing is not None, "no untagged housing found centred on the left pad's own dots"
        assert canvas.type(housing) == "polygon", (
            "the left pad's housing is a %s, not the rounded rectangle "
            "(polygon) that was asked for" % canvas.type(housing)
        )
        rocker_centre_y = centre(canvas, "control:button_024")[1]
        assert pad_centre[1] < rocker_centre_y - 10.0, (
            "the left pad (y=%.1f) is not clearly above the rocker (y=%.1f)"
            % (pad_centre[1], rocker_centre_y)
        )
        print("  [ok] the grip pads are rounded rectangles, positioned above the rocker")

        # -- the whole yoke moved down, as far as the panel allows safely -----
        # A literal 3 cm does not fit without shrinking geometry nobody asked
        # to change (see MOZA_YOKE_VERTICAL_SHIFT); this checks that a real,
        # positive shift was actually applied, not just attempted, and that
        # it is the source of the hub's own drawn position - not merely a
        # constant that exists but goes unused.
        assert Studio.MOZA_YOKE_VERTICAL_SHIFT > 0.0, (
            "the yoke was asked to move down and the shift constant is not "
            "positive"
        )
        # A single select dot sits offset from its own ring's centre by the
        # ring's radial spread, exactly like a grip pad's dot above - the
        # combined bbox of one side's four dots is needed for the true
        # centre, which sits at local y=0, level with the hub.
        select_box = canvas.bbox(*[button_tag(n) for n in (5, 6, 7, 8)])
        select_ring_y = (select_box[1] + select_box[3]) / 2.0
        expected_hub_y = HEIGHT / 2.0 + Studio.MOZA_YOKE_VERTICAL_SHIFT
        assert abs(select_ring_y - expected_hub_y) < 5.0, (
            "the hub-level cluster is at y=%.1f, not the %.1f the shift "
            "constant predicts - the constant exists but is not what is "
            "actually positioning the yoke" % (select_ring_y, expected_hub_y)
        )
        print("  [ok] the yoke is shifted down %.0f px (%.1f cm @96dpi) - the "
              "largest amount that keeps every element on-panel at full zoom"
              % (Studio.MOZA_YOKE_VERTICAL_SHIFT, Studio.MOZA_YOKE_VERTICAL_SHIFT / 37.8))

        # -- no contact prints its raw number ---------------------------------
        for number in ALL_PROVEN_NUMBERS:
            items = canvas.find_withtag(button_tag(number))
            text_items = [item for item in items if canvas.type(item) == "text"]
            assert not text_items, (
                "contact %d still has a text item drawn on it (%s) - a raw "
                "contact number is not a function and must not be printed on "
                "the hardware's own face"
                % (number, [canvas.itemcget(i, "text") for i in text_items])
            )
        print("  [ok] no contact prints its raw number - live colour only")

        # -- centred is centred, and grips sit ABOVE the hub -----------------
        left_ref = centre(canvas, button_tag(19))
        right_ref = centre(canvas, button_tag(14))
        # The hub's own position is known analytically (the panel is centred
        # exactly on it by construction), so "above the hub" can be checked
        # against the real pivot rather than against another drawn cluster
        # whose own placement is a separate, non-essential layout choice.
        hub_y_for_check = HEIGHT / 2.0 + Studio.MOZA_YOKE_VERTICAL_SHIFT
        assert abs(left_ref[1] - right_ref[1]) < 30.0, (
            "at rest the two grips are not roughly level with each other: "
            "%s vs %s" % (left_ref, right_ref)
        )
        assert left_ref[1] < hub_y_for_check - 20.0, (
            "the left grip (%s) is not clearly above the hub (y=%.1f) - the "
            "real MFY yoke has its grips above the hub, not below it, and "
            "this was drawn upside down once already"
            % (left_ref, hub_y_for_check)
        )
        print("  [ok] centred axes draw a level yoke with grips above the hub")

        # -- grip captions sit to the side, not above -------------------------
        # "the right and left grip text should be on the side": the caption
        # must be offset horizontally, outward from the yoke's own centre,
        # rather than floating directly above the cluster.
        left_grip_centre_x = left_ref[0]
        left_caption = next(
            item for item in canvas.find_all()
            if canvas.type(item) == "text" and canvas.itemcget(item, "text") == "LEFT GRIP"
        )
        caption_x = canvas.coords(left_caption)[0]
        assert caption_x < left_grip_centre_x - 15.0, (
            "the LEFT GRIP caption (x=%.1f) is not offset to the outer side "
            "of its cluster (x=%.1f) - it should sit beside the cluster, not "
            "above it" % (caption_x, left_grip_centre_x)
        )
        print("  [ok] grip captions are offset to the side, not above")

        # -- there is no visible shaft/rod - the axle is a fixed point -------
        # A shaft is a straight two-point line (exactly 4 coordinates) from
        # the hub to some other fixed point. The horns are also thin strokes,
        # but they are smoothed curves through five waypoints (10
        # coordinates) - the distinguishing fact is the point count, not the
        # width, since a horn's own inner decorative stroke is thin too.
        straight_lines = sum(
            1 for item in canvas.find_all()
            if canvas.type(item) == "line" and len(canvas.coords(item)) == 4
        )
        assert straight_lines == 0, (
            "found %d straight two-point line(s) on the yoke - the visible "
            "connecting rod the owner asked to have removed appears to be "
            "back" % straight_lines
        )
        print("  [ok] no visible shaft/rod - the axle is an undrawn fixed point")

        # -- roll rotates about the FIXED axle by the commanded angle --------
        # The hub is analytically known - the panel is centred exactly on it
        # by construction - so the *angle* swept by a point relative to the
        # hub is the correct, starting-angle-independent proof of rotation.
        hub_x, hub_y = WIDTH / 2.0, HEIGHT / 2.0 + Studio.MOZA_YOKE_VERTICAL_SHIFT

        def angle_from_hub(point: tuple[float, float]) -> float:
            return math.degrees(math.atan2(point[1] - hub_y, point[0] - hub_x))

        angle_before_left = angle_from_hub(left_ref)
        angle_before_right = angle_from_hub(right_ref)
        fresh_draw(canvas, 1.0, 0.5)
        left_full_roll = centre(canvas, button_tag(19))
        right_full_roll = centre(canvas, button_tag(14))
        swept_left = (angle_from_hub(left_full_roll) - angle_before_left + 540.0) % 360.0 - 180.0
        swept_right = (angle_from_hub(right_full_roll) - angle_before_right + 540.0) % 360.0 - 180.0
        for label, swept in (("left", swept_left), ("right", swept_right)):
            assert abs(abs(swept) - Studio.MOZA_YOKE_MAX_ROLL_DEGREES) < 1.0, (
                "full roll swept the %s grip through %.1f degrees about the "
                "hub, not the commanded %.1f - a rigid-body rotation must "
                "turn every point by exactly the roll angle"
                % (label, swept, Studio.MOZA_YOKE_MAX_ROLL_DEGREES)
            )
        print("  [ok] roll sweeps both grips through exactly %.0f degrees "
              "about the fixed hub" % Studio.MOZA_YOKE_MAX_ROLL_DEGREES)

        # -- full deflection is 90 degrees each way, as asked -----------------
        assert Studio.MOZA_YOKE_MAX_ROLL_DEGREES == 90.0, (
            "full roll deflection is %.0f degrees, not the 90 degrees each "
            "way that was asked for" % Studio.MOZA_YOKE_MAX_ROLL_DEGREES
        )
        print("  [ok] full roll deflection is 90 degrees each way")

        # -- the whole shape stays on the visible panel at full deflection ---
        panel = (20, 20, WIDTH - 20, HEIGHT - 20)
        for axis_x in (0.0, 0.5, 1.0):
            for axis_y in (0.0, 0.5, 1.0):
                fresh_draw(canvas, axis_x, axis_y)
                box = canvas.bbox("all")
                assert box is not None
                assert box[0] >= panel[0] - 2 and box[1] >= panel[1] - 2, (
                    "the yoke drew outside the top-left of its panel at "
                    "axis_x=%.1f axis_y=%.1f: bbox %s vs panel %s"
                    % (axis_x, axis_y, box, panel)
                )
                assert box[2] <= panel[2] + 2 and box[3] <= panel[3] + 2, (
                    "the yoke drew outside the bottom-right of its panel at "
                    "axis_x=%.1f axis_y=%.1f: bbox %s vs panel %s"
                    % (axis_x, axis_y, box, panel)
                )
        print("  [ok] the full silhouette stays inside its panel at every "
              "roll/pitch extreme tested")

        # -- pitch scales the assembly; the axle itself never moves ----------
        def pivot_x_from_symmetry(axis_x: float, axis_y: float) -> float:
            fresh_draw(canvas, axis_x, axis_y)
            left_x, _ = centre(canvas, button_tag(19))
            right_x, _ = centre(canvas, button_tag(14))
            return (left_x + right_x) / 2.0

        pivot_rest = pivot_x_from_symmetry(0.5, 0.5)
        pivot_push = pivot_x_from_symmetry(0.5, 1.0)
        pivot_pull = pivot_x_from_symmetry(0.5, 0.0)
        assert abs(pivot_push - hub_x) < 1.0 and abs(pivot_pull - hub_x) < 1.0, (
            "the pivot implied by the two grips' midpoint moved under pitch "
            "(rest %.1f, push %.1f, pull %.1f, true centre %.1f) - it was "
            "asked to be fixed in the middle, with only size changing"
            % (pivot_rest, pivot_push, pivot_pull, hub_x)
        )
        fresh_draw(canvas, 0.5, 0.5)
        span_rest = canvas.bbox(button_tag(19))
        rest_width = span_rest[2] - span_rest[0]
        fresh_draw(canvas, 0.5, 1.0)
        push_width = canvas.bbox(button_tag(19))[2] - canvas.bbox(button_tag(19))[0]
        fresh_draw(canvas, 0.5, 0.0)
        pull_width = canvas.bbox(button_tag(19))[2] - canvas.bbox(button_tag(19))[0]
        assert push_width > rest_width > pull_width, (
            "sizes at push/rest/pull were %.1f / %.1f / %.1f - push must be "
            "the largest (zoom in) and pull the smallest (zoom out), per the "
            "owner's own description" % (push_width, rest_width, pull_width)
        )
        print("  [ok] the axle stays fixed; push zooms in (%.0fpx), rest is "
              "%.0fpx, pull zooms out (%.0fpx)" % (push_width, rest_width, pull_width))

        # -- the transform itself: a pure rotation preserves distance from hub
        harness = YokeHarness()
        hub_cx, hub_cy = 400.0, 300.0
        for roll in (-90.0, -40.0, 0.0, 17.0, 90.0):
            for local_x, local_y in ((112.0, -80.0), (-112.0, -80.0), (0.0, -52.0)):
                px, py = harness._moza_yoke_point(local_x, local_y, hub_cx, hub_cy, roll, 1.0)
                distance = math.hypot(px - hub_cx, py - hub_cy)
                expected = math.hypot(local_x, local_y)
                assert abs(distance - expected) < 0.01, (
                    "rotating by %.0f degrees changed a point's distance from "
                    "the hub from %.2f to %.2f - this is not a rotation"
                    % (roll, expected, distance)
                )
        print("  [ok] the transform preserves distance from the fixed axle "
              "at every angle tested, including the full 90 degree extremes")

        # -- motion is eased toward its target, not snapped ------------------
        smooth_harness = YokeHarness()
        draw(canvas, smooth_harness, 0.5, 0.5)
        rest_x, _ = centre(canvas, button_tag(19))
        draw(canvas, smooth_harness, 1.0, 0.5)
        first_step_x, _ = centre(canvas, button_tag(19))
        draw(canvas, smooth_harness, 1.0, 0.5)
        second_step_x, _ = centre(canvas, button_tag(19))
        for _ in range(30):
            draw(canvas, smooth_harness, 1.0, 0.5)
        settled_x, _ = centre(canvas, button_tag(19))
        first_gap = abs(first_step_x - rest_x)
        total_gap = abs(settled_x - rest_x)
        assert 0.0 < first_gap < total_gap * 0.95, (
            "the first frame after a target change landed at %.1f of the way "
            "there (start %.1f, first %.1f, settled %.1f) - motion must ease "
            "toward its target across several frames, not snap in one"
            % (first_gap / max(total_gap, 1e-6), rest_x, first_step_x, settled_x)
        )
        assert abs(second_step_x - first_step_x) > 0.5, (
            "the second frame did not move any further than the first - the "
            "easing stalled instead of continuing toward the target"
        )
        print("  [ok] roll eases toward a new target across frames instead "
              "of snapping (first step %.1f%% of the way there)"
              % (100.0 * first_gap / max(total_gap, 1e-6)))

        print("MOZA yoke faceplate test passed.")
        return 0
    finally:
        root.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
