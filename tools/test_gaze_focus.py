#!/usr/bin/env python3
"""Focusing on something must hold the pointer still; looking away must not wait.

The owner's complaint: reading a tablet in the cockpit or turning a knob several
times, and the view shakes and the pointer will not stay put, because it follows
every tremor of the head and eyes.

Everything here is one of two claims:

  * while dwelling, the output barely moves even though the input never stops;
  * the moment the gaze deliberately leaves, the output follows at once.

Those pull against each other, and any change that buys steadiness with slower
release is the wrong trade - so both are measured, not asserted loosely.

Traces are synthetic but shaped like the real thing: 33 Hz, which is what the
owner's Eye Tracker 5 actually runs at, with gaussian tremor of about a quarter
of a degree on top. Seeded, so a failure is reproducible.

Offline: no tracker, no simulator, no Tk window.
"""

from __future__ import annotations

from pathlib import Path
import math
import random
import sys


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.platform.gaze_focus import FocusSettings, GazeFocus


RATE = 33.0
DT = 1.0 / RATE
TREMOR = 0.004          # about a quarter of a degree on a normal desk setup


def dwell(seed, centre, seconds, tremor=TREMOR, drift=0.0):
    """Somebody looking at one spot: tremor, plus optional slow drift."""

    rng = random.Random(seed)
    samples = int(seconds * RATE)
    for index in range(samples):
        slide = drift * (index / max(1, samples - 1))
        yield (
            centre[0] + rng.gauss(0.0, tremor) + slide,
            centre[1] + rng.gauss(0.0, tremor),
        )


def path_length(points):
    return sum(
        math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:])
    )


def run(focus, samples, start=0.0, valid=True):
    """Feed samples at the tracker's rate; return every state produced."""

    states = []
    now = start
    for x, y in samples:
        states.append(focus.update(now, x, y, valid=valid))
        now += DT
    return states


def check_dwelling_holds_the_pointer_still():
    """The headline: the input never stops moving and the output nearly does."""

    focus = GazeFocus()
    trace = list(dwell(1, (0.5, 0.5), 3.0))
    states = run(focus, trace)

    locked = [s for s in states if s.focused]
    assert locked, "three seconds of dwelling never registered as focus at all"

    raw_travel = path_length(trace)
    held_travel = path_length([s.point for s in locked])
    assert raw_travel > 0.15, (
        "the synthetic tremor is too small to be a fair test (%.4f)" % raw_travel
    )
    assert held_travel < raw_travel / 40.0, (
        "while focused the pointer travelled %.4f against the eye's %.4f - only "
        "%.0fx steadier. Tremor is passing through to the pointer, which is the "
        "whole complaint." % (held_travel, raw_travel, raw_travel / max(held_travel, 1e-9))
    )
    print("  [ok] dwelling: eye moved %.3f, pointer moved %.4f (%.0fx steadier)"
          % (raw_travel, held_travel, raw_travel / max(held_travel, 1e-9)))


def check_focus_takes_about_as_long_as_it_should():
    focus = GazeFocus()
    states = run(focus, dwell(2, (0.5, 0.5), 2.0))
    first = next((i for i, s in enumerate(states) if s.focused), None)
    assert first is not None, "never focused"
    settled = first * DT
    assert 0.10 <= settled <= 0.45, (
        "focus took %.3f s to engage; it should be around the settle window, "
        "not instant and not a noticeable wait" % settled
    )
    print("  [ok] focus engages after %.0f ms of dwelling" % (settled * 1000))


def check_looking_away_releases_at_once():
    """The asymmetry. This is the one that makes it feel right or broken."""

    focus = GazeFocus()
    run(focus, dwell(3, (0.3, 0.3), 1.5))
    assert focus.update(1.5, 0.3, 0.3).focused, "was not focused before the flick"

    # A real saccade: most of the screen inside two frames.
    now = 1.5
    released = None
    for step, point in enumerate(((0.55, 0.45), (0.80, 0.60), (0.82, 0.61))):
        now += DT
        state = focus.update(now, point[0], point[1])
        if not state.focused and released is None:
            released = step + 1
    assert released is not None, "a full-screen flick never released the lock"
    assert released <= 2, (
        "the lock survived %d samples of a deliberate flick. Anything past one "
        "or two frames reads as the pointer fighting the owner." % released
    )
    print("  [ok] a deliberate flick releases after %d sample(s), %.0f ms"
          % (released, released * DT * 1000))


