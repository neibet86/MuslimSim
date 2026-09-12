#!/usr/bin/env python3
"""The right PDC's RANGE knob is an endless encoder and must turn like one.

The left PDC's RANGE is an eight-way switch with fixed detent positions. The
right one is a rotary encoder - `range_inc` / `range_dec` pulses - so its Studio
knob has to keep turning for as long as the owner keeps turning it, in the
direction they are turning, rather than nudging a few degrees and springing back
to centre.

Offline: no hardware, no simulator, no Tk window. The angle helper is exercised
directly, because that is where the behaviour lives.
"""

from __future__ import annotations

import math
from pathlib import Path
import sys


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.gui.studio import MuslimSimStudio

DEVICE = "pdc_bb52_right"


class _Knob:
    """The smallest object the real angle helper needs."""

    _pdc_range_turn_angle = MuslimSimStudio._pdc_range_turn_angle
    PDC_RANGE_DETENT_DEGREES = MuslimSimStudio.PDC_RANGE_DETENT_DEGREES

    def __init__(self):
        self._pdc_flat_anim = {}


def _mirror(inc=None, dec=None):
    records = {}
    if inc is not None:
        records["range_inc"] = {"sequence": inc}
    if dec is not None:
        records["range_dec"] = {"sequence": dec}
    return {"lab_inputs": records}


def check_first_sight_does_not_invent_a_turn():
    knob = _Knob()
    angle = knob._pdc_range_turn_angle(DEVICE, _mirror(inc=5))
    assert angle == 0.0, (
        "The knob jumped to %s the first time it saw the encoder. A pulse counter "
        "that is already non-zero when Studio opens is not a turn the owner "
        "made." % angle
    )
    print("  [ok] the first sight of the encoder does not invent a turn")


def check_each_pulse_turns_one_detent():
    knob = _Knob()
    knob._pdc_range_turn_angle(DEVICE, _mirror(inc=0))
    step = MuslimSimStudio.PDC_RANGE_DETENT_DEGREES
    for pulse in range(1, 5):
        angle = knob._pdc_range_turn_angle(DEVICE, _mirror(inc=pulse))
        assert abs(angle - pulse * step) < 1e-9, (
            "after %d pulses the knob was at %s, expected %s" % (pulse, angle, pulse * step)
        )
    print("  [ok] each pulse turns exactly one %.0f degree detent" % step)


def check_it_keeps_turning_past_a_full_revolution():
    """The whole point: no clamp, no spring back to centre."""

    knob = _Knob()
    knob._pdc_range_turn_angle(DEVICE, _mirror(inc=0))
    angle = 0.0
    for pulse in range(1, 41):
        angle = knob._pdc_range_turn_angle(DEVICE, _mirror(inc=pulse))
    step = MuslimSimStudio.PDC_RANGE_DETENT_DEGREES
    assert abs(angle - 40 * step) < 1e-9, (
        "after 40 pulses the knob was at %s, not %s. It is clamping or springing "
        "back instead of turning continuously." % (angle, 40 * step)
    )
    assert angle > 360.0, (
        "40 detents did not carry the knob past a full revolution (%s deg); the "
        "encoder is endless and the drawing must be too." % angle
    )
    print("  [ok] it keeps turning past a full revolution (%.0f degrees)" % angle)


def check_it_unwinds_the_other_way():
    knob = _Knob()
    knob._pdc_range_turn_angle(DEVICE, _mirror(inc=0, dec=0))
    for pulse in range(1, 6):
        knob._pdc_range_turn_angle(DEVICE, _mirror(inc=pulse, dec=0))
    forward = knob._pdc_range_turn_angle(DEVICE, _mirror(inc=5, dec=0))
    back = knob._pdc_range_turn_angle(DEVICE, _mirror(inc=5, dec=1))
    step = MuslimSimStudio.PDC_RANGE_DETENT_DEGREES
    assert abs((forward - back) - step) < 1e-9, (
        "a counter-clockwise pulse moved the knob by %s, expected %s"
        % (forward - back, step)
    )
    print("  [ok] turning the other way unwinds it by one detent")


def check_a_bridge_restart_does_not_spin_the_knob():
    """A pulse counter that resets must be adopted, not read as a huge turn."""

    knob = _Knob()
    knob._pdc_range_turn_angle(DEVICE, _mirror(inc=0))
    for pulse in range(1, 11):
        knob._pdc_range_turn_angle(DEVICE, _mirror(inc=pulse))
    before = knob._pdc_range_turn_angle(DEVICE, _mirror(inc=10))
    after = knob._pdc_range_turn_angle(DEVICE, _mirror(inc=0))
    assert after == before, (
        "the counter restarting at zero moved the knob from %s to %s; a bridge "
        "restart is not a turn." % (before, after)
    )
    print("  [ok] a restarted pulse counter does not spin the knob")


def check_folding_is_invisible():
    """Large angles fold back, and the fold must not move the drawn marker."""

    knob = _Knob()
    knob._pdc_range_turn_angle(DEVICE, _mirror(inc=0))
    previous = None
    for pulse in range(1, 200):
        angle = knob._pdc_range_turn_angle(DEVICE, _mirror(inc=pulse))
        drawn = (round(math.sin(math.radians(angle)), 9), round(math.cos(math.radians(angle)), 9))
        if previous is not None:
            step = MuslimSimStudio.PDC_RANGE_DETENT_DEGREES
            expected = (
                round(math.sin(math.radians(previous + step)), 9),
                round(math.cos(math.radians(previous + step)), 9),
            )
            assert drawn == expected, (
                "at pulse %d the drawn marker jumped: %s, expected %s. A fold "
                "back toward zero must move by a whole number of turns."
                % (pulse, drawn, expected)
            )
        previous = angle
    assert abs(angle) < 3600.0, (
        "the accumulated angle reached %s without folding; unbounded state on a "
        "path that runs forever is what rule 0.3 forbids." % angle
    )
    print("  [ok] the angle folds back without moving the drawn marker")


def check_the_two_pdcs_are_independent():
    knob = _Knob()
    knob._pdc_range_turn_angle("pdc_bb52_right", _mirror(inc=0))
    knob._pdc_range_turn_angle("pdc_bb52_right", _mirror(inc=1))
    left = knob._pdc_range_turn_angle("pdc_bb61_left", _mirror(inc=7))
    assert left == 0.0, (
        "turning the right PDC moved the left one to %s" % left
    )
    print("  [ok] the left and right knobs keep separate positions")


def main():
    print("PDC RANGE endless encoder:")
    check_first_sight_does_not_invent_a_turn()
    check_each_pulse_turns_one_detent()
    check_it_keeps_turning_past_a_full_revolution()
    check_it_unwinds_the_other_way()
    check_a_bridge_restart_does_not_spin_the_knob()
    check_folding_is_invisible()
    check_the_two_pdcs_are_independent()
    print("PDC RANGE endless encoder test passed.")


if __name__ == "__main__":
    main()
