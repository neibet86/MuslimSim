#!/usr/bin/env python3
"""The eye-focus feature must be switchable, and must never take the mouse hostage.

This is the part that actually touches the owner's desktop, so the checks here
are mostly about restraint: warp once per fixation and then be quiet, never
move the pointer while the gaze is roaming, and get out of the way the instant
the physical mouse moves - because that is the escape hatch if anything about
this ever misbehaves.

Offline: a fake tracker and a pointer that writes to a list. No eye tracker, no
desktop, no Tk window.
"""

from __future__ import annotations

from pathlib import Path
import random
import sys


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.platform.gaze_focus import FocusSettings
from muslimsim.platform.gaze_service import (
    GazeFocusService, NullPointer, PointerSettings,
)
from muslimsim.platform.tobii_stream import GazeSample


RATE = 33.0
DT = 1.0 / RATE
# The tracker stamps samples with its own uptime, not with anything this
# process would recognise. Starting the fake clock at a large number keeps that
# distinction visible: anything that mixes the two time bases fails here.
TRACKER_EPOCH = 176544.0


class FakeStream:
    """A tracker that is entirely under the test's control."""

    device_url = "fake://tracker"

    def __init__(self, on_gaze=None, **_kwargs):
        self.on_gaze = on_gaze
        self.started = False
        self.stopped = False
        self.polls = 0

    def start(self):
        self.started = True

    def poll(self, _timeout=0.1):
        self.polls += 1

    def stop(self):
        self.stopped = True

    def feed(self, timestamp, x, y, valid=True):
        self.on_gaze(GazeSample(timestamp=timestamp, x=x, y=y, valid=valid))


class RefusingStream(FakeStream):
    def start(self):
        raise RuntimeError("no tracker plugged in")


def build(pointer=None, **kwargs):
    """A service wired to a fake tracker, with the stream handed back."""

    made = {}

    def factory(on_gaze=None, **_ignored):
        made["stream"] = FakeStream(on_gaze=on_gaze)
        return made["stream"]

    service = GazeFocusService(
        pointer=pointer if pointer is not None else NullPointer(),
        stream_factory=kwargs.pop("stream_factory", factory),
        **kwargs,
    )
    return service, made


def stare(service, stream, seconds, centre=(0.5, 0.5), tremor=0.004, seed=1,
          start=TRACKER_EPOCH):
    rng = random.Random(seed)
    now = start
    for _ in range(int(seconds * RATE)):
        stream.feed(now, centre[0] + rng.gauss(0, tremor),
                    centre[1] + rng.gauss(0, tremor))
        now += DT
    return now


def check_it_is_off_until_switched_on():
    service, _ = build()
    assert not service.running, "the service was running before anything asked"
    status = service.status()
    assert status["samples"] == 0 and status["warps"] == 0
    assert service.summary() == "Eye focus", (
        "the label claimed something before the feature was ever enabled"
    )
    print("  [ok] off, and doing nothing, until switched on")


def check_starting_and_stopping_is_clean():
    service, made = build()
    service.start()
    stream = made["stream"]
    assert service.running and stream.started, "start() did not open the tracker"
    service.stop()
    assert not service.running, "stop() left the service claiming to run"
    assert stream.stopped, "stop() did not close the tracker"
    print("  [ok] starts and stops cleanly")


def check_a_refusing_tracker_leaves_it_off():
    service = GazeFocusService(pointer=NullPointer(), stream_factory=RefusingStream)
    try:
        service.start()
    except RuntimeError:
        pass
    else:
        raise AssertionError("a tracker that refuses to open must not start quietly")
    assert not service.running, (
        "the tracker refused to open and the service still claims to be running"
    )
    print("  [ok] a tracker that will not open leaves the feature off")


def check_a_fixation_warps_the_pointer_once():
    pointer = NullPointer()
    service, made = build(pointer)
    service.start()
    stare(service, made["stream"], 2.0)
    service.stop()

    assert pointer.writes, "two seconds of staring never moved the pointer"
    assert len(pointer.writes) <= 3, (
        "the pointer was written %d times for one fixation. It should be placed "
        "once and then left alone - a stream of writes is the shakiness this is "
        "meant to remove, and it also defeats the physical-mouse check."
        % len(pointer.writes)
    )
    spread = max(
        abs(a[0] - b[0]) + abs(a[1] - b[1])
        for a in pointer.writes for b in pointer.writes
    )
    assert spread <= 4, (
        "the writes were %d pixels apart; a held fixation should land in one "
        "place" % spread
    )
    print("  [ok] one fixation warps the pointer %d time(s)" % len(pointer.writes))


def check_roaming_never_moves_the_pointer():
    pointer = NullPointer()
    service, made = build(pointer)
    service.start()
    stream = made["stream"]
    now = TRACKER_EPOCH
    # Scanning across the screen, never settling anywhere.
    for step in range(60):
        stream.feed(now, 0.1 + 0.013 * step, 0.5 + 0.006 * step)
        now += DT
    service.stop()
    assert not pointer.writes, (
        "the pointer was dragged along while the owner was just looking around. "
        "Nothing should happen until a fixation is established."
    )
    print("  [ok] looking around does not move the pointer at all")