def check_release_is_faster_than_lock():
    """Stated as a ratio, so a future tuning pass cannot quietly invert it."""

    focus = GazeFocus()
    states = run(focus, dwell(4, (0.5, 0.5), 2.0))
    lock_samples = next(i for i, s in enumerate(states) if s.focused)

    now = 2.0
    release_samples = 0
    for point in ((0.60, 0.55), (0.85, 0.70), (0.88, 0.72)):
        now += DT
        release_samples += 1
        if not focus.update(now, point[0], point[1]).focused:
            break
    assert release_samples < lock_samples, (
        "locking took %d samples and releasing took %d. Releasing must always "
        "be the faster of the two." % (lock_samples, release_samples)
    )
    print("  [ok] locks in %d samples, releases in %d" % (lock_samples, release_samples))


def check_a_blink_does_not_break_focus():
    focus = GazeFocus()
    run(focus, dwell(5, (0.4, 0.6), 1.5))
    now = 1.5
    assert focus.update(now, 0.4, 0.6).focused

    # A blink: about 120 ms of invalid gaze.
    for _ in range(4):
        now += DT
        state = focus.update(now, 0.0, 0.0, valid=False)
        assert state.focused, (
            "a blink dropped the lock. Blinks happen every few seconds, so this "
            "would read as the pointer letting go at random."
        )
    now += DT
    assert focus.update(now, 0.4, 0.6).focused, "focus did not survive the blink"
    print("  [ok] a 120 ms blink does not break focus")


def check_looking_right_away_does_break_focus():
    focus = GazeFocus()
    run(focus, dwell(6, (0.4, 0.6), 1.5))
    now = 1.5
    for _ in range(int(0.6 * RATE)):
        now += DT
        state = focus.update(now, 0.0, 0.0, valid=False)
    assert not state.focused, (
        "gaze was gone for 0.6 s - well past a blink - and the lock was still "
        "held"
    )
    print("  [ok] gaze gone for longer than a blink does break focus")


def check_the_filter_measures_its_own_gap_not_the_coast_gap():
    """A subtle timing bug: dt must span the filter's own last real sample.

    ``update()`` is called on every coasted (blink or recovery-window) sample
    too, not just the ones the filter actually sees. If the filter's dt were
    measured against the *previous call to update()* rather than against its
    own last invocation, the first sample after any gap would divide a real
    position change by a one-sample dt instead of the true elapsed gap - an
    apparent speed roughly ten times too high, right when the filter should be
    at its most cautious rather than its least.
    """

    focus = GazeFocus()
    run(focus, dwell(90, (0.5, 0.5), 1.0))

    # A long, quiet gap - a blink held a beat longer than usual - then, still
    # within the recovery window, gaze resumes a real distance away, the way
    # it does after a real blink: the eyelid leaves the reading off to the
    # side while the tracker is still saying "valid". Every one of those
    # samples is a real call to update(), exactly like the real trace, so the
    # bug is exercised the same way it was in production - not just a gap in
    # wall-clock time with no calls in between.
    now = 1.0
    for _ in range(int(0.5 * RATE)):
        now += DT
        focus.update(now, 0.0, 0.0, valid=False)
    settings = FocusSettings()
    gated_samples = int(settings.recovery_seconds / DT)
    for _ in range(gated_samples):
        now += DT
        focus.update(now, 0.60, 0.55)   # gated: still inside recovery_seconds
    now += DT
    state = focus.update(now, 0.60, 0.55)   # the first ungated sample
    assert state.speed < 1.0, (
        "the first ungated sample after the recovery window reported speed "
        "%.3f for a jump that took the better part of a second in wall-clock "
        "time, spread across real calls to update() the whole way. That is the "
        "true elapsed gap being replaced with a single sample interval, which "
        "reads as roughly a magnitude too fast and defeats the smoothing "
        "exactly when a spurious jump most needs to be damped." % state.speed
    )
    print("  [ok] the filter's dt spans its own last sample, not the coast gap")


