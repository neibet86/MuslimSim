"""Decide when the owner is trying to *focus* on something, and hold still for it.

The problem this exists to solve, in the owner's words: looking at a tablet in
the cockpit to read it, or at a knob to turn it several times, and the view
shakes and the pointer will not stay put, because it follows the smallest
tremor of the head and the eyes.

That tremor is not a mistake in the tracker. A steady human gaze is never
actually steady - it drifts and jitters continuously, by roughly a degree, all
the time. Feed that straight to a pointer and the pointer jitters, and no amount
of better hardware changes it. What has to change is the *interpretation*: while
someone is dwelling on one thing, their small movements are noise and must be
thrown away; the moment they deliberately look somewhere else, that same
movement is signal and must be obeyed instantly.

So this module is built around one asymmetry, and everything else follows from
it:

    **slow to lock, instant to let go.**

Being half a second slow to settle is invisible. Being even a tenth of a second
slow to release feels broken - it reads as the pointer fighting you. Any change
here that trades release speed for steadiness is the wrong trade.

Four things do the work:

1. **A speed-adaptive filter** (the "one euro" filter, Casiez, Roussel and Vogel
   2012). A plain low-pass filter removes jitter and adds lag in equal measure.
   This one varies its cutoff with how fast the point is moving: heavy smoothing
   when nearly still, almost none when moving fast. Jitter goes, lag does not
   arrive.

2. **Dispersion over a short window.** Gaze that stays inside a small circle for
   long enough is a fixation - somebody looking at something. This is the
   classic dispersion-and-duration test, and it is what tells intent apart from
   drift.

3. **An anchor with a dead zone.** Once focused, the output *is* the anchor, not
   the live point, so the pointer is genuinely frozen rather than merely
   smoothed. Movement inside the dead zone changes nothing at all. Movement
   beyond it lets the anchor creep, so slow deliberate re-aiming still works.
   Movement beyond the break radius, or a fast enough flick, drops the lock at
   once.

4. **A hold, for when the owner is busy.** MuslimSim knows something a general
   eye tracker never does: whether a physical control is being operated right
   now. Somebody a third of the way through turning a knob is not trying to look
   away, so while a control is live the lock is widened and held. This is the
   one part of this design that only works because the panels and the tracker
   live in the same process.

Blinks are handled deliberately. A blink invalidates gaze for a tenth of a
second or so, and treating that as "focus lost" would drop the lock every few
seconds. Invalid samples freeze the output instead, and only give up after a
grace period.

Units are whatever the caller supplies, and the defaults assume **normalised
screen coordinates**, 0..1 across the display. On a 27-inch monitor at arm's
length one degree of visual angle is about 0.017 of the screen width, so the
default settle radius of 0.020 is a little over one degree - which is where the
research puts the dispersion threshold for a fixation.

Every threshold below is a starting point, not a measurement. The tracker
reports where the eyes are, never what the owner meant, so intent is inferred
and the numbers that infer it are tuning. They are gathered in one dataclass so
they can be tuned in one place.

Pure computation: no hardware, no simulator, no Tk. Feed it samples and it
answers.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional, Tuple
import math


# MUSLIMSIM_GAZE_FOCUS_V1


@dataclass(frozen=True)
class FocusSettings:
    """Every number that decides what counts as focus.

    Defaults are for normalised screen coordinates (0..1 across the display).
    """

    # --- the speed-adaptive filter -----------------------------------------
    min_cutoff: float = 1.0
    """Cutoff in Hz when the gaze is still. Lower is steadier and laggier."""

    beta: float = 0.010
    """How fast the cutoff opens up with speed. Higher means less lag when
    moving and more jitter allowed through."""

    d_cutoff: float = 1.0
    """Cutoff in Hz for the speed estimate itself, so a single noisy sample
    cannot open the filter wide."""

    # --- what counts as dwelling -------------------------------------------
    settle_radius: float = 0.020
    """Gaze must stay within this of its own centroid to count as a fixation.
    A little over one degree of visual angle on a typical desk setup."""

    settle_seconds: float = 0.18
    """And it must stay there this long. Below about 0.1 s this starts firing
    on the pauses inside ordinary scanning."""

    # --- what breaks it -----------------------------------------------------
    dead_zone: float = 0.012
    """Inside this of the anchor, the output does not move at all. This is what
    makes the pointer genuinely still rather than gently drifting."""

    break_radius: float = 0.055
    """Beyond this from the anchor, focus is over. Deliberately much wider than
    settle_radius: the gap is the hysteresis that stops the lock chattering on
    and off at the boundary."""

    saccade_speed: float = 0.90
    """A flick faster than this (screen widths per second) ends focus
    immediately, without waiting to leave the break radius. This is the fast
    path, and it is the whole reason releasing feels instant."""

    anchor_creep: float = 0.06
    """How much of the way the anchor moves toward the gaze each sample, once
    the gaze is outside the dead zone. Slow re-aiming without losing the lock."""

    creep_limit: float = 0.024
    """The creep only applies out to here. Past it the anchor stops following
    and waits to be either come back to or broken.

    Without this bound the creep quietly defeats the break radius: the anchor
    chases a real move fast enough that the gap between them never grows wide
    enough to trigger a release, and the lock follows the owner to somewhere
    they never dwelled. The creep is for drifting a little while reading, not
    for travelling."""

    # --- staying locked through the gaps ------------------------------------
    recovery_seconds: float = 0.20
    """How long after gaze returns to keep ignoring it.

    A blink does not begin and end where the tracker says it does. Measured on
    the owner's own trace, the eyelid corrupts the estimate for about four
    samples before the tracker admits the eyes are gone and about seven after
    it says they are back - and every one of those is flagged valid, some of
    them a tenth of the screen away from where the owner was actually looking.
    Trusting them is what broke the lock on every blink."""

    break_hold_seconds: float = 0.15
    """Drift must stay beyond the break radius this long before focus ends.

    This costs nothing in responsiveness, because a deliberate look away is a
    saccade and leaves by the speed path instead. What it buys is immunity to
    the excursion on the *near* side of a blink, which cannot be waited out
    because it arrives before there is any sign that a blink is coming."""

    blink_grace: float = 0.35
    """How long invalid gaze - a blink, mostly - may last before focus is given
    up. A blink is about 0.1-0.15 s, so this rides over blinks and gives up on
    someone actually looking away."""

    hold_grace: float = 0.60
    """How long a control counts as being operated after its last input. Turning
    a knob is a series of clicks with gaps between them, and the gaps are not
    the owner changing their mind."""

    hold_break_scale: float = 2.5
    """How much wider the break radius gets while a control is being operated."""

    # --- what the camera should do -------------------------------------------
    focused_view_gain: float = 0.15
    """Head-driven view movement is multiplied by this while focused, so the
    view stops swimming while the owner reads something. Not zero: the view
    going completely rigid reads as a freeze, and a little residual movement
    keeps it feeling alive."""

    gain_ramp_seconds: float = 0.25
    """The view gain ramps over this long rather than snapping, because a step
    change in camera gain is itself a visible jolt."""

    # --- bounds --------------------------------------------------------------
    window_seconds: float = 0.50
    """How much history the dispersion test looks at."""

    max_window_samples: int = 256
    """Hard cap on that history. A sample rate far above what is expected must
    not turn the window into unbounded work per sample - the rule is that every
    path stays the same cost as this project grows."""


@dataclass
class FocusState:
    """What the detector believes right now."""

    point: Tuple[float, float]
    """Where the pointer should be. This is the anchor while focused, and the
    smoothed gaze otherwise."""

    smoothed: Tuple[float, float]
    """The gaze after filtering, before any anchoring. Useful for showing what
    the stabiliser is doing."""

    raw: Tuple[float, float]
    """Exactly what came in."""

    state: str = "roaming"
    """One of ``roaming``, ``settling``, ``focused``."""

    focused: bool = False
    dwell: float = 0.0
    """How long the current focus has lasted, in seconds."""

    view_gain: float = 1.0
    """Multiply head-driven camera movement by this."""

    dispersion: float = 0.0
    speed: float = 0.0
    valid: bool = True
    held: bool = False
    """Whether a physical control is currently holding the lock open."""

    release: str = ""
    """Why focus ended on this sample, when it did: ``saccade``, ``drift``,
    ``blink`` or ``""``. Tuning these thresholds without knowing which one is
    firing is guesswork, so the detector says."""


class _LowPass:
    """One exponential low-pass stage."""

    __slots__ = ("_value",)

    def __init__(self) -> None:
        self._value: Optional[float] = None

    def reset(self) -> None:
        self._value = None

    def __call__(self, value: float, alpha: float) -> float:
        if self._value is None:
            self._value = float(value)
        else:
            self._value = alpha * float(value) + (1.0 - alpha) * self._value
        return self._value

    @property
    def value(self) -> Optional[float]:
        return self._value


def _alpha(cutoff: float, dt: float) -> float:
    """The smoothing factor for a cutoff frequency at this sample spacing."""

    if cutoff <= 0.0 or dt <= 0.0:
        return 1.0
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class _OneEuro2D:
    """The one-euro filter, driven by 2D speed so it has no preferred axis.

    Filtering each axis on its own speed makes a diagonal flick lag differently
    from a horizontal one, which shows up as the pointer curving. One shared
    cutoff, taken from the magnitude of the velocity, avoids that.
    """

    def __init__(self, settings: FocusSettings) -> None:
        self._settings = settings
        self._x = _LowPass()
        self._y = _LowPass()
        self._dx = _LowPass()
        self._dy = _LowPass()
        self._previous: Optional[Tuple[float, float]] = None

    def reset(self) -> None:
        self._x.reset()
        self._y.reset()
        self._dx.reset()
        self._dy.reset()
        self._previous = None

    def __call__(self, x: float, y: float, dt: float) -> Tuple[float, float, float]:
        """Returns the smoothed point and the speed that shaped it."""

        settings = self._settings
        if self._previous is None or dt <= 0.0:
            velocity_x = velocity_y = 0.0
        else:
            velocity_x = (x - self._previous[0]) / dt
            velocity_y = (y - self._previous[1]) / dt
        self._previous = (x, y)

        speed_alpha = _alpha(settings.d_cutoff, dt if dt > 0.0 else 1.0)
        eased_x = self._dx(velocity_x, speed_alpha)
        eased_y = self._dy(velocity_y, speed_alpha)
        speed = math.hypot(eased_x, eased_y)

        cutoff = settings.min_cutoff + settings.beta * speed
        point_alpha = _alpha(cutoff, dt if dt > 0.0 else 1.0)
        return self._x(x, point_alpha), self._y(y, point_alpha), speed


class GazeFocus:
    """Turn a stream of gaze samples into a pointer that holds still on purpose.

    Feed it every sample with :meth:`update`. Tell it when a physical control is
    being operated with :meth:`hold`. Read the returned :class:`FocusState`.
    """

    def __init__(self, settings: Optional[FocusSettings] = None) -> None:
        self.settings = settings or FocusSettings()
        self._filter = _OneEuro2D(self.settings)
        self._window: Deque[Tuple[float, float, float]] = deque()
        self._anchor: Optional[Tuple[float, float]] = None
        self._state = "roaming"
        self._focus_since = 0.0
        self._last_time: Optional[float] = None
        self._last_valid_time: Optional[float] = None
        self._held_until = 0.0
        self._view_gain = 1.0
        self._recover_until = 0.0
        self._drift_since: Optional[float] = None
        self._last_output: Tuple[float, float] = (0.0, 0.0)
        self._last_smoothed: Tuple[float, float] = (0.0, 0.0)
        self._released = ""

    # -- inputs other than gaze ---------------------------------------------

    def hold(self, now: float, seconds: Optional[float] = None) -> None:
        """A physical control was just operated; keep the lock open.

        Called from wherever hardware input is seen. Turning a knob is a run of
        separate clicks, so this extends a window rather than setting a flag,
        and the window is refreshed by every click.
        """

        grace = self.settings.hold_grace if seconds is None else float(seconds)
        self._held_until = max(self._held_until, float(now) + grace)

    def reset(self) -> None:
        """Forget everything. Used when tracking is lost or the owner leaves."""

        self._filter.reset()
        self._window.clear()
        self._anchor = None
        self._state = "roaming"
        self._focus_since = 0.0
        self._last_time = None
        self._last_valid_time = None
        self._view_gain = 1.0

    # -- the main path -------------------------------------------------------

    def update(
        self,
        now: float,
        x: float,
        y: float,
        *,
        valid: bool = True,
    ) -> FocusState:
        """Take one gaze sample and say where the pointer should be."""

        now = float(now)
        settings = self.settings
        previous_time = self._last_time
        dt = 0.0 if previous_time is None else max(0.0, now - previous_time)
        self._last_time = now
        held = now < self._held_until

        if not valid:
            self._recover_until = now + settings.recovery_seconds
            return self._coast(now, x, y, held)

        if now < self._recover_until:
            # The eyes are back but these samples are still the eyelid's, not
            # the owner's. Coast rather than believe them.
            self._last_valid_time = now
            return self._coast(now, x, y, held)

        self._last_valid_time = now
        smoothed_x, smoothed_y, speed = self._filter(float(x), float(y), dt)
        smoothed = (smoothed_x, smoothed_y)
        self._last_smoothed = smoothed

        self._window.append((now, smoothed_x, smoothed_y))
        self._trim(now)
        dispersion = self._dispersion()

        if self._state == "focused":
            self._continue_focus(now, smoothed, speed, held)
        else:
            self._look_for_focus(now, dispersion)

        point = self._anchor if self._state == "focused" else smoothed
        self._last_output = point
        self._advance_view_gain(dt)
        released, self._released = self._released, ""

        return FocusState(
            point=point,
            smoothed=smoothed,
            raw=(float(x), float(y)),
            state=self._state,
            focused=self._state == "focused",
            dwell=(now - self._focus_since) if self._state == "focused" else 0.0,
            view_gain=self._view_gain,
            dispersion=dispersion,
            speed=speed,
            valid=True,
            held=held,
            release=released,
        )

    # -- the pieces ----------------------------------------------------------

    def _coast(self, now: float, x: float, y: float, held: bool) -> FocusState:
        """Gaze is invalid - almost always a blink. Freeze, do not conclude.

        Dropping focus here would unlock every few seconds for no reason the
        owner could see. The output stops moving and the state is kept until the
        grace period runs out.
        """

        settings = self.settings
        since = self._last_valid_time
        expired = since is not None and (now - since) > settings.blink_grace
        if expired and self._state != "roaming":
            self._release("blink")
        self._advance_view_gain(0.0)
        return FocusState(
            point=self._last_output,
            smoothed=self._last_smoothed,
            raw=(float(x), float(y)),
            state=self._state,
            focused=self._state == "focused",
            dwell=(now - self._focus_since) if self._state == "focused" else 0.0,
            view_gain=self._view_gain,
            dispersion=self._dispersion(),
            speed=0.0,
            valid=False,
            held=held,
        )

    def _trim(self, now: float) -> None:
        settings = self.settings
        oldest = now - settings.window_seconds
        window = self._window
        while window and window[0][0] < oldest:
            window.popleft()
        # The time bound is the real one; this is the guard that keeps the cost
        # per sample flat no matter what rate the tracker runs at.
        while len(window) > settings.max_window_samples:
            window.popleft()

    def _dispersion(self) -> float:
        """How far the recent gaze strays from its own centre."""

        window = self._window
        if len(window) < 2:
            return 0.0
        count = float(len(window))
        centre_x = sum(item[1] for item in window) / count
        centre_y = sum(item[2] for item in window) / count
        return max(
            math.hypot(item[1] - centre_x, item[2] - centre_y) for item in window
        )

    def _look_for_focus(self, now: float, dispersion: float) -> None:
        window = self._window
        if len(window) < 2:
            self._state = "roaming"
            return
        span = window[-1][0] - window[0][0]
        if dispersion > self.settings.settle_radius:
            self._state = "roaming"
            return
        if span < self.settings.settle_seconds:
            self._state = "settling"
            return
        count = float(len(window))
        self._anchor = (
            sum(item[1] for item in window) / count,
            sum(item[2] for item in window) / count,
        )
        self._state = "focused"
        self._focus_since = now
        self._drift_since = None

    def _continue_focus(
        self,
        now: float,
        smoothed: Tuple[float, float],
        speed: float,
        held: bool,
    ) -> None:
        settings = self.settings
        anchor = self._anchor
        if anchor is None:
            self._release("lost")
            return

        break_radius = settings.break_radius
        if held:
            break_radius *= settings.hold_break_scale

        # The fast path. A deliberate flick away must not have to travel the
        # whole break radius first - waiting for that is exactly what reads as
        # the pointer fighting you. While a control is being worked, a flick is
        # not enough on its own; the gaze also has to actually leave.
        if speed > settings.saccade_speed and not held:
            self._release("saccade")
            return

        drift = math.hypot(smoothed[0] - anchor[0], smoothed[1] - anchor[1])
        if drift > break_radius:
            # Wait for it to mean something. A blink throws the reported gaze a
            # tenth of the screen away for a few samples and then brings it
            # straight back; the owner actually looking away does not come back.
            if self._drift_since is None:
                self._drift_since = now
            elif now - self._drift_since >= settings.break_hold_seconds:
                self._release("drift")
            return
        self._drift_since = None

        if settings.dead_zone < drift <= settings.creep_limit:
            # Outside the dead zone but still close: let the anchor follow,
            # slowly, so re-aiming by a small amount does not need a full
            # unlock and re-settle. Beyond creep_limit the anchor deliberately
            # stops following, so that a real move keeps opening the gap
            # instead of dragging the lock along with it.
            creep = settings.anchor_creep
            self._anchor = (
                anchor[0] + (smoothed[0] - anchor[0]) * creep,
                anchor[1] + (smoothed[1] - anchor[1]) * creep,
            )

    def _release(self, reason: str = "") -> None:
        self._state = "roaming"
        self._anchor = None
        self._focus_since = 0.0
        self._drift_since = None
        self._released = str(reason)
        self._window.clear()

    def _advance_view_gain(self, dt: float) -> None:
        """Ease the camera gain toward where the current state wants it."""

        settings = self.settings
        target = settings.focused_view_gain if self._state == "focused" else 1.0
        ramp = settings.gain_ramp_seconds
        if ramp <= 0.0 or dt <= 0.0:
            self._view_gain = target
            return
        step = min(1.0, dt / ramp)
        self._view_gain += (target - self._view_gain) * step


__all__ = ("FocusSettings", "FocusState", "GazeFocus")