def check_the_physical_mouse_always_wins():
    pointer = NullPointer()
    service, made = build(pointer)
    service.start()
    stream = made["stream"]
    end = stare(service, stream, 2.0)
    assert pointer.writes, "never warped, so the test cannot prove anything"
    before = len(pointer.writes)

    # The owner grabs the mouse and moves it somewhere else entirely.
    pointer._position = (10, 10)
    stare(service, stream, 2.0, centre=(0.7, 0.3), seed=2, start=end)
    service.stop()

    assert len(pointer.writes) == before, (
        "the owner moved the mouse and the stabiliser wrote to the cursor %d "
        "more times, fighting them for it. Moving the mouse must always take "
        "control back." % (len(pointer.writes) - before)
    )
    print("  [ok] moving the mouse takes the pointer back and keeps it")


def check_the_mouse_grace_expires():
    pointer = NullPointer()
    options = PointerSettings(mouse_grace=0.05)
    clock = {"now": 0.0}
    service, made = build(pointer, pointer_settings=options,
                          clock=lambda: clock["now"])
    service.start()
    stream = made["stream"]
    end = stare(service, stream, 2.0)
    before = len(pointer.writes)
    pointer._position = (10, 10)
    stare(service, stream, 0.5, centre=(0.7, 0.3), seed=3, start=end)
    clock["now"] = 10.0                      # long past the grace period
    stare(service, stream, 2.0, centre=(0.7, 0.3), seed=4, start=end + 0.5)
    service.stop()
    assert len(pointer.writes) > before, (
        "the stabiliser stood back for the mouse and never came back"
    )
    print("  [ok] it resumes once the owner stops using the mouse")


def check_control_activity_reaches_the_detector():
    """The hold has to speak the tracker's clock, not this process's."""

    pointer = NullPointer()
    service, made = build(pointer)
    service.start()
    stream = made["stream"]
    end = stare(service, stream, 1.5)
    assert service.status()["focused"], "not focused before the knob was turned"

    service.note_control_activity()
    held = service._focus._held_until
    assert held > TRACKER_EPOCH, (
        "the hold was stamped at %.3f, which is this process's clock, not the "
        "tracker's. The detector compares it against sample timestamps, so a "
        "hold in the wrong time base either never applies or never expires."
        % held
    )
    assert held <= end + FocusSettings().hold_grace + 1.0, (
        "the hold expiry %.3f is nowhere near the newest sample %.3f" % (held, end)
    )

    # And it must actually do something: a glance that would otherwise break
    # the lock survives while a control is being worked.
    now = end
    broke = False
    for _ in range(12):
        service.note_control_activity()
        stream.feed(now, 0.5 + 0.072, 0.5 + 0.022)
        now += DT
        if not service.status()["focused"]:
            broke = True
    service.stop()
    assert not broke, (
        "the owner was turning a knob and glanced at the instrument, and the "
        "lock dropped anyway"
    )
    print("  [ok] turning a knob holds the lock, on the tracker's own clock")


def check_the_label_does_not_churn():
    service, made = build()
    service.start()
    stare(service, made["stream"], 1.5)
    seen = {service.summary() for _ in range(20)}
    service.stop()
    assert len(seen) == 1, (
        "the toggle label produced %s for one unchanged state. A label that "
        "rewrites itself every tick is the flicker the owner asked to be rid "
        "of." % seen
    )
    print("  [ok] the toggle label is stable: %r" % seen.pop())


def check_blind_samples_do_not_move_anything():
    pointer = NullPointer()
    service, made = build(pointer)
    service.start()
    stream = made["stream"]
    now = TRACKER_EPOCH
    for _ in range(60):
        stream.feed(now, -1.0, -1.0, valid=False)
        now += DT
    assert not pointer.writes, (
        "the tracker reported no eyes and the pointer was moved anyway - the "
        "sentinel position was treated as a real one"
    )
    assert service.status()["valid_ratio"] == 0.0
    # Read the label while it is still running: a stopped service correctly
    # says nothing about eyes.
    assert service.summary() == "Eye focus - no eyes found", (
        "the label did not say why nothing is happening: %r" % service.summary()
    )
    service.stop()
    print("  [ok] no eyes found moves nothing and says so")


def main():
    print("Eye focus service:")
    check_it_is_off_until_switched_on()
    check_starting_and_stopping_is_clean()
    check_a_refusing_tracker_leaves_it_off()
    check_a_fixation_warps_the_pointer_once()
    check_roaming_never_moves_the_pointer()
    check_the_physical_mouse_always_wins()
    check_the_mouse_grace_expires()
    check_control_activity_reaches_the_detector()
    check_the_label_does_not_churn()
    check_blind_samples_do_not_move_anything()
    print("Eye focus service test passed.")


if __name__ == "__main__":
    main()