def check_drift_must_be_sustained_not_glimpsed():
    """The gap between crossing the break radius and releasing is the point.

    Isolating this needed care: the one-euro filter damps the very first
    sample of any jump so heavily that drift does not even cross the break
    radius on sample one, so a naive "one sample does not release" check
    passes regardless of whether persistence exists at all - it never reaches
    that code path. What actually proves persistence is timing: once *smoothed*
    drift is genuinely and continuously past the break radius, release must
    still wait `break_hold_seconds` from that point, not fire immediately.

    The recorded blink trace does not exercise this either - that blink's
    smoothed drift never climbs past the break radius at all, filtered enough
    on its own. This is the mechanism on its own terms, measured directly.
    """

    settings = FocusSettings()
    focus = GazeFocus()
    run(focus, dwell(95, (0.5, 0.5), 1.0))
    now = 1.0
    assert focus.update(now, 0.5, 0.5).focused

    spike = settings.break_radius + 0.03
    crossed_at = None
    released_at = None
    for _ in range(int(2.0 * RATE)):
        now += DT
        state = focus.update(now, 0.5 + spike, 0.5)
        anchor = focus._anchor
        if anchor is not None and crossed_at is None:
            drift = math.hypot(
                state.smoothed[0] - anchor[0], state.smoothed[1] - anchor[1]
            )
            if drift > settings.break_radius:
                crossed_at = now
        if state.release == "drift":
            released_at = now
            break

    assert crossed_at is not None, (
        "the test is not proving anything: smoothed drift never reached the "
        "break radius at all"
    )
    assert released_at is not None, (
        "drift stayed past the break radius for two full seconds and never "
        "released"
    )
    waited = released_at - crossed_at
    assert waited >= settings.break_hold_seconds - DT, (
        "release fired only %.3f s after drift crossed the break radius, but "
        "break_hold_seconds is %.3f s. A momentary excursion - the near side "
        "of a blink, most often - must be sustained this long before it counts "
        "as looking away, and %.3f s is releasing on sight instead."
        % (waited, settings.break_hold_seconds, waited)
    )
    assert waited <= settings.break_hold_seconds + 0.10, (
        "release took %.3f s after crossing, well past break_hold_seconds "
        "(%.3f s) - the persistence timer is not the thing gating this"
        % (waited, settings.break_hold_seconds)
    )
    print("  [ok] drift releases %.3f s after crossing (break_hold_seconds is %.3f s)"
          % (waited, settings.break_hold_seconds))


def check_the_owners_recorded_blink_does_not_break_focus():
    """The exact regression the owner's first live run surfaced.

    Recorded with `tools/probe_tobii_focus.py --save gaze.txt` while staring at
    one spot: the eyelid corrupts the reported gaze for several samples both
    before and after the three the tracker admits are invalid, and every one of
    those samples is flagged *valid* - some of them a tenth of the screen away
    from where the owner was actually looking. Reading them at face value threw
    focus away on every blink; that is what `recovery_seconds` exists to fix.
    """

    # (seconds since first sample, x, y, valid) - unedited, from gaze.txt.
    trace = (
        (0.000, 0.650069, 0.356619, True), (0.030, 0.651681, 0.352433, True),
        (0.060, 0.652883, 0.348614, True), (0.091, 0.653953, 0.346538, True),
        (0.121, 0.654731, 0.345359, True), (0.151, 0.655190, 0.345009, True),
        (0.181, 0.655650, 0.344497, True), (0.212, 0.656127, 0.344149, True),
        (0.242, 0.656593, 0.344230, True), (0.272, 0.657038, 0.343858, True),
        (0.302, 0.657516, 0.343638, True), (0.332, 0.658077, 0.343472, True),
        (0.362, 0.658557, 0.343317, True), (0.393, 0.658962, 0.342967, True),
        (0.423, 0.659300, 0.342510, True), (0.453, 0.659606, 0.342044, True),
        (0.484, 0.659887, 0.341768, True), (0.514, 0.660109, 0.341365, True),
        (0.544, 0.660389, 0.340975, True), (0.574, 0.660695, 0.340589, True),
        (0.604, 0.660863, 0.340298, True), (0.634, 0.660978, 0.340337, True),
        (0.665, 0.661112, 0.340311, True), (0.695, 0.661349, 0.340485, True),
        (0.725, 0.665570, 0.348717, True),   # eyelid starts closing - still "valid"
        (0.755, 0.650185, 0.346242, True),
        (0.786, 0.702962, 0.443796, True),   # a tenth of the screen away
        (0.816, 0.694928, 0.422456, True),
        (0.846, 0.691665, 0.409665, True),
        (0.877, 0.689563, 0.405590, True),
        (0.907, -1.000000, -1.000000, False),   # the tracker's own blink flag
        (0.937, -1.000000, -1.000000, False),
        (0.968, -1.000000, -1.000000, False),
        (0.998, 0.682094, 0.430350, True),      # eyelid still opening
        (1.028, 0.708117, 0.458075, True),
        (1.059, 0.704946, 0.451790, True),
        (1.089, 0.698348, 0.438763, True),
        (1.119, 0.690684, 0.423721, True),
        (1.149, 0.683545, 0.407938, True),
        (1.179, 0.677908, 0.394936, True),
        (1.209, 0.674581, 0.383549, True),
        (1.239, 0.672307, 0.376330, True),
        (1.269, 0.670671, 0.371678, True),
        (1.299, 0.669368, 0.368526, True),
        (1.329, 0.668102, 0.366981, True),
        (1.359, 0.667324, 0.366058, True),
        (1.390, 0.667164, 0.364729, True),
        (1.420, 0.667197, 0.363170, True),
        (1.450, 0.666917, 0.361882, True),
    )
    focus = GazeFocus()
    releases = []
    state = None
    for t, x, y, ok in trace:
        state = focus.update(t, x, y, valid=ok)
        if state.release:
            releases.append((t, state.release))
    assert not releases, (
        "the recorded blink released focus (%s), reproducing the exact failure "
        "seen on the owner's first live run - a blink must not read as looking "
        "away" % releases
    )
    assert state.focused, "focus did not survive the owner's recorded blink"
    print("  [ok] the owner's recorded blink no longer breaks focus")


def check_turning_a_knob_holds_the_lock():
    """The part only MuslimSim can do: it knows a control is being operated."""

    settings = FocusSettings()
    loose = GazeFocus(settings)
    strict = GazeFocus(settings)
    run(loose, dwell(7, (0.5, 0.5), 1.5))
    run(strict, dwell(7, (0.5, 0.5), 1.5))

    # Gaze glances further than the break radius would normally allow and stays
    # there, the way it does when the owner looks between a knob and the
    # instrument it moves while still working the knob.
    # Whether the lock ever broke is the question - not where it ended up, since
    # a released lock simply settles again wherever the gaze went.
    now = 1.5
    loose_broke = strict_broke = False
    loose_state = None
    for point in dwell(70, (0.5 + 0.072, 0.5 + 0.022), 0.4):
        now += DT
        loose.hold(now)                      # a knob click just arrived
        loose_state = loose.update(now, point[0], point[1])
        strict_state = strict.update(now, point[0], point[1])
        loose_broke = loose_broke or not loose_state.focused
        strict_broke = strict_broke or not strict_state.focused

    assert strict_broke, (
        "the test is not proving anything: gaze glanced past the break radius "
        "and the lock held even without a control being operated"
    )
    assert not loose_broke, (
        "the owner was mid-way through turning a knob and the lock dropped "
        "anyway. Somebody a third of the way through a knob is not trying to "
        "look somewhere else."
    )
    assert loose_state.held, "the hold was not reported in the state"
    print("  [ok] operating a control holds the lock through a wider glance")


def check_the_hold_expires():
    focus = GazeFocus()
    run(focus, dwell(8, (0.5, 0.5), 1.5))
    now = 1.5
    focus.hold(now)
    now += FocusSettings().hold_grace + 0.1
    # Sustained, because drift alone no longer releases on a single sample -
    # a blink throws the reported gaze off for a few frames and then brings it
    # back, and that must not read as looking away. What has to happen here is
    # that the lock is given up on the *old* anchor - it may well re-settle on
    # the new spot a few frames later, and that is correct, not a bug.
    released = False
    state = None
    for point in dwell(80, (0.5 + 0.075, 0.5 + 0.025), 0.4):
        now += DT
        state = focus.update(now, point[0], point[1])
        if state.release == "drift":
            released = True
        assert not state.held, "the hold outlived its grace period"
    assert released, (
        "the owner stopped working the control and looked well away, and the "
        "lock on the old spot was never given up"
    )
    print("  [ok] the hold expires when the owner stops working the control")


def check_slow_reaiming_follows_without_unlocking():
    focus = GazeFocus()
    run(focus, dwell(9, (0.4, 0.4), 1.5))
    start = focus.update(1.5, 0.4, 0.4)
    assert start.focused

    # Drifting deliberately but gently across a third of the settle radius per
    # second - reading along a line, say.
    now = 1.5
    state = start
    for point in dwell(10, (0.4, 0.4), 2.0, drift=0.030):
        now += DT
        state = focus.update(now, point[0], point[1])
    assert state.focused, "a slow deliberate re-aim unlocked instead of following"
    moved = state.point[0] - start.point[0]
    assert moved > 0.010, (
        "the anchor followed the re-aim by only %.4f; it should creep toward a "
        "sustained move, not sit frozen while the owner drifts off it" % moved
    )
    print("  [ok] a slow re-aim is followed (%.3f) without unlocking" % moved)


def check_the_view_gain_damps_and_ramps():
    focus = GazeFocus()
    states = run(focus, dwell(11, (0.5, 0.5), 2.0))
    roaming = states[0].view_gain
    settled = states[-1].view_gain
    assert roaming > 0.9, "the view was damped before focus was ever established"
    assert settled < 0.25, (
        "the view gain only reached %.2f while focused; head shake is still "
        "driving the camera while the owner tries to read" % settled
    )
    steps = [
        abs(b.view_gain - a.view_gain) for a, b in zip(states, states[1:])
    ]
    assert max(steps) < 0.25, (
        "the view gain jumped by %.2f in one frame. A step change in camera "
        "gain is itself a visible jolt, which is what this is meant to remove."
        % max(steps)
    )
    print("  [ok] view gain eases %.2f -> %.2f, largest step %.3f"
          % (roaming, settled, max(steps)))


def check_it_does_not_chatter_at_the_boundary():
    """Hysteresis: gaze sitting right at the edge must not flicker in and out."""

    focus = GazeFocus()
    settings = FocusSettings()
    edge = settings.settle_radius * 0.95
    rng = random.Random(12)
    now = 0.0
    flips = 0
    was = False
    for _ in range(int(4.0 * RATE)):
        angle = rng.uniform(0.0, 2.0 * math.pi)
        state = focus.update(
            now, 0.5 + edge * math.cos(angle), 0.5 + edge * math.sin(angle)
        )
        if state.focused != was:
            flips += 1
            was = state.focused
        now += DT
    assert flips <= 4, (
        "the lock flipped %d times in four seconds with the gaze hovering at "
        "the settle boundary. The gap between settle_radius and break_radius "
        "exists to stop exactly this." % flips
    )
    print("  [ok] no chatter at the boundary (%d transitions in 4 s)" % flips)


def check_the_work_per_sample_stays_bounded():
    """Rule 0.3: nothing may grow with how long the session has been running."""

    focus = GazeFocus()
    settings = FocusSettings()
    now = 0.0
    # A tracker running far faster than any real one, for a long time.
    for _ in range(20000):
        focus.update(now, 0.5, 0.5)
        now += 0.0005
    assert len(focus._window) <= settings.max_window_samples, (
        "the dispersion window grew to %d samples. Work per sample must not "
        "grow with the sample rate or the length of the session."
        % len(focus._window)
    )
    print("  [ok] the window stays capped at %d samples" % len(focus._window))


def main():
    print("Gaze focus detection:")
    check_dwelling_holds_the_pointer_still()
    check_focus_takes_about_as_long_as_it_should()
    check_looking_away_releases_at_once()
    check_release_is_faster_than_lock()
    check_a_blink_does_not_break_focus()
    check_looking_right_away_does_break_focus()
    check_the_filter_measures_its_own_gap_not_the_coast_gap()
    check_drift_must_be_sustained_not_glimpsed()
    check_the_owners_recorded_blink_does_not_break_focus()
    check_turning_a_knob_holds_the_lock()
    check_the_hold_expires()
    check_slow_reaiming_follows_without_unlocking()
    check_the_view_gain_damps_and_ramps()
    check_it_does_not_chatter_at_the_boundary()
    check_the_work_per_sample_stays_bounded()
    print("Gaze focus test passed.")


if __name__ == "__main__":
    main()
